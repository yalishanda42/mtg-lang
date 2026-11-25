"""List eval-en mismatches from build/eval-en/report.json: uv run python scripts/mism.py [cause-substring] [N] [text]"""
import json
import sys

cause = sys.argv[1] if len(sys.argv) > 1 else ""
n = int(sys.argv[2]) if len(sys.argv) > 2 else 30
text = sys.argv[3] if len(sys.argv) > 3 else ""
d = json.load(open("build/eval-en/report.json"))
k = 0
for r in d["lines"]:
    if r["match"] or cause not in (r["cause"] or "") or r["field"] != "ability":
        continue
    if text and text not in r["oracle"] and text not in r["rendered"] and text not in r["notation"]:
        continue
    print(f"{r['ref']}  [{r['cause']}]\n   N {r['notation']}\n   R {r['rendered']}\n   O {r['oracle']}")
    k += 1
    if k >= n:
        break
