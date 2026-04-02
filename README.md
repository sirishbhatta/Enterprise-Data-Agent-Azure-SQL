# Multi-Agent BI Engine 🤖📊

An intelligent business intelligence platform that uses multiple AI models to generate SQL queries, understand data semantics through vector embeddings, and automate report scheduling — all running locally on your machine with support for cloud databases.Running on my local machine with Nvidia GPU. Used my business intelligence experience to quickly build this automatic system in Python, with help from Gemini and Anthropic for faster development and smarter features.

**Status:** Development | **Last Updated:** April 2026

---

## ✨ Key Features

### 🤖 Multi-Model AI Engine
- **Model Cascade:** Automatically escalates from your selected model (local Ollama) → Google Gemini → Claude → DeepSeek if any model fails
- **Semantic Routing:** AI reads your question and picks the right database (HR, Claims, Sales, etc.) automatically
- **Vector Memory:** Questions you liked are embedded (768-dim vectors) and stored. Future similar questions trigger memory hints → faster, more accurate results
- **Federated Queries:** Ask questions spanning multiple databases (e.g., "HR names + Claims total by employee"). The app queries each DB separately and joins in Python

### 📊 Multi-Database Support
- **PostgreSQL** (HR data)
- **SQL Server / Azure SQL** (Healthcare Claims)
- **Oracle** (Sales)
- **FUTURE additions and configurations SQLite, MySQL, DuckDB, Snowflake, BigQuery, Databricks, Redshift** (template configs included)
- All connections configured via YAML — no hardcoding

### 📋 Scheduled Reports
- Save SQL queries as named reports
- Run on demand or via **Windows Task Scheduler** (auto-generated batch file)
- Choose frequency: Daily, Weekly, Monthly, or On Demand per report
- Export to Excel automatically
- Track last run timestamp and output file location

### 🛡️ Safety & Performance
- **Row Limit Guardrail:** All queries capped at 500 rows (chat) / 5,000 rows (reports) unless you specify otherwise — prevents runaway queries from crashing the browser
- **Smart Query Injection:** Dialect-aware row limit injection (TOP for MSSQL, LIMIT for PostgreSQL, ROWNUM for Oracle)
- **Schema Caching:** Auto-generated `schema_cache.json` — the AI learns your table names and columns without hardcoding
- **5-minute result caching:** Duplicate queries within 5 minutes return cached results for speed

### 📥 Export & Download
- **Download as Excel:** Every query result has an in-memory Excel export button (no temp files)
- **Batch Report Runs:** Generate all saved reports in one click
- **Timestamped outputs:** Files saved to `reports_output/` with timestamps so they never overwrite

---

## 🏗️ Architecture

```
sirish_ai/
├── app.py                       # Entry point — Streamlit multi-page router
├── bi_dashboard.py              # AI chat interface + query execution
├── db_connector.py              # Universal database engine (SQLAlchemy)
├── db_registry.yaml             # Database config (credentials via .env)
├── .env                         # Secrets (passwords, API keys)
├── requirements.txt             # Python dependencies
├── pages/
│   ├── 1_Connection_Manager.py # Test & manage database connections
│   └── 2_Scheduled_Reports.py  # Save, run, and schedule reports
├── saved_reports.json           # Auto-created when you save your first report
├── reports_output/              # Auto-created — Excel files go here
├── schema_cache.json            # Auto-generated — table/column knowledge
└── PROJECT_GUIDE.html           # Comprehensive visual guide (open in browser)
```

### How a Question Becomes Results

1. **You ask:** "Show me average salary by department"
2. **Vector Memory Search:** Checks if you've asked something similar before (87% match found)
3. **Memory Hint Injected:** The matched past SQL is given to the AI as a hint
4. **Routing:** AI reads your question, picks the database (HR)
5. **SQL Generation:** AI generates SQL using schema knowledge
6. **Row Limit:** Query capped at 500 rows automatically
7. **Execute:** SQL runs on PostgreSQL
8. **Display:** Results shown + download button + memory hit badge
9. **Feedback:** Thumbs up → embeddings saved for future use

