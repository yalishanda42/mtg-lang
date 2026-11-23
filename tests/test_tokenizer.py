import pytest

from mtglang.tokenizer import TokenizeError, to_ascii, tokenize


def test_tokenize_name_with_comma_apostrophe(fx_glossary):
    toks = tokenize("«Dal R'El, Augment Orphan» {1}{R}{G}", fx_glossary)
    assert [(t.type, t.value) for t in toks] == [("NAME", "Dal R'El, Augment Orphan"), ("MANA", "{1}"), ("MANA", "{R}"), ("MANA", "{G}")]


def test_tokenize_ascii_name_delims(fx_glossary):
    assert [(t.type, t.value) for t in tokenize("<<70,000 Light-Years from Home>>", fx_glossary)] == [("NAME", "70,000 Light-Years from Home")]


def test_tokenize_longest_match_and_ascii_alias(fx_glossary):
    assert [t.value for t in tokenize("⛰⇡ ▸ ⛰↑", fx_glossary)] == ["⛰⇡", "▸", "⛰", "↑"]
    assert [t.type for t in tokenize("LF |> Ld^ => Ad", fx_glossary)] == ["SYMBOL", "LABEL_SEP", "SYMBOL", "SYMBOL", "IMPLIES", "SYMBOL"]


def test_tokenize_fixed_punct_var_and_unicode_minus(fx_glossary):
    toks = tokenize("−4 : +X/-1 [F] (F, F) ⟨DS9-reveal⟩", fx_glossary)
    assert [t.type for t in toks] == ["MINUS", "NUMBER", "COST_SEP", "PLUS", "VAR", "SLASH", "MINUS", "NUMBER",
                                      "LSQB", "SYMBOL", "RSQB", "LPAR", "SYMBOL", "COMMA", "SYMBOL", "RPAR", "EFFECT"]
    assert toks[-1].value == "DS9-reveal"
    assert [t.col for t in toks[:3]] == [1, 2, 4]


def test_tokenize_errors_have_column(fx_glossary):
    with pytest.raises(TokenizeError) as e:
        tokenize("⇒ Flying", fx_glossary)
    assert e.value.col == 3 and "natural-language word" in e.value.message
    with pytest.raises(TokenizeError) as e:
        tokenize("⇒ ☃", fx_glossary)
    assert e.value.col == 3 and "unknown symbol" in e.value.message
    with pytest.raises(TokenizeError) as e:
        tokenize("«unclosed", fx_glossary)
    assert e.value.col == 1


def test_to_ascii_roundtrip(fx_glossary):
    line = "⛰⇡ ▸ ⛰[◉]↑ ⇒ ⊕ {R} ∨ {G}"
    a = to_ascii(line, fx_glossary)
    assert a == "LF |> Ld[Me]^ => Ad {R} vv {G}"
    assert [t.symbol for t in tokenize(a, fx_glossary)] == [t.symbol for t in tokenize(line, fx_glossary)]
    assert to_ascii("«Dal R'El, Augment Orphan» {1}", fx_glossary) == "<<Dal R'El, Augment Orphan>> {1}"
