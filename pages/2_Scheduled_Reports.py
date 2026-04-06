"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  pages/2_Scheduled_Reports.py — SCHEDULED REPORTS (Azure SQL Only)          ║
║  ─────────────────────────────────────────────────────────────────────────── ║
║  Save SQL queries as named reports and run them on demand.                   ║
║                                                                              ║
║  How it works:                                                               ║
║   1. Fill in a form: name, description, and the SQL query.                  ║
║   2. The report is saved to saved_reports.json in the project folder.        ║
║   3. Click "Run Now" → executes the query → saves Excel to reports_output/.  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import pandas as pd
import json
import sys
from io import BytesIO
from datetime import datetime
from pathlib import Path

# ── Import Azure SQL connector ────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
import db_connector as dbc

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).parent.parent
REPORTS_FILE   = BASE_DIR / "saved_reports.json"
REPORTS_OUTPUT = BASE_DIR / "reports_output"
REPORTS_OUTPUT.mkdir(exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_reports() -> list:
    """Load saved reports from JSON file."""
    if REPORTS_FILE.exists():
        with open(REPORTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []

def save_reports(reports: list):
    """Write the full reports list back to the JSON file."""
    with open(REPORTS_FILE, "w", encoding="utf-8") as f:
        json.dump(reports, f, indent=2, default=str)

def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    """Convert DataFrame to Excel bytes for the download button."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Report")
    return buf.getvalue()

def run_report(report: dict) -> dict:
    """
    Execute a saved report's SQL query against Azure SQL.
    Returns {"success": bool, "data": DataFrame or None, "error": str, "file": str or None}
    """
    sql = report["sql"]
    try:
        result_df = dbc.execute_query(sql, max_rows=5000)
        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe  = report["name"].replace(" ", "_").replace("/", "-")
        fname = REPORTS_OUTPUT / f"{safe}_{ts}.xlsx"
        with pd.ExcelWriter(str(fname), engine="openpyxl") as w:
            result_df.to_excel(w, index=False, sheet_name="Report")
        return {"success": True, "data": result_df, "error": None, "file": str(fname)}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e), "file": None}

# ── Page layout ───────────────────────────────────────────────────────────────

st.title("📅 Scheduled Reports")
st.caption("Save SQL queries as named reports and run them on demand against Azure SQL.")

# Session state
if "show_add_form" not in st.session_state:
    st.session_state.show_add_form = False
if "run_results" not in st.session_state:
    st.session_state.run_results = {}

# ── Add New Report ────────────────────────────────────────────────────────────

col_hdr, col_btn = st.columns([6, 2])
with col_hdr:
    st.subheader("📋 Saved Reports")
with col_btn:
    if st.button("➕ Add Report", use_container_width=True):
        st.session_state.show_add_form = not st.session_state.show_add_form

if st.session_state.show_add_form:
    with st.form("add_report_form", clear_on_submit=True):
        st.markdown("#### New Report")
        report_name = st.text_input("Report Name *", placeholder="e.g. Daily Claims Summary")
        report_desc = st.text_area("Description", placeholder="What does this report show?", height=60)
        report_sql  = st.text_area("SQL Query *", placeholder="SELECT TOP 100 * FROM Claims", height=120)

        submitted = st.form_submit_button("💾 Save Report")
        if submitted:
            if not report_name.strip():
                st.error("Report name is required.")
            elif not report_sql.strip():
                st.error("SQL query is required.")
            else:
                reports = load_reports()
                reports.append({
                    "id":          len(reports) + 1,
                    "name":        report_name.strip(),
                    "description": report_desc.strip(),
                    "sql":         report_sql.strip(),
                    "created_at":  datetime.now().isoformat(),
                    "last_run":    None,
                })
                save_reports(reports)
                st.session_state.show_add_form = False
                st.success(f"✅ Report '{report_name}' saved!")
                st.rerun()

# ── Report List ───────────────────────────────────────────────────────────────

reports = load_reports()

if not reports:
    st.info("No reports yet. Click ➕ Add Report to create one.")
else:
    for i, report in enumerate(reports):
        with st.expander(f"📄 {report['name']}", expanded=False):
            st.markdown(f"**Description:** {report.get('description', '—')}")
            st.markdown(f"**Created:** {report.get('created_at', '—')[:10]}")
            if report.get("last_run"):
                st.markdown(f"**Last Run:** {report['last_run'][:19]}")

            st.code(report["sql"], language="sql")

            col_run, col_del = st.columns([1, 1])

            with col_run:
                if st.button("▶️ Run Now", key=f"run_{i}", use_container_width=True):
                    with st.spinner("Running query..."):
                        result = run_report(report)
                        st.session_state.run_results[i] = result
                        if result["success"]:
                            reports[i]["last_run"] = datetime.now().isoformat()
                            save_reports(reports)

            with col_del:
                if st.button("🗑️ Delete", key=f"del_{i}", use_container_width=True):
                    reports.pop(i)
                    save_reports(reports)
                    st.rerun()

            # Show results if run
            if i in st.session_state.run_results:
                result = st.session_state.run_results[i]
                if result["success"]:
                    df = result["data"]
                    st.success(f"✅ {len(df)} rows returned")
                    st.dataframe(df, use_container_width=True)
                    st.download_button(
                        label="📥 Download Excel",
                        data=df_to_excel_bytes(df),
                        file_name=f"{report['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"dl_{i}"
                    )
                else:
                    st.error(f"❌ {result['error']}")
