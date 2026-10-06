"""Streamlit widgets, charts and tables; calculations live in metrics.py."""
import plotly.express as px
import streamlit as st

from src.db import read_dashboard_data
from src.metrics import (
    eligible_orders,
    filter_orders,
    group_summary,
    monthly_summary,
    prepare_orders,
    rank_groups,
    review_summary,
)


@st.cache_data(ttl=60)
def read_data():
    """Cache a consistent database snapshot for at most one minute."""
    return read_dashboard_data()


def render_filters(frame):
    """Collect sidebar choices and return the selected orders."""
    dates = frame['purchase_date'].dropna()
    period = st.sidebar.date_input(
        'Purchase date range',
        value=(dates.min(), dates.max()),
        min_value=dates.min(),
        max_value=dates.max(),
    )
    states = st.sidebar.multiselect(
        'Customer states', sorted(frame['customer_state'].unique())
    )
    categories = st.sidebar.multiselect(
        'Order category', sorted(frame['category'].unique())
    )
    minimum = st.sidebar.number_input(
        'Minimum eligible orders for ranking', min_value=1, value=100, step=10
    )
    if len(period) != 2:
        st.info('Choose both a start and an end date.')
        st.stop()
    selected = filter_orders(frame, period[0], period[1], states, categories)
    return selected, period, minimum


def render_summary(frame, selected, eligible):
    """Show counts and the eligible-delivery denominator."""
    late_count = int(eligible['late_int'].sum())
    late_rate = f'{late_count / len(eligible):.1%}' if len(eligible) else 'N/A'
    orders_card, eligible_card, late_card, rate_card = st.columns(4)
    orders_card.metric('All selected orders', f'{len(selected):,}')
    eligible_card.metric('Eligible deliveries', f'{len(eligible):,}')
    late_card.metric('Late orders', f'{late_count:,}')
    rate_card.metric('Late delivery rate', late_rate)
    missing_dates = int(frame['purchase_date'].isna().sum())
    st.caption(
        f'{len(selected) - len(eligible):,} selected orders excluded from the '
        f'lateness denominator. Filters exclude {missing_dates} source orders '
        'with missing purchase dates. A late delivery arrives after the '
        'estimated calendar date.'
    )


def render_trend(eligible, period):
    """Show a continuous purchase-month timeline."""
    if eligible.empty:
        st.info('No eligible deliveries for this selection.')
        return
    trend = monthly_summary(eligible, period[0], period[1])
    figure = px.line(
        trend,
        x='month',
        y='late_rate',
        markers=True,
        hover_data=['eligible_orders', 'late_orders'],
        title='Late rate by purchase month',
    )
    figure.update_yaxes(tickformat='.0%')
    st.plotly_chart(figure, use_container_width=True)
    st.dataframe(trend, hide_index=True)
    st.download_button('Download monthly results', trend.to_csv(index=False),
                       'monthly.csv', 'text/csv')
    st.caption(
        'Edge months may be partial. Small or recent cohorts can give '
        'unstable comparisons.'
    )


def render_priorities(eligible, minimum):
    """Compare late-order volume, rates and uncertainty."""
    dimension = st.radio(
        'Group by', ['customer_state', 'category'], horizontal=True,
        format_func=lambda value: {'customer_state': 'Customer state', 'category': 'Category'}[value],
    )
    if eligible.empty:
        st.info('No eligible deliveries for this selection.')
        return
    grouped = group_summary(eligible, dimension)
    ranked = rank_groups(grouped, dimension, minimum)
    if ranked.empty:
        st.info(
            'No groups meet the minimum. Lower it to inspect small groups; '
            'interpret their intervals cautiously.'
        )
    else:
        chart = ranked.head(15).copy()
        chart['error_plus'] = chart['ci_high'] - chart['late_rate']
        chart['error_minus'] = chart['late_rate'] - chart['ci_low']
        figure = px.scatter(
            chart,
            x='late_rate',
            y=dimension,
            size='eligible_orders',
            error_x='error_plus',
            error_x_minus='error_minus',
            hover_data=['late_orders', 'eligible_orders'],
            title='Top 15 groups by late-order count · 95% Wilson intervals',
        )
        figure.update_xaxes(tickformat='.0%')
        st.plotly_chart(figure, use_container_width=True)
        st.dataframe(ranked, hide_index=True)
    st.download_button(
        'Download all group results',
        grouped.to_csv(index=False),
        'states.csv' if dimension == 'customer_state' else 'categories.csv',
        'text/csv',
    )


