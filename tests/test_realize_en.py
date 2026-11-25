"""English realizer."""
from pathlib import Path

import pytest

from mtglang import planner
from mtglang.astexport import card_ast
from mtglang.glossary import load_glossary
from mtglang.lexicon import Lexicon
from mtglang.realize.en import self_phrase

ROOT = Path(__file__).parent.parent
G = load_glossary(ROOT / "glossary")
LEX = Lexicon(G, "en")


def ctx(ref, face=0):
    return planner.context_for(card_ast(ROOT, ref), face, G)


@pytest.mark.parametrize("ref,face,want", [
    ("fra/afterthought-sentry", 0, "this creature"),
    ("fra/aerid-konstrari", 0, "Aerid Konstrari"),
    ("fra/ajani-resolute", 0, "Ajani"),
    ("fra/arni-humble-scribe", 0, "Arni"),
    ("fra/vigorbloom-vanguard-seed-suture", 0, "this creature"),
    ("fra/vigorbloom-vanguard-seed-suture", 1, "this spell"),
    ("trk/dr-beverly-crusher", 0, "Dr. Crusher"),
    ("trk/captain-james-t-kirk", 0, "Captain Kirk"),
    ("trk/amok-time", 0, "this Saga"),
    ("trk/andoria", 0, "this land"),
    ("fra/academic-ascent", 0, "this spell"),
])
def test_self_phrase(ref, face, want):
    assert self_phrase(ctx(ref, face), LEX) == want


def test_self_phrase_in_token():
    assert self_phrase(ctx("fra/ajani-resolute"), LEX, in_token=True) == "this token"


def test_self_phrase_as_card_and_spell():
    c = ctx("fra/aerid-konstrari")
    assert self_phrase(c, LEX, as_="card") == "this card"
    assert self_phrase(c, LEX, as_="spell") == "this spell"
