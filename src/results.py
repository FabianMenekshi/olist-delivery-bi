"""Publish a compact, full-dataset snapshot: python -m src.results --help.

This is separate from importing data. It never generates prose or a reports folder.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator, PercentFormatter, StrMethodFormatter
import pandas as pd

from src.stats import add_intervals

ROOT = Path(__file__).resolve().parents[1]
MINIMUM_ORDERS = 100
OUTPUT_FILES = (
    'overview.png', 'state-ranking.png', 'monthly.csv', 'states.csv',
    'quality.csv', 'provenance.json',
)
MONTHLY_COLUMNS = ['month', 'all_orders', 'eligible_orders', 'late_orders', 'late_rate']
STATE_COLUMNS = [
    'customer_state', 'all_orders', 'eligible_orders', 'late_orders',
    'late_rate', 'ci_low', 'ci_high',
]
NAVY, TEAL, ORANGE, MUTED = '#152C43', '#087E8B', '#D3623B', '#617185'


def style_axis(axis):
    axis.spines[['top', 'right']].set_visible(False)
    axis.spines[['left', 'bottom']].set_color('#D5DDE5')
    axis.tick_params(colors=MUTED, labelsize=10)
    axis.grid(axis='y', color='#E9EDF2', linewidth=0.8)
    axis.set_axisbelow(True)


def draw_overview(overview, monthly, path):
    """Show all-order KPIs, screened monthly rates, and all monthly volumes."""
    row = overview.iloc[0]
    monthly = monthly.copy()
    monthly['month'] = pd.to_datetime(monthly['month'])
    with plt.rc_context({'font.family': 'DejaVu Sans', 'text.color': NAVY}):
        figure = plt.figure(figsize=(14, 9), facecolor='white')
        figure.text(.07, .95, 'OLIST / DELIVERY PERFORMANCE', fontsize=12, color=TEAL, weight='bold')
        figure.text(.07, .90, 'How often did orders arrive late?', fontsize=26, weight='bold')
        figure.text(.07, .86, 'Full dataset · all states and categories · purchase cohorts', fontsize=11, color=MUTED)
        cards = [('SOURCE ORDERS', f'{int(row.all_orders):,}'),
                 ('ELIGIBLE DELIVERIES', f'{int(row.eligible_orders):,}'),
                 ('LATE DELIVERIES', f'{int(row.late_orders):,}'),
                 ('LATE RATE', f'{row.late_rate:.1%}' if pd.notna(row.late_rate) else 'N/A')]
        for x, (label, value) in zip([.07, .30, .54, .78], cards):
            figure.text(x, .78, value, fontsize=28, weight='bold', color=TEAL if label == 'LATE RATE' else NAVY)
            figure.text(x, .745, label, fontsize=10, color=MUTED)
        rate_axis = figure.add_axes([.07, .34, .86, .32])
        volume_axis = figure.add_axes([.07, .17, .86, .12], sharex=rate_axis)
        rates = monthly['late_rate'].where(monthly['eligible_orders'] >= MINIMUM_ORDERS)
        rate_axis.plot(monthly['month'], rates, color=TEAL, linewidth=2.6, marker='o', markersize=5)
        if pd.notna(row.late_rate):
            rate_axis.axhline(row.late_rate, color=MUTED, linestyle='--', linewidth=1,
                             label=f'Overall: {row.late_rate:.1%}')
            rate_axis.legend(loc='upper left', frameon=False, fontsize=10)
        if rates.notna().any():
            peak = rates.idxmax()
            month, rate = monthly.loc[peak, 'month'], rates.loc[peak]
            rate_axis.annotate(f'{month:%b %Y} · {rate:.1%}', (month, rate),
                               xytext=(0, 16), textcoords='offset points', ha='center',
                               fontsize=11, weight='bold', color=ORANGE)
        rate_axis.set_ylim(0, max(.10, rates.max() * 1.32 if rates.notna().any() else .10))
        rate_axis.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        rate_axis.set_title('Monthly late rate · months with at least 100 eligible deliveries',
                            loc='left', fontsize=12, pad=16)
        rate_axis.tick_params(labelbottom=False)
        volume_axis.bar(monthly['month'], monthly['eligible_orders'], width=23, color='#A5CCD1')
        volume_axis.set_title('Eligible deliveries · every month', loc='left', fontsize=10, pad=8)
        volume_axis.yaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
        volume_axis.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        volume_axis.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        for axis in [rate_axis, volume_axis]:
            style_axis(axis)
        figure.text(.07, .075,
                    'Late = delivered after the estimated calendar date. Missing or invalid KPI dates are excluded.',
                    fontsize=10, color=MUTED)
        figure.text(.07, .046,
                    'Rates for months below 100 eligible orders are hidden; all counts remain in monthly.csv. Edge cohorts may be incomplete.',
                    fontsize=9, color=MUTED)
        figure.savefig(path, dpi=160, facecolor='white')
        plt.close(figure)


def draw_states(states, path):
    """Align late-order volume and rate for the same top ten destination states."""
    ranked = states.loc[states['eligible_orders'] >= MINIMUM_ORDERS].sort_values(
        ['late_orders', 'customer_state'], ascending=[False, True]
    ).head(10).reset_index(drop=True)
    with plt.rc_context({'font.family': 'DejaVu Sans', 'text.color': NAVY}):
        figure = plt.figure(figsize=(14, 8), facecolor='white')
        figure.text(.07, .94, 'OLIST / WHERE TO INVESTIGATE', fontsize=12, color=TEAL, weight='bold')
        figure.text(.07, .875, 'Volume and rate answer different questions', fontsize=25, weight='bold')
        figure.text(.07, .83, 'Top 10 destination states by late-order count · at least 100 eligible deliveries',
                    fontsize=11, color=MUTED)
        count_axis = figure.add_axes([.10, .20, .38, .53])
        rate_axis = figure.add_axes([.60, .20, .32, .53])
        if ranked.empty:
            count_axis.text(.5, .5, 'No states meet the minimum', ha='center')
        else:
            y = range(len(ranked))
            count_axis.barh(y, ranked['late_orders'], color=TEAL, height=.58)
            maximum = max(1, ranked['late_orders'].max())
            for index, row in ranked.iterrows():
                count_axis.text(row.late_orders + maximum * .02, index, f'{int(row.late_orders):,}',
                                va='center', fontsize=11, color=NAVY)
            count_axis.set_xlim(0, maximum * 1.24)
            rates = ranked['late_rate']
            rate_axis.errorbar(rates, y,
                               xerr=[rates - ranked['ci_low'], ranked['ci_high'] - rates],
                               fmt='o', color=ORANGE, ecolor='#DCA18D', capsize=3, markersize=7)
            for index, row in ranked.iterrows():
                rate_axis.text(row.ci_high + .004, index, f'{row.late_rate:.1%}', va='center', fontsize=10)
            rate_axis.set_xlim(0, max(.10, ranked['ci_high'].max() * 1.35))
            for axis in [count_axis, rate_axis]:
                axis.set_yticks(list(y), ranked['customer_state'])
                axis.set_ylim(len(ranked) - .5, -.5)
        count_axis.set_title('Late deliveries', loc='left', fontsize=13, pad=14)
        rate_axis.set_title('Late rate · 95% Wilson interval', loc='left', fontsize=13, pad=14)
        count_axis.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
        rate_axis.xaxis.set_major_locator(MultipleLocator(.05))
        rate_axis.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        for axis in [count_axis, rate_axis]:
            style_axis(axis)
        figure.text(.07, .10, 'Ranking describes affected order volume; it does not estimate preventable delays or savings.',
                    fontsize=10, color=MUTED)
        figure.text(.07, .06, 'Intervals assume independent orders. All states, counts and denominators are retained in states.csv.',
                    fontsize=10, color=MUTED)
        figure.savefig(path, dpi=160, facecolor='white')
        plt.close(figure)


def write_snapshot(frames, provenance, output, replace=False):
    """Stage known assets before replacing them; preserve README and other files."""
    output = Path(output)
    if not replace and any((output / name).exists() for name in OUTPUT_FILES):
        raise FileExistsError(f'{output} already has results. Use --replace to refresh them.')
    quality = frames['quality']
    if ((quality['severity'] == 'error') & (quality['issues'] > 0)).any():
        raise ValueError('Quality gate failed; no results were published.')
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.results-', dir=output.parent) as temporary:
        stage = Path(temporary)
        frames['monthly'][MONTHLY_COLUMNS].to_csv(stage / 'monthly.csv', index=False)
        frames['states'][STATE_COLUMNS].to_csv(stage / 'states.csv', index=False)
        quality.to_csv(stage / 'quality.csv', index=False)
        draw_overview(frames['overview'], frames['monthly'], stage / 'overview.png')
        draw_states(frames['states'], stage / 'state-ranking.png')
        metadata = dict(provenance)
        metadata['published_at_utc'] = datetime.now(timezone.utc).isoformat()
        metadata['scope'] = {'filters': 'none', 'minimum_orders_for_charts': MINIMUM_ORDERS,
                             'state_chart_limit': 10}
        metadata['overview'] = json.loads(frames['overview'].to_json(orient='records', double_precision=15))[0]
        metadata['output_sha256'] = {
            name: hashlib.sha256((stage / name).read_bytes()).hexdigest()
            for name in OUTPUT_FILES if name != 'provenance.json'
        }
        (stage / 'provenance.json').write_text(json.dumps(metadata, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        for name in OUTPUT_FILES:
            (stage / name).replace(output / name)
    return output


def read_snapshot():
    """Read summaries and provenance from one consistent, read-only transaction."""
    from src.db import connect, query_frame
    with connect() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        run = conn.execute('SELECT dataset_label, loaded_at, manifest FROM olist_bi.run_metadata').fetchone()
        if not run or run[0] != 'olist':
            raise ValueError('Load the real Olist dataset before publishing results.')
        frames = {name: query_frame(conn, ROOT / 'sql/analysis' / f'{name}.sql')
                  for name in ['overview', 'monthly', 'states']}
        frames['quality'] = query_frame(conn, ROOT / 'sql/03_quality.sql')
    frames['states'] = add_intervals(frames['states'])
    provenance = {'dataset_label': run[0], 'database_loaded_at': run[1].isoformat(),
                  'source': 'PostgreSQL read-only snapshot', 'files': run[2]}
    provenance['sql_sha256'] = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / 'sql').rglob('*.sql'))
    }
    return frames, provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'results')
    parser.add_argument('--replace', action='store_true', help='Refresh the six generated assets; preserve other files.')
    args = parser.parse_args()
    frames, provenance = read_snapshot()
    output = write_snapshot(frames, provenance, args.output, args.replace)
    print(f'Published full-dataset results: {output}')


if __name__ == '__main__':
    main()
