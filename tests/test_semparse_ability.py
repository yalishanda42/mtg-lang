"""Ability shapes and whole cards."""
from pathlib import Path

import pytest

from mtglang import ast as A
from mtglang.cardfile import parse_card_file
from mtglang.glossary import load_glossary
from mtglang.lineparser import LineParser
from mtglang.semparse import SemParser, build_card
from mtglang.tokenizer import _key, tokenize
from mtglang.unparse import Unparser, unparse_card

ROOT = Path(__file__).parent.parent
G = load_glossary(ROOT / "glossary")
P = SemParser(G)
U = Unparser(G)


def toks(text):
    return [_key(t) for t in tokenize(text, G)]


def rt(text):
    node = P.parse_ability(text)
    assert toks(U.node(node)) == toks(text), U.node(node)
    return node


def test_keywords_with_params():
    k = rt("🪽, ⊙, ♡, ⊠{2}")
    assert isinstance(k, A.Keywords) and len(k.items) == 4 and k.items[3].params == (A.Mana("{2}"),)


def test_cycling_variant():
    k = rt("♲[⊡⛰] {2}")
    (kw,) = k.items
    assert isinstance(kw.params[0], A.Filter) and kw.params[1] == A.Mana("{2}")


def test_triggered_intervening_if():
    t = rt("◈↥ ∧ #⛰[⚑●] ≥ 6 ⇒ ✖ ◎▣[⚑○]")
    assert isinstance(t, A.Triggered) and t.event.verb.glyph == "↥" and len(t.conds) == 1
    assert isinstance(t.conds[0], A.Compare)


def test_trigger_while():
    t = rt("● ➹ ∵ Σ△ ♞[⚑●] ≥ 8 ⇒ ◎♞ ¬⛉ ◷")
    assert isinstance(t.while_, A.Compare) and t.event.verb.glyph == "➹"


def test_activated_with_limit():
    a = rt("{2}, {T} : ◎♞[➹◷] ⧉ ; ≡✎")
    assert isinstance(a, A.Activated) and len(a.cost) == 2 and len(a.limits) == 1
    assert len(a.effect.sentences) == 1


def test_loyalty_cost():
    a = rt("−4 : ✚ ◌[2/2 ♦{W} «Cat» «Soldier» ♞] «Ajani's Pridemate» ∋ (● ♥+ ⇒ ⊞+1/+1 → ◈)")
    assert a.cost == (A.Num(4, "-"),)
    assert U.node(a).startswith("−4")


def test_labelled_landfall():
    lab = rt("⛶ ▸ ⛰[⚑●]↥ ⇒ ◈ ✸1 → ∀○ ; ☞ ∈ «Mountain» ⊃ ⊕{R}")
    assert isinstance(lab, A.Labelled) and isinstance(lab.ability, A.Triggered)
    assert len(lab.ability.effect.sentences) == 2


def test_flavor_label():
    lab = rt("«Open a Channel» ▸ ○ ✷ ✦[⌀ = Y] ⇒ ● ⤓1")
    assert lab.label == (A.NameRef("Open a Channel"),)


def test_saga_chapter():
    c = rt("§1,2,3 ▸ ⤓2 ; ▭[☚●] → ⊘")
    assert isinstance(c, A.Chapter) and c.numbers == (1, 2, 3)


def test_station_threshold():
    t = rt("12+ | ⚙♞[⚑●] ∋ 🪽")
    assert isinstance(t, A.Threshold) and t.n == 12


def test_replacement():
    r = rt("◈↥ ⤳ ⊻ Y ; 0 ≤ Y ≤ 10")
    first, second = r.body.sentences
    assert isinstance(first, A.Replace) and isinstance(second, A.Compare) and len(second.ops) == 2


def test_type_line_dash():
    tl = P.parse_type_line("⚜♞ — «Human» «Warrior»")
    assert [t.glyph for t in tl.types] == ["⚜", "♞"] and tl.dash == "—" and len(tl.subtypes) == 2
    assert U.node(tl) == "⚜ ♞ — «Human» «Warrior»"


def _card(rel):
    doc, issues = parse_card_file(ROOT / "cards" / rel, LineParser(G))
    assert not issues
    return doc, build_card(doc, P)


def test_modal_on_trigger_groups_modes():
    _, card = _card("fra/archive-arbiter.mtgl")
    abilities = card.faces[0].abilities
    assert len(abilities) == 2
    trig = abilities[1]
    modal = trig.effect.sentences[0]
    assert isinstance(modal, A.Modal) and len(modal.modes) == 2


def test_modal_spell():
    _, card = _card("fra/charge-the-sanctum.mtgl")
    (ab,) = card.faces[0].abilities
    assert isinstance(ab.body.sentences[0], A.Modal)


def test_multi_face_card():
    _, card = _card("fra/theorix-metamage-omit-variables.mtgl")
    assert len(card.faces) == 2


@pytest.mark.parametrize("rel", ["fra/archive-arbiter.mtgl", "fra/charge-the-sanctum.mtgl",
                                 "fra/theorix-metamage-omit-variables.mtgl", "fra/ajani-resolute.mtgl"])
def test_card_roundtrip(rel):
    doc, card = _card(rel)
    src = [l for l in (ROOT / "cards" / rel).read_text(encoding="utf-8").splitlines()
           if l.strip() and not l.lstrip().startswith("#")]
    out = unparse_card(card, G).splitlines()
    assert [toks(l) for l in out] == [toks(l) for l in src]
