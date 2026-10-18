-- Tables used by the GenAI layer. Safe to re-run (also applied by `python -m ecom.ai.setup`).
CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS ai;

-- Every generated insight, with the facts and SQL it was grounded on and the fact-check result.
CREATE TABLE IF NOT EXISTS ai.ai_insights (
    id              BIGSERIAL PRIMARY KEY,
    kind            TEXT NOT NULL,              -- executive_summary | anomaly | answer
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    title           TEXT NOT NULL,
    body            JSONB NOT NULL,             -- structured output from the model
    facts           JSONB NOT NULL,             -- the numbers the model was given, with source SQL
    fact_check      JSONB NOT NULL,             -- verified / unverified numbers
    passed          BOOLEAN NOT NULL,
    model           TEXT NOT NULL
);

-- One row per model call: tokens, latency and cost, for the LLMOps view.
CREATE TABLE IF NOT EXISTS ai.llm_calls (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    purpose         TEXT NOT NULL,
    model           TEXT NOT NULL,
    input_tokens    INT,
    output_tokens   INT,
    latency_ms      INT,
    cost_usd        NUMERIC(10, 6),
    stop_reason     TEXT
);

-- Retrieval store for text-to-SQL: table docs, KPI definitions and worked examples.
CREATE TABLE IF NOT EXISTS ai.knowledge (
    id              TEXT PRIMARY KEY,
    kind            TEXT NOT NULL,              -- table | metric | example
    content         TEXT NOT NULL,
    embedding       vector(384) NOT NULL
);
