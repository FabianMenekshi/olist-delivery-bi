"""Integration tests require an EMPTY dedicated test database.

Set TEST_DATABASE_URL; tests refuse an existing olist_raw/olist_bi schema.
All database changes are rolled back. Never use your working Olist database.
Test CSVs are created in a temporary folder and automatically removed.
"""

import csv
import os
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory


def _write_test_data(folder: Path):
    """Write deterministic fixtures for the database regression checks.

    Keep the original 240 cases to preserve expected totals and monthly groups.
    These records belong only to tests and are written to a temporary folder.
    """
    from src.manifest import TABLES

    folder.mkdir(parents=True, exist_ok=True)
    rows = {table: [] for table in TABLES}
    rows['products'] = [['p1', 'books'], ['p2', 'electronics']]
    rows['sellers'] = [['s1', 'SP'], ['s2', 'RJ']]
    for index in range(1, 241):
        order_id = f'o{index:04}'
        customer_id = f'c{index:04}'
        state = ['SP', 'RJ', 'MG'][index % 3]
        purchase = datetime(2018, 1, 1, 12) + timedelta(days=index % 150)
        estimate = (purchase + timedelta(days=12)).replace(hour=0)
        delivered = purchase + timedelta(days=15 if index % 5 == 0 else 8)
        status = 'delivered'
        if index % 29 == 0:
            status, delivered = 'canceled', None
        if index == 7:
            estimate = None  # Delivered but excluded from the lateness KPI.
        if index == 8:
            delivered = purchase - timedelta(days=1)  # Suspicious duration.
        if index == 9:
            delivered = estimate + timedelta(hours=23)  # Same day: on time.

        rows['customers'].append([customer_id, f'u{index // 2:04}', state])
        rows['orders'].append([
            order_id, customer_id, status, purchase,
            purchase + timedelta(hours=1), purchase + timedelta(days=2),
            delivered, estimate,
        ])
        rows['items'].append([
            order_id, 1, 'p1', 's1', purchase + timedelta(days=3), 100, 10,
        ])
        total = 110
        if index % 4 == 0:
            rows['items'].append([
                order_id, 2, 'p2', 's2', purchase + timedelta(days=3), 50, 5,
            ])
            total = 165
        if index % 6 == 0:
            rows['payments'].extend([
                [order_id, 1, 'credit_card', 1, total - 20],
                [order_id, 2, 'voucher', 1, 20],
            ])
        else:
            rows['payments'].append([order_id, 1, 'credit_card', 1, total])
        if index % 11:
            score = 2 if index % 5 == 0 else 5
            rows['reviews'].append([
                f'r{index:04}', order_id, score,
                purchase + timedelta(days=20), purchase + timedelta(days=21),
            ])
        if index == 12:
            # Two items, payments and reviews: the later review must win.
            rows['reviews'].append([
                'r0012b', order_id, 1,
                purchase + timedelta(days=22), purchase + timedelta(days=23),
            ])

    for table, (filename, columns) in TABLES.items():
        with (folder / filename).open('w', newline='', encoding='utf-8') as output:
            writer = csv.writer(output)
            writer.writerow(columns)
            writer.writerows(rows[table])

