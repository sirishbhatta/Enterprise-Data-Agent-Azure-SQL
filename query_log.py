"""Append one JSON line per question so failures can be turned into tests later."""
import json
import os
from datetime import datetime

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "query_log.jsonl")


def log_query(question, domain, model, result, seconds):
    """result is the dict from agent_execution, or None if every model failed."""
    result = result or {}
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "question": question,
        "domain": domain,
        "model": model,
        "ok": bool(result.get("df") is not None and not result.get("error")),
        "rows": len(result["df"]) if result.get("df") is not None else 0,
        "sql": result.get("sql", ""),
        "error": result.get("error", ""),
        "attempts": [e.get("model") for e in result.get("escalation_log", [])],
        "seconds": round(seconds, 2),
    }
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")
