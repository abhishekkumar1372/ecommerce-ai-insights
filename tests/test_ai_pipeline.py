"""End-to-end AI pipeline against the warehouse, with a fake LLM (no API key needed)."""
import yaml
from conftest import needs_warehouse

from ecom.ai import anomalies, facts, insights, retrieval, text_to_sql
from ecom.ai.evals import EVAL_FILE, results_match
from ecom.ai.llm import FakeLLM

pytestmark = needs_warehouse


def _summary_from(fact_list, wrong_number=False):
    f = {x.id: x for x in fact_list}
    rev = "R$ 1" if wrong_number else f["revenue"].display()
    return {
        "headline": {"text": f"Revenue reached {rev} in {f['month'].value}", "fact_ids": ["revenue", "month"]},
        "wins": [{"text": f"Average review score held at {f['review'].display()}", "fact_ids": ["review"]}],
        "risks": [{"text": f"Late orders score {f['review_late'].display()} vs {f['review_on_time'].display()}",
                   "fact_ids": ["review_late", "review_on_time"]}],
        "actions": [{"text": "Prioritise carriers in the worst state",
                     "rationale": f"Its late rate is {f['worst_state_late_rate'].display()}",
                     "fact_ids": ["worst_state_late_rate"]}],
    }


def test_summary_passes_fact_check_when_grounded():
    fs = facts.collect()
    llm = FakeLLM(lambda purpose, user: _summary_from(fs))
    r = insights.generate(llm=llm, save=False)
    assert r["passed"], r["fact_check"]
    assert len(llm.calls) == 1


def test_summary_with_wrong_number_is_regenerated():
    fs = facts.collect()
    llm = FakeLLM(lambda purpose, user: _summary_from(fs, wrong_number=(purpose == "executive_summary")))
    r = insights.generate(llm=llm, save=False)
    assert [p for p, _ in llm.calls] == ["executive_summary", "executive_summary_retry"]
    assert "does not match" in llm.calls[1][1] or "do not match" in llm.calls[1][1]
    assert r["passed"] and r["fact_check"]["attempts"] == 2


def test_every_fact_has_source_sql():
    assert all(f.source_sql.lower().startswith("select") or f.source_sql.lower().startswith("with")
               for f in facts.collect())


def test_retrieval_finds_relevant_tables():
    ids = [h["id"] for h in retrieval.search("how many customers are in each RFM segment", k=3)]
    assert "kpi.kpi_rfm_segments" in ids


def test_text_to_sql_retries_after_bad_sql():
    gold = "select segment, count(*) as n from kpi.kpi_rfm_segments group by 1"
    drafts = iter(["select * from raw.orders", gold])

    def responder(purpose, user):
        if purpose == "text_to_sql":
            return {"reasoning": "-", "sql": next(drafts), "chart": "bar"}
        return {"answer": "Customers are spread across six segments.", "caveats": []}

    r = text_to_sql.ask("How many customers are in each RFM segment?", llm=FakeLLM(responder))
    assert r["ok"] and len(r["attempts"]) == 2
    assert "not allowed" in r["attempts"][0]["error"]
    assert len(r["rows"]) == 6


def test_text_to_sql_runs_as_readonly_role():
    def responder(purpose, user):
        # Passes the guard (marts schema) but the role has no INSERT rights either way.
        return {"reasoning": "-", "sql": "select current_user as u", "chart": "number"} if purpose == "text_to_sql" \
            else {"answer": "ok", "caveats": []}
    r = text_to_sql.ask("who am I", llm=FakeLLM(responder))
    assert r["rows"][0]["u"] == "ai_readonly"


def test_answer_numbers_are_checked_against_rows():
    rows = [{"state": "SP", "late_rate": 0.082}]
    assert text_to_sql.check_answer("SP has a late rate of 8.2%", rows)["passed"]
    assert not text_to_sql.check_answer("SP has a late rate of 12%", rows)["passed"]


def test_gold_eval_queries_match_themselves():
    from ecom.ai import db
    for case in yaml.safe_load(EVAL_FILE.read_text()):
        rows = db.query(case["sql"])
        assert results_match(rows, rows, case.get("ordered", False)), case["question"]


def test_eval_accepts_extra_columns():
    assert results_match([{"s": "SP", "n": 3}], [{"state": "SP"}])
    assert not results_match([{"s": "RJ", "n": 3}], [{"state": "SP"}])


def test_detects_black_friday_spike():
    days = [a["date_day"] for a in anomalies.detect()]
    assert "2017-11-24" in days


def test_anomaly_explanation_is_fact_checked():
    a = next(x for x in anomalies.detect() if x["date_day"] == "2017-11-24")

    def responder(purpose, user):
        return {"title": "Black Friday spike",
                "explanation": f"Revenue hit R$ {a['revenue']:,.0f} against a typical R$ {a['baseline']:,.0f}.",
                "likely_cause": "Hypothesis: Black Friday promotions.", "fact_ids": ["revenue", "baseline"]}
    r = anomalies.explain(a, llm=FakeLLM(responder), save=False)
    assert r["passed"], r["fact_check"]
