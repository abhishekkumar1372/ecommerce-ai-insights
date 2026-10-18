"""Database helpers for the AI layer: an admin connection and a read-only one."""
import os
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row

from ecom.config import pg_dsn


def readonly_dsn() -> str:
    """Connection used for model-written SQL: role ai_readonly can only SELECT from marts and kpi."""
    return (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DB', 'ecommerce')} "
        f"user={os.getenv('AI_READONLY_USER', 'ai_readonly')} "
        f"password={os.getenv('AI_READONLY_PASSWORD', 'ai_readonly')}"
    )


@contextmanager
def connect(readonly: bool = False):
    with psycopg.connect(readonly_dsn() if readonly else pg_dsn(), row_factory=dict_row) as conn:
        if readonly:
            conn.read_only = True
        yield conn


def to_jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def query(sql: str, params=None, readonly: bool = False) -> list[dict]:
    with connect(readonly) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [{k: to_jsonable(v) for k, v in r.items()} for r in rows]
