"""
Test local models on tests/questions.yaml.

For each model and question: ask the model for SQL from the schema, run it,
and check the row count and column names. Results are printed as a table and
appended to logs/eval_results.jsonl.

Usage (from the project folder):
    python tests/run_evals.py --models a,b,c          # all questions, one model after another
    python tests/run_evals.py --models qwen2.5-coder:7b
    python tests/run_evals.py --held-out               # only held-out questions
    python tests/run_evals.py --dev                    # only development questions

Note: this uses a shorter prompt than the app, so the numbers compare models
with each other. They are not an exact copy of what the app does.
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

import ollama
import yaml
from reference_sql import REFERENCE

client = ollama.Client(timeout=300)  # 5 minutes per request, then move on

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
import db_connector as dbc  # noqa: E402

DEFAULT_MODELS = ["qwen2.5-coder:7b", "gemma4:12b", "qwen2.5-coder:14b"]
QUESTIONS_PATH = os.path.join(ROOT, "tests", "questions.yaml")
RESULTS_PATH = os.path.join(ROOT, "logs", "eval_results.jsonl")

SYSTEM = (
    "You write one SQL SELECT statement for the database described below. "
    "Use only the tables and columns listed, copied exactly as written (same spelling, underscores, and capitalization). Never invent or shorten a name. Output only the SQL, with no explanation.\n\n"
)


def extract_sql(text):
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", text, re.S | re.I)
    sql = fenced.group(1) if fenced else text
    # Drop the trailing semicolon: Oracle rejects it when the query is wrapped for row limits.
    return sql.strip().rstrip(";").strip()


def ask_model(model, schema, question, dialect=""):
    res = client.generate(model=model, system=SYSTEM + dialect + schema,
                          prompt=question, options={"temperature": 0})
    return extract_sql(res["response"])


def check(q, sql):
    """Return (passed, reason)."""
    resolved = dbc.resolve_domain(q["domain"])
    if not resolved:
        return False, f"no database for domain {q['domain']}"
    db_key, cfg = resolved
    result = dbc.execute_query(db_key, cfg, sql)
    if not result.get("success"):
        return False, "SQL error: " + str(result.get("error", ""))[:150]
    df = result["data"]
    if len(df) < q.get("expect_min_rows", 0):
        return False, f"{len(df)} rows, expected at least {q['expect_min_rows']}"
    cols = {c.lower() for c in df.columns}
    missing = [c for c in q.get("must_have_columns", []) if c.lower() not in cols]
    if missing:
        return False, f"missing columns: {', '.join(missing)}"
    ref = REFERENCE.get(q["question"])
    if ref:
        ok, reason = check_against_reference(df, ref)
        if not ok:
            return False, reason
    return True, "ok"


def _values(df):
    """Every cell as a rounded number or a stripped string, so types and column names don't matter."""
    out = []
    for row in df.itertuples(index=False):
        for v in row:
            try:
                out.append(round(float(v), 2))
            except (TypeError, ValueError):
                out.append(str(v).strip())
    return out


def check_against_reference(df, ref):
    """Every value in the reference result must appear in the model's result."""
    ref_domain, ref_sql = ref
    resolved = dbc.resolve_domain(ref_domain)
    if not resolved:
        return False, f"reference: no database for {ref_domain}"
    db_key, cfg = resolved
    ref_res = dbc.execute_query(db_key, cfg, ref_sql)
    if not ref_res.get("success"):
        return False, "reference SQL error: " + str(ref_res.get("error", ""))[:120]
    model_vals = _values(df)
    missing = [v for v in _values(ref_res["data"]) if v not in model_vals]
    if missing:
        return False, f"values differ from reference (missing {missing[:3]})"
    return True, "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--held-out", action="store_true", help="run only held-out questions")
    ap.add_argument("--dev", action="store_true", help="run only development questions")
    ap.add_argument("--only", help="run one question by id, e.g. sales_top_customers")
    args = ap.parse_args()

    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        questions = yaml.safe_load(f)
    if args.only:  # --only ignores the held-out split so any single question can be rerun
        questions = [q for q in questions if q["id"] == args.only]
    elif args.held_out:
        questions = [q for q in questions if q.get("held_out")]
    elif args.dev:
        questions = [q for q in questions if not q.get("held_out")]
    schema = dbc.get_schema_for_llm()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)

    summary = {}
    with open(RESULTS_PATH, "a", encoding="utf-8") as log:
        for model in models:
            passed, secs = 0, 0.0
            print(f"\n== {model} ==")
            for q in questions:
                t0 = time.time()
                try:
                    resolved = dbc.resolve_domain(q["domain"])
                    dialect = dbc.dialect_note(resolved[1]["type"]) + "\n\n" if resolved else ""
                    sql = ask_model(model, schema, q["question"], dialect)
                    ok, reason = check(q, sql)
                except Exception as e:  # model not installed, Ollama down, etc.
                    sql, ok, reason = "", False, f"model error: {e}"
                elapsed = time.time() - t0
                secs += elapsed
                passed += ok
                print(f"  {'PASS' if ok else 'FAIL'}  {q['id']:<24} {elapsed:5.1f}s  {reason}")
                log.write(json.dumps({
                    "ts": datetime.now().isoformat(timespec="seconds"), "model": model,
                    "id": q["id"], "held_out": bool(q.get("held_out")), "ok": ok,
                    "reason": reason, "sql": sql, "seconds": round(elapsed, 2),
                }) + "\n")
            summary[model] = (passed, len(questions), secs / max(len(questions), 1))

    print("\nSUMMARY")
    for model, (p, n, avg) in summary.items():
        print(f"  {model:<22} {p}/{n} passed   avg {avg:.1f}s per question")


if __name__ == "__main__":
    main()
