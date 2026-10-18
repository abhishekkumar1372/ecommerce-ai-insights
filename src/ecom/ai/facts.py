"""Collect the numbers an AI summary is allowed to use.

Every fact carries the SQL that produced it, so any number in a generated
summary can be traced back to a query. The model never sees raw tables here,
only these facts.
"""
from dataclasses import asdict, dataclass

from ecom.ai import db


@dataclass
class Fact:
    id: str
    label: str
    value: float | str
    unit: str          # currency | pct | count | score | days | text | month
    source_sql: str

    def display(self) -> str:
        v = self.value
        if self.unit == "currency":
            return f"R$ {v:,.0f}"
        if self.unit == "pct":
            return f"{v * 100:.1f}%"
        if self.unit in ("score", "days"):
            return f"{v:.2f}"
        if self.unit == "count":
            return f"{v:,.0f}"
        return str(v)


def _one(sql: str) -> dict:
    rows = db.query(sql)
    return rows[0] if rows else {}


MONTH_SQL = """
select * from kpi.kpi_monthly_sales
where month < (select date_trunc('month', max(purchased_at)) from marts.fct_orders)
order by month desc limit 1
"""


def collect() -> list[Fact]:
    """Headline facts for the latest complete month plus the standing business drivers."""
    facts: list[Fact] = []

    def add(id_, label, value, unit, sql):
        if value is not None:
            facts.append(Fact(id_, label, float(value) if unit not in ("text", "month") else value, unit,
                              " ".join(sql.split())))

    m = _one(MONTH_SQL)
    if m:
        add("month", "Reporting month", m["month"][:7], "month", MONTH_SQL)
        add("revenue", "Revenue in the month", m["revenue"], "currency", MONTH_SQL)
        add("revenue_mom", "Revenue change vs previous month", m["revenue_mom_growth"], "pct", MONTH_SQL)
        add("revenue_yoy", "Revenue change vs same month last year", m["revenue_yoy_growth"], "pct", MONTH_SQL)
        add("orders", "Orders in the month", m["orders"], "count", MONTH_SQL)
        add("aov", "Average order value", m["avg_order_value"], "currency", MONTH_SQL)
        add("margin", "Estimated gross margin", m["est_margin_pct"], "pct", MONTH_SQL)
        add("review", "Average review score (1-5)", m["avg_review_score"], "score", MONTH_SQL)
        add("late_rate", "Share of orders delivered late", m["late_delivery_rate"], "pct", MONTH_SQL)

    sql = "select category, revenue_share from kpi.kpi_category_pareto order by revenue_rank limit 1"
    top = _one(sql)
    if top:
        add("top_category", "Top category by revenue (all time)", top["category"], "text", sql)
        add("top_category_share", "Top category's share of revenue", top["revenue_share"], "pct", sql)

    sql = ("select count(*) filter (where is_top_80_pct) as n80, count(*) as n "
           "from kpi.kpi_category_pareto")
    p = _one(sql)
    if p:
        add("categories_80pct", "Categories that make up 80% of revenue", p["n80"], "count", sql)
        add("categories_total", "Total categories", p["n"], "count", sql)

    sql = ("select count(*) as n, sum(monetary) as revenue from kpi.kpi_rfm_segments "
           "where segment = 'At Risk (high value)'")
    r = _one(sql)
    if r:
        add("at_risk_customers", "High-value customers at risk of churning", r["n"], "count", sql)
        add("at_risk_revenue", "Lifetime revenue from at-risk customers", r["revenue"], "currency", sql)

    sql = ("select round(avg(review_score) filter (where not is_late), 2) as on_time, "
           "round(avg(review_score) filter (where is_late), 2) as late "
           "from marts.fct_orders where order_status = 'delivered'")
    d = _one(sql)
    if d and d["late"] is not None:
        add("review_on_time", "Average review when delivered on time", d["on_time"], "score", sql)
        add("review_late", "Average review when delivered late", d["late"], "score", sql)
        add("review_gap", "Review score drop when an order is late", d["on_time"] - d["late"], "score", sql)

    sql = ("select state, late_rate from kpi.kpi_delivery_impact where delivered_orders >= 30 "
           "order by late_rate desc limit 1")
    s = _one(sql)
    if s:
        add("worst_state", "State with the highest late-delivery rate", s["state"], "text", sql)
        add("worst_state_late_rate", "Late-delivery rate in that state", s["late_rate"], "pct", sql)

    sql = "select count(*) as n from kpi.kpi_seller_scorecard where needs_attention"
    add("sellers_flagged", "Sellers flagged for poor reviews or late delivery", _one(sql).get("n"), "count", sql)
    return facts


def as_prompt(facts: list[Fact]) -> str:
    return "\n".join(f"- [{f.id}] {f.label}: {f.display()}" for f in facts)


def as_json(facts: list[Fact]) -> list[dict]:
    return [asdict(f) | {"display": f.display()} for f in facts]
