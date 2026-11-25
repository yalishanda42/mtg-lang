"""v0.2 notation change: `● ? ◈ ❐ (⚙ ∨ ♞)[▦] ∧ ¬⚜` → `● ? (◈ ❐ (⚙ ∨ ♞)[▦] ∧ ¬⚜)` ("you may have this enter as a copy …").

"You may have X do Y": the group gives ● a body with its own subject, like `◎○ ? (● ⤓1)`. Idempotent."""
import sys
from pathlib import Path

from mtglang.migrate import rewrite_lines, sub_tokens

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
print(rewrite_lines(root, lambda line, g: sub_tokens(line, g, "● ? ◈ ❐ (⚙ ∨ ♞)[▦] ∧ ¬⚜", "● ? (◈ ❐ (⚙ ∨ ♞)[▦] ∧ ¬⚜)")), "line(s) changed")
