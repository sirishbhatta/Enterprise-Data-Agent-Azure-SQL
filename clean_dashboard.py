import re
import os

path = r"C:\Users\siris\.gemini\tmp\sirish-ai\azure-worktree-temp\bi_dashboard.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove vector memory imports
content = re.sub(r'import psycopg2.*?\n', '', content)
content = re.sub(r'import pyodbc.*?\n', '', content)
content = re.sub(r'import ollama.*?\n', '', content)

# 2. Remove vector memory functions
content = re.sub(r'def get_sql_connection\(\):.*?(?=# Initialize session state)', '', content, flags=re.DOTALL)

# 3. Clean up supervisor_routing memory usage
content = re.sub(r'    memory, _ = check_vector_memory\(user_question\)\n    memory_hint = .*? if memory else ""\n', '', content)
content = re.sub(r'    \{memory_hint\}', '', content)

# 4. Clean up agent_execution
agent_exec_new = """def agent_execution(user_question, domain, history_str, model):
    context = ACTIVE_SCHEMA
    format_req = '{ "explanation": "...", "sql_query": "..." }'

    system_prompt = f\"\"\"Senior Data Architect. Context: {context}
    Return JSON ONLY: {format_req}\"\"\"
    
    cascade = [model, "gemini-2.5-flash", "claude-sonnet-4-6"]
    models_to_try = list(dict.fromkeys(cascade))
    escalation_log = []

    for current_model in models_to_try:
        with st.status(f"✨ Agent: {current_model}...", expanded=False) as status:
            try:
                raw_res = generate_ai_response(current_model, system_prompt, f"History: {history_str}\\nQuestion: {user_question}")
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
"""
content = re.sub(r'def agent_execution\(user_question, domain, history_str, model\):.*?(?=def format_model_label)', agent_exec_new, content, flags=re.DOTALL)

# 5. Remove federated join configs
content = re.sub(r'# ── FEDERATED join configurations ──.*?(?=# --- 4\. UNIFIED AI ROUTER ---)', '', content, flags=re.DOTALL)

# 6. Remove vector memory UI from sidebar
content = re.sub(r'    memory_count = get_vector_memory_count\(\)\n.*?</div>\', unsafe_allow_html=True\)\n', '', content, flags=re.DOTALL)

# 7. Remove UI columns for memory in chat loop
content = re.sub(r'            c4\.metric\("📚 Memory Assist", f"\{msg\[\'metadata\'\]\.get\(\'memory_ratio\', 0\):\.1f\}% Match" if msg\["metadata"\]\.get\("memory_used"\) else "None"\)\n', '', content)
content = re.sub(r'            confidence_label = "Memory Hit" if msg\["metadata"\].get\("memory_used"\) else \("1st Try ✓" if escalations == 0 else f"After \{escalations\} retries"\)', '            confidence_label = "1st Try ✓" if escalations == 0 else f"After {escalations} retries"', content)
content = re.sub(r'            c1, c2, c3, c4 = st\.columns\(4\)', '            c1, c2, c3 = st.columns(3)', content)

# 8. Remove UI columns for memory in execution result
content = re.sub(r'            memory_used = result\.get\("memory_used", False\)\n            memory_ratio = result\.get\("memory_ratio", 0\)\n', '', content)
content = re.sub(r'            c4\.metric\("📚 Memory Assist", f"\{memory_ratio:\.1f\}% Match" if memory_used else "None"\)\n', '', content)
content = re.sub(r'            confidence_label = "Memory Hit" if memory_used else \("1st Try ✓" if escalations == 0 else f"After \{escalations\} retries"\)', '            confidence_label = "1st Try ✓" if escalations == 0 else f"After {escalations} retries"', content)
content = re.sub(r'            c1, c2, c3, c4 = st\.columns\(4\)', '            c1, c2, c3 = st.columns(3)', content)
content = re.sub(r'                    "memory_used":      memory_used,\n                    "memory_ratio":     memory_ratio,\n', '', content)

# 9. Remove save_vector_memory feedback loop
feedback_code = """        if msg["role"] == "assistant" and "metadata" in msg:
            feedback_key = f"fb_{i}"
            feedback = st.feedback("thumbs", key=feedback_key)"""
content = re.sub(r'        if msg\["role"\] == "assistant" and "metadata" in msg:\n            feedback_key = f"fb_\{i\}"\n            feedback = st\.feedback\("thumbs", key=feedback_key\).*?(?=    if msg\["role"\] == "assistant":)', feedback_code + '\n\n', content, flags=re.DOTALL)

# 10. Update SCHEMA_FALLBACK
schema_fb = """_SCHEMA_FALLBACK = (
    "[AZURE_CLAIMS | Azure SQL Claims | MSSQL]\\n"
    "  Table Claims: ClaimID* (INTEGER), MemberID (VARCHAR), ServiceDate (DATE), ProviderName (VARCHAR), "
    "DiagnosisCode (VARCHAR), ProcedureCode (VARCHAR), BilledAmount (DECIMAL), PaidAmount (DECIMAL), ClaimStatus (VARCHAR)\\n"
    "  Table ProviderClaimSummary: ProviderName (VARCHAR), TotalBilled (DECIMAL), TotalPaid (DECIMAL), DeniedClaims (INT)"
)"""
content = re.sub(r'_SCHEMA_FALLBACK = \(.*?\)', schema_fb, content, flags=re.DOTALL)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
