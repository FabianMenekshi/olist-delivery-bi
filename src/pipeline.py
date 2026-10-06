"""Import and validate Olist data: python -m src.pipeline --help."""
import argparse
from pathlib import Path

from psycopg.types.json import Jsonb

from src.db import ROOT, connect, execute_file, query_frame
from src.ingest import load
from src.manifest import TABLES


SQL_DIR = ROOT / 'sql'


def validate_dataset_label(data_dir: Path, label: str) -> None:
    """Prevent fictional data from being presented as Olist observations."""
    if label != 'olist':
        raise ValueError('This project expects --label olist.')
    if (data_dir / 'SYNTHETIC_DEMO.json').exists():
        raise ValueError('Synthetic inputs cannot be loaded as Olist data.')


def prepare_database(conn, replace: bool) -> None:
    """Create project schemas and enforce explicit permission to replace rows."""
    execute_file(conn, SQL_DIR / '01_schema.sql')
    # Table identifiers come only from our fixed manifest.
    has_data = any(
        conn.execute(f'SELECT EXISTS(SELECT 1 FROM olist_raw.{table})').fetchone()[0]
        for table in TABLES
    )
    if has_data and not replace:
        raise RuntimeError(
            'Project tables already contain data. Pass --replace to replace only '
            'the Olist project data.'
        )
    conn.execute('''
        TRUNCATE olist_raw.reviews, olist_raw.payments, olist_raw.items,
                 olist_raw.orders, olist_raw.customers, olist_raw.products,
                 olist_raw.sellers
    ''')


def check_quality(conn):
    """Raise inside the transaction when any blocking check has issues."""
    quality = query_frame(conn, SQL_DIR / '03_quality.sql')
    errors = quality.loc[(quality['severity'] == 'error') & (quality['issues'] > 0)]
    if not errors.empty:
        raise RuntimeError('Quality gate failed; import rolled back:\n' + errors.to_string(index=False))
    return quality


def record_run(conn, label, manifest) -> None:
    """Record provenance in the same transaction as the imported data."""
    conn.execute('''
        INSERT INTO olist_bi.run_metadata (singleton, dataset_label, manifest)
        VALUES (true, %s, %s)
        ON CONFLICT (singleton) DO UPDATE SET
            dataset_label = excluded.dataset_label,
            manifest = excluded.manifest,
            loaded_at = now()
    ''', (label, Jsonb(manifest)))


def run(data_dir, label="olist", replace=False):
    """Commit the data and provenance together; create no output files."""
    data_dir = Path(data_dir).resolve()
    validate_dataset_label(data_dir, label)
    with connect() as conn:
        prepare_database(conn, replace)
        manifest = load(conn, data_dir)
        execute_file(conn, SQL_DIR / '02_order_mart.sql')
        quality = check_quality(conn)
        record_run(conn, label, manifest)

    print(f'Committed {label}. Database updated; no files generated.')
    print(quality.to_string(index=False))
    return quality


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--label', choices=['olist'], default='olist')
    parser.add_argument(
        '--replace', action='store_true',
        help='Replace existing data in the project schemas, transactionally.',
    )
    args = parser.parse_args()
    run(args.data_dir, args.label, args.replace)


if __name__ == '__main__':
    main()
