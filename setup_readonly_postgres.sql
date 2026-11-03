-- ============================================================
-- Read-only login for the HR database (PostgreSQL)
-- Run as the postgres superuser in pgAdmin or psql,
-- connected to the hr_analytics database.
-- Replace CHANGE_ME_STRONG_PASSWORD before running.
-- ============================================================

CREATE ROLE bi_reader LOGIN PASSWORD 'CHANGE_ME_STRONG_PASSWORD';

GRANT CONNECT ON DATABASE hr_analytics TO bi_reader;
GRANT USAGE ON SCHEMA public TO bi_reader;

-- Read-only on every existing table, and on any table created later
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bi_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO bi_reader;

-- Check: this should list only SELECT privileges for bi_reader
SELECT table_name, privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'bi_reader';
