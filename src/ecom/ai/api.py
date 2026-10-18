"""REST API for the AI layer.  Run:  uvicorn ecom.ai.api:app --reload"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ecom.ai import anomalies, db, insights, text_to_sql
from ecom.ai.llm import LLMRefusal

app = FastAPI(title="E-commerce AI Insights", version="0.3.0")


class Question(BaseModel):
    question: str


@app.get("/health")
def health() -> dict:
    db.query("select 1")
    return {"status": "ok"}


@app.get("/insights/latest")
def latest_insight(kind: str = "executive_summary") -> dict:
    rows = db.query("select * from ai.ai_insights where kind = %s order by created_at desc limit 1", (kind,))
    if not rows:
        raise HTTPException(404, "no insight generated yet")
    return rows[0]


@app.post("/insights/generate")
def generate_insight() -> dict:
    try:
        return insights.generate()
    except LLMRefusal as e:
        raise HTTPException(422, str(e)) from e


@app.post("/ask")
def ask(q: Question) -> dict:
    if not q.question.strip():
        raise HTTPException(400, "question is empty")
    try:
        result = text_to_sql.ask(q.question)
    except LLMRefusal as e:
        raise HTTPException(422, str(e)) from e
    result["rows"] = result["rows"][:200]
    return result


@app.get("/anomalies")
def list_anomalies(z: float = anomalies.Z_THRESHOLD) -> list[dict]:
    return anomalies.detect(z)


@app.post("/anomalies/{day}/explain")
def explain_anomaly(day: str) -> dict:
    match = [a for a in anomalies.detect() if a["date_day"] == day]
    if not match:
        raise HTTPException(404, f"{day} is not flagged as anomalous")
    return anomalies.explain(match[0])


@app.get("/llm/usage")
def llm_usage() -> list[dict]:
    return db.query(
        "select purpose, model, count(*) as calls, sum(input_tokens) as input_tokens, "
        "sum(output_tokens) as output_tokens, round(avg(latency_ms)) as avg_latency_ms, "
        "sum(cost_usd) as cost_usd from ai.llm_calls group by 1, 2 order by cost_usd desc"
    )
