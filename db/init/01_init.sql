-- Runs once when the Postgres container is first created.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS raw;

-- Read-only role used later by the AI text-to-SQL service.
-- It can only SELECT from the analytics marts, never raw data or writes.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ai_readonly') THEN
    CREATE ROLE ai_readonly LOGIN PASSWORD 'ai_readonly';
  END IF;
END $$;
ALTER ROLE ai_readonly SET statement_timeout = '10s';
