"""v0.2 notation change: `(○ ✷ ✦ ∨ ○ ⊳ ▣)[ⁿ = ☞]` → `○ ✷ ✦[ⁿ = ☞] ∨ ○ ⊳ ▣[ⁿ = ☞]`.

A filter applies to a phrase, not to a pair of clauses; it now sits on each alternative's object. Idempotent."""
import sys
from pathlib import Path

from mtglang.migrate import rewrite_lines, sub_tokens

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
print(rewrite_lines(root, lambda line, g: sub_tokens(line, g, "(○ ✷ ✦ ∨ ○ ⊳ ▣)[ⁿ = ☞]", "○ ✷ ✦[ⁿ = ☞] ∨ ○ ⊳ ▣[ⁿ = ☞]")), "line(s) changed")
