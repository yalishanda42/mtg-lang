"""Phrase-level parsing (noun phrases, filters, values, zones, times) against the real glossary."""
import shutil
from pathlib import Path

import pytest

from mtglang import ast as A
from mtglang.ast import to_json
from mtglang.glossary import load_glossary
from mtglang.semparse import SemParser, SemSyntaxError
from mtglang.tokenizer import _key, tokenize
from mtglang.unparse import Unparser

ROOT = Path(__file__).parent.parent
G = load_glossary(ROOT / "glossary")
P = SemParser(G)
U = Unparser(G)


def rt(text, parse=P.parse_phrase, g=G):
    node = parse(text)
    back = Unparser(g).node(node)
    assert [_key(t) for t in tokenize(back, g)] == [_key(t) for t in tokenize(text, g)], back
    return node


def glyphs(items):
    return [i.glyph for i in items]


def test_target_np_with_filter():
    np = rt("◎▣[⚑○]")
    assert np.quant.glyph == "◎" and glyphs(np.heads) == ["▣"]
    (f,) = np.filters
    (cond,) = f.conds
    assert isinstance(cond, A.Rel) and cond.rel.glyph == "⚑" and cond.other.heads[0].glyph == "○"


def test_up_to_n_targets():
    np = rt("≤1◎♞")
    assert np.quant.glyph == "◎"
    assert isinstance(np.count, A.Bound) and np.count.op.glyph == "≤" and np.count.value == A.Num(1)


def test_or_head_with_filter():
    np = rt("(♞ ∨ ⚝)[⚑● ≠◈]")
    (head,) = np.heads
    assert isinstance(head, A.Or) and glyphs(head.items) == ["♞", "⚝"]
    rels = [c.rel.glyph for c in np.filters[0].conds]
    assert rels == ["⚑", "≠"]


def test_nested_filter_or():
    np = rt("♞[⚑○ (△ ≤ 1 ∨ ▽ ≤ 1)]")
    ctl, alt = np.filters[0].conds
    assert isinstance(alt, A.Or) and all(isinstance(c, A.Compare) for c in alt.items)


def test_token_spec():
    np = rt("◌[2/2 ♦{W} «Cat» «Soldier» ♞] «Ajani's Pridemate»")
    assert glyphs(np.heads) == ["◌"] and np.name == A.NameRef("Ajani's Pridemate")
    pt, color, types = np.filters[0].conds
    assert isinstance(pt, A.PT) and isinstance(color, A.Characteristic) and color.char.glyph == "♦"
    assert types.heads[:2] == (A.NameRef("Cat"), A.NameRef("Soldier")) and types.heads[2].glyph == "♞"


def test_predefined_token():
    np = rt("◌«Treasure»")
    assert glyphs(np.heads[:1]) == ["◌"] and np.heads[1] == A.NameRef("Treasure")


def test_zone_top_n():
    z = rt("⌃4▤●")
    assert isinstance(z, A.Zone) and z.zone.glyph == "▤" and z.pos.glyph == "⌃"
    assert z.count == A.Num(4) and z.owner.heads[0].glyph == "●"


def test_count_value():
    c = rt("#≢ ⛰[⚑●]")
    assert isinstance(c, A.Count) and glyphs(c.mods) == ["≢"] and c.of.heads[0].glyph == "⛰"


def test_characteristic_postfix_and_prefix():
    a = rt("◈△")
    assert isinstance(a, A.Characteristic) and a.char.glyph == "△" and a.of.heads[0].glyph == "◈"
    b = rt("♥●")
    assert isinstance(b, A.Characteristic) and b.prefix and b.of.heads[0].glyph == "●"


def test_duration_each_of_your_turns():
    t = rt("∀◷●")
    assert isinstance(t, A.Time) and glyphs(t.items[:2]) == ["∀", "◷"]


def test_ascii_form_same_ast():
    assert to_json(P.parse_phrase("Tg Pm[Ct Op]")) == to_json(P.parse_phrase("◎▣[⚑○]"))


def test_appended_symbol_uses_class_default(tmp_path):
    shutil.copytree(ROOT / "glossary", tmp_path / "g")
    p = tmp_path / "g" / "symbols.yaml"
    p.write_text(p.read_text(encoding="utf-8") + '- {glyph: ⛵, ascii: Bt, class: type, labels: {en: Boat}}\n',
                 encoding="utf-8")
    g2 = load_glossary(tmp_path / "g")
    np = rt("◎⛵", parse=SemParser(g2).parse_phrase, g=g2)
    assert np.heads[0].glyph == "⛵"


def test_error_column():
    with pytest.raises(SemSyntaxError) as e:
        P.parse_phrase("◎▣[⚑○")
    assert e.value.col == 6


def test_keyword_relation_after_another():
    np = rt("♞[⚑● ≠◈ ⚒«Communicator»]")
    ctl, other, eq = np.filters[0].conds
    assert other.other.post == () and isinstance(eq, A.Rel) and eq.rel.glyph == "⚒"


def test_reference_is_never_a_second_head():
    np = rt("▭[▣ ☞]")
    assert len(np.filters[0].conds) == 2
