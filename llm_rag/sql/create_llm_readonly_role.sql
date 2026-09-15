-- Read-only role for the LLM + RAG system.
-- Run this against BOTH your local Postgres and Supabase.
-- Never let the LLM's generated SQL run under an admin/owner role.

CREATE ROLE llm_readonly WITH LOGIN PASSWORD 'CHANGE_THIS_PASSWORD';

-- Adjust the database name: 'olist_oltp' locally, 'postgres' on Supabase
GRANT CONNECT ON DATABASE olist_oltp TO llm_readonly;

GRANT USAGE ON SCHEMA analytics TO llm_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO llm_readonly;

-- Make sure future tables created by dbt (e.g. after adding new models)
-- are automatically readable too, without having to re-grant manually.
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO llm_readonly;

-- Extra safety net: cap how long any single query from this role can run,
-- so a runaway/expensive generated query can't hang the connection forever.
ALTER ROLE llm_readonly SET statement_timeout = '5s';