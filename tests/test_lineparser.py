import pytest

from mtglang.lineparser import LineSyntaxError


def top(tree):
    return [c.data for c in tree.children]


def test_parse_shapes(lp):
    assert lp.parse_ability("⛰↑ ⇒ ✋1").children[-1].data == "triggered"
    assert lp.parse_ability("{3}, ✝⛰ : ✋1").children[-1].data == "activated"
    assert lp.parse_ability("F").children[-1].data == "statement"
    assert top(lp.parse_ability("⛰⇡ ▸ ⛰[◉]↑ ⇒ ⊕ {R} ∨ {G}")) == ["label", "triggered"]
    assert lp.parse_ability("9+ | F").children[0].data == "threshold"
    assert lp.parse_ability("§1,2 ▸ ✋1").children[0].data == "chapter"
    assert lp.parse_ability("• ✋1").children[0].data == "mode"
    assert top(lp.parse_ability("• «Human» ▸ ✋1")) == ["mode", "label", "statement"]
    assert lp.parse_ability("−4 : ✋1").children[-1].data == "activated"


def test_parse_nested_granted_ability(lp):
    t = lp.parse_ability("◉ ⇒ ☺ F ({T}, ✝◈ : ⊕ {R})")
    assert t.children[-1].data == "triggered"


def test_parse_type_line(lp):
    assert lp.parse_type_line("⚜☺ — «Human» «Mutant»").data == "type_line"
    with pytest.raises(LineSyntaxError):
        lp.parse_type_line("⚜☺ — ✋1")


def test_parse_error_col(lp):
    with pytest.raises(LineSyntaxError) as e:
        lp.parse_ability("✋1 ⇒ ⇒ ✋1")
    assert e.value.col == 6
    with pytest.raises(LineSyntaxError) as e:
        lp.parse_ability("✋1 ⇒")
    assert e.value.col == len("✋1 ⇒") + 1
    with pytest.raises(LineSyntaxError) as e:
        lp.parse_ability("⇒ Flying")
    assert e.value.col == 3 and "natural-language word" in e.value.message


def test_parse_ascii_type_line(lp):
    assert lp.parse_type_line("LgCr - <<Human>>").data == "type_line"
