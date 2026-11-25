"""v0.2 notation change 1: "you get an emblem" gets a verb — `● ✪ ∋ (…)` → `● ✚ ✪ ∋ (…)`.

Without a verb the clause had two subjects (● and ✪) and no predicate. Idempotent."""
import sys
from pathlib import Path

from mtglang.migrate import rewrite_lines, sub_tokens

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
print(rewrite_lines(root, lambda line, g: sub_tokens(line, g, "● ✪ ∋", "● ✚ ✪ ∋")), "line(s) changed")
