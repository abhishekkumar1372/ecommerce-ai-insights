"""Detect unusual days in revenue and explain them.

Detection is plain statistics in SQL: a day is anomalous when its revenue is
more than Z_THRESHOLD standard deviations from the trailing 28-day mean.
Explanation drills down by category and state, comparing the day with its
baseline, and asks Claude to explain the drivers using only those numbers.

Usage:  python -m ecom.ai.anomalies [--explain 3]
"""
import argparse
import json

from pydantic import BaseModel, Field

from ecom.ai import db
from ecom.ai.factcheck import CheckResult, check_point
from ecom.ai.insights import save_insight
from ecom.ai.llm import LLM, default_llm

Z_THRESHOLD = 3.0

DETECT_SQL = """
with daily as (
    select d.date_day, coalesce(sum(f.revenue), 0) as revenue
    from marts.dim_date d
    left join marts.fct_order_items f
        on f.date_key = d.date_key and f.order_status not in ('canceled', 'unavailable')
    where d.date_day between (select min(purchased_at)::date from marts.fct_orders)
                         and (select max(purchased_at)::date from marts.fct_orders)
    group by 1
),
scored as (
    select date_day, revenue,
           avg(revenue)    over w as baseline,
           stddev(revenue) over w as sd,
           count(*)        over w as n
    from daily
    window w as (order by date_day rows between 28 preceding and 1 preceding)
)
select date_day, round(revenue, 2) as revenue, round(baseline, 2) as baseline,
       round((revenue - baseline) / nullif(sd, 0), 2) as z_score
from scored
where n = 28 and abs((revenue - baseline) / nullif(sd, 0)) >= %(z)s
order by abs((revenue - baseline) / nullif(sd, 0)) desc
"""

DRILL_SQL = """
with day as (
    select {dim} as segment, sum(f.revenue) as revenue
    from marts.fct_order_items f {join}
    where f.purchased_at::date = %(day)s and f.order_status not in ('canceled', 'unavailable')
    group by 1
),
base as (
    select {dim} as segment, sum(f.revenue) / 28.0 as revenue
    from marts.fct_order_items f {join}
    where f.purchased_at::date >= %(day)s::date - 28 and f.purchased_at::date < %(day)s
      and f.order_status not in ('canceled', 'unavailable')
    group by 1
)
select coalesce(day.segment, base.segment) as segment,
       round(coalesce(day.revenue, 0), 2) as revenue_on_day,
       round(coalesce(base.revenue, 0), 2) as typical_daily_revenue,
       round(coalesce(day.revenue, 0) - coalesce(base.revenue, 0), 2) as change
from day full join base using (segment)
order by abs(coalesce(day.revenue, 0) - coalesce(base.revenue, 0)) desc
limit 5
"""

DIMENSIONS = {
    "category": ("p.category", "join marts.dim_product p using (product_id)"),
    "state": ("c.state", "join marts.dim_customer c using (customer_id)"),
}


class Explanation(BaseModel):
    title: str = Field(description="Short title, e.g. 'Black Friday spike in watches_gifts'.")
    explanation: str = Field(description="2-3 sentences on what drove the change, citing numbers.")
    likely_cause: str = Field(description="Most likely business cause, marked as a hypothesis.")
    fact_ids: list[str]


SYSTEM = """You explain unusual days in e-commerce revenue to a business team.
Use only the numbers in the facts and cite their ids. Say which segments drove the change.
The likely cause is a hypothesis (promotion, holiday, stock-out, data issue); say so."""


def detect(z: float = Z_THRESHOLD) -> list[dict]:
    return db.query(DETECT_SQL, {"z": z})


def drill_down(day: str) -> dict[str, list[dict]]:
    return {name: db.query(DRILL_SQL.format(dim=dim, join=join), {"day": day})
            for name, (dim, join) in DIMENSIONS.items()}


def build_facts(anomaly: dict, drill: dict[str, list[dict]]) -> list[dict]:
    facts = [
        {"id": "day", "value": anomaly["date_day"], "unit": "text", "label": "Date"},
        {"id": "revenue", "value": anomaly["revenue"], "unit": "currency", "label": "Revenue on the day"},
        {"id": "baseline", "value": anomaly["baseline"], "unit": "currency", "label": "Typical daily revenue (28d)"},
        {"id": "z", "value": anomaly["z_score"], "unit": "score", "label": "Standard deviations from typical"},
    ]
    for dim, rows in drill.items():
        for i, r in enumerate(rows[:3], 1):
            for col in ("revenue_on_day", "typical_daily_revenue", "change"):
                facts.append({"id": f"{dim}{i}_{col}", "value": r[col], "unit": "currency",
                              "label": f"{dim} '{r['segment']}': {col.replace('_', ' ')}"})
    return facts


def explain(anomaly: dict, llm: LLM | None = None, save: bool = True) -> dict:
    llm = llm or default_llm()
    drill = drill_down(anomaly["date_day"])
    facts = build_facts(anomaly, drill)
    prompt = "Facts:\n" + "\n".join(f"- [{f['id']}] {f['label']}: {f['value']}" for f in facts)
    result = llm.structured("anomaly_explanation", SYSTEM, prompt, Explanation)
    check = CheckResult()
    check_point(f"{result.explanation} {result.likely_cause}", result.fact_ids, {f["id"]: f for f in facts}, check)
    record = {"kind": "anomaly", "title": result.title, "body": result.model_dump() | {"drill_down": drill},
              "facts": facts, "fact_check": check.as_dict(), "passed": check.passed, "model": llm.model}
    if save:
        record["id"] = save_insight(record)
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--explain", type=int, default=0, help="explain the top N anomalies with Claude")
    args = parser.parse_args()
    found = detect()
    print(json.dumps(found[:10], indent=2, default=str))
    for a in found[: args.explain]:
        r = explain(a)
        print(f"\n{r['title']}  (fact-check passed: {r['passed']})\n{r['body']['explanation']}")


if __name__ == "__main__":
    main()
