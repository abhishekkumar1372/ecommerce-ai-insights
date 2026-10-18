"""Fact-checked executive summary.

1. Run fixed KPI queries and turn the results into facts (ecom.ai.facts).
2. Ask Claude for a structured summary where every point cites the fact ids it uses.
3. Check every number against the cited facts (ecom.ai.factcheck).
4. If anything fails, send the failures back once and regenerate.
5. Store the summary, its facts, the SQL behind them and the check result in ai.ai_insights.

Usage:  python -m ecom.ai.insights
"""
import json
import logging

from pydantic import BaseModel, Field

from ecom.ai import db
from ecom.ai import facts as facts_mod
from ecom.ai.factcheck import CheckResult, check_point
from ecom.ai.llm import LLM, default_llm

log = logging.getLogger("insights")


class Point(BaseModel):
    text: str = Field(description="One sentence for a business reader.")
    fact_ids: list[str] = Field(description="Ids of every fact whose number appears in the text.")


class Action(BaseModel):
    text: str = Field(description="A concrete action the business can take.")
    rationale: str = Field(description="Why, citing numbers from the facts.")
    fact_ids: list[str]


class Summary(BaseModel):
    headline: Point
    wins: list[Point]
    risks: list[Point]
    actions: list[Action]


SYSTEM = """You are the analyst writing the monthly business summary for an e-commerce marketplace in Brazil.

Rules:
- Use only the facts provided. Every number you write must be one of those facts, written the way it is
  displayed (you may round, e.g. R$ 70,680 as R$ 70.7k). Do not calculate new numbers.
- Every point lists the ids of the facts it uses in fact_ids.
- Profit and margin are estimates based on assumed category margins; say "estimated" when you use them.
- Be specific and plain. 2-3 wins, 2-3 risks, exactly 3 actions ranked by expected impact."""


def all_points(summary: Summary) -> list[tuple[str, list[str]]]:
    pts = [(summary.headline.text, summary.headline.fact_ids)]
    pts += [(p.text, p.fact_ids) for p in summary.wins + summary.risks]
    pts += [(f"{a.text} {a.rationale}", a.fact_ids) for a in summary.actions]
    return pts


def fact_check(summary: Summary, facts: list[dict]) -> CheckResult:
    by_id = {f["id"]: f for f in facts}
    result = CheckResult()
    for text, ids in all_points(summary):
        check_point(text, ids, by_id, result)
    return result


def generate(llm: LLM | None = None, save: bool = True) -> dict:
    llm = llm or default_llm()
    facts = facts_mod.collect()
    fact_rows = facts_mod.as_json(facts)
    prompt = f"Facts:\n{facts_mod.as_prompt(facts)}\n\nWrite the summary."

    summary = llm.structured("executive_summary", SYSTEM, prompt, Summary)
    check = fact_check(summary, fact_rows)
    attempts = 1
    if not check.passed:
        log.info("fact-check failed, regenerating: %s", check.unverified + check.unknown_fact_ids)
        feedback = "\n".join(f"- {u}" for u in check.unverified + [f"unknown fact id {i}" for i in check.unknown_fact_ids])
        summary = llm.structured(
            "executive_summary_retry", SYSTEM,
            f"{prompt}\n\nYour previous draft had numbers that do not match the cited facts:\n{feedback}\n"
            "Rewrite it using only the facts, citing the right fact ids.",
            Summary,
        )
        check = fact_check(summary, fact_rows)
        attempts = 2

    record = {
        "kind": "executive_summary",
        "title": summary.headline.text,
        "body": summary.model_dump(),
        "facts": fact_rows,
        "fact_check": check.as_dict() | {"attempts": attempts},
        "passed": check.passed,
        "model": llm.model,
    }
    if save:
        record["id"] = save_insight(record)
    return record


def save_insight(record: dict) -> int:
    with db.connect() as conn:
        row = conn.execute(
            "INSERT INTO ai.ai_insights (kind, title, body, facts, fact_check, passed, model)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (record["kind"], record["title"], json.dumps(record["body"]), json.dumps(record["facts"]),
             json.dumps(record["fact_check"]), record["passed"], record["model"]),
        ).fetchone()
    return row["id"]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    r = generate()
    print(json.dumps({"headline": r["title"], "passed": r["passed"], "fact_check": r["fact_check"]}, indent=2))


if __name__ == "__main__":
    main()