---

## 🚀 Quick Start

### Prerequisites
- **Windows 11** (for Task Scheduler integration) or macOS/Linux (works but without scheduled task generation)
- **Python 3.9+**
- **NVIDIA GPU** (RTX 3060 12GB tested; required for local Ollama models)
- **Ollama** installed and running (`ollama serve` on port 11434)
- **Local Models:** `nomic-embed-text` (embeddings) + one reasoning model (e.g., `gemma3:12b`, `qwen2.5-coder:7b`)

### Installation

1. **Clone the repo**
   ```bash
   git clone https://github.com/yourusername/multi-agent-bi-engine.git
   cd multi-agent-bi-engine
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up secrets**
   - Copy `.env.example` to `.env` (if provided)
   - Add your database passwords and API keys:
     ```
     POSTGRES_PASSWORD=your_postgres_password
     MSSQL_PASSWORD=your_mssql_password
     ORACLE_PASSWORD=your_oracle_password
     AZURE_SQL_PASSWORD=your_azure_password
     GEMINI_API_KEY=your_gemini_key
     ANTHROPIC_API_KEY=your_claude_key
     ```

5. **Configure databases**
   - Open `db_registry.yaml`
   - Update host, username, database names for your environment
   - Keep disabled databases set to `enabled: false`
   - Example:
     ```yaml
     postgres:
       name: HR Analytics
       type: postgresql
       host: localhost
       port: 5432
       database: hr_db
       username: postgres
       password_env: POSTGRES_PASSWORD
       domain: HR
       enabled: true
     ```

6. **Start Ollama** (if using local models)
   ```bash
   ollama serve
   ```
   Then pull models in another terminal:
   ```bash
   ollama pull nomic-embed-text
   ollama pull gemma3:12b
   ```

### Run the App

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501/`

---

## 💬 Usage Examples

### Example 1: Simple Query (Chat)
```
You: "What is the average salary in the Sales department?"

→ AI routes to HR database
→ Generates: SELECT department, AVG(salary) FROM hr_employees WHERE department='Sales' GROUP BY department
→ Results shown + download as Excel
```

### Example 2: Federated Query
```
You: "Show me HR employee names with their total billed claims"

→ AI detects this needs HR + CLAIMS
→ Runs two queries:
   - PostgreSQL: SELECT emp_id, name FROM hr_employees
   - SQL Server: SELECT memberid, SUM(billed_amount) FROM claims GROUP BY memberid
→ Joins on emp_id = memberid in Python
→ Single merged table shown with names + claim totals
```

### Example 3: Memory Hit
```
You previously asked: "Top 3 providers by billing" and gave it 👍

You now ask: "Who are the leading providers by revenue?"

→ Vector search finds 89% match to your previous question
→ Memory hint: "Use this SQL: SELECT TOP 3 ProviderName..."
→ Badge shows "Memory Hit 89.0%"
→ AI reuses the proven query → faster, more accurate
```

### Example 4: Scheduled Report
```
1. Go to Scheduled Reports page
2. Click "➕ Add New Report"
3. Fill in:
   - Name: "Daily Claims Summary"
   - SQL: SELECT ProviderName, COUNT(*) FROM Claims GROUP BY ProviderName
   - Domain: CLAIMS
   - Frequency: Daily
4. Click "💾 Save Report"
5. Click "⚙️ Generate Batch File"
6. Open Windows Task Scheduler → Create Basic Task → set trigger to Daily 9:00 AM
7. Point action to the generated `run_all_reports.bat`
8. Every day at 9:00 AM, all reports run and Excel files are saved to `reports_output/`
```

---

## 🧠 Key Concepts

### Vector Memory (Semantic Search)
Questions are converted to **768-dimensional vectors** using `nomic-embed-text` (running on your GPU). When you ask a new question:
- New question → 768 numbers
- Search SQL Server for closest match using **cosine distance**
- If similarity ≥ 65%, inject the past SQL as a hint
- Threshold: save only if <95% duplicate already exists

