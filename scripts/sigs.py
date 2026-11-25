"""Top mismatch groups (cause + first differing tokens): uv run python scripts/sigs.py [N]"""
import json
import sys
from collections import Counter

from mtglang.evalen import LineResult, _signature

n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
d = json.load(open("build/eval-en/report.json"))
c = Counter()
ex = {}
for r in d["lines"]:
    if r["match"] or r["field"] != "ability":
        continue
    lr = LineResult(**r)
    if lr.cause.startswith("gap:"):
        import re
        m = re.search(r"⟦([^⟧]*)⟧", lr.rendered)
        sig = f"{lr.cause} {m.group(1) if m else ''}"
    else:
        sig = f"{lr.cause} {_signature(lr)}"
    c[sig] += 1
    ex.setdefault(sig, lr.ref)
for sig, k in c.most_common(n):
    print(f"{k:4}  {sig}   e.g. {ex[sig]}")
