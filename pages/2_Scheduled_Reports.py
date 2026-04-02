"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  pages/2_Scheduled_Reports.py — SCHEDULED REPORTS                           ║
║  ─────────────────────────────────────────────────────────────────────────── ║
║  Lets you save SQL queries as named reports and run them on demand or on a   ║
║  Windows schedule (via the generated Task Scheduler batch file).             ║
║                                                                              ║
║  How it works:                                                               ║
║   1. You fill in a form: name, description, which domain, and the SQL.       ║
║   2. The report is saved to saved_reports.json in the project folder.        ║
║   3. Click "Run Now" → executes the query → saves Excel to reports_output/.  ║
║   4. "Generate Scheduler Script" → creates run_all_reports.bat you can add  ║
║      to Windows Task Scheduler to run automatically on any interval.         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import pandas as pd
import json
import sys
import os
import time
from io import BytesIO
from datetime import datetime
from pathlib import Path

# ── Import project modules ────────────────────────────────────────────────────
# This file lives in pages/ so the parent folder (sirish_ai/) must be on the path.
sys.path.insert(0, str(Path(__file__).parent.parent))
import db_connector as dbc

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR          = Path(__file__).parent.parent
REPORTS_FILE      = BASE_DIR / "saved_reports.json"      # Where reports are stored
REPORTS_OUTPUT    = BASE_DIR / "reports_output"           # Where Excel output files go
REPORTS_OUTPUT.mkdir(exist_ok=True)                       # Create folder if it doesn't exist

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_reports() -> list:
    """Load saved reports from JSON file. Returns empty list if file doesn't exist."""
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
    Execute a saved report's SQL query against its configured database.
    Returns {"success": bool, "data": DataFrame or None, "error": str, "file": str or None}
    """
    domain   = report["domain"]
    sql      = report["sql"]
    resolved = dbc.resolve_domain(domain)

    if not resolved:
        all_dbs = dbc.get_enabled_databases()
        db_key  = domain.lower()
        if db_key not in all_dbs:
            return {"success": False, "error": f"Domain '{domain}' not found in registry.", "data": None, "file": None}
        db_key, db_config = db_key, all_dbs[db_key]
    else:
        db_key, db_config = resolved

    # Run with a higher row limit for reports (reports often need more rows than chat)
    result = dbc.execute_query(db_key, db_config, sql, max_rows=5000)

    if result["success"]:
        # Save Excel to reports_output/
        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe  = report["name"].replace(" ", "_").replace("/", "-")
        fname = REPORTS_OUTPUT / f"{safe}_{ts}.xlsx"
        with pd.ExcelWriter(str(fname), engine="openpyxl") as w:
            result["data"].to_excel(w, index=False, sheet_name="Report")
        return {"success": True, "data": result["data"], "error": None, "file": str(fname)}
    else:
        return {"success": False, "data": None, "error": result["error"], "file": None}


# ── Page layout ───────────────────────────────────────────────────────────────

st.title("📅 Scheduled Reports")
st.caption(
    "Save SQL queries as named reports. Run them on demand or schedule them automatically "
    "via Windows Task Scheduler using the generated batch file."
)

# Session state for UI flags
if "show_add_form"   not in st.session_state: st.session_state.show_add_form   = False
if "run_results"     not in st.session_state: st.session_state.run_results     = {}

reports = load_reports()

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — stats + controls
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 📅 Scheduled Reports")
    st.caption("Manage your saved SQL reports.")
    st.divider()
    st.metric("Saved Reports", len(reports))

    output_files = list(REPORTS_OUTPUT.glob("*.xlsx"))
    st.metric("Output Files", len(output_files))

    st.divider()
    if st.button("➕ Add New Report", use_container_width=True):
        st.session_state.show_add_form = not st.session_state.show_add_form
        st.rerun()

    if st.button("▶️ Run All Reports", use_container_width=True):
        if reports:
            with st.spinner("Running all reports…"):
                for r in reports:
                    result = run_report(r)
                    st.session_state.run_results[r["name"]] = result
                    r["last_run"]  = datetime.now().isoformat()
                    r["last_file"] = result.get("file")
            save_reports(reports)
            st.success(f"Ran {len(reports)} reports.")
            st.rerun()
        else:
            st.info("No reports saved yet.")

# ══════════════════════════════════════════════════════════════════════════════
# ADD NEW REPORT FORM
# ══════════════════════════════════════════════════════════════════════════════
# WHY st.form() here?
# Without st.form(), every widget interaction (typing, selecting) triggers a full
# Streamlit rerun. When the Save button fires a rerun, the other widget values
# can be lost if they don't have explicit keys AND the form is conditionally shown.
# st.form() solves this by batching ALL widget values together and submitting them
# atomically in one shot — the values are guaranteed to be populated when the
# form_submit_button is clicked.
if st.session_state.show_add_form:
    with st.container(border=True):
        st.subheader("➕ Add New Report")
        st.caption("Fill in the form below. The SQL will be run as-is against the selected domain.")

        enabled_dbs    = dbc.get_enabled_databases()
        domain_options = [v.get("domain", k) for k, v in enabled_dbs.items() if v.get("domain")]

        # ── st.form() wraps all inputs so values are captured together on submit ──
        with st.form("add_report_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                new_name = st.text_input(
                    "Report Name *",
                    placeholder="e.g. Daily Claims Summary",
                )
                new_desc = st.text_input(
                    "Description",
                    placeholder="Short description of what this shows",
                )
            with c2:
                new_domain = st.selectbox("Database Domain *", domain_options)
                new_rows   = st.number_input(
                    "Max Rows", min_value=100, max_value=50000, value=5000, step=500,
                    help="Row cap for this report. Reports allow more rows than the chat interface.",
                )

            new_sql = st.text_area(
                "SQL Query *",
                height=120,
                placeholder=(
                    "SELECT ProviderName, COUNT(*) AS Claims, SUM(BilledAmount) AS Total\n"
                    "FROM Claims\n"
                    "GROUP BY ProviderName\n"
                    "ORDER BY Total DESC"
                ),
            )

            # Frequency selector (used when scheduling via Task Scheduler)
            new_frequency = st.selectbox(
                "Run Frequency",
                ["On Demand", "Daily", "Weekly (Mon)", "Monthly (1st)"],
                help="This is saved with the report. Use it when generating the Task Scheduler batch file.",
            )

            # Submit buttons — both live inside the form
            b1, b2, _ = st.columns([1, 1, 4])
            with b1:
                submitted = st.form_submit_button("💾 Save Report", type="primary")
            with b2:
                cancelled = st.form_submit_button("Cancel")

        # ── Handle form result OUTSIDE the form block ─────────────────────────
        # (Streamlit evaluates form_submit_button results after the with block closes)
        if submitted:
            if new_name and new_sql and new_domain:
                reports.append({
                    "name":        new_name.strip(),
                    "description": new_desc.strip(),
                    "domain":      new_domain.upper(),
                    "sql":         new_sql.strip(),
                    "max_rows":    int(new_rows),
                    "frequency":   new_frequency,
                    "created_at":  datetime.now().isoformat(),
                    "last_run":    None,
                    "last_file":   None,
                })
                save_reports(reports)
                st.session_state.show_add_form = False
                st.success(f"✅ Report '{new_name}' saved!")
                time.sleep(0.4)
                st.rerun()
            else:
                st.error("⚠️ Report Name, SQL Query, and Domain are all required fields (marked with *).")

        if cancelled:
            st.session_state.show_add_form = False
            st.rerun()

    st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# SAVED REPORTS LIST
# ══════════════════════════════════════════════════════════════════════════════
if not reports:
    st.info("No reports saved yet. Click **➕ Add New Report** in the sidebar to get started.")
else:
    st.subheader(f"📋 Saved Reports ({len(reports)})")

    for i, report in enumerate(reports):
        run_res = st.session_state.run_results.get(report["name"])

        with st.container(border=True):
            # Header row
            col_title, col_domain, col_status = st.columns([3, 1, 2])
            with col_title:
                st.markdown(f"**{report['name']}**")
                if report.get("description"):
                    st.caption(report["description"])
            with col_domain:
                st.markdown(
                    f"<span style='background:#e8f0fe;color:#1a73e8;padding:3px 10px;"
                    f"border-radius:20px;font-size:0.78rem;font-weight:600'>"
                    f"{report['domain']}</span>",
                    unsafe_allow_html=True
                )
            with col_status:
                if report.get("last_run"):
                    # Format the ISO timestamp into a readable string
                    last = report["last_run"][:16].replace("T", " ")
                    st.caption(f"Last run: {last}")
                else:
                    st.caption("Never run")

            # SQL preview
            with st.expander("🔍 View SQL"):
                st.code(report["sql"], language="sql")

            # Action buttons
            btn1, btn2, btn3, _ = st.columns([1, 1, 1, 3])

            with btn1:
                if st.button("▶️ Run Now", key=f"run_{i}", use_container_width=True):
                    with st.spinner(f"Running '{report['name']}'…"):
                        res = run_report(report)
                        st.session_state.run_results[report["name"]] = res
                        reports[i]["last_run"]  = datetime.now().isoformat()
                        reports[i]["last_file"] = res.get("file")
                    save_reports(reports)
                    st.rerun()

            with btn2:
                # Show download button if a previous result is available
                if report.get("last_file") and Path(report["last_file"]).exists():
                    with open(report["last_file"], "rb") as fh:
                        st.download_button(
                            label="📥 Download",
                            data=fh.read(),
                            file_name=Path(report["last_file"]).name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"dl_{i}",
                            use_container_width=True,
                        )
                else:
                    st.button("📥 Download", disabled=True, key=f"dl_dis_{i}", use_container_width=True)

            with btn3:
                if st.button("🗑️ Delete", key=f"del_{i}", use_container_width=True):
                    reports.pop(i)
                    save_reports(reports)
                    st.rerun()

            # Show run result inline if just executed
            if run_res:
                if run_res["success"] and run_res["data"] is not None:
                    st.success(f"✅ Ran successfully — {len(run_res['data'])} rows. Saved to `reports_output/`.")
                    st.dataframe(run_res["data"].head(20), use_container_width=True)
                    st.download_button(
                        label="📥 Download this result",
                        data=df_to_excel_bytes(run_res["data"]),
                        file_name=f"{report['name'].replace(' ','_')}_latest.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"dl_inline_{i}",
                    )
                else:
                    st.error(f"❌ Failed: {run_res.get('error', 'Unknown error')}")

# ══════════════════════════════════════════════════════════════════════════════
# WINDOWS TASK SCHEDULER GENERATOR
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
st.subheader("⏰ Windows Task Scheduler Setup")
st.caption(
    "Generate a batch file you can add to Windows Task Scheduler to run all reports automatically."
)

if reports:
    col_time, col_gen = st.columns([2, 2])
    with col_time:
        run_time = st.time_input("Default run time", value=None, help="The time of day Task Scheduler will fire the batch file.")

    with col_gen:
        st.write("")
        st.write("")
        if st.button("⚙️ Generate Batch File", use_container_width=True):
            # Summarise frequencies from the saved reports
            freq = ", ".join(sorted({r.get("frequency", "On Demand") for r in reports}))
            python_exe = sys.executable
            script_path = BASE_DIR / "run_all_reports.py"

            # Write the runner script that Task Scheduler will call
            runner_content = f'''"""