**Example similarity:**
- "average salary by department" vs "mean pay grouped by dept" → **94% match** ✅ (memory hit)
- "average salary by department" vs "top providers by billing" → **42% match** ❌ (different topic)

### Row Limit Guardrail
Every query automatically gets a hard cap injected **before** running:
- **SQL Server/Azure:** `SELECT TOP 500` (chat) or `TOP 5000` (reports)
- **PostgreSQL/MySQL:** `LIMIT 500` appended
- **Oracle:** Wrapped in `SELECT * FROM (...) WHERE ROWNUM <= 500`

This prevents accidental `SELECT * FROM 1_000_000_row_table` from crashing the browser.

### Federated Queries
When a question needs data from 2+ databases:
1. AI generates **separate queries** for each database (keyed by domain: `HR_query`, `CLAIMS_query`, etc.)
2. Each query runs in parallel
3. Results joined in Python using `pd.merge()` on a common key (e.g., `emp_id` = `memberid`)
4. Single merged table displayed

**Why not direct SQL JOIN?** SQL can't natively join across different database servers (PostgreSQL on one machine, SQL Server on another).

### Model Cascade
If your selected model fails (syntax error, timeout, etc.):
```
[Your selected model]
    ↓ (fails)
gemini-2.5-flash
    ↓ (fails)
gemini-3.1-flash-lite-preview
    ↓ (fails)
claude-sonnet-4-6
    ↓ (succeeds)
Result shown with badge "After 2 retries"
```

---

## 📊 AI Models & Costs

| Model | Provider | Tier | Cost | Runs On | Best For |
|-------|----------|------|------|---------|----------|
| `claude-opus-4-6` | Anthropic | Elite | 💰💰💰 | Cloud API | Complex, multi-step reasoning |
| `claude-sonnet-4-6` | Anthropic | Elite | 💰💰 | Cloud API | Best quality/speed/cost balance |
| `gemini-2.5-flash` | Google | Fast | 💰 | Cloud API | Fallback workhorse |
| `gemma3:12b` | Google/Ollama | Local | 🆓 | Your GPU | Offline use, general reasoning |
| `qwen2.5-coder:7b` | Alibaba/Ollama | Local | 🆓 | Your GPU | SQL/code generation |
| `deepseek-r1:8b` | DeepSeek/Ollama | Local | 🆓 | Your GPU | Step-by-step reasoning |

**Your setup:** Runs local models (Ollama) first → falls back to cloud APIs if needed.

---

## 🔧 Configuration

### Adding a New Database
1. Open `db_registry.yaml`
2. Add a new entry:
   ```yaml
   my_warehouse:
     name: Data Warehouse
     type: snowflake  # or redshift, bigquery, etc.
     host: my-account.us-east-1.snowflakecomputing.com
     username: sirish
     password_env: SNOWFLAKE_PASSWORD
     database: analytics
     domain: WAREHOUSE
     enabled: true
     description: Cloud data warehouse
   ```
3. Add the password to `.env`: `SNOWFLAKE_PASSWORD=...`
4. Restart the app — new database appears in Connection Manager and Scheduled Reports

### Adding a Federated Pair
Edit `bi_dashboard.py`:
```python
FEDERATED_JOIN_CONFIGS = {
    frozenset(["HR", "CLAIMS"]): {
        "left": "HR", "right": "CLAIMS",
        "left_key": "emp_id", "right_key": "memberid",
        "hint": "JOIN KEY: hr_employees.emp_id (INT) ↔ Claims.MemberID (VARCHAR)"
    },
    frozenset(["WAREHOUSE", "CLAIMS"]): {  # ← new pair
        "left": "WAREHOUSE", "right": "CLAIMS",
        "left_key": "customer_id", "right_key": "customer_id",
        "hint": "JOIN KEY: customer_id (both INT)"
    },
}
```

