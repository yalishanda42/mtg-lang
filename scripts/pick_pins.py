"""Suggest matching lines to pin in tests/test_en_lines.py: uv run python scripts/pick_pins.py "phrase" [N]"""
import json
import re
import sys

pinned = set(re.findall(r'"([a-z0-9]+/[^"#]+#\d+\.\d+)"', open("tests/test_en_lines.py").read()))
d = json.load(open("build/eval-en/report.json"))
n = int(sys.argv[2]) if len(sys.argv) > 2 else 2
for phrase in sys.argv[1].split("|"):
    k = 0
    for r in d["lines"]:
        if r["match"] and r["field"] == "ability" and phrase in r["oracle"] and r["ref"] not in pinned:
            print(f'    "{r["ref"]}",  # {r["oracle"][:70]}')
            pinned.add(r["ref"])
            k += 1
            if k >= n:
                break
