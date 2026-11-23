from dataclasses import replace

from mtglang.glossary import Glossary, Symbol, check_glossary


def replace_symbols(g: Glossary, extra) -> Glossary:
    return Glossary(symbols=g.symbols + list(extra), names=g.names, effects=g.effects)


def test_fixture_glossary_clean(fx_glossary):
    assert check_glossary(fx_glossary) == []


def test_glossary_rejects_words_reserved_dups(fx_glossary):
    bad = replace_symbols(fx_glossary, extra=[Symbol("tgt", "tg", "other", {"en": "t"}),
                                              Symbol("[x", "q", "other", {"en": "x"}),
                                              Symbol("✋", "Zz", "other", {"en": "dup"})])
    codes = {i.code for i in check_glossary(bad)}
    assert {"G-WORD", "G-RESERVED", "G-DUP"} <= codes


def test_glossary_reserved_variants(fx_glossary):
    for glyph in ("X", "12", "a−b"):
        bad = replace_symbols(fx_glossary, extra=[Symbol(glyph, "qq", "other", {"en": "x"})])
        assert "G-RESERVED" in {i.code for i in check_glossary(bad)}, glyph


def test_glossary_missing_role_and_label(fx_glossary):
    syms = [s for s in fx_glossary.symbols if s.role != "implies"]
    syms[-1] = replace(syms[-1], labels={"fr": "Vol"})
    codes = {i.code for i in check_glossary(Glossary(syms, fx_glossary.names, fx_glossary.effects))}
    assert {"G-ROLE", "G-LABEL"} <= codes


def test_lookup_role_label(fx_glossary):
    g = fx_glossary
    assert g.lookup["=>"] is g.lookup["⇒"] is g.role("implies")
    assert g.label(g.lookup["☺"]) == "Creature"
    assert g.label(g.names["Human"], "de") == "Human"
    assert g.label(g.lookup["F"], "en") == "Flying"
