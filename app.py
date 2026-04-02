"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  app.py — MAIN ENTRY POINT                                                   ║
║  ─────────────────────────────────────────────────────────────────────────── ║
║  This is the FIRST file Streamlit runs. Think of it as the "front door"      ║
║  of the whole application.                                                   ║
║                                                                              ║
║  What it does:                                                               ║
║   1. Sets up the page layout (title, icon, sidebar)                          ║
║   2. Draws the sidebar — branding, DB status pills, navigation links         ║
║   3. Defines which pages exist (BI Dashboard + Connection Manager)           ║
║   4. Hands off to whichever page the user clicked                            ║
║                                                                              ║
║  How to run:                                                                 ║
║    streamlit run app.py --server.port 8502                                   ║
║                                                                              ║
║  File relationships:                                                         ║
║    app.py  ──►  bi_dashboard.py        (the main AI chat page)               ║
║            ──►  pages/1_Connection_Manager.py  (DB settings page)            ║
║    Both pages share:  db_connector.py  (the database brain)                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import sys
from pathlib import Path

# sys.path.insert tells Python WHERE to look for modules.
# Without this, "import db_connector" would fail because Python doesn't
# automatically search the current project folder in all configurations.
sys.path.insert(0, str(Path(__file__).parent))
import db_connector as dbc

# ── Single page config for the whole app ─────────────────────────────────────
# IMPORTANT: st.set_page_config must be the VERY FIRST Streamlit call.
# It can only be called ONCE — that's why it lives here in app.py and
# NOT in the sub-pages. Setting it here applies it to all pages.
st.set_page_config(
    page_title="BI Engine — Sirish Bhatta",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar branding ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding: 18px 4px 8px 4px;">
        <div style="font-size:1.35rem; font-weight:800; color:#1a73e8; letter-spacing:-0.5px;">
            ✨ Multi-Agent BI
        </div>
        <div style="font-size:0.78rem; color:#5f6368; margin-top:3px;">
            by <b>Sirish Bhatta</b>
        </div>
    </div>
    <hr style="border:none; border-top:1px solid #e8eaed; margin: 8px 0 16px 0;">
        <style>
        /* Make navigation items look like obvious clickable buttons instead of text labels */
        [data-testid="stSidebarNavItems"] a {
            border: 1px solid #dadce0 !important;
            border-radius: 8px !important;
            background-color: #f8f9fa !important;
            margin: 0px 10px 8px 10px !important;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
            transition: all 0.2s ease-in-out !important;
        }
        [data-testid="stSidebarNavItems"] a:hover {
            background-color: #ffffff !important;
            border-color: #1a73e8 !important;
            box-shadow: 0 3px 6px rgba(26,115,232,0.1) !important;
            transform: translateY(-1px) !important;
        }
        [data-testid="stSidebarNavItems"] a[aria-current="page"] {
            background-color: #e8f0fe !important;
            border-color: #1a73e8 !important;
            border-left: 5px solid #1a73e8 !important;
            font-weight: 700 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Live DB status pills — read directly from db_registry.yaml so they
    # always reflect the current state without any manual updates needed.
    enabled_dbs = dbc.get_enabled_databases()
    if enabled_dbs:
        st.markdown("<div style='font-size:0.72rem; font-weight:700; color:#5f6368; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;'>Active Databases</div>", unsafe_allow_html=True)
        db_type_colors = {
            "postgresql": ("#e8f0fe", "#1a73e8"),
            "mssql":      ("#fce8e6", "#c5221f"),
            "oracle":     ("#fef3e2", "#e37400"),
            "mysql":      ("#e6f4ea", "#137333"),
            "sqlite":     ("#f3e8fd", "#7b1fa2"),
            "duckdb":     ("#e8f5e9", "#2e7d32"),
            "snowflake":  ("#e3f2fd", "#1565c0"),
            "bigquery":   ("#e8f0fe", "#4285f4"),
        }
        pills_html = ""
        for db_key, db_cfg in enabled_dbs.items():
            db_type = db_cfg.get("type", "db")
            bg, fg  = db_type_colors.get(db_type, ("#f1f3f4", "#3c4043"))
            label   = db_cfg.get("name", db_key)
            pills_html += f"<span style='background:{bg};color:{fg};padding:3px 9px;border-radius:20px;font-size:0.72rem;font-weight:600;margin:2px 2px;display:inline-block;'>{label}</span>"
        st.markdown(f"<div style='margin-bottom:14px;line-height:2'>{pills_html}</div>", unsafe_allow_html=True)

    st.markdown("<hr style='border:none; border-top:1px solid #e8eaed; margin-bottom:4px;'>", unsafe_allow_html=True)

# ── Page definitions ─────────────────────────────────────────────────────────
# st.Page() registers a Python file as a navigable page.
# default=True means this page loads when the app first opens.
dashboard_page = st.Page(
    "bi_dashboard.py",
    title="BI Dashboard",
    icon="📊",
    default=True,
)

connection_page = st.Page(
    "pages/1_Connection_Manager.py",
    title="Connection Manager",
    icon="🔌",
)

reports_page = st.Page(
    "pages/2_Scheduled_Reports.py",
    title="Scheduled Reports",
    icon="📅",
)

# ── Navigation ────────────────────────────────────────────────────────────────
# st.navigation() builds the sidebar menu. Pages are grouped under section
# headers ("🤖 AI Agent", "⚙️ Settings"). When the user clicks a link,
# Streamlit re-runs this script and pg.run() executes the selected page file.
pg = st.navigation(
    {
        "🤖 AI Agent": [dashboard_page],
        "⚙️ Settings": [connection_page, reports_page],
    },
    position="sidebar",
    expanded=True,
)

pg.run()  # Execute whichever page the user navigated to