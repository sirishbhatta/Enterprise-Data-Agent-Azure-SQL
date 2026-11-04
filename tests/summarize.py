"""
Summarize logs/eval_results.jsonl: pass rate per model and split, average time,
the most common failure reasons, and the failed questions.   Usage:  python tests/summarize.py
"""
import collections
import json
import os

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "eval_results.jsonl")
rows = [json.loads(l) for l in open(PATH, encoding="utf-8")]
by_model = collections.defaultdict(collections.Counter)
for r in rows:
    split = "held" if r["held_out"] else "dev"
    by_model[r["model"]][f"{split}_total"] += 1
    by_model[r["model"]][f"{split}_pass"] += int(r["ok"])
    by_model[r["model"]]["secs"] += r["seconds"]
    by_model[r["model"]]["n"] += 1

print("MODEL                   DEV          HELD-OUT     AVG SEC/Q")
for m, c in by_model.items():
    print(f"{m:<23} {c['dev_pass']}/{c['dev_total']:<10} {c['held_pass']}/{c['held_total']:<10} {c['secs']/max(c['n'],1):.1f}")

print("\nMOST COMMON FAILURE REASONS")
reasons = collections.Counter((r["model"], r["reason"][:80]) for r in rows if not r["ok"])
for (m, reason), n in reasons.most_common(15):
    print(f"  {n:>3}  {m:<22} {reason}")

print("\nFAILED QUESTIONS")
for r in rows:
    if not r["ok"]:
        print(f"  {r['model']:<22} {r['id']:<12} {r['reason'][:90]}")
