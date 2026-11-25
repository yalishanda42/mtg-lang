"""v0.2 notation change: `◌[«Planet» ⛰]↷ «New Planet»` → `◌[«Planet» ⛰] «New Planet»↷`.

The name belongs to the token phrase; after `↷` it read as the thing being tapped. Idempotent."""
import sys
from pathlib import Path

from mtglang.migrate import rewrite_lines, sub_tokens

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
print(rewrite_lines(root, lambda line, g: sub_tokens(line, g, "◌[«Planet» ⛰]↷ «New Planet»", "◌[«Planet» ⛰] «New Planet»↷")), "line(s) changed")
