"""Load the raw Olist CSV files into Postgres, unchanged.

Every column lands as TEXT in the `raw` schema. Typing, cleaning and
deduplication happen downstream in dbt, so the raw layer is always an exact,
re-loadable copy of the source files.

Usage:  python -m ecom.ingest [--data-dir data/raw]
"""
import argparse
import csv
import logging
import time
from pathlib import Path

import psycopg
from psycopg import sql

from ecom.config import RAW_DIR, pg_dsn
from ecom.datasets import OLIST_FILES

log = logging.getLogger("ingest")


def read_header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [c.strip() for c in next(csv.reader(f))]


def existing_columns(cur: psycopg.Cursor, schema: str, table: str) -> list[str]:
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s AND column_name <> '_loaded_at' ORDER BY ordinal_position",
        (schema, table),
    )
    return [r[0] for r in cur.fetchall()]


def load_file(conn: psycopg.Connection, path: Path, table: str, schema: str = "raw") -> int:
    columns = read_header(path)
    ident = sql.Identifier(schema, table)
    col_defs = sql.SQL(", ").join(
        sql.SQL("{} TEXT").format(sql.Identifier(c)) for c in columns
    )
    with conn.cursor() as cur:
        if existing_columns(cur, schema, table) == columns:
            # Same shape: truncate so the dbt staging views built on top stay valid.
            cur.execute(sql.SQL("TRUNCATE {}").format(ident))
        else:
            # New or changed file layout: rebuild. CASCADE drops dependent staging
            # views; the next `dbt build` recreates them.
            cur.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(ident))
            cur.execute(
                sql.SQL("CREATE TABLE {} ({}, _loaded_at TIMESTAMPTZ DEFAULT now())").format(ident, col_defs)
            )
        copy_stmt = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true)").format(
            ident, sql.SQL(", ").join(sql.Identifier(c) for c in columns)
        )
        with path.open("rb") as f, cur.copy(copy_stmt) as copy:
            while chunk := f.read(1 << 20):
                copy.write(chunk)
        cur.execute(sql.SQL("SELECT count(*) FROM {}").format(ident))
        return cur.fetchone()[0]


def run(data_dir: Path = RAW_DIR, dsn: str | None = None, schema: str = "raw") -> dict[str, int]:
    missing = [f for f in OLIST_FILES if not (data_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing files in {data_dir}: {missing}. "
            "Run `python -m ecom.download` (Kaggle) or `python -m ecom.sample_data`."
        )
    counts: dict[str, int] = {}
    with psycopg.connect(dsn or pg_dsn()) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
        for file_name, table in OLIST_FILES.items():
            start = time.perf_counter()
            counts[table] = load_file(conn, data_dir / file_name, table, schema)
            log.info("%s.%-36s %8d rows  %.1fs", schema, table, counts[table], time.perf_counter() - start)
    return counts


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=RAW_DIR)
    run(parser.parse_args().data_dir)


if __name__ == "__main__":
    main()
