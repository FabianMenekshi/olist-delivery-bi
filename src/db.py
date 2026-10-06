"""Shared connection settings and database reads for CLI and dashboard."""
import os
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')


def connect():
    """Open the configured PostgreSQL connection with a bounded timeout."""
    url = os.getenv('DATABASE_URL')
    if not url:
        raise RuntimeError('Copy .env.example to .env and set DATABASE_URL first.')
    return psycopg.connect(url, connect_timeout=10)


def execute_file(conn, path):
    """Execute a project SQL file inside the caller's transaction."""
    conn.execute(Path(path).read_text(encoding='utf-8'))


def cursor_frame(cursor):
    """Turn a query result into a DataFrame with its database column names."""
    return pd.DataFrame(
        cursor.fetchall(), columns=[column.name for column in cursor.description]
    )


def query_frame(conn, path):
    """Execute a project SQL file and return its named result columns."""
    return cursor_frame(conn.execute(Path(path).read_text(encoding='utf-8')))


def read_dashboard_data():
    """Read metadata and orders from one consistent, read-only snapshot."""
    with connect() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        metadata = conn.execute(
            'SELECT dataset_label, loaded_at FROM olist_bi.run_metadata'
        ).fetchone()
        orders = cursor_frame(conn.execute('SELECT * FROM olist_bi.order_mart'))
    return metadata, orders
