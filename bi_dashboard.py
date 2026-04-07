"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  bi_dashboard.py — THE MAIN AI AGENT PAGE                                    ║
║  ─────────────────────────────────────────────────────────────────────────── ║
║  This is the heart of the application — the chat interface where users ask   ║
║  questions in plain English and get data back from their databases.           ║
║                                                                              ║
║  How a user query flows through this file (step by step):                    ║
║                                                                              ║
║  User types a question                                                       ║
║       │                                                                      ║
║       ▼                                                                      ║
║  [1] rewrite_query()      — If it's a follow-up ("what about Sales?"),       ║
║                              rewrite it as a complete standalone question     ║
║       │                                                                      ║
║       ▼                                                                      ║
║  [2] check_vector_memory()— Search SQL Server for a past similar question.   ║
║                              If found (≥65% match), give the AI a hint.      ║
║       │                                                                      ║
║       ▼                                                                      ║
║  [3] supervisor_routing() — Ask the AI: which database does this belong to?  ║
║                              Returns: HR, CLAIMS, AZURE_CLAIMS, or FEDERATED ║
║       │                                                                      ║
║       ▼                                                                      ║
║  [4] agent_execution()    — Ask the AI to write SQL for that database.       ║
║                              If it fails, automatically try the next model.  ║
║       │                                                                      ║
║       ▼                                                                      ║
║  [5] get_db_data()        — Run the SQL on the real database via             ║
║                              db_connector.py. Return a DataFrame.            ║
║       │                                                                      ║
║       ▼                                                                      ║
║  [6] Display results + get thumbs feedback → save_vector_memory()           ║
║                                                                              ║
║  Key concepts for learning:                                                  ║
║   - "Session state" in Streamlit = memory between user interactions          ║
║   - @st.cache_data = cache expensive DB results for 5 minutes                ║
║   - The "cascade" model list = automatic failover if one AI is unavailable  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import pandas as pd
import psycopg2   # PostgreSQL driver — used ONLY for the vector memory functions below
import pyodbc     # SQL Server driver — used ONLY for the vector memory functions below
import os
import time
import json
import ollama     # Python client for your local Ollama server (runs on your GPU)
import re         # Regular expressions — used to extract JSON from AI responses
import sqlparse   # Pretty-prints SQL queries in the UI (adds indentation, uppercase keywords)
import warnings
import sys
from io import BytesIO                    # Used to build Excel files in memory for download
from datetime import datetime             # Used to timestamp downloaded filenames
from pathlib import Path
from anthropic import Anthropic           # Claude API client
from google import genai                  # Gemini API client
from google.genai import types
from dotenv import load_dotenv            # Reads secrets from your .env file

# Allow import of db_connector from parent directory
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
import db_connector as dbc

# --- 0. SUPPRESS WARNINGS ---
# SQLAlchemy warns when pandas uses it in a certain way — we know it's fine, so silence it.
warnings.filterwarnings('ignore', message='.*pandas only supports SQLAlchemy connectable.*')

# --- 1. INITIALIZATION & VECTOR MEMORY SETUP ---
# load_dotenv() reads your .env file and puts all variables into os.environ.
# After this call, os.getenv("ANTHROPIC_API_KEY") returns the value from .env.
load_dotenv()  # Automatically finds .env in the project folder — no hardcoded path needed

# os.getenv("KEY") reads an environment variable. The second argument is the
# DEFAULT value if the variable isn't found (e.g., "DOG" for SQL_SERVER_NAME).
SQL_SERVER_NAME = os.getenv("SQL_SERVER_NAME", "DOG")
SQL_USER        = os.getenv("SQL_USER")
SQL_PASSWORD    = os.getenv("SQL_PASSWORD")
PG_PASSWORD     = os.getenv("PG_PASSWORD")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY")
MINIMAX_API_KEY   = os.getenv("MINIMAX_API_KEY")

def get_sql_connection():
    """Helper to get a SQL Server connection for the Vector Engine."""
    drivers = pyodbc.drivers()
    sql_drivers = [d for d in drivers if 'SQL Server' in d]
    odbc_drivers = [d for d in sql_drivers if 'ODBC Driver' in d]
    driver_name = odbc_drivers[-1] if odbc_drivers else (sql_drivers[-1] if sql_drivers else 'SQL Server')
    
    conn_str = f"DRIVER={{{driver_name}}};SERVER={SQL_SERVER_NAME};DATABASE=HealthcareClaims;UID={SQL_USER};PWD={SQL_PASSWORD};Timeout=15;"
    if driver_name != 'SQL Server':
        conn_str += "TrustServerCertificate=yes;"
    return pyodbc.connect(conn_str)

def get_vector_memory_count():
    """Counts how many memories are stored in the SQL Server vector table."""
    try:
        conn = get_sql_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ai_query_cache;")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"Memory Count Error: {e}")
        return 0

