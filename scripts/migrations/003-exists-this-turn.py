"""v0.2 notation change: `▣[▦ → ☚●] ◷` → `∃▣[▦ → ☚● ◷]` ("if a permanent was returned … this turn").

A bare phrase plus a time is not a condition; ∃ with the time inside the filter is, as in `∃♞☠◷`. Idempotent."""
import sys
from pathlib import Path

from mtglang.migrate import rewrite_lines, sub_tokens

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
print(rewrite_lines(root, lambda line, g: sub_tokens(line, g, "▣[▦ → ☚●] ◷", "∃▣[▦ → ☚● ◷]")), "line(s) changed")
