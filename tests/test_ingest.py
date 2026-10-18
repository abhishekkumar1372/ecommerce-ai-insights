"""Integration test: needs a running Postgres (skipped otherwise)."""
import psycopg
import pytest

from ecom import ingest, sample_data
from ecom.config import pg_dsn


def _db_available() -> bool:
    try:
        psycopg.connect(pg_dsn(), connect_timeout=2).close()
        return True
    except psycopg.OperationalError:
        return False


@pytest.mark.skipif(not _db_available(), reason="Postgres not running")
def test_ingest_loads_every_row(tmp_path):
    sample_data.write(tmp_path, n_orders=200)
    try:
        counts = ingest.run(tmp_path, schema="raw_test")
        assert counts["orders"] == 200
        assert counts["order_items"] >= 200
        # Re-running must truncate and reload, not append or fail.
        assert ingest.run(tmp_path, schema="raw_test") == counts
    finally:
        with psycopg.connect(pg_dsn(), autocommit=True) as conn:
            conn.execute("DROP SCHEMA IF EXISTS raw_test CASCADE")


def test_ingest_reports_missing_files(tmp_path):
    with pytest.raises(FileNotFoundError, match="Missing files"):
        ingest.run(tmp_path)
