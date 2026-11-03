-- ============================================================
-- Read-only login for the Claims database (SQL Server)
-- Run in SSMS as an administrator (for example, sa or your Windows login).
-- Replace CHANGE_ME_STRONG_PASSWORD before running.
-- ============================================================

USE master;
CREATE LOGIN bi_reader WITH PASSWORD = 'CHANGE_ME_STRONG_PASSWORD', CHECK_POLICY = ON;

USE HealthcareClaims;
CREATE USER bi_reader FOR LOGIN bi_reader;

-- Read everything in the database
ALTER ROLE db_datareader ADD MEMBER bi_reader;

-- The app saves good answers as "memories" in ai_query_cache, so it needs INSERT there.
-- Nothing else: no UPDATE, DELETE or DDL.
GRANT INSERT ON OBJECT::dbo.ai_query_cache TO bi_reader;

-- Check
SELECT dp.name AS principal, r.name AS role
FROM sys.database_role_members m
JOIN sys.database_principals r  ON m.role_principal_id = r.principal_id
JOIN sys.database_principals dp ON m.member_principal_id = dp.principal_id
WHERE dp.name = 'bi_reader';
