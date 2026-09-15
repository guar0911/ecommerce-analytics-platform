-- Run this in the Supabase SQL Editor (or via psql as the project owner).
-- Closes the "table publicly accessible" security warning, WITHOUT breaking
-- the LLM+RAG chat, which needs the llm_readonly role to keep working.

-- 1. Enable RLS on every table in both schemas.
--    Once enabled, only the table owner (and superusers) can read/write
--    without an explicit policy -- everyone else, including Supabase's
--    public Data API (anon/authenticated roles), is denied by default.
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT schemaname, tablename
        FROM pg_tables
        WHERE schemaname IN ('public', 'analytics')
    LOOP
        EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY;', r.schemaname, r.tablename);
    END LOOP;
END $$;

-- 2. Explicitly allow llm_readonly to SELECT from the analytics schema --
--    this is the role your public LLM+RAG chat actually uses.
--    Intentionally NOT granting anything to anon/authenticated: that's what
--    keeps Supabase's public Data API locked out, which is the fix Supabase
--    is asking for.
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'analytics'
    LOOP
        EXECUTE format(
            'CREATE POLICY llm_readonly_select ON analytics.%I FOR SELECT TO llm_readonly USING (true);',
            r.tablename
        );
    END LOOP;
END $$;