def save_vector_memory(query, sql, domain, agent, is_positive):
    """Saves user feedback to the SQL Server Vector Memory Bank.
    Skips saving if a near-duplicate (>=95% similarity) already exists.
    """
    if not is_positive:
        return

    try:
        # Deduplication check — skip if we already have a very similar entry
        existing, score = check_vector_memory(query, threshold=95.0)
        if existing:
            print(f"[Vector Memory] Skipping duplicate — {score:.1f}% match already cached.")
            return

        vector_data = ollama.embeddings(model="nomic-embed-text", prompt=query)["embedding"]
        vector_string = json.dumps(vector_data)

        conn = get_sql_connection()
        cursor = conn.cursor()
        insert_query = """
            INSERT INTO ai_query_cache (user_question, sql_code, question_embedding)
            VALUES (?, ?, CAST(CAST(? AS NVARCHAR(MAX)) AS VECTOR(768)))
        """
        cursor.execute(insert_query, query, sql, vector_string)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Failed to save vector memory: {e}")

def check_vector_memory(user_question, threshold=65.0):
    """Searches SQL Server 2025 using VECTOR_DISTANCE for a semantic match."""
    try:
        vector_data = ollama.embeddings(model="nomic-embed-text", prompt=user_question)["embedding"]
        vector_string = json.dumps(vector_data)

        conn = get_sql_connection()
        cursor = conn.cursor()
        search_query = """
            SELECT TOP 1 
                user_question, 
                sql_code,
                VECTOR_DISTANCE('cosine', question_embedding, CAST(CAST(? AS NVARCHAR(MAX)) AS VECTOR(768))) AS distance_score
            FROM ai_query_cache
            ORDER BY distance_score ASC;
        """
        cursor.execute(search_query, vector_string)
        result = cursor.fetchone()
        conn.close()

        if result:
            cached_question = result[0]
            cached_sql = result[1]
            sql_distance = result[2]
            similarity_score = (1 - sql_distance) * 100
            
            if similarity_score >= threshold:
                return {"query": cached_question, "sql": cached_sql}, similarity_score
                
    except Exception as e:
        print(f"Vector Search Error: {e}")
        
    return None, 0.0

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_query" not in st.session_state:
    st.session_state.user_query = None

anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# --- 2. PAGE CONFIGURATION & STYLING ---
# st.set_page_config is handled by app.py (the navigation entry point)

