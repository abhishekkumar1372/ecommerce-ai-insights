import psycopg
import pytest

from ecom.config import pg_dsn


def _warehouse_ready() -> bool:
    try:
        with psycopg.connect(pg_dsn(), connect_timeout=2) as conn:
            return conn.execute("select to_regclass('kpi.kpi_monthly_sales') is not null "
                                "and to_regclass('ai.knowledge') is not null").fetchone()[0]
    except psycopg.OperationalError:
        return False


needs_warehouse = pytest.mark.skipif(
    not _warehouse_ready(), reason="needs Postgres with dbt models built and `python -m ecom.ai.setup` run"
)