run_all_reports.py — called by Windows Task Scheduler
Runs all saved reports and saves Excel output to reports_output/
Generated by the Scheduled Reports page on {datetime.now().strftime("%Y-%m-%d")}
"""
import json, sys
from pathlib import Path
from datetime import datetime
import pandas as pd

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
import db_connector as dbc

REPORTS_FILE   = BASE_DIR / "saved_reports.json"
REPORTS_OUTPUT = BASE_DIR / "reports_output"
REPORTS_OUTPUT.mkdir(exist_ok=True)

reports = json.loads(REPORTS_FILE.read_text(encoding="utf-8")) if REPORTS_FILE.exists() else []

for report in reports:
    print(f"Running: {{report['name']}}...")
    domain   = report["domain"]
    sql      = report["sql"]
    max_rows = report.get("max_rows", 5000)

    resolved = dbc.resolve_domain(domain)
    if not resolved:
        all_dbs = dbc.get_enabled_databases()
        db_key, db_config = domain.lower(), all_dbs.get(domain.lower(), {{}})
    else:
        db_key, db_config = resolved

    result = dbc.execute_query(db_key, db_config, sql, max_rows=max_rows)

    if result["success"]:
        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe  = report["name"].replace(" ", "_").replace("/", "-")
        fname = REPORTS_OUTPUT / f"{{safe}}_{{ts}}.xlsx"
        result["data"].to_excel(str(fname), index=False, engine="openpyxl")
        report["last_run"]  = datetime.now().isoformat()
        report["last_file"] = str(fname)
        print(f"  ✅ Saved {{len(result['data'])}} rows to {{fname}}")
    else:
        print(f"  ❌ Error: {{result['error']}}")

# Save updated last_run timestamps
REPORTS_FILE.write_text(json.dumps(reports, indent=2, default=str), encoding="utf-8")
print("Done.")
'''
            script_path.write_text(runner_content, encoding="utf-8")

            # Write the .bat file
            bat_content = f"""@echo off
REM ─────────────────────────────────────────────────────
REM  Auto-generated by Multi-Agent BI Engine
REM  Runs all saved reports and exports to Excel
REM  Frequency: {freq}
REM ─────────────────────────────────────────────────────
echo Running BI Engine reports...
cd /d {BASE_DIR}
"{python_exe}" run_all_reports.py >> reports_output\\run_log.txt 2>&1
echo Done.
"""
            bat_path = BASE_DIR / "run_all_reports.bat"
            bat_path.write_text(bat_content, encoding="utf-8")

            st.success("✅ Generated `run_all_reports.py` and `run_all_reports.bat`")
            st.info(
                "**To schedule in Windows:**\n"
                "1. Press **Win + R**, type `taskschd.msc`, press Enter\n"
                "2. Click **Create Basic Task**\n"
                f"3. Set trigger: {freq}\n"
                f"4. Action: Start a program → browse to `run_all_reports.bat`\n"
                "5. Click Finish"
            )
else:
    st.info("Add at least one report above before generating a schedule.")
