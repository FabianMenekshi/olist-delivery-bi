"""Boundary tests for dashboard summaries; no database required."""
from datetime import date
import unittest

import pandas as pd

from src.metrics import (
    eligible_orders, filter_orders, group_summary, monthly_summary,
    prepare_orders, rank_groups, review_summary,
)


class DashboardMetricsTests(unittest.TestCase):
    def setUp(self):
        self.orders = prepare_orders(pd.DataFrame({
            'order_id': ['a', 'b', 'c', 'd', 'e'],
            'order_purchase_timestamp': [
                '2018-01-01', '2018-01-31', '2018-03-01', '2018-03-02', None,
            ],
            'purchase_month': ['2018-01-01'] * 2 + ['2018-03-01'] * 2 + [None],
            'customer_state': ['SP', 'SP', 'RJ', 'RJ', 'MG'],
            'category': ['books', 'books', 'mixed_categories', 'no_items', 'books'],
            'eligible_delivery': [True, True, True, False, False],
            'is_late': [True, False, True, None, None],
            'review_score': [1, 5, None, 1, None],
        }))
        self.eligible = eligible_orders(self.orders)

    def test_filters_include_both_dates_and_exclude_missing_dates(self):
        selected = filter_orders(self.orders, date(2018, 1, 1), date(2018, 1, 31))
        self.assertEqual(selected['order_id'].tolist(), ['a', 'b'])
        selected = filter_orders(
            self.orders, date(2018, 1, 1), date(2018, 3, 31),
            states=['RJ'], categories=['mixed_categories'],
        )
        self.assertEqual(selected['order_id'].tolist(), ['c'])
        self.assertEqual(len(self.orders), 5)

    def test_monthly_counts_reconcile_and_empty_month_is_not_zero_risk(self):
        trend = monthly_summary(self.eligible, date(2018, 1, 1), date(2018, 3, 31))
        self.assertEqual(trend['eligible_orders'].tolist(), [2, 0, 1])
        self.assertEqual(trend['late_orders'].tolist(), [1, 0, 1])
        self.assertTrue(pd.isna(trend.loc[1, 'late_rate']))
        self.assertAlmostEqual(
            trend['late_orders'].sum() / trend['eligible_orders'].sum(), 2 / 3
        )

    def test_ranking_threshold_and_ties(self):
        groups = group_summary(self.eligible, 'customer_state')
        self.assertEqual(
            rank_groups(groups, 'customer_state', 1)['customer_state'].tolist(),
            ['RJ', 'SP'],
        )
        self.assertEqual(
            rank_groups(groups, 'customer_state', 2)['customer_state'].tolist(), ['SP']
        )
        self.assertTrue(rank_groups(groups, 'customer_state', 100).empty)
        self.assertEqual(groups['eligible_orders'].sum(), 3)

    def test_review_denominator_excludes_unreviewed_and_ineligible(self):
        reviews = review_summary(self.eligible).set_index('delivery_group')
        self.assertEqual(reviews['reviewed_orders'].sum(), 2)
        self.assertEqual(reviews.loc['Late', 'low_review_rate'], 1)
        self.assertEqual(reviews.loc['On time', 'low_review_rate'], 0)

    def test_empty_selection_and_no_eligible_orders(self):
        empty = eligible_orders(self.orders.iloc[0:0])
        self.assertTrue(group_summary(empty, 'category').empty)
        self.assertTrue(review_summary(empty).empty)
        trend = monthly_summary(empty, date(2018, 1, 1), date(2018, 2, 28))
        self.assertTrue(trend['late_rate'].isna().all())
        selected = filter_orders(self.orders, date(2018, 3, 2), date(2018, 3, 2))
        self.assertEqual(len(selected), 1)
        self.assertTrue(eligible_orders(selected).empty)

    def test_unknown_dimension_is_rejected(self):
        with self.assertRaises(ValueError):
            group_summary(self.eligible, 'review_score')


if __name__ == '__main__':
    unittest.main()
