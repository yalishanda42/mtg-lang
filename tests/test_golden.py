"""Golden files: resolved ASTs of 20 sample cards, each checked by hand against its Oracle text.

Regenerate after an intended change with  MTGLANG_UPDATE_GOLDEN=1 uv run pytest tests/test_golden.py
and review the diff before committing."""
import json
import os
from pathlib import Path

import pytest

from mtglang.ast import to_json
from mtglang.astexport import card_ast

ROOT = Path(__file__).parent.parent
GOLDEN = Path(__file__).parent / "golden"
CARDS = ["fra/hexhaven-battalion", "fra/kwia-vigorbloom", "fra/theorix-metamage-omit-variables", "trk/borg-cube",
         "trk/amok-time", "trk/pah-wraith", "fra/ferocity-of-the-hunt", "fra/koth-the-geomancer",
         "fra/tetsuko-umezawa-pursuer", "fra/vraska-the-cutting-glare", "trk/elim-garak-simple-tailor",
         "trk/nyota-uhura-communications", "fra/ajani-resolute", "fra/arni-renowned-champion",
         "fra/bestial-incursion", "fra/charge-the-sanctum", "fra/countersculpt", "fra/fblthp-knows-the-way",
         "fra/forest", "fra/hunters-axe"]


@pytest.mark.parametrize("ref", CARDS)
def test_golden(ref):
    got = to_json(card_ast(ROOT, ref))
    path = GOLDEN / (ref.replace("/", "-") + ".json")
    if os.environ.get("MTGLANG_UPDATE_GOLDEN"):
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(got, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    assert got == json.loads(path.read_text(encoding="utf-8"))
