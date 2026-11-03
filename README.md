# Multi-Agent BI Engine

Ask questions about your data in plain English and get answers back as tables. The app picks the right database, has an AI model write the SQL, runs it, and fixes its own mistakes when the SQL fails.

I built this to see how far a BI workflow I know well (SQL, dimensional data, healthcare claims) could be automated with a mix of local and cloud AI models. It runs on my own Windows machine with an NVIDIA RTX 3060 (12 GB) and is shared through ngrok behind a Google sign-in.

**Status:** personal project, actively maintained · **Last updated:** November 2026

---

## What it does

- **Routes each question to the right database.** A "supervisor" model reads the question and picks HR (PostgreSQL), Claims (SQL Server) or Sales (Oracle). Questions that need two databases are split into one query per database and joined in Python.
- **Writes SQL in the right dialect.** The model is told which database it's writing for. As a safety net, row limits are translated automatically (`LIMIT` ↔ `TOP` ↔ `FETCH FIRST`) because models mix these up often.
- **Fixes its own SQL.** If a query fails, the model is shown the database error and gets one try to correct it before the app moves on to the next model.
- **Falls back across models.** Free models are tried first. A paid model is only used if everything else fails.
- **Remembers good answers.** Questions you give a thumbs-up are stored as embeddings in SQL Server. Similar questions later reuse the proven SQL as a hint.
- **Read-only by design.** Only `SELECT`/`WITH` queries run, and write keywords (`INSERT`, `DELETE`, `DROP`, etc.) are blocked anywhere in the query. Every result is capped at 500 rows.
- **Scheduled reports.** Save a query, run it on demand or on a schedule through Windows Task Scheduler, and get an Excel file.

---

## Databases

| Domain | Database | Contents |
|---|---|---|
| HR | PostgreSQL (local) | Employees, departments, salaries, hire dates |
| CLAIMS | SQL Server 2025 Developer (local) | Healthcare claims: providers, billed/paid amounts, approvals, denials |
| SALES | Oracle 21c XE (local) | CRM: customers, orders, products, sales reps, regions |

Connections live in `db_registry.yaml`, passwords in `.env`. Templates for MySQL, Snowflake, BigQuery, Databricks, Redshift, DuckDB and SQLite are in the registry, turned off. Setup scripts for the three sample databases are included (`*_setup.sql`).

---

## AI models

Tried in this order. The model you pick in the sidebar goes first.

| Order | Model | Where it runs | Cost |
|---|---|---|---|
| 1 | `gemini-3.5-flash-lite` | Google API | Free tier |
| 2 | `gemini-3.5-flash` | Google API | Free tier |
| 3 | `qwen2.5-coder:14b` | Local GPU (Ollama) | Free |
| 4 | `gemma4:12b` | Local GPU (Ollama) | Free |
| 5 | `qwen2.5-coder:7b` | Local GPU (Ollama) | Free |
| 6 | `claude-haiku-5-5` | Anthropic API | Paid (cheap backup) |

Also available in the dropdown: `nemotron-3.5-bolt:e4b` (local, small and fast) and `gemma4:31b-cloud` (Ollama Cloud free plan). Embeddings use `nomic-embed-text` locally.

Model names change often. If one is retired, its error shows up under **View SQL Execution Details** and the next model takes over.

---

## How a question flows

```
Question
  → check memory for a similar past question (vector search in SQL Server)
  → supervisor picks the database (HR / CLAIMS / SALES / FEDERATED)
  → model writes SQL for that database's dialect
  → safety checks: read-only, dialect fix, 500-row cap
  → run it
      ✔ success → show table, Excel download, thumbs up/down
      ✘ error   → show the error to the same model, let it fix the SQL once
                → still failing? try the next model
```

---

## Running it

**You'll need:** Windows 11, Python 3.9+, Ollama, the three databases above (or any you configure), and API keys for Gemini and (optionally) Anthropic.

```powershell
git clone https://github.com/sirishbhatta/Enterprise-Data-Agent-Azure-SQL.git
cd Enterprise-Data-Agent-Azure-SQL
pip install -r requirements.txt

ollama pull nomic-embed-text
ollama pull qwen2.5-coder:14b
ollama pull gemma4:12b
ollama pull qwen2.5-coder:7b
ollama pull nemotron-3.5-bolt:e4b
```

Create a `.env` file:
```
PG_PASSWORD=...
SQL_SERVER_NAME=localhost
SQL_USER=...
SQL_PASSWORD=...
ORACLE_PASSWORD=...
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=...
```

Run locally:
```powershell
streamlit run app.py
```

Then open **Connection Manager** and refresh the schemas, so the AI knows your tables.

### Sharing it (ngrok + Google sign-in)

`start_dashboard.bat` starts Streamlit on port 8502 and an ngrok endpoint in front of it. The ngrok config adds a Google sign-in using a Traffic Policy, so no login code lives in the app:

```yaml
version: "3"
agent:
  authtoken: <your token>
endpoints:
  - name: bi-app
    url: https://<your-domain>.ngrok.app
    upstream:
      url: 8502
    traffic_policy:
      on_http_request:
        - actions:
            - type: oauth
              config:
                provider: google
```

If ngrok was installed from the Microsoft Store, it reads a private copy of `ngrok.yml` under `%LOCALAPPDATA%\Packages\ngrok...\LocalCache`. The launcher copies your real config over it each time it starts.

---

## Project layout

```
app.py                         Entry point and page navigation
bi_dashboard.py                Chat page: routing, SQL generation, self-correction, memory
db_connector.py                Database engine: connections, schema discovery, safety checks
db_registry.yaml               Which databases exist and how to reach them
pages/1_Connection_Manager.py  Test connections, refresh schemas
pages/2_Scheduled_Reports.py   Save, run and schedule reports to Excel
start_dashboard.bat            Starts Streamlit + ngrok
*_setup.sql                    Sample data for HR, Claims and Sales
```

---

## Troubleshooting

- **Every model fails with the same database error:** it's the connection, not the models. Check Connection Manager.
- **SQL Server won't start (error 17051):** the Evaluation edition expired. Upgrade it in place to the free Developer edition (Installation Center → Maintenance → Edition Upgrade). Your databases are kept.
- **Oracle "invalid username/password" with the right password:** connect to the service name `XEPDB1`, not SID `xe`. The app's user lives in the pluggable database.
- **First answer after switching local models is slow:** the model is loading onto the GPU. A 12 GB card holds one of the larger models at a time.
- **ngrok "authtoken is invalid":** run `ngrok config add-authtoken <token>` with the current token from the dashboard.

---

## What's next

- Read-only database logins for each database (the app currently relies on its own keyword guard)
- A test set of known-good questions to score each model's accuracy
- Retiring the Azure SQL name from the repo (the Azure database was shut down; claims now run on local SQL Server)

---

## License

**Proprietary - All Rights Reserved.** This code and its documentation belong to Sirish Bhatta. Please contact the owner about any use.
