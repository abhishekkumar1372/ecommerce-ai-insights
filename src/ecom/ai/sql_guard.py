"""Validate model-written SQL before it runs.

Defence in depth: the query also runs as the ai_readonly role (SELECT only on
marts and kpi, 10s statement timeout) in a read-only transaction. This check
gives the model a clear error message to fix instead of a database error.
"""
import sqlglot
from sqlglot import exp

ALLOWED_SCHEMAS = {"marts", "kpi"}
MAX_ROWS = 500


class UnsafeSQL(ValueError):
    pass


def validate(sql: str) -> str:
    """Return a safe, row-limited version of `sql`, or raise UnsafeSQL with the reason."""
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except sqlglot.errors.ParseError as e:
        raise UnsafeSQL(f"could not parse SQL: {e}") from e
    if len(statements) != 1:
        raise UnsafeSQL("exactly one statement is allowed")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Except, exp.Intersect)):
        raise UnsafeSQL(f"only SELECT queries are allowed, got {tree.key.upper()}")
    for node in tree.walk():
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command)):
            raise UnsafeSQL(f"{node.key.upper()} is not allowed")
    cte_names = {c.alias_or_name for c in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if table.name in cte_names and not table.db:
            continue
        if table.db not in ALLOWED_SCHEMAS:
            raise UnsafeSQL(
                f"table {table.sql()} is not allowed; use schema-qualified tables from {sorted(ALLOWED_SCHEMAS)}"
            )
    if isinstance(tree, exp.Select):
        limit = tree.args.get("limit")
        if limit is None:
            tree = tree.limit(MAX_ROWS)
        else:
            try:
                if int(limit.expression.name) > MAX_ROWS:
                    tree = tree.limit(MAX_ROWS)
            except (ValueError, AttributeError):
                tree = tree.limit(MAX_ROWS)
    else:
        tree = exp.select("*").from_(tree.subquery("q")).limit(MAX_ROWS)
    return tree.sql(dialect="postgres")
