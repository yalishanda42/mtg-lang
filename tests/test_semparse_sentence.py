"""Actions and sentences."""
from pathlib import Path

from mtglang import ast as A
from mtglang.glossary import load_glossary
from mtglang.semparse import SemParser
from mtglang.tokenizer import _key, tokenize
from mtglang.unparse import Unparser

ROOT = Path(__file__).parent.parent
G = load_glossary(ROOT / "glossary")
P = SemParser(G)
U = Unparser(G)


def rt(text):
    eff = P.parse_effects(text)
    back = U.node(eff)
    assert [_key(t) for t in tokenize(back, G)] == [_key(t) for t in tokenize(text, G)], back
    return eff.sentences[0] if len(eff.sentences) == 1 else eff


def args(a):
    return dict(a.args)


def test_damage_slots():
    a = rt("◈ ✸3 → ◎")
    assert isinstance(a, A.Action) and a.verb.glyph == "→" and a.subject.heads[0].glyph == "◈"
    obj = args(a)["object"]
    assert obj.heads[0].glyph == "✸" and obj.count == A.Num(3)
    dest = args(a)["destination"]
    assert dest.quant.glyph == "◎" and dest.heads == ()


def test_zone_move():
    a = rt("◎▭♞[⚰●] → ☚●")
    assert a.verb.glyph == "→" and a.subject is None and a.before == 1
    assert isinstance(args(a)["destination"], A.Zone)


def test_optional_subject():
    a = rt("● ? ⤓1")
    assert a.optional and a.subject.heads[0].glyph == "●" and args(a)["amount"] == A.Num(1)


def test_implicit_subject():
    a = rt("⤓1")
    assert a.subject is None and a.verb.glyph == "⤓"


def test_pt_change_with_duration():
    m = rt("◎♞ +2/+0 ⧗")
    assert isinstance(m, A.Modify) and isinstance(m.change, A.PT) and args(m)["time"].items[0].glyph == "⧗"


def test_coord_and_then():
    eff = rt("◎♞ +2/+0 ∧ ∋↟ ⧗ ; ⊞+1/+1 → ☞")
    first, second = eff.sentences
    assert isinstance(first, A.Coord) and first.op.glyph == "∧"
    modify, has = first.items
    assert isinstance(modify, A.Modify) and has.verb.glyph == "∋" and has.subject is None
    assert second.verb.glyph == "→"


def test_np_conjunction_is_not_a_clause():
    a = rt("◈ ✸2 → ∀♞ ∧ ∀◐")
    assert isinstance(args(a)["destination"], A.And)


def test_mana_alternatives():
    a = rt("⊕ {R} ∨ {G}")
    assert isinstance(args(a)["mana"], A.Or)


def test_if_you_do():
    eff = rt("● ? ⊷{2} ; ✓ ⊃ ⤓1")
    cond = eff.sentences[1]
    assert isinstance(cond, A.Conditional) and cond.mode == "if_do" and cond.then.verb.glyph == "⤓"


def test_unless():
    c = rt("◈ ↥↷ ¬⊃ ∃⚝[⚑●]")
    assert c.mode == "unless" and c.then.verb.glyph == "↥" and c.cond.quant.glyph == "∃"
    assert args(c.then)["state"].verb.glyph == "↷"


def test_bind_variable():
    eff = rt("◎♞ +X/+0 ⧗ ; X ≔ #≢ ⛰[⚑●]")
    b = eff.sentences[1]
    assert isinstance(b, A.Bind) and b.var == A.Var("X") and isinstance(b.value, A.Count)


def test_becomes():
    a = rt("◈ ≔ «Ferengi» «Scout»")
    assert isinstance(a, A.Action) and a.verb.glyph == "≔"
    assert args(a)["types"].heads == (A.NameRef("Ferengi"), A.NameRef("Scout"))


def test_for_each_player():
    f = rt("(∀○) ✖ ≤1◎♞[⚑☞]")
    assert isinstance(f, A.ForEach) and f.over.quant.glyph == "∀" and f.body.verb.glyph == "✖"


def test_reflexive_trigger():
    eff = rt("● ? ⌫1 ; (✓ ⇒ ◈ ✸2 → ◎)")
    n = eff.sentences[1]
    assert isinstance(n, A.Nested) and isinstance(n.ability, A.Triggered)


def test_until_reveal_vs_until_time():
    u = rt("◉ ⌃▤● ⊣ ◉▭(♞ ∨ ⚝)")
    assert isinstance(u, A.Until) and isinstance(u.until, A.Action)
    u2 = rt("≤1◎♞ -4/-1 ⊣▷◷●")
    assert isinstance(u2, A.Until) and isinstance(u2.until, A.Time)


def test_granted_activated():
    a = rt("◌[♦∅ ⚙] ∋ ({T}, ✝◈ : ⊕ 3◆)")
    ab = args(a)["ability"]
    assert isinstance(ab, A.Nested) and isinstance(ab.ability, A.Activated) and len(ab.ability.cost) == 2


def test_instead():
    eff = rt("◈↷ ⇒ ⌕1 ; ◈△ ≥ 4 ⊃ ⤳ ⤓1".split(" ⇒ ")[1])
    c = eff.sentences[1]
    assert c.mode == "if" and isinstance(c.then, A.Replace) and c.then.event is None


def test_scoped_subject():
    s = rt("∀◐ ? (⌫☚ ∧ ⤓7)")
    assert isinstance(s, A.Scoped) and s.optional and isinstance(s.body, A.Coord)


def test_double_life():
    m = rt("● ♥ × 2")
    assert isinstance(m, A.Modify) and m.change.times == A.Num(2)
