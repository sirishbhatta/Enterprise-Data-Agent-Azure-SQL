# CLAUDE.md — handoff for Claude Code

Read this first. It was written from a claude.ai chat titled "Enterprise Data Agent SQL setup"
(https://claude.ai/chat/bf6983f1-3c9c-4997-9e0c-b049cd071d4d), so the history lives there
if a detail is missing. Keep this file current when the state changes.

## Who you're helping
- Sirish. Senior data/BI professional (SQL, dimensional modeling, ETL). Beginner in Python.
- Explain Python using SQL analogies where they fit (a dict is like a lookup table, a
  for loop over rows is like a cursor, a DataFrame is like a result set).
- Plain, direct language. Honest feedback over praise. Don't pad answers.

## What the project is
A Streamlit multi-agent BI app (`bi_dashboard.py`, Connection Manager page). Users ask
plain-English questions; a local Ollama model writes SQL; the app runs it read-only.
Runs on localhost:8503 (also 8501/8502) and sirish.ngrok.app.

Three databases, registered in `db_registry.yaml`:
- HR: PostgreSQL, database `hr_analytics`, table `public.hr_employees`. Login `bi_reader`,
  password from env `PG_PASSWORD`.
- Claims: SQL Server, database `HealthcareClaims`, table `dbo.Claims`. Login from env
  `SQL_USER` / `SQL_PASSWORD`, host from env `SQL_SERVER_NAME`. Default instance `DOG`.
- Sales: Oracle XE, PDB `XEPDB1`, schema `BI_SALES` (set in the registry, so the scrape
  doesn't use `BI_READER` as owner). Login `BI_READER`, password from env `ORACLE_PASSWORD`.

## Model
- Default: `qwen2.5-coder:14b` on an RTX 3060 12 GB (about 10 GB loaded, 100% GPU, 8192 context).
- `qwen2.5-coder:7b` is about 5.1 GB and is the fallback.
- The 14B model passes the full 100-question set on the dev and held-out splits.

## Schema cache
- `schema_cache.json` (project root, gitignored) is what the model sees.
- Refresh it with "Discover All Schemas" on the Connection Manager, only when all three
  connections show green. A failed scrape no longer overwrites the cache (see 8bd091c).
- A corrupt cache is moved to `schema_cache.corrupt.json` on load.

## Testing
- Questions: `tests/build_questions.py` generates 100 questions into `tests/questions.yaml`.
  It asserts the count is 100. Every 4th question is held out. Regenerate it only on purpose.
- Reference values: `tests/reference_sql.py` maps question text to a hand-written reference
  query. `run_evals.py` checks the model's values against it. Only three HR questions
  have entries so far (count, max salary, average salary). Add more only after checking
  the reference SQL by hand.
- Run:
  ```
  python tests\run_evals.py --models qwen2.5-coder:14b              # all questions
  python tests\run_evals.py --models qwen2.5-coder:14b --held-out   # held-out only
  python tests\run_evals.py --only hr_001 --models qwen2.5-coder:14b
  python tests\summarize.py
  ```
- Results append to `logs/eval_results.jsonl` (gitignored). Delete it before a clean run.
- Known slow queries: `claims_036` (330 s) and `claims_096` (181 s) on SQL Server.
  Check their generated SQL in the log before blaming the connection.
- The SAWarning about SQL Server version `17.0.1145.4` is harmless. Ignore it.

## Git
- Repo: `sirishbhatta/Enterprise-Data-Agent-Azure-SQL`, branch `main`.
- Recent commits, all pushed to origin/main: `6641db1` reference check, `8bd091c` schema
  cache protection, `928000d` eval runner split. Verify with `git log origin/main -3`.
- Repo stores LF line endings. Windows git warns about LF to CRLF. The warning is harmless.
- Commits need the attribution trailers:
  ```
  Co-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01PuSamrRTZUZeKyCW5uTzKj
  ```
- Never stage or commit: `.env`, `ngrok.yml`, `setup_readonly_*.sql` (they contain real
  passwords and are modified locally), `rag_ai_explainer.html`, `schema_cache.json`,
  `logs/`.
- Ask before committing or pushing. Sirish reviews the diff and says "commit" first.

## Security rules (important)
- Never print, paste, or commit passwords, tokens, or API keys. Refer to env var names only.
- Oracle locks an account after repeated failed logins (ORA-28000). Stop after one failure
  and check the password instead of retrying in a loop. To unlock, connect as a DBA with
  `ALTER SESSION SET CONTAINER = XEPDB1;` before `ALTER USER`.
- Passwords that appeared in earlier screenshots need rotation. Oracle is done. Postgres and
  SQL Server are not confirmed yet: check the old values no longer log in.
- Stale PowerShell env vars override `.env`. Clear them with `Remove-Item env:NAME`.

## Open items (in order)
1. Explicit SQL Server host: `db_connector.py` defaults to `localhost` (line ~92). Shared
   Memory timed out. Set `SQL_SERVER_NAME` to `tcp:DOG,1433` or make the host required.
2. Slow Claims queries: inspect the generated SQL for `claims_036` and `claims_096`.
3. Finish password rotation for Postgres and SQL Server.
4. Confirm `git ls-files ngrok.yml` is empty on the PC (it wasn't in the repo folder).
5. Grow the reference set to some Claims and Sales questions.
6. Later: DuckDB for eval analytics (load `logs/eval_results.jsonl`), and a query memory
   that stores successful question and SQL pairs and feeds similar ones into the prompt.
   `ai_query_cache` already exists in HealthcareClaims; check it first.

## Known history (so you don't repeat it)
- Stale cache wiped HR and Oracle sections. Model then wrote `FROM employees` instead of
  `hr_employees`. Fixed with the copy-names-exactly rule and cache protection.
- `--only` takes one ID per run. Run several by looping in PowerShell.
- Changing the question set changes `build_questions.py`'s count. Keep it at 100 or update
  the assertion on purpose.
