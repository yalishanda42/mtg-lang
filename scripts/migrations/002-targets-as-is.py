"""v0.2 notation change: `◈ ◎ ♞[➹]` → `♞[➹] ∈ ◎ ◈` ("if it targets an attacking creature").

Same form as `◈ ∈ ◎ ○`; the old form had two subjects and no verb. Idempotent."""
import sys
from pathlib import Path

from mtglang.migrate import rewrite_lines, sub_tokens

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
print(rewrite_lines(root, lambda line, g: sub_tokens(line, g, "◈ ◎ ♞[➹]", "♞[➹] ∈ ◎ ◈")), "line(s) changed")
