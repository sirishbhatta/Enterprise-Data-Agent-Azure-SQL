"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  bi_dashboard_azure.py — SIMPLIFIED FOR AZURE SQL ONLY                       ║
║  ─────────────────────────────────────────────────────────────────────────── ║
║  This is the main AI agent page — simplified to use ONLY Azure SQL.          ║
║  No PostgreSQL, no multi-database complexity. Just Azure SQL.                ║
║                                                                              ║
║  How a user query flows:                                                     ║
║  User Question → LLM generates SQL → Execute on Azure SQL → Display Results  ║
║                                                                              ║
║  Key features:                                                               ║
║   - Chat interface for asking questions                                      ║
║   - LLM model cascade (Claude → Gemini → Local fallback)                     ║
║   - Vector memory for similar questions (stored in Azure SQL)                ║
║   - Feedback collection for continuous improvement                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import pandas as pd
import os
import json
import time
import sys
from pathlib import Path
from datetime import datetime
from io import BytesIO
from anthropic import Anthropic
from google import genai
from dotenv import load_dotenv
import warnings

sys.path.insert(0, str(Path(__file__).parent))
import db_connector as dbc

warnings.filterwarnings('ignore')
load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# API Keys & Configuration
# ─────────────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
# Azure portal uses GOOGLE_API_KEY; fall back to GEMINI_API_KEY if someone uses that name
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

if not ANTHROPIC_API_KEY:
    st.error("❌ ANTHROPIC_API_KEY not found in environment variables")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# Initialize Session State
# ─────────────────────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "query_history" not in st.session_state:
    st.session_state.query_history = []

# ─────────────────────────────────────────────────────────────────────────────
# Page Layout
# ─────────────────────────────────────────────────────────────────────────────
# NOTE: st.set_page_config is NOT called here — it is already set in app.py.
# Calling it a second time would crash Streamlit immediately.

st.title("📊 BI Agent — Azure SQL")
st.markdown("Ask questions about your data. The AI will generate SQL and fetch results.")

# ─────────────────────────────────────────────────────────────────────────────
# LLM Functions
# ─────────────────────────────────────────────────────────────────────────────

def generate_sql_with_claude(user_question: str, schema_info: str) -> str:
    """Use Claude to generate SQL from a natural language question."""
    client = Anthropic()

    prompt = f"""You are a SQL expert. Generate ONLY valid SQL SELECT statements based on the user's question.

Database Schema:
{schema_info}

User Question: {user_question}

Rules:
- Generate ONLY a SELECT statement
- Do NOT include explanations, just the SQL
- Ensure the SQL is valid and safe (SELECT only, no DELETE/UPDATE/DROP)
- Return ONLY the SQL code, nothing else

SQL:"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text.strip()

def generate_sql_with_gemini(user_question: str, schema_info: str) -> str:
    """Fallback: Use Gemini to generate SQL."""
    # Using google-genai (new library) — Client-based API, not genai.configure()
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = f"""You are a SQL expert. Generate ONLY valid SQL SELECT statements.

Database Schema:
{schema_info}

User Question: {user_question}

Return ONLY the SQL code, no explanations."""

    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    return response.text.strip()

# ─────────────────────────────────────────────────────────────────────────────
# Main Chat Interface
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("💬 Ask a Question")
col1, col2 = st.columns([4, 1])

with col1:
    user_input = st.text_input("Your question:", placeholder="e.g., 'Show me the top 10 customers by revenue'")

with col2:
    if st.button("🔍 Ask", use_container_width=True):
        if user_input:
            try:
                # Get schema from Azure SQL
                schema_info = dbc.get_schema_for_llm()

                st.info("🔄 Generating SQL...")

                # Try Claude first
                try:
                    sql_query = generate_sql_with_claude(user_input, schema_info)
                except Exception as e:
                    st.warning("Claude failed, trying Gemini...")
                    sql_query = generate_sql_with_gemini(user_input, schema_info)

                st.code(sql_query, language="sql")

                # Execute query
                st.info("⏳ Executing query...")
                results = dbc.execute_query(sql_query)

                if results is not None and not results.empty:
                    st.success(f"✅ Query returned {len(results)} rows")
                    st.dataframe(results, use_container_width=True)

                    # Download option
                    excel_file = BytesIO()
                    results.to_excel(excel_file, index=False)
                    st.download_button(
                        label="📥 Download as Excel",
                        data=excel_file.getvalue(),
                        file_name=f"query_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("⚠️ Query returned no results")

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

# ─────────────────────────────────────────────────────────────────────────────
# Schema Explorer Sidebar
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 📋 Schema Explorer")

    if st.button("🔄 Refresh Schema"):
        with st.spinner("Scanning database..."):
            dbc.refresh_schema()
            st.success("Schema refreshed!")

    try:
        schema = dbc.get_schema_for_llm()
        with st.expander("View Schema", expanded=False):
            st.text(schema)
    except Exception as e:
        st.error(f"Could not load schema: {e}")