def render_reviews(eligible):
    """Show review outcomes without implying causation."""
    summary = review_summary(eligible)
    reviewed_count = int(summary['reviewed_orders'].sum())
    if summary.empty:
        st.info('No reviews on eligible deliveries.')
    else:
        figure = px.bar(
            summary,
            x='delivery_group',
            y='low_review_rate',
            hover_data=['reviewed_orders', 'low_review_orders'],
        )
        figure.update_yaxes(tickformat='.0%')
        st.plotly_chart(figure, use_container_width=True)
        st.dataframe(summary, hide_index=True)
    st.caption(
        f'{reviewed_count:,} reviewed of {len(eligible):,} eligible orders. '
        'Missing reviews excluded. Association does not establish causation.'
    )


def render_definitions():
    """Explain the metric rules alongside the dashboard."""
    st.markdown('''
- **Eligible:** delivered status, purchase/delivery/estimate present, delivery not before purchase, estimate date not before purchase date.
- **Late:** actual delivery calendar date is after the estimated calendar date. Same-day evening deliveries are on time.
- **Low review:** score 1 or 2; denominator is orders with a selected review.
- **Category:** single category, `mixed_categories`, `unknown`, or `no_items`; each order is counted once.
- **Intervals:** 95% Wilson intervals, assuming independent Bernoulli trials. They are not causal evidence or adjusted for multiple comparisons.
- **Priority:** investigate high late-order counts alongside rates and volumes; this does not estimate savings.
- **Dates:** treated as recorded local timestamps; the source has no explicit time zone here.

Open `docs/METRICS.md` for full definitions. The pipeline prints current quality checks; `results/quality.csv` is the published snapshot.
''')


def main():
    """Load, filter and render the dashboard in reading order."""
    st.set_page_config(page_title='Delivery performance', page_icon='📦', layout='wide')
    st.title('Delivery performance & customer satisfaction')
    st.caption('Purchase cohorts • calendar-day lateness • one row per order')
    if st.sidebar.button('Refresh data'):
        read_data.clear()
    try:
        metadata, orders = read_data()
    except Exception:
        st.error(
            'Database is unavailable or has not been loaded. Follow README.md, '
            'run the pipeline, then refresh.'
        )
        st.stop()
    if not metadata or orders.empty:
        st.info('No orders loaded. Run the pipeline first.')
        st.stop()
    label, loaded_at = metadata
    if label == 'synthetic-demo':
        st.warning('SYNTHETIC DEMO — these charts are for learning, not Olist findings.')
    st.caption(f'Dataset: {label} · Loaded: {loaded_at}')
    frame = prepare_orders(orders)
    if frame['purchase_date'].dropna().empty:
        st.warning('No usable purchase dates. Inspect the pipeline quality checks.')
        st.stop()
    selected, period, minimum = render_filters(frame)
    if selected.empty:
        st.info('No orders match these filters.')
        st.stop()
    eligible = eligible_orders(selected)
    render_summary(frame, selected, eligible)
    trend, priorities, reviews, definitions = st.tabs(
        ['Trend', 'Where to investigate', 'Reviews', 'Definitions']
    )
    with trend:
        render_trend(eligible, period)
    with priorities:
        render_priorities(eligible, minimum)
    with reviews:
        render_reviews(eligible)
    with definitions:
        render_definitions()
