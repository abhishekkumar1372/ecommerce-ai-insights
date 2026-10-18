"""Answer a plain-English question with SQL.

question -> retrieve schema docs, metric definitions and examples (pgvector)
         -> Claude writes SQL (structured output)
         -> sql_guard validates it (single SELECT, allowed schemas, row limit)
         -> runs as the read-only role; on error the message goes back to Claude (max 2 retries)
         -> Claude writes the answer from the result rows
         -> numbers in the answer are fact-checked against the result rows

Usage:  python -m ecom.ai.text_to_sql "Which state has the highest average order value?"
"""
import json
import sys

from pydantic import BaseModel, Field

from ecom.ai import db, retrieval
from ecom.ai.factcheck import extract_numbers
from ecom.ai.llm import LLM, default_llm
from ecom.ai.sql_guard import UnsafeSQL, validate

MAX_RETRIES = 2
ROWS_FOR_ANSWER = 50


class SQLDraft(BaseModel):
    reasoning: str = Field(description="Which tables and columns answer the question, briefly.")
    sql: str = Field(description="One PostgreSQL SELECT using schema-qualified marts.* or kpi.* tables.")
    chart: str = Field(description="Best chart for the result: bar, line, table or number.")


class Answer(BaseModel):
    answer: str = Field(description="2-4 sentences answering the question using numbers from the rows.")
    caveats: list[str] = Field(description="Assumptions or data limits the reader should know.")


SQL_SYSTEM = """You write PostgreSQL for an e-commerce analytics warehouse.
Use only the tables and columns in the context. Always schema-qualify tables (marts.x or kpi.x).
Follow the metric definitions exactly. Prefer the kpi.* views when they already answer the question.
Return one SELECT statement, no comments."""

ANSWER_SYSTEM = """You explain query results to a business user.
Use only numbers that appear in the result rows (you may round them). Do not compute new numbers.
Revenue is in Brazilian reais (R$). Profit and margin are estimates."""


def _context(question: str) -> str:
    return "\n\n".join(f"[{h['id']}]\n{h['content']}" for h in retrieval.search(question))


def numbers_in_rows(rows: list[dict]) -> list[float]:
    out = []
    for r in rows:
        for v in r.values():
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                out.append(float(v))
    return out


def check_answer(text: str, rows: list[dict]) -> dict:
    values = numbers_in_rows(rows)
    verified, unverified = [], []
    for m in extract_numbers(text):
        candidates = [v * 100 for v in values] if m.is_pct else values
        decimals = len(m.text.split(".")[1].rstrip("%kKM ")) if "." in m.text else 0
        tol = max(0.5 * 10 ** -decimals, 0.01 * abs(m.value) if abs(m.value) >= 1000 else 0)
        ok = any(abs(abs(m.value) - abs(c)) <= tol + 1e-9 for c in candidates)
        (verified if ok else unverified).append(m.text)
    return {"passed": not unverified, "verified": verified, "unverified": unverified}


def ask(question: str, llm: LLM | None = None) -> dict:
    llm = llm or default_llm()
    context = _context(question)
    prompt = f"Context:\n{context}\n\nQuestion: {question}"
    attempts: list[dict] = []
    rows: list[dict] | None = None
    draft = None
    for attempt in range(MAX_RETRIES + 1):
        draft = llm.structured("text_to_sql", SQL_SYSTEM, prompt, SQLDraft)
        try:
            safe_sql = validate(draft.sql)
            rows = db.query(safe_sql, readonly=True)
            attempts.append({"sql": safe_sql, "error": None})
            break
        except (UnsafeSQL, Exception) as e:  # noqa: BLE001 - any DB error is fed back to the model
            error = str(e).strip().splitlines()[0]
            attempts.append({"sql": draft.sql, "error": error})
            prompt += f"\n\nYour SQL:\n{draft.sql}\nfailed with: {error}\nFix it."
    if rows is None:
        return {"question": question, "ok": False, "attempts": attempts,
                "answer": "I could not write a working query for that question.", "rows": []}

    shown = rows[:ROWS_FOR_ANSWER]
    answer = llm.structured(
        "answer", ANSWER_SYSTEM,
        f"Question: {question}\nSQL: {attempts[-1]['sql']}\nRows ({len(rows)} total, first {len(shown)}):\n"
        f"{json.dumps(shown, default=str)}",
        Answer,
    )
    return {
        "question": question, "ok": True, "sql": attempts[-1]["sql"], "attempts": attempts,
        "chart": draft.chart, "rows": rows, "answer": answer.answer, "caveats": answer.caveats,
        "fact_check": check_answer(answer.answer, shown),
    }


def main() -> None:
    result = ask(" ".join(sys.argv[1:]) or "Which 5 categories brought the most revenue?")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2, default=str))


if __name__ == "__main__":
    main()
