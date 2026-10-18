import pytest

from ecom.ai.sql_guard import MAX_ROWS, UnsafeSQL, validate


def test_adds_row_limit():
    assert f"LIMIT {MAX_ROWS}" in validate("select * from marts.fct_orders")


def test_keeps_smaller_limit_and_caps_larger():
    assert "LIMIT 5" in validate("select * from kpi.kpi_monthly_sales limit 5")
    assert f"LIMIT {MAX_ROWS}" in validate("select * from kpi.kpi_monthly_sales limit 100000")


def test_allows_ctes_and_joins():
    validate("with t as (select * from marts.fct_orders) select count(*) from t join marts.dim_customer using (customer_id)")


@pytest.mark.parametrize("sql", [
    "delete from marts.fct_orders",
    "drop table marts.fct_orders",
    "insert into marts.dim_date values (1)",
    "update marts.fct_orders set revenue = 0",
    "select 1; select 2",
    "select * from raw.orders",
    "select * from pg_catalog.pg_roles",
    "select * from fct_orders",
    "copy marts.fct_orders to '/tmp/x'",
])
def test_rejects_unsafe_sql(sql):
    with pytest.raises(UnsafeSQL):
        validate(sql)
