"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  app.py — MAIN ENTRY POINT (AZURE SQL ONLY)                                  ║
║  ─────────────────────────────────────────────────────────────────────────── ║
║  Simplified entry point for Azure SQL deployment.                            ║
║                                                                              ║
║  What it does:                                                               ║
║   1. Sets up the page layout (title, icon, sidebar)                          ║
║   2. Draws the sidebar — branding, Azure SQL status                          ║
║   3. Loads the BI Dashboard page                                             ║
║                                                                              ║
║  How to run:                                                                 ║
║    streamlit run app.py --server.port 8080                                   ║
║                                                                              ║
║  File relationships:                                                         ║
║    app.py  ──►  bi_dashboard.py     (the main AI chat page)                  ║
║    Both share:  db_connector.py     (Azure SQL connector)                     ║
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

    # Azure SQL Status
    st.markdown("<div style='font-size:0.72rem; font-weight:700; color:#5f6368; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;'>Database</div>", unsafe_allow_html=True)

    # Check connection status
    try:
        is_connected = dbc.test_connection()
        status_color = "#137333" if is_connected else "#c5221f"
        status_text = "✅ Connected" if is_connected else "❌ Disconnected"
    except Exception as e:
        status_color = "#c5221f"
        status_text = "❌ Error"

    st.markdown(f"<span style='background:#e6f4ea;color:{status_color};padding:4px 12px;border-radius:20px;font-size:0.75rem;font-weight:600;'>{status_text}</span>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:0.7rem; color:#5f6368; margin-top:6px;'>Azure SQL<br/>sirish_azure_sql_db</div>", unsafe_allow_html=True)

    st.markdown("<hr style='border:none; border-top:1px solid #e8eaed; margin-bottom:4px;'>", unsafe_allow_html=True)

# ── Page definitions ─────────────────────────────────────────────────────────
dashboard_page = st.Page(
    "bi_dashboard.py",
    title="BI Dashboard",
    icon="📊",
    default=True,
)

# ── Navigation ────────────────────────────────────────────────────────────────
pg = st.navigation(
    {
        "🤖 AI Agent": [dashboard_page],
    },
    position="sidebar",
    expanded=True,
)

pg.run()