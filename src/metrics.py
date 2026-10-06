"""Summarize SQL-derived order flags for the dashboard's selected population.

SQL owns eligibility, lateness and review selection. These functions only filter
and aggregate those results; they never reconnect to the database or render UI.
"""
from datetime import date

import pandas as pd

from src.stats import add_intervals


def prepare_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Add the calendar purchase date used by the sidebar."""
    prepared = orders.copy()
    prepared['purchase_date'] = pd.to_datetime(
        prepared['order_purchase_timestamp']
    ).dt.date
    return prepared


def filter_orders(orders, start: date, end: date, states=(), categories=()):
    """Include both boundary dates. Empty state/category choices mean all."""
    selected = orders.loc[
        orders['purchase_date'].notna()
        & (orders['purchase_date'] >= start)
        & (orders['purchase_date'] <= end)
    ]
    if states:
        selected = selected.loc[selected['customer_state'].isin(states)]
    if categories:
        selected = selected.loc[selected['category'].isin(categories)]
    return selected.copy()


def eligible_orders(orders: pd.DataFrame) -> pd.DataFrame:
    """Retain the SQL-eligible denominator and an integer flag for counting."""
    eligible = orders.loc[orders['eligible_delivery']].copy()
    eligible['late_int'] = eligible['is_late'].astype(int)
    return eligible


def monthly_summary(eligible, start: date, end: date):
    """Keep empty calendar months visible, with an undefined rate."""
    dated = eligible.assign(month=pd.to_datetime(eligible['purchase_month']))
    summary = dated.groupby('month').agg(
        eligible_orders=('order_id', 'size'),
        late_orders=('late_int', 'sum'),
    )
    months = pd.date_range(
        pd.Timestamp(start).to_period('M').start_time,
        pd.Timestamp(end).to_period('M').start_time,
        freq='MS',
    )
    summary = summary.reindex(months, fill_value=0).rename_axis('month').reset_index()
    summary['late_rate'] = summary['late_orders'] / summary['eligible_orders'].replace(
        0, float('nan')
    )
    return summary


def group_summary(eligible, dimension: str):
    """Count eligible and late orders per state or mutually exclusive category."""
    if dimension not in ('customer_state', 'category'):
        raise ValueError('Group by customer_state or category.')
    summary = eligible.groupby(dimension).agg(
        eligible_orders=('order_id', 'size'),
        late_orders=('late_int', 'sum'),
    ).reset_index()
    summary['late_rate'] = summary['late_orders'] / summary['eligible_orders']
    return add_intervals(summary)


def rank_groups(summary, dimension: str, minimum: int):
    """Rank by late-order count, breaking ties alphabetically as before."""
    return summary.loc[summary['eligible_orders'] >= minimum].sort_values(
        ['late_orders', dimension], ascending=[False, True]
    )


def review_summary(eligible):
    """Compare scores 1–2 among reviewed eligible orders only."""
    observed = eligible.loc[eligible['review_score'].notna()].copy()
    observed['delivery_group'] = observed['is_late'].map({True: 'Late', False: 'On time'})
    observed['low'] = observed['review_score'] <= 2
    summary = observed.groupby('delivery_group').agg(
        reviewed_orders=('order_id', 'size'),
        low_review_orders=('low', 'sum'),
    ).reset_index()
    summary['low_review_rate'] = summary['low_review_orders'] / summary['reviewed_orders']
    return add_intervals(summary, 'low_review_orders', 'reviewed_orders')