@unittest.skipUnless(
    os.getenv("TEST_DATABASE_URL"),
    "TEST_DATABASE_URL not set: PostgreSQL integration tests skipped",
)
class PostgreSQLTests(unittest.TestCase):
    def test_pipeline_grain_dates_totals_and_reviews(self):
        import psycopg
        from src.ingest import load

        root = Path(__file__).resolve().parents[1]
        conn = psycopg.connect(os.environ["TEST_DATABASE_URL"])
        try:
            for schema in ("olist_raw", "olist_bi"):
                exists = conn.execute(
                    "SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname=%s)",
                    (schema,),
                ).fetchone()[0]
                self.assertFalse(exists, "Use an empty, dedicated test database.")

            conn.execute((root / "sql/01_schema.sql").read_text())
            with TemporaryDirectory(prefix="olist-test-") as temporary_folder:
                fixture_folder = Path(temporary_folder)
                _write_test_data(fixture_folder)
                load(conn, fixture_folder)
            conn.execute((root / "sql/02_order_mart.sql").read_text())

            # Joining items and payments must preserve one row per order and totals.
            self.assertEqual(
                conn.execute("""
                    SELECT count(*), count(DISTINCT order_id),
                           sum(item_value), sum(freight_value), sum(payment_value)
                    FROM olist_bi.order_mart
                """).fetchone(),
                (240, 240, 27000, 2700, 29700),
            )
            # This order has two items, payments and reviews; latest review wins.
            self.assertEqual(
                conn.execute("""
                    SELECT item_count, payment_count, review_score,
                           item_value, payment_value
                    FROM olist_bi.order_mart WHERE order_id = 'o0012'
                """).fetchone(),
                (2, 2, 1, 150, 165),
            )
            # Delivery on the promised calendar day is on time, even at 23:00.
            self.assertEqual(
                conn.execute("""
                    SELECT is_late FROM olist_bi.order_mart
                    WHERE order_id = 'o0009'
                """).fetchone(),
                (False,),
            )
            self.assertEqual(
                conn.execute("""
                    SELECT count(*) FROM olist_bi.order_mart
                    WHERE order_id IN ('o0007', 'o0008', 'o0029')
                      AND NOT eligible_delivery AND is_late IS NULL
                """).fetchone(),
                (3,),
            )
            self.assertEqual(
                conn.execute("""
                    SELECT count(*) FILTER (WHERE eligible_delivery),
                           count(*) FILTER (WHERE is_late)
                    FROM olist_bi.order_mart
                """).fetchone(),
                (230, 47),
            )
            quality = conn.execute((root / "sql/03_quality.sql").read_text()).fetchall()
            self.assertTrue(
                all(count == 0 for _, severity, count in quality if severity == "error")
            )
            for path in (root / "sql/analysis").glob("*.sql"):
                self.assertTrue(conn.execute(path.read_text()).fetchall(), path.name)

            self._assert_dashboard_matches_sql(conn, root)

            # A duplicate payment key must fail without damaging the transaction.
            conn.execute("SAVEPOINT bad_import")
            with self.assertRaises(psycopg.errors.UniqueViolation):
                conn.execute(
                    "INSERT INTO olist_raw.payments "
                    "SELECT * FROM olist_raw.payments LIMIT 1"
                )
            conn.execute("ROLLBACK TO SAVEPOINT bad_import")
        finally:
            conn.rollback()
            conn.close()

    def _assert_dashboard_matches_sql(self, conn, root):
        import pandas as pd
        from src.db import query_frame
        from src.metrics import (
            eligible_orders,
            group_summary,
            monthly_summary,
            prepare_orders,
            review_summary,
        )

        cursor = conn.execute("SELECT * FROM olist_bi.order_mart")
        orders = prepare_orders(pd.DataFrame(
            cursor.fetchall(), columns=[column.name for column in cursor.description]
        ))
        eligible = eligible_orders(orders)
        dates = orders["purchase_date"].dropna()
        dashboard_monthly = monthly_summary(eligible, dates.min(), dates.max())
        sql_monthly = query_frame(conn, root / "sql/analysis/monthly.sql")
        for column in ("eligible_orders", "late_orders", "late_rate"):
            pd.testing.assert_series_equal(
                dashboard_monthly[column].reset_index(drop=True),
                sql_monthly[column].astype(float).reset_index(drop=True),
                check_dtype=False,
            )

        for dimension, query in [("customer_state", "states"), ("category", "categories")]:
            dashboard_groups = (
                group_summary(eligible, dimension).set_index(dimension).sort_index()
            )
            sql_groups = (
                query_frame(conn, root / f"sql/analysis/{query}.sql")
                .set_index(dimension).sort_index()
            )
            for column in ("eligible_orders", "late_orders", "late_rate"):
                pd.testing.assert_series_equal(
                    dashboard_groups[column], sql_groups[column].astype(float),
                    check_dtype=False,
                )

        dashboard_reviews = (
            review_summary(eligible).set_index("delivery_group").sort_index()
        )
        sql_reviews = (
            query_frame(conn, root / "sql/analysis/review_association.sql")
            .set_index("delivery_group").sort_index()
        )
        for column in ("reviewed_orders", "low_review_orders", "low_review_rate"):
            pd.testing.assert_series_equal(
                dashboard_reviews[column], sql_reviews[column].astype(float),
                check_dtype=False,
            )


if __name__ == "__main__":
    unittest.main()