st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,600,0,0" rel="stylesheet" />
<style>
.stApp { background-color: #f8f9fa; } 
[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #dadce0; box-shadow: 2px 0 12px rgba(0, 0, 0, 0.05); }
.mat-icon { vertical-align: -5px; margin-right: 6px; font-size: 1.3em; }
.sidebar-header { background: linear-gradient(135deg, #e8f0fe 0%, #ffffff 100%); border: 1px solid #d2e3fc; border-left: 6px solid #1a73e8; padding: 14px 16px; margin-top: 28px; margin-bottom: 16px; border-radius: 10px; font-weight: 700; color: #174ea6; font-size: 1rem; box-shadow: 0 2px 4px rgba(26, 115, 232, 0.05); }
.stButton>button { border-radius: 20px; min-height: 44px; font-weight: 600; border: 1px solid #dadce0; color: #3c4043; transition: all 0.2s ease; }
.stButton>button:hover { border-color: #1a73e8; color: #1a73e8; background-color: #f8f9fa; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
[data-testid="stMetric"] { background-color: #ffffff; padding: 16px 20px; border-radius: 16px; border: 1px solid #dadce0; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.03); }
.api-info { background-color: #e8f0fe; border: 1px solid #d2e3fc; color: #174ea6; padding: 16px; border-radius: 12px; font-size: 0.85rem; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
.quota-warning { background-color: #fce8e6; border: 1px solid #fad2cf; color: #b31412; padding: 16px; border-radius: 12px; font-size: 0.85rem; margin-bottom: 15px; }
.stChatMessage[data-testid="stChatMessage-assistant"] { background-color: #ffffff; border: 1px solid #dadce0; border-radius: 20px; padding: 1.5rem; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04); margin-bottom: 1rem; }
.stChatMessage[data-testid="stChatMessage-user"] { background-color: #e8f0fe; border: 1px solid #d2e3fc; color: #174ea6; border-radius: 20px; padding: 1.5rem; margin-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

# --- 3. SCHEMAS — loaded dynamically from schema_cache.json (scraped via Connection Manager) ---
# The schema tells the AI *exactly* what tables and columns exist in each database.
# Without this, the AI would hallucinate column names. Always click "Discover Schema"
# in Connection Manager after adding a new database or changing table structures.
# Falls back to hardcoded strings if the cache hasn't been populated yet.
_dynamic_schema = dbc.get_schema_for_llm()
_SCHEMA_FALLBACK = (
    "[HR | HR Analytics | POSTGRESQL]\n"
    "  Table hr_employees: emp_id* (INTEGER), name (VARCHAR), department (VARCHAR), salary (DECIMAL), hire_date (DATE)\n\n"
    "[CLAIMS | Healthcare Claims | MSSQL]\n"
    "  Table Claims: ClaimID* (INTEGER), MemberID (VARCHAR), ServiceDate (DATE), ProviderName (VARCHAR), "
    "DiagnosisCode (VARCHAR), ProcedureCode (VARCHAR), BilledAmount (DECIMAL), PaidAmount (DECIMAL), ClaimStatus (VARCHAR)"
)
ACTIVE_SCHEMA = _dynamic_schema if "Table" in _dynamic_schema else _SCHEMA_FALLBACK

# Build domain list dynamically from the registry for the routing supervisor
DOMAIN_MAP = dbc.get_domain_map()          # e.g. {"HR": "hr", "CLAIMS": "claims"}
ACTIVE_DOMAINS = list(DOMAIN_MAP.keys())   # e.g. ["HR", "CLAIMS"]

# ── Row limit cap ────────────────────────────────────────────────────────────
# Injected into every query that doesn't already have a TOP/LIMIT clause.
# Prevents "SELECT * FROM Claims" from returning 500k rows and crashing things.
# Change this number if you need more rows for a specific use case.
MAX_ROWS = 500

# ── FEDERATED join configurations ────────────────────────────────────────────
# When the AI routes to FEDERATED, two databases are queried separately and
# then joined in Python using pandas.merge(). This dict defines the join keys
# for every known pair of databases.
#
# How to add a new pair: add an entry with frozenset(["DOMAIN_A", "DOMAIN_B"])
# as the key and specify which columns to join on (left_key / right_key).
# Both key values will be cast to string before merging to avoid type mismatches.
FEDERATED_JOIN_CONFIGS = {
    frozenset(["HR", "CLAIMS"]): {
        "left":      "HR",
        "right":     "CLAIMS",
        "left_key":  "emp_id",
        "right_key": "memberid",
        "hint": (
            "JOIN KEY: hr_employees.emp_id (INT) = Claims.MemberID (VARCHAR). "
            "Cast both to string in the merge step. MemberID MUST be quoted in SQL."
        ),
    },
    frozenset(["HR", "AZURE_CLAIMS"]): {
        # Azure SQL has the same Claims table structure as the local SQL Server Claims DB.
        # The join key is identical — emp_id (HR) maps to MemberID (Azure Claims).
        "left":      "HR",
        "right":     "AZURE_CLAIMS",
        "left_key":  "emp_id",
        "right_key": "memberid",
        "hint": (
            "JOIN KEY: hr_employees.emp_id (INT) = Azure Claims.MemberID (VARCHAR). "
            "Cast both to string in the merge step. MemberID MUST be quoted in SQL."
        ),
    },
}

# --- 4. UNIFIED AI ROUTER ---
# This single function handles ALL AI providers: Gemini, Claude, and Ollama.
# By routing through one function, the rest of the code doesn't need to know
# which AI is being used — it just calls generate_ai_response() and gets text back.
def generate_ai_response(model_name, system_prompt, user_prompt):
    """
    Send a prompt to any supported AI model and return the text response.

    - system_prompt: Background instructions (e.g. "You are a SQL expert")
    - user_prompt:   The actual question or task
    - Returns:       A string — either the AI's answer or a JSON error message
    """
    if "gemini" in model_name.lower():
        if not gemini_client: return '{"error": "GEMINI_API_KEY missing"}'
        try:
            target_id = {"gemini-2.5-flash": "gemini-2.5-flash", "gemini-2.5-flash-lite": "gemini-2.5-flash-lite", "gemini-3.1-flash-lite-preview": "gemini-3.1-flash-lite-preview"}.get(model_name, "gemini-2.5-flash")
            res = gemini_client.models.generate_content(model=target_id, contents=user_prompt, config=types.GenerateContentConfig(system_instruction=system_prompt))
            return res.text if res.text else '{"error": "No response text"}'
        except Exception as e: return f'{{"error": "Gemini Error: {str(e)}"}}'

    elif any(n in model_name.lower() for n in ["claude", "sonnet", "opus", "haiku"]):
        if not anthropic_client: return '{"error": "ANTHROPIC_API_KEY missing"}'
        try:
            target_id = {"claude-opus-4-6": "claude-opus-4-6", "claude-sonnet-4-6": "claude-sonnet-4-6", "claude-haiku-4-5": "claude-haiku-4-5-20251001", "claude-3-5-sonnet-20241022": "claude-3-5-sonnet-20241022"}.get(model_name, model_name)
            res = anthropic_client.messages.create(model=target_id, max_tokens=2048, system=system_prompt, messages=[{"role": "user", "content": user_prompt}])
            return res.content[0].text
        except Exception as e: return f'{{"error": "Claude Error: {str(e)}"}}'
            
    else:
        try:
            res = ollama.generate(model=model_name, system=system_prompt, prompt=user_prompt)
            return res['response']
        except Exception as e: return f'{{"error": "Ollama Error: {str(e)}"}}'

# --- 5. DATABASE ENGINE ---
# Uses db_connector.execute_query which reads db_registry.yaml — no hardcoded connections.
# @st.cache_data means: if the SAME query+domain is called again within 300 seconds (5 min),
# Streamlit returns the cached result instead of hitting the database again. This is a huge
# performance win for repeated or similar questions.
@st.cache_data(ttl=300, show_spinner=False)
def get_db_data(query: str, domain: str):
    """
    Run a SQL query on the database that owns the given domain.
    Returns a dict: {"success": True, "data": DataFrame} or {"success": False, "error": "..."}
    """
    if not query:
        return {"success": False, "error": "Empty Query"}

    resolved = dbc.resolve_domain(domain)
    if not resolved:
        # Fallback: domain string IS the db_key (for backward compatibility)
        all_dbs = dbc.get_enabled_databases()
        db_key  = domain.lower()
        if db_key not in all_dbs:
            return {"success": False, "error": f"No database registered for domain '{domain}'."}
        db_config = all_dbs[db_key]
    else:
        db_key, db_config = resolved

    result = dbc.execute_query(db_key, db_config, str(query))
    return result

# --- 6. AGENT WORKFLOW ---
# These three functions form the "brain pipeline":
#   rewrite_query → supervisor_routing → agent_execution
#
# Think of it like a team:
#   rewrite_query   = Translator  (makes sure the question is clear)
#   supervisor      = Manager     (decides which expert to send it to)
#   agent_execution = Worker      (writes the SQL and runs it)

def rewrite_query(current_question, history_list, model):
    """
    Translates follow-up questions into standalone queries.
    Example: "what about Sales?" becomes "What is the average salary in the Sales department?"
    This prevents the AI from losing context when generating SQL.
    """
    if not history_list: return current_question

    system_prompt = """You are an AI query translator. Look at the conversation history and the user's latest question.
    1. If the latest question is a follow-up, rewrite it into a single, comprehensive, standalone sentence containing all necessary context from the history.
    2. If it is already fully self-contained, return it exactly as is.
    3. CRITICAL: Output ONLY the rewritten question. No filler."""
    
    prompt = f"### History:\n{chr(10).join(history_list)}\n\n### Latest Question:\n{current_question}\n\n### Rewritten Standalone Question:"
    rewritten = generate_ai_response(model, system_prompt, prompt)
    
    if '"error":' in rewritten: return current_question
    return rewritten.strip('"').strip()

def supervisor_routing(user_question, history_str, model):
    memory, _ = check_vector_memory(user_question)
    memory_hint = f"\n\n[HINT]: A past similar question ('{memory['query']}') was routed correctly." if memory else ""

    # Build domain routing rules dynamically from the registry
    domain_rules = "\n".join(
        f"    - {domain}: Questions about {dbc.get_enabled_databases().get(db_key, {}).get('description', domain)}"
        for domain, db_key in DOMAIN_MAP.items()
    )
    valid_outputs = "', '".join(ACTIVE_DOMAINS) + "', or 'FEDERATED'"

    system = f"""You are a Routing Supervisor. Output ONLY one of: '{valid_outputs}'.
    Routing rules:
{domain_rules}
    - FEDERATED: ONLY if the question explicitly requires joining data from TWO OR MORE of the above databases.
    {memory_hint}"""

    raw = generate_ai_response(model, system, f"History: {history_str}\nQuestion: {user_question}")

    if '"error":' in raw:
        raw = generate_ai_response("gemma3:12b", system, f"History: {history_str}\nQuestion: {user_question}")

    raw_upper = raw.upper()
    if "FEDERATED" in raw_upper:
        return "FEDERATED"
    # Check all registered domains
    for domain in sorted(ACTIVE_DOMAINS, key=len, reverse=True):
        if domain in raw_upper:
            return domain
    # Default to first active domain
    return ACTIVE_DOMAINS[0] if ACTIVE_DOMAINS else "HR"

def agent_execution(user_question, domain, history_str, model):
    """
    The core worker: asks an AI to write SQL, runs it on the database, returns results.

    "Cascade" pattern: if the first AI fails (API error, bad SQL), automatically
    tries the next model in the list. This makes the app resilient — it won't give
    up just because one provider is down or returns garbage SQL.
    """
    # Use dynamically discovered schema — refreshed via Connection Manager
    context = ACTIVE_SCHEMA

    if domain == "FEDERATED":
        # Look up the join hint for whichever pair of active domains is configured.
        # This replaces the old hardcoded "HR+CLAIMS only" check and now supports
        # HR+AZURE_CLAIMS (and any future pair added to FEDERATED_JOIN_CONFIGS).
        active_set = set(ACTIVE_DOMAINS)
        for pair, cfg in FEDERATED_JOIN_CONFIGS.items():
            if pair.issubset(active_set):
                context += f"\n{cfg['hint']}"
                break   # Use the first matching pair — usually only one applies

        # Build a dynamic format string that names query keys by their domain.
        # e.g. { "explanation": "...", "HR_query": "SELECT ...", "CLAIMS_query": "SELECT ..." }
        # Using domain names (not "postgres_query") means the AI knows exactly
        # which query goes to which database without us hardcoding it.
        fed_fields = ", ".join(f'"{d}_query": "SELECT ..."' for d in ACTIVE_DOMAINS)
        format_req = '{ "explanation": "...", ' + fed_fields + ' }'
    else:
        format_req = '{ "explanation": "...", "sql_query": "..." }'

    memory, match_ratio = check_vector_memory(user_question)
    memory_hint = f"\n[CRITICAL OVERRIDE]: Found {match_ratio:.1f}% semantic match! Past Question: '{memory['query']}'\nPast SQL:\n{memory['sql']}\nBorrow this syntax heavily!" if memory else ""

    # UPDATED: Relaxed the Join Key rule so it doesn't break aggregate GROUP BY queries
    system_prompt = f"""Senior Data Architect. Context: {context}
    1. Join key is emp_id (INT) and MemberID (VARCHAR). MemberID MUST be in quotes.
    2. FEDERATED requires BOTH queries. NO CROSS-DATABASE JOINS.
    3. FOR FEDERATED QUERIES ONLY: Include join keys in SELECT clauses. Do NOT force join keys into standard HR or CLAIMS aggregate queries!
    4. Flat strings for SQL.{memory_hint}
    Return JSON ONLY: {format_req}"""
    
    # The cascade list: try models in order. dict.fromkeys() removes duplicates
    # while preserving order, so if the user already selected "claude-sonnet-4-6"
    # it won't appear twice in the list.
    cascade = [model, "gemini-2.5-flash", "gemini-3.1-flash-lite-preview", "claude-sonnet-4-6", "qwen2.5-coder:7b", "deepseek-r1:8b", "gemma3:12b"]
    models_to_try = list(dict.fromkeys(cascade))
    escalation_log = []   # Track which models were tried and why they failed

    for current_model in models_to_try:
        with st.status(f"✨ Agent: {current_model}...", expanded=False) as status:
            try:
                raw_res = generate_ai_response(current_model, system_prompt, f"History: {history_str}\nQuestion: {user_question}")
                if '"error":' in raw_res: 
                    status.update(label=f"⚠️ {current_model} API Error", state="error")
                    escalation_log.append({"model": current_model, "error": f"API Error: {raw_res}"})
                    continue

                match = re.search(r'\{.*\}', re.sub(r'<think>.*?</think>', '', raw_res, flags=re.DOTALL), re.DOTALL)
                if match:
                    plan = json.loads(match.group(0))
                    
                    if domain == "FEDERATED":
                        # ── Step 1: Collect all domain queries from the AI's response ──
                        # The AI returns keys like "HR_query", "CLAIMS_query", etc.
                        # We also check old keys ("postgres_query", "sql_server_query")
                        # for backward compatibility with cached vector memory hints.
                        domain_queries = {}
                        for k, v in plan.items():
                            if k.endswith("_query") and v and str(v).strip():
                                dom = k.replace("_query", "").upper()
                                domain_queries[dom] = str(v)

                        # Backward-compat: old format used postgres_query / sql_server_query
                        _compat = {"POSTGRES": "HR", "SQL_SERVER": "CLAIMS"}
                        for old, new_dom in _compat.items():
                            if old + "_QUERY" in {k.upper() for k in plan} and new_dom not in domain_queries:
                                fallback = plan.get(f"{old.lower()}_query", "")
                                if fallback:
                                    domain_queries[new_dom] = str(fallback)

                        # ── Step 2: Run each domain query against its database ──
                        domain_results = {}
                        err_msgs       = []
                        for dom, sql_q in domain_queries.items():
                            res = get_db_data(sql_q, dom)
                            domain_results[dom] = res
                            if not res["success"]:
                                err_msgs.append(f"{dom}: {res.get('error', 'unknown error')}")

                        all_ok = not err_msgs and len(domain_results) >= 2

                        if all_ok:
                            # ── Step 3: Merge using the configured join keys ──
                            active_pair = frozenset(domain_results.keys())
                            join_cfg    = FEDERATED_JOIN_CONFIGS.get(active_pair)

                            if join_cfg:
                                # Known pair — use configured join keys
                                df_left  = domain_results[join_cfg["left"]]["data"].copy()
                                df_right = domain_results[join_cfg["right"]]["data"].copy()
                                df_left.columns  = [c.lower() for c in df_left.columns]
                                df_right.columns = [c.lower() for c in df_right.columns]
                                df_left[join_cfg["left_key"]]   = df_left[join_cfg["left_key"]].astype(str).str.strip()
                                df_right[join_cfg["right_key"]] = df_right[join_cfg["right_key"]].astype(str).str.strip()
                                final_df = pd.merge(df_left, df_right,
                                                    left_on=join_cfg["left_key"],
                                                    right_on=join_cfg["right_key"],
                                                    how="inner")
                            else:
                                # Unknown pair — try merging on the first common column name
                                dfs = [r["data"].copy() for r in domain_results.values()]
                                for d in dfs:
                                    d.columns = [c.lower() for c in d.columns]
                                common = list(set(dfs[0].columns) & set(dfs[1].columns))
                                if common:
                                    final_df = pd.merge(dfs[0], dfs[1], on=common[0], how="inner")
                                else:
                                    # No common column — return both tables side-by-side
                                    final_df = pd.concat(dfs, axis=1)

                            was_limited = any(r.get("was_limited", False) for r in domain_results.values())
                            fed_sql_display = (
                                "-- FEDERATED QUERY EXECUTED\n"
                                + "\n\n".join(f"-- {dom}:\n{sql_q}" for dom, sql_q in domain_queries.items())
                            )
                            return {
                                "df":            final_df,
                                "sql":           fed_sql_display,
                                "agent":         current_model,
                                "reasoning":     plan.get("explanation", "N/A"),
                                "escalation_log": escalation_log,
                                "memory_used":   bool(memory),
                                "memory_ratio":  match_ratio,
                                "was_limited":   was_limited,
                            }
                        else:
                            err_msg = " | ".join(err_msgs) if err_msgs else "AI returned no valid domain queries"
                            status.update(label=f"⚠️ {current_model} FEDERATED Error", state="error")
                            st.toast(f"{current_model} Failed: {err_msg}", icon="❌")
                            escalation_log.append({"model": current_model, "error": err_msg})
                            continue

                    else:
                        # ── Single-database query path ──
                        # Try all possible key names the AI might use for the SQL
                        target_sql = str(
                            plan.get("sql_query") or
                            plan.get("postgres_query") or
                            plan.get("sql_server_query") or ""
                        )
                        res_db = get_db_data(target_sql, domain)
                        if res_db["success"]:
                            return {
                                "df":            res_db["data"],
                                "sql":           target_sql,
                                "agent":         current_model,
                                "reasoning":     plan.get("explanation", "N/A"),
                                "escalation_log": escalation_log,
                                "memory_used":   bool(memory),
                                "memory_ratio":  match_ratio,
                                "was_limited":   res_db.get("was_limited", False),
                                "max_rows":      res_db.get("max_rows", MAX_ROWS),
                            }
                        else:
                            status.update(label=f"⚠️ {current_model} DB Error", state="error")
                            st.toast(f"{current_model} Failed: {res_db['error']}", icon="❌")
                            escalation_log.append({"model": current_model, "error": f"DB Error: {res_db['error']}"})
                            continue
            except Exception as e:
                status.update(label=f"⚠️ {current_model} Execution Error", state="error")
                escalation_log.append({"model": current_model, "error": f"Execution Error: {str(e)}"})
    return None

def format_model_label(model_name):
    if "opus" in model_name or "sonnet" in model_name: return f"✨ {model_name} (Cloud Pro)"
    elif "haiku" in model_name or "gemini" in model_name: return f"⚡ {model_name} (Cloud)"
    elif ":cloud" in model_name: return f"☁️ {model_name} (Ollama Cloud)"
    else: return f"💻 {model_name} (Local)"

def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    """
    Convert a pandas DataFrame to Excel file bytes.

    Why BytesIO?
    st.download_button needs file bytes, not a file path. BytesIO is an
    in-memory "fake file" — we write the Excel content into memory and then
    hand the bytes directly to Streamlit. No temp file written to disk.
    """
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Query Results")
    # After the 'with' block closes, the Excel bytes are finalised in buffer.
    return buffer.getvalue()  # Returns raw bytes ready for download

# --- 7. MAIN UI ---
st.title(":material/domain: Multi-Agent | Multi-LLMs | Multi Database  \n"
         "**Enterprise BI**")

with st.container(border=True):
    # --- Build database lists DYNAMICALLY from db_registry.yaml ---
    # This way you never need to edit this file when you add/remove a database —
    # it just reads whatever is currently in the registry.

    _all_dbs = dbc.get_all_databases()

    # Active databases: any entry where enabled=True
    active_db_items = []
    for _key, _cfg in _all_dbs.items():
        if _cfg.get("enabled"):
            _type = _cfg.get("type", "db").upper()
            _host = _cfg.get("host", "")
            # Detect cloud vs local: Azure SQL hostnames end in .windows.net
            _is_cloud = any(kw in _host.lower() for kw in ["windows.net", "cloud", ".azure", "snowflake", "bigquery"])
            _location = "CLOUD" if _is_cloud else "LOCAL"
            active_db_items.append(f"- {_cfg.get('name', _key)} (**{_type} {_location}**)")

    # Future add-ons: any entry where enabled=False
    future_db_items = []
    for _key, _cfg in _all_dbs.items():
        if not _cfg.get("enabled"):
            _type = _cfg.get("type", "db").upper()
            future_db_items.append(f"- {_cfg.get('name', _key)} (**{_type}**)")

    # Get active LLM providers
    active_providers = []
    llm_details = []

    if ANTHROPIC_API_KEY:
        active_providers.append("Anthropic")
        llm_details.append("- **Claude Series LLMs (Opus, Sonnet, Haiku)** (Cloud | Tiered Cost)")

    if GEMINI_API_KEY:
        active_providers.append("Google")
        llm_details.append("- **Gemini Flash Series LLMs** (Cloud | Low Cost)")

    if MINIMAX_API_KEY:
        active_providers.append("Minimax")
        llm_details.append("- **Minimax m2.7** (Cloud | Med Cost)")

    try:
        # Check if ollama server is running. If it is, we list the local models from the dropdown.
        ollama.list() # This will throw an exception if the server is not running.
        active_providers.append("Ollama (Local)")
        # This now matches the local models available in the primary model dropdown.
        llm_details.append("- **Gemma, Qwen Coder, DeepSeek** (Local | Open Source | Free)")
    except Exception:
        pass # Ollama not running or installed

    # Display active components
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**<span class='material-symbols-rounded mat-icon'>database</span> Active Databases ({len(active_db_items)})**", unsafe_allow_html=True)
        st.markdown("\n".join(active_db_items))
        
        st.markdown("<div style='margin-top: 15px; color: #5f6368;'><b><span class='material-symbols-rounded mat-icon'>extension</span> Future Add-ons</b></div>", unsafe_allow_html=True)
        st.markdown("\n".join(future_db_items))
    with col2:
        st.markdown(f"**<span class='material-symbols-rounded mat-icon'>psychology</span> Active LLM Providers ({len(active_providers)})**", unsafe_allow_html=True)
        if llm_details:
            st.markdown("\n".join(llm_details))
        else:
            st.caption("None configured. Check API keys or run `ollama serve`.")

with st.sidebar:
    if GEMINI_API_KEY:
        st.markdown('<div class="api-info"><span class="material-symbols-rounded mat-icon">cloud_done</span><b>Cloud Inference Active</b></div>', unsafe_allow_html=True)

    memory_count = get_vector_memory_count()
    if memory_count > 0:
        st.markdown(f'<div class="api-info" style="background-color: #f0fdf4; border-color: #bbf7d0; color: #166534;"><span class="material-symbols-rounded mat-icon">database</span><b>SQL Server Brain:</b> {memory_count} semantic vectors stored</div>', unsafe_allow_html=True)

    if st.button(":material/delete: Clear History", use_container_width=True):
        st.session_state.messages = []
        st.cache_data.clear() 
        st.rerun()

    st.markdown('<div class="sidebar-header"><span class="material-symbols-rounded mat-icon">memory</span> AI Reasoning Engine</div>', unsafe_allow_html=True)
    
    selected_model = st.selectbox("Select primary model:", [
        "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5", "gemini-2.5-flash", 
        "gemini-2.5-flash-lite", "gemini-3.1-flash-lite-preview", "minimax-m2.7:cloud", 
        "gemma3:12b", "qwen2.5-coder:7b", "deepseek-r1:8b"
    ], format_func=format_model_label)

    st.markdown('<div class="sidebar-header"><span class="material-symbols-rounded mat-icon">payments</span> Model Cost Hierarchy</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="margin-top: 10px;">
        <b><span class="material-symbols-rounded mat-icon" style="color: #d97706;">military_tech</span> Tier 1: Elite Reasoners</b><br>
        <span style="font-size: 0.8rem;">• <b>Claude Opus 4.6</b> / <b>Claude Sonnet 4.6</b></span>
    </div>
    <div style="margin-top: 12px;">
        <b><span class="material-symbols-rounded mat-icon" style="color: #8b5cf6;">cloud_sync</span> Tier 1.5: Ollama Cloud (Previews)</b><br>
        <span style="font-size: 0.8rem;">• <b>Minimax (m2.7)</b></span>
    </div>
    <div style="margin-top: 12px;">
        <b><span class="material-symbols-rounded mat-icon" style="color: #2563eb;">speed</span> Tier 2: Fast & Efficient</b><br>
        <span style="font-size: 0.8rem;">• <b>Claude Haiku 4.5</b> / <b>Gemini 2.5 Flash</b></span>
    </div>
    <div style="margin-top: 12px;">
        <b><span class="material-symbols-rounded mat-icon" style="color: #16a34a;">dns</span> Tier 3: Local Specialists</b><br>
        <span style="font-size: 0.8rem;">• <b>Qwen Coder</b> / <b>DeepSeek-R1</b> / <b>Gemma 3</b></span>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="sidebar-header"><span class="material-symbols-rounded mat-icon">science</span> Actionable Test Suite</div>', unsafe_allow_html=True)
    
    # NEW SPECIFIC TEST QUESTIONS for the updated hr_employees schema
    if st.button(":material/bar_chart: HR: Average Salary", use_container_width=True): 
        st.session_state.user_query = "What is the average salary by department?"
    if st.button(":material/calendar_month: HR: Recent Hires", use_container_width=True): 
        st.session_state.user_query = "Which employees were hired after January 1, 2024?"
    if st.button(":material/cancel: Claims: Total Denied", use_container_width=True): 
        st.session_state.user_query = "What is the total billed amount for claims that were Denied?"
    if st.button(":material/health_and_safety: Claims: Top Provider", use_container_width=True): 
        st.session_state.user_query = "Which ProviderName has the highest number of approved claims?"
    if st.button(":material/hub: Federated: High Earners Claims", use_container_width=True): 
        st.session_state.user_query = "Show me the names and total billed claims of employees in the Marketing department."

# Chat Rendering
for i, msg in enumerate(st.session_state.messages):
    avatar_icon = "✨" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar_icon):
        if "metadata" in msg:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("⏱️ Latency", f"{msg['metadata']['time']}s")
            escalations = len(msg['metadata'].get('escalation_log', []))
            confidence_label = "Memory Hit" if msg["metadata"].get("memory_used") else ("1st Try ✓" if escalations == 0 else f"After {escalations} retries")
            c2.metric("🎯 Result", confidence_label)
            c3.metric("🧠 Agent", msg['metadata']['agent'])
            c4.metric("📚 Memory Assist", f"{msg['metadata'].get('memory_ratio', 0):.1f}% Match" if msg["metadata"].get("memory_used") else "None")
            
            with st.expander("🔍 View SQL Execution Details"):
                st.write(f"**Strategy:** {msg['metadata'].get('reasoning', 'N/A')}")
                st.code(sqlparse.format(msg['metadata']['sql'], reindent=True, keyword_case='upper'), language="sql")
        
        st.markdown(msg["content"].replace('$', '\\$'))
        if "data" in msg and not msg["data"].empty:
            st.dataframe(msg["data"], width='stretch')

            # Row-cap notice — shown when the result was automatically truncated
            if msg.get("metadata", {}).get("was_limited"):
                max_r = msg["metadata"].get("max_rows", MAX_ROWS)
                st.warning(
                    f"⚠️ Results capped at **{max_r} rows**. "
                    "Your query likely matched more data — add a WHERE clause or ask for a specific filter to narrow it down.",
                    icon="📊"
                )

            # Download button — converts the DataFrame to Excel bytes in memory
            ts  = msg.get("metadata", {}).get("time", "")
            fname = f"query_results_{ts}s.xlsx".replace(" ", "_")
            st.download_button(
                label="📥 Download as Excel",
                data=df_to_excel_bytes(msg["data"]),
                file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_{id(msg)}",    # unique key per message so buttons don't conflict
            )

        if msg["role"] == "assistant" and "metadata" in msg:
            feedback_key = f"fb_{i}"
            feedback = st.feedback("thumbs", key=feedback_key)
            
            if feedback is not None and not msg.get("feedback_saved"):
                is_positive = (feedback == 1)
                clean_query = msg["metadata"].get("standalone_query", st.session_state.messages[i-1]["content"])
                
                save_vector_memory(clean_query, msg["metadata"]["sql"], msg["metadata"]["domain"], msg["metadata"]["agent"], is_positive)
                msg["feedback_saved"] = True
                if is_positive: st.toast("Embedded and saved to SQL Server Vector Engine! 🧠", icon="✅")
                time.sleep(0.5) 
                st.rerun()

    if msg["role"] == "assistant":
        st.markdown("<div style='margin: 40px 0; border-bottom: 3px dashed #cbd5e1;'></div>", unsafe_allow_html=True)

# Main Input
user_input = st.chat_input("Ask about your data...")
final_query = user_input if user_input else st.session_state.get("user_query")

if final_query:
    st.session_state.user_query = None
    
    rewriter_history = [f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages[-4:]]

    agent_history_list = []
    for m in st.session_state.messages[-5:]:
        msg_text = f"{m['role'].upper()}: {m['content']}"
        if m["role"] == "assistant" and "metadata" in m and "sql" in m["metadata"]:
            msg_text += f"\n[SYSTEM CONTEXT - Previous SQL Executed: {m['metadata']['sql']}]"
        agent_history_list.append(msg_text)
    agent_history_str = "\n".join(agent_history_list)

    st.session_state.messages.append({"role": "user", "content": final_query})
    with st.chat_message("user", avatar="👤"):
        st.markdown(final_query.replace('$', '\\$'))
        
        with st.spinner("Translating context..."):
            standalone_query = rewrite_query(final_query, rewriter_history, selected_model)
            
        if standalone_query.lower() != final_query.lower():            st.caption(f"*(Interpreted as: {standalone_query})*")

    with st.chat_message("assistant", avatar="✨"):
        start_time = time.time()
        
        with st.spinner("Supervisor analyzing intent..."):
            domain = supervisor_routing(standalone_query, agent_history_str, selected_model)
            st.write(f"🔀 Supervisor routed to **{domain}**")
            
        result = agent_execution(standalone_query, domain, agent_history_str, selected_model)
        
        if result:
            latency = round(time.time() - start_time, 2)
            memory_used = result.get("memory_used", False)
            memory_ratio = result.get("memory_ratio", 0)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("⏱️ Latency", f"{latency}s")
            escalations = len(result.get("escalation_log", []))
            confidence_label = "Memory Hit" if memory_used else ("1st Try ✓" if escalations == 0 else f"After {escalations} retries")
            c2.metric("🎯 Result", confidence_label)
            c3.metric("🧠 Agent", result['agent'])
            c4.metric("📚 Memory Assist", f"{memory_ratio:.1f}% Match" if memory_used else "None")
            
            summary_prompt = f"Summarize these findings in 2-3 short bullet points. No markdown tables. Data: {result['df'].head(5).to_dict()}. Query: {standalone_query}"
            summary = generate_ai_response(result['agent'], "Helpful BI Analyst", summary_prompt)
            if '"error":' in summary:
                summary = "Data retrieved successfully. See table below."
                
            st.markdown(summary.replace('$', '\\$'))
            st.dataframe(result['df'], width='stretch')

            # ── Row-cap notice ──────────────────────────────────────────────
            # was_limited=True means the row limit was injected into the SQL.
            # We warn the user so they know they might not be seeing all data.
            was_limited = result.get("was_limited", False)
            max_r       = result.get("max_rows", MAX_ROWS)
            if was_limited:
                st.warning(
                    f"⚠️ Results capped at **{max_r} rows**. "
                    "Your query matched more data — add a WHERE clause or specify a filter to narrow it down.",
                    icon="📊"
                )

            # ── Excel download button ───────────────────────────────────────
            # df_to_excel_bytes() converts the DataFrame to an in-memory Excel file.
            # st.download_button serves it as a file download — no temp file on disk.
            dl_filename = f"query_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            st.download_button(
                label="📥 Download as Excel",
                data=df_to_excel_bytes(result['df']),
                file_name=dl_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            st.session_state.messages.append({
                "role": "assistant",
                "content": summary,
                "data": result['df'],
                "metadata": {
                    "time":             latency,
                    "agent":            result['agent'],
                    "sql":              result['sql'],
                    "reasoning":        result['reasoning'],
                    "domain":           domain,
                    "memory_used":      memory_used,
                    "memory_ratio":     memory_ratio,
                    "standalone_query": standalone_query,
                    "escalation_log":   result.get("escalation_log", []),
                    "was_limited":      was_limited,      # persist for chat history redisplay
                    "max_rows":         max_r,
                }
            })
            st.rerun()
        else:
            st.error("Escalation failed. All models failed to generate a working query.")
