"""
Connection Manager — Multi-Database BI Engine
==============================================
A Streamlit page for managing database connections.

Features:
  • View all registered databases (active + placeholders)
  • Test connections live
  • Discover & refresh schemas (tables, columns, views, procedures)
  • Browse table structures inline
  • Add new database connections
  • Enable / disable connections
"""

import streamlit as st
import pandas as pd          # Moved to top — Python best practice: all imports at the start of the file
import yaml
import time
import sys
from pathlib import Path

# Allow imports from the parent directory (this file lives in pages/, parent is sirish_ai/)
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import db_connector as dbc

# ─────────────────────────────────────────────────────────────────────────────
# NOTE: st.set_page_config is intentionally NOT called here.
# It is already called once in app.py (the main entry point). Streamlit only
# allows set_page_config to be called once per app run — calling it twice would
# throw an error. The app.py config applies to all pages automatically.
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
.stApp { background-color: #f8f9fa; }
[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #dadce0; }
.db-card {
    background: #fff;
    border: 1px solid #dadce0;
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 14px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04);
}
.db-card-enabled  { border-left: 5px solid #34a853; }
.db-card-disabled { border-left: 5px solid #dadce0; }
.db-card-error    { border-left: 5px solid #ea4335; }
.badge-enabled  { background:#e6f4ea; color:#137333; padding:3px 10px; border-radius:20px; font-size:0.78rem; font-weight:600; }
.badge-disabled { background:#f1f3f4; color:#5f6368; padding:3px 10px; border-radius:20px; font-size:0.78rem; font-weight:600; }
.badge-type { background:#e8f0fe; color:#1a73e8; padding:3px 10px; border-radius:20px; font-size:0.78rem; font-weight:600; margin-left:6px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────

if "test_results"   not in st.session_state: st.session_state.test_results   = {}
if "schema_results" not in st.session_state: st.session_state.schema_results = {}
if "show_add_form"  not in st.session_state: st.session_state.show_add_form  = False

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🔌 Connection Manager")
    st.caption("Manage your database connections, test them live, and scrape schemas for the AI engine.")
    st.divider()

    all_dbs   = dbc.get_all_databases()
    enabled   = [k for k, v in all_dbs.items() if v.get("enabled")]
    disabled  = [k for k, v in all_dbs.items() if not v.get("enabled")]

    st.metric("Active Connections",   len(enabled))
    st.metric("Available Placeholders", len(disabled))

    st.divider()

    if st.button("🔄 Test All Active", use_container_width=True):
        for k in enabled:
            ok, msg, lat = dbc.test_connection(k, all_dbs[k])
            st.session_state.test_results[k] = {"ok": ok, "msg": msg, "lat": lat}
        st.rerun()

    if st.button("🗂️ Discover All Schemas", use_container_width=True):
        with st.spinner("Scraping schemas from all active databases…"):
            results = dbc.refresh_all_schemas()
            for k, schema in results.items():
                st.session_state.schema_results[k] = schema
        st.success("Schema cache updated!")
        st.rerun()

    st.divider()
    if st.button("➕ Add New Database", use_container_width=True):
        st.session_state.show_add_form = not st.session_state.show_add_form
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────

st.title("🔌 Database Connection Manager")
st.caption("Define your databases here. The AI engine automatically uses the discovered schemas to write accurate SQL.")

cache = dbc.load_schema_cache()
all_dbs = dbc.get_all_databases()

# ─────────────────────────────────────────────────────────────────────────────
# Add New Database Form
# ─────────────────────────────────────────────────────────────────────────────

if st.session_state.show_add_form:
    with st.container(border=True):
        st.subheader("➕ Add New Database")
        st.caption("Fill in the details below. Passwords should be stored in your `.env` file and referenced by their variable name.")

        col1, col2, col3 = st.columns(3)
        with col1:
            new_key  = st.text_input("Registry Key (unique ID)", placeholder="e.g. my_mysql_db")
            new_name = st.text_input("Display Name", placeholder="e.g. My MySQL App DB")
            new_type = st.selectbox("Database Type", [
                "postgresql", "mssql", "mysql", "sqlite", "duckdb",
                "snowflake", "bigquery", "oracle", "databricks", "redshift"
            ])
        with col2:
            new_host     = st.text_input("Host / Server", placeholder="localhost")
            new_port     = st.text_input("Port", placeholder="Leave blank for default")
            new_database = st.text_input("Database Name", placeholder="e.g. my_database")
        with col3:
            new_username     = st.text_input("Username", placeholder="e.g. db_user")
            new_password_env = st.text_input("Password ENV var name", placeholder="e.g. MY_DB_PASSWORD")
            new_domain       = st.text_input("Domain Label", placeholder="e.g. ORDERS (for AI routing)")
            new_desc         = st.text_input("Description", placeholder="Short description for the AI")

        btn_col1, btn_col2 = st.columns([1, 4])
        with btn_col1:
            if st.button("💾 Save", type="primary", use_container_width=True):
                if new_key and new_type:
                    registry = dbc.load_registry()
                    registry["databases"][new_key] = {
                        "name":         new_name or new_key,
                        "type":         new_type,
                        "host":         new_host or "localhost",
                        "database":     new_database,
                        "username":     new_username,
                        "password_env": new_password_env,
                        "domain":       new_domain.upper() if new_domain else "",
                        "description":  new_desc,
                        "enabled":      False,
                    }
                    if new_port:
                        registry["databases"][new_key]["port"] = int(new_port)
                    dbc.save_registry(registry)
                    st.success(f"✅ '{new_key}' added! Enable it below to activate.")
                    st.session_state.show_add_form = False
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Registry key and database type are required.")
        with btn_col2:
            if st.button("Cancel", use_container_width=False):
                st.session_state.show_add_form = False
                st.rerun()

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# Active Databases
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("✅ Active Connections")

active_dbs = {k: v for k, v in all_dbs.items() if v.get("enabled")}

if not active_dbs:
    st.info("No active databases yet. Enable a placeholder below or add a new one.")
else:
    for db_key, db_config in active_dbs.items():
        test_res   = st.session_state.test_results.get(db_key, {})
        schema_res = st.session_state.schema_results.get(db_key) or cache.get(db_key, {})
        has_schema = bool(schema_res.get("tables"))

        card_class = "db-card-enabled"
        if test_res and not test_res["ok"]:
            card_class = "db-card-error"

        # Pre-compute optional badges — avoids ternaries inside f-strings which render as raw text
        error_badge  = "&nbsp;<span style='background:#fce8e6;color:#b31412;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:600'>ERROR</span>" if test_res and not test_res["ok"] else ""
        schema_badge = "&nbsp;<span style='background:#e6f4ea;color:#137333;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:600'>Schema Cached</span>" if has_schema else ""
        db_name      = db_config.get("name", db_key)
        db_type      = db_config["type"].upper()
        description  = db_config.get("description", "")

        st.markdown(
            f'<div class="db-card {card_class}">'
            f'<div style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px;">'
            f'<b style="font-size:1.05rem">{db_name}</b>'
            f'<span style="background:#e6f4ea;color:#137333;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:600">ACTIVE</span>'
            f'<span style="background:#e8f0fe;color:#1a73e8;padding:3px 10px;border-radius:20px;font-size:0.78rem;font-weight:600">{db_type}</span>'
            f'{error_badge}{schema_badge}</div>'
            f'<div style="color:#5f6368;font-size:0.85rem;margin-top:6px;">{description}</div>'
            f'</div>', unsafe_allow_html=True)

        c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1])

        with c1:
            if st.button("🔌 Test Connection", key=f"test_{db_key}", use_container_width=True):
                with st.spinner("Testing…"):
                    ok, msg, lat = dbc.test_connection(db_key, db_config)
                st.session_state.test_results[db_key] = {"ok": ok, "msg": msg, "lat": lat}
                st.rerun()

        with c2:
            if st.button("🗂️ Discover Schema", key=f"schema_{db_key}", use_container_width=True):
                with st.spinner(f"Scraping {db_config.get('name', db_key)}…"):
                    schema = dbc.refresh_schema(db_key, db_config)
                st.session_state.schema_results[db_key] = schema
                st.rerun()

        with c3:
            if test_res:
                if test_res["ok"]:
                    st.success(f"✅ {test_res['lat']}s — {test_res['msg']}")
                else:
                    st.error(f"❌ {test_res['msg'][:80]}")

        with c5:
            if st.button("Disable", key=f"disable_{db_key}", use_container_width=True):
                registry = dbc.load_registry()
                registry["databases"][db_key]["enabled"] = False
                dbc.save_registry(registry)
                st.rerun()

        # Schema browser
        if has_schema:
            with st.expander(f"📋 Browse Schema — {len(schema_res.get('tables', {}))} tables, "
                             f"{len(schema_res.get('views', []))} views, "
                             f"{len(schema_res.get('procedures', []))} procedures  "
                             f"(last scraped: {schema_res.get('discovered_at', 'unknown')})"):

                tab_tables, tab_views, tab_procs = st.tabs(["Tables", "Views", "Procedures"])

                with tab_tables:
                    for table_name, table_info in schema_res.get("tables", {}).items():
                        with st.expander(f"🗃️ {table_name}  ({len(table_info['columns'])} columns)"):
                            col_df = pd.DataFrame(table_info["columns"])
                            col_df["primary_key"] = col_df["primary_key"].map({True: "🔑", False: ""})
                            col_df["nullable"]    = col_df["nullable"].map({True: "✓", False: "✗"})
                            col_df = col_df.rename(columns={
                                "name": "Column", "type": "Type",
                                "nullable": "Nullable", "primary_key": "PK"
                            })
                            st.dataframe(col_df[["Column", "Type", "PK", "Nullable"]],
                                         use_container_width=True, hide_index=True)
                            if table_info.get("foreign_keys"):
                                st.caption("Foreign Keys:")
                                for fk in table_info["foreign_keys"]:
                                    st.code(f"{fk['columns']} → {fk['references']}", language=None)

                with tab_views:
                    views = schema_res.get("views", [])
                    if views:
                        for v in views:
                            st.markdown(f"- `{v}`")
                    else:
                        st.caption("No views found.")

                with tab_procs:
                    procs = schema_res.get("procedures", [])
                    if procs:
                        for p in procs:
                            st.markdown(f"- `{p}`")
                    else:
                        st.caption("No stored procedures found.")

        st.markdown("---")

# ─────────────────────────────────────────────────────────────────────────────
# Placeholder Databases
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("🗄️ Available Database Connectors")
st.caption("Enable any of these to add it to your AI engine. Fill in your credentials in `.env` first.")

placeholder_dbs = {k: v for k, v in all_dbs.items() if not v.get("enabled")}

if placeholder_dbs:
    # Group by type
    cols = st.columns(3)
    for i, (db_key, db_config) in enumerate(placeholder_dbs.items()):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{db_config.get('name', db_key)}**")
                st.caption(f"`{db_config['type'].upper()}` — {db_config.get('description', '')}")

                if st.button("Enable & Configure", key=f"enable_{db_key}", use_container_width=True):
                    registry = dbc.load_registry()
                    registry["databases"][db_key]["enabled"] = True
                    dbc.save_registry(registry)
                    st.info(f"'{db_key}' enabled. Make sure your .env has the required credentials, then test the connection above.")
                    time.sleep(0.5)
                    st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# LLM Schema Preview
# ─────────────────────────────────────────────────────────────────────────────

st.divider()
st.subheader("🤖 LLM Schema Context Preview")
st.caption("This is exactly what gets injected into the AI's system prompt when generating SQL. Discover schemas above to populate this.")

schema_str = dbc.get_schema_for_llm()
st.code(schema_str, language="text")