### Changing Row Limits
Edit `bi_dashboard.py`:
```python
MAX_ROWS = 500  # Change this number
```

Or per-report in Scheduled Reports form.

---

## 📚 Documentation

- **Visual Guide:** Open `PROJECT_GUIDE.html` in your browser for diagrams, flow paths, and detailed explanations
- **Code Comments:** Every file has a header explaining its purpose; functions have docstrings
- **This README:** High-level overview and quick reference

---

## 🧪 Testing

### Test a Database Connection
1. Go to **Settings → Connection Manager**
2. Click "Test Connection" next to any database
3. See latency, table count, and sample data

### Test a Report
1. Go to **Scheduled Reports**
2. Click "▶️ Run Now" on any saved report
3. Check `reports_output/` for the Excel file
4. Click "📥 Download" to get it

### Test Vector Memory
1. Ask a question in the chat (e.g., "average salary by department")
2. Give it 👍 feedback
3. Ask a similar question (e.g., "mean pay per dept")
4. You should see "Memory Hit" badge with a similarity %

---

## 🚨 Troubleshooting

### "Name, SQL, and Domain are required" when saving a report
- **Fixed in latest version** with `st.form()` wrapping. Make sure you're on the latest code.

### Vector memory searches are slow
- Ollama embedding might be warming up. First embedding takes 5-10s; subsequent ones are fast.
- Check that `nomic-embed-text` is downloaded: `ollama list`

### Model cascade exhausted (all models failed)
- Check your API keys in `.env` (Gemini, Claude)
- Check Ollama is running (`ollama serve`)
- Check your question is unambiguous and schema matches

### Database connection timeout
- Verify host/port are correct in `db_registry.yaml`
- Verify credentials in `.env` are correct
- Test with `Connection Manager` page
- Check firewall/VPN if using remote databases

### Excel export fails
- Ensure `openpyxl` is installed: `pip install openpyxl`
- Check disk space in `reports_output/`

---

## 📈 Performance Tips

1. **Cache schema:** The app auto-generates `schema_cache.json` on first run. This is the AI's "knowledge" of your tables — subsequent queries are faster.
2. **Use memory hints:** Thumbs-up on queries you like. The memory bank grows over time → more accurate results.
3. **Batch reports:** Running 10 reports at once via "Run All Reports" is faster than 10 individual runs (parallelism).
4. **Local models first:** If you're offline or want free inference, local Ollama models are faster than cloud API round-trips.

---

## 📄 License

**Proprietary - All Rights Reserved**

This project and all associated code, documentation, and materials are the exclusive property of Sirish Bhatta. Unauthorized copying, modification, distribution, or use of this software is prohibited. For inquiries regarding licensing or usage rights, please contact the owner.

---

## 🙋 FAQ

**Q: Can I use this without Ollama?**
A: Yes, but you'll rely entirely on cloud models (Gemini, Claude). Set `OLLAMA_HOST=""` or disable local models in `bi_dashboard.py`.

**Q: Can I run this on macOS/Linux?**
A: Yes, but Task Scheduler generation is Windows-only. You can manually write cron/launchd jobs instead.

**Q: How much does it cost to run?**
A: If you use only local Ollama models, it's **free** (just electricity). Cloud API costs depend on usage — usually $0.01–$0.10 per query.

**Q: What if I want to add a different embedding model?**
A: Edit `bi_dashboard.py` → `check_vector_memory()` and change `model="nomic-embed-text"` to any Ollama model that supports embeddings.

**Q: Can I use this commercially?**
A: This is proprietary software. All rights are reserved. Unauthorized use is prohibited.

---

## 📞 Support

For questions, issues, or feedback:
- Check `PROJECT_GUIDE.html` first (visual explanations)
- Review code comments (designed for learning)
- Open an issue on GitHub with details

---

**Built with ❤️ using Python, Streamlit, SQLAlchemy, and AI models**

*Last updated: April 2026*
