"""Validate headers and stream selected CSV fields through PostgreSQL COPY.

Review text, coordinates and unused product attributes are intentionally omitted.
SQL identifiers come from the fixed manifest, never from user-supplied SQL.
"""
import csv
import hashlib
from pathlib import Path

from psycopg import sql

from src.manifest import TABLES


def load_table(conn, path: Path, table: str, columns: list[str]) -> int:
    """Load one source table and return its row count."""
    if not path.is_file():
        raise FileNotFoundError(
            f'Missing {path}; extract the Olist CSVs directly into the input folder.'
        )
    count = 0
    with path.open(newline='', encoding='utf-8-sig') as source:
        reader = csv.DictReader(source)
        missing = set(columns) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f'{path.name}: missing columns {sorted(missing)}')
        statement = sql.SQL('COPY olist_raw.{} ({}) FROM STDIN').format(
            sql.Identifier(table),
            sql.SQL(',').join(map(sql.Identifier, columns)),
        )
        with conn.cursor().copy(statement) as copy:
            for row in reader:
                # Preserve zero and whitespace; only empty fields become NULL.
                copy.write_row([
                    None if row[column] == '' else row[column] for column in columns
                ])
                count += 1
    return count


def load(conn, folder):
    """Load all seven tables in manifest order, inside the caller's transaction."""
    manifest = {}
    for table, (filename, columns) in TABLES.items():
        path = Path(folder) / filename
        count = load_table(conn, path, table, columns)
        manifest[filename] = {
            'rows': count,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    return manifest
