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
import os
import time
import json
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
from vector_memory import save_vector_memory, check_vector_memory, get_vector_memory_stats

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
    "[AZURE_CLAIMS | Azure SQL Claims | MSSQL]\n"
    "  Table Claims: ClaimID* (INTEGER), MemberID (VARCHAR), ServiceDate (DATE), ProviderName (VARCHAR), "
    "DiagnosisCode (VARCHAR), ProcedureCode (VARCHAR), BilledAmount (DECIMAL), PaidAmount (DECIMAL), ClaimStatus (VARCHAR)\n"
    "  Table ProviderClaimSummary: ProviderName (VARCHAR), TotalBilled (DECIMAL), TotalPaid (DECIMAL), DeniedClaims (INT)"
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
        return f'{"error": "Model {model_name} is not supported in this cloud deployment"}'

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
"""

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
    context = ACTIVE_SCHEMA
    format_req = '{ "explanation": "...", "sql_query": "..." }'

    system_prompt = f"""Senior Data Architect. Context: {context}
    Return JSON ONLY: {format_req}"""
    
    cascade = [model, "gemini-2.5-flash", "claude-sonnet-4-6"]
    models_to_try = list(dict.fromkeys(cascade))
    escalation_log = []

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
                    target_sql = str(plan.get("sql_query", ""))
                    res_db = get_db_data(target_sql, domain)
                    if res_db["success"]:
                        return {
                            "df":            res_db["data"],
                            "sql":           target_sql,
                            "agent":         current_model,
                            "reasoning":     plan.get("explanation", "N/A"),
                            "escalation_log": escalation_log,
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

    try:
        pass # Ollama not running or installed
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

    # ✅ NEW: Show vector memory stats
    try:
        stats = get_vector_memory_stats(SQL_SERVER_NAME, SQL_USER, SQL_PASSWORD)
        st.metric("📚 Cached Answers", stats["total_cached_questions"])
    except:
        pass  # If vector table doesn't exist yet, just skip

    if st.button(":material/delete: Clear History", use_container_width=True):
        st.session_state.messages = []
        st.cache_data.clear() 
        st.rerun()

    st.markdown('<div class="sidebar-header"><span class="material-symbols-rounded mat-icon">memory</span> AI Reasoning Engine</div>', unsafe_allow_html=True)
    
    selected_model = st.selectbox("Select primary model:", [
        "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5", "gemini-2.5-flash", 
        "gemini-2.5-flash-lite", "gemini-3.1-flash-lite-preview"
    ], format_func=format_model_label)

    st.markdown('<div class="sidebar-header"><span class="material-symbols-rounded mat-icon">payments</span> Model Cost Hierarchy</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="margin-top: 10px;">
        <b><span class="material-symbols-rounded mat-icon" style="color: #d97706;">military_tech</span> Tier 1: Elite Reasoners</b><br>
        <span style="font-size: 0.8rem;">• <b>Claude Opus 4.6</b> / <b>Claude Sonnet 4.6</b></span>
    </div>
    <div style="margin-top: 12px;">
        <b><span class="material-symbols-rounded mat-icon" style="color: #2563eb;">speed</span> Tier 2: Fast & Efficient</b><br>
        <span style="font-size: 0.8rem;">• <b>Claude Haiku 4.5</b> / <b>Gemini 2.5 Flash</b></span>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="sidebar-header"><span class="material-symbols-rounded mat-icon">science</span> Actionable Test Suite</div>', unsafe_allow_html=True)
    
    # Azure SQL (Claims) TEST QUESTIONS
    if st.button(":material/cancel: Claims: Total Denied", use_container_width=True): 
        st.session_state.user_query = "What is the total billed amount for claims that were Denied?"
    if st.button(":material/health_and_safety: Claims: Top Provider", use_container_width=True): 
        st.session_state.user_query = "Which ProviderName has the highest number of approved claims?"
    if st.button(":material/analytics: Provider Summary", use_container_width=True):
        st.session_state.user_query = "Show me the provider with the highest TotalBilled amount from the ProviderClaimSummary table."

# Chat Rendering
for i, msg in enumerate(st.session_state.messages):
    avatar_icon = "✨" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar_icon):
        if "metadata" in msg:
            c1, c2, c3 = st.columns(3)
            c1.metric("⏱️ Latency", f"{msg['metadata']['time']}s")
            escalations = len(msg['metadata'].get('escalation_log', []))
            confidence_label = "1st Try ✓" if escalations == 0 else f"After {escalations} retries"
            c2.metric("🎯 Result", confidence_label)
            c3.metric("🧠 Agent", msg['metadata']['agent'])
            
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

            # ✅ NEW: Save vector memory when user gives feedback
            if feedback is not None:  # feedback = 1 (thumbs up), 0 (thumbs down)
                is_positive = (feedback == 1)
                save_vector_memory(
                    gemini_client=gemini_client,
                    sql_server=SQL_SERVER_NAME,
                    sql_user=SQL_USER,
                    sql_password=SQL_PASSWORD,
                    user_question=msg["metadata"]["standalone_query"],
                    sql_code=msg["metadata"]["sql"],
                    domain=msg["metadata"]["domain"],
                    agent_model=msg["metadata"]["agent"],
                    is_positive=is_positive
                )

    if msg["role"] == "assistant":
        st.markdown("<div style='margin: 40px 0; border-bottom: 3px dashed #cbd5e1;'></div>", unsafe_allow_html=True)

# Main Input
user_input = st.chat_input("Ask about your data...")
final_query = user_input if user_input else st.session_state.get("user_query")

if final_query:
    st.session_state.user_query = None

    # ✅ NEW: Check if we've seen a similar question before
    if gemini_client:
        cached_sql, similarity_score = check_vector_memory(
            gemini_client=gemini_client,
            sql_server=SQL_SERVER_NAME,
            sql_user=SQL_USER,
            sql_password=SQL_PASSWORD,
            user_question=final_query,
            threshold=65.0
        )
        if cached_sql:
            st.info(f"💡 **Cached Answer Found!** ({similarity_score:.1f}% similar)\n\n"
                   f"We've seen a very similar question before. Using that as a hint...")

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

            c1, c2, c3 = st.columns(3)
            c1.metric("⏱️ Latency", f"{latency}s")
            escalations = len(result.get("escalation_log", []))
            confidence_label = "1st Try ✓" if escalations == 0 else f"After {escalations} retries"
            c2.metric("🎯 Result", confidence_label)
            c3.metric("🧠 Agent", result['agent'])
            
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
                    "standalone_query": standalone_query,
                    "escalation_log":   result.get("escalation_log", []),
                    "was_limited":      was_limited,      # persist for chat history redisplay
                    "max_rows":         max_r,
                }
            })
            st.rerun()
        else:
            st.error("Escalation failed. All models failed to generate a working query.")
