"""Evaluate text-to-SQL accuracy and summary fact-check pass rate.

Text-to-SQL: each question's predicted SQL is executed and its result set compared
with the gold SQL's (execution accuracy, the standard text-to-SQL metric).
Summaries: generate N summaries and count how many pass the fact-check first time.

Needs an API key; costs are logged to ai.llm_calls.
Usage:  python -m ecom.ai.evals [--summaries 3]
"""
import argparse
import json
from pathlib import Path

import yaml

from ecom.ai import db, insights, text_to_sql
from ecom.config import ROOT

EVAL_FILE = Path(ROOT / "evals/text_to_sql.yml")


def normalise(rows: list[dict], ordered: bool) -> list[tuple]:
    def cell(v):
        if isinstance(v, bool) or v is None:
            return v
        if isinstance(v, (int, float)):
            return round(float(v), 2)
        return str(v)
    out = [tuple(cell(v) for v in r.values()) for r in rows]
    return out if ordered else sorted(out, key=repr)


def results_match(pred: list[dict], gold: list[dict], ordered: bool = False) -> bool:
    """Match when the gold columns all appear in the prediction (extra columns are allowed)."""
    if len(pred) != len(gold):
        return False
    if not gold:
        return True
    gold_n = normalise(gold, ordered)
    width = len(gold_n[0])
    pred_n = normalise(pred, ordered)
    if len(pred_n[0]) == width:
        return pred_n == gold_n
    # Prediction has extra columns: accept if some subset of its columns in order equals gold.
    from itertools import combinations
    for cols in combinations(range(len(pred_n[0])), width):
        proj = [tuple(r[i] for i in cols) for r in pred_n]
        if (proj if ordered else sorted(proj, key=repr)) == gold_n:
            return True
    return False


def run_text_to_sql(llm=None) -> dict:
    cases = yaml.safe_load(EVAL_FILE.read_text())
    results = []
    for case in cases:
        gold = db.query(case["sql"])
        pred = text_to_sql.ask(case["question"], llm=llm)
        ok = pred["ok"] and results_match(pred["rows"], gold, case.get("ordered", False))
        results.append({"question": case["question"], "correct": ok, "sql": pred.get("sql"),
                        "retries": len(pred["attempts"]) - 1,
                        "answer_fact_check": pred.get("fact_check", {}).get("passed")})
    n = len(results)
    return {"accuracy": sum(r["correct"] for r in results) / n,
            "answer_fact_check_pass_rate": sum(bool(r["answer_fact_check"]) for r in results) / n,
            "cases": results}


def run_summaries(n: int, llm=None) -> dict:
    first_try = final = 0
    for _ in range(n):
        r = insights.generate(llm=llm, save=False)
        final += r["passed"]
        first_try += r["passed"] and r["fact_check"]["attempts"] == 1
    return {"runs": n, "passed_first_try": first_try / n, "passed_after_retry": final / n}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summaries", type=int, default=3)
    args = parser.parse_args()
    report = {"text_to_sql": run_text_to_sql(), "summaries": run_summaries(args.summaries)}
    cost = db.query("select coalesce(sum(cost_usd), 0) as usd from ai.llm_calls "
                    "where created_at > now() - interval '1 hour'")[0]["usd"]
    report["approx_cost_usd_last_hour"] = cost
    print(json.dumps({k: v for k, v in report.items()} | {"text_to_sql": {
        k: v for k, v in report["text_to_sql"].items() if k != "cases"}}, indent=2))
    Path(ROOT / "evals/last_report.json").write_text(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
