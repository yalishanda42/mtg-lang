"""Per-language lexicon data (`lex:`) on glossary entries."""
from pathlib import Path

import pytest

from mtglang.glossary import check_glossary, load_glossary
from mtglang.lexicon import Lexicon

ROOT = Path(__file__).parent.parent


def _glossary_with(tmp_path, fx_copy, extra: str):
    p = fx_copy / "glossary" / "symbols.yaml"
    p.write_text(p.read_text().rstrip("\n") + "\n" + extra + "\n")
    return load_glossary(fx_copy / "glossary")


def _new_index(g):
    return len(g.symbols) - 1


def test_lex_loaded(tmp_path, fx_copy):
    g = _glossary_with(tmp_path, fx_copy,
                       '- {glyph: "✖", ascii: "Ds", class: action, labels: {en: destroy}, lex: {en: {verb: destroy, s: destroys}}}')
    assert Lexicon(g, "en").sym(_new_index(g)) == {"verb": "destroy", "s": "destroys"}
    assert Lexicon(g, "bg").sym(_new_index(g)) == {}
    assert not [i for i in check_glossary(g) if i.code == "G-LEX"]


def test_lex_unknown_key_is_error(tmp_path, fx_copy):
    g = _glossary_with(tmp_path, fx_copy,
                       '- {glyph: "✖", ascii: "Ds", class: action, labels: {en: destroy}, lex: {en: {colour: x}}}')
    assert [i for i in check_glossary(g) if i.code == "G-LEX" and i.severity == "error"]


def test_lex_frame_bad_slot_is_error(tmp_path, fx_copy):
    g = _glossary_with(tmp_path, fx_copy,
                       '- {glyph: "✖", ascii: "Ds", class: action, labels: {en: destroy}, lex: {en: {frame: "{foo} onto"}}}')
    assert [i for i in check_glossary(g) if i.code == "G-LEX"]


def test_lex_frame_good_slots_ok(tmp_path, fx_copy):
    g = _glossary_with(tmp_path, fx_copy,
                       '- {glyph: "✖", ascii: "Ds", class: action, labels: {en: put}, lex: {en: {frame: "{object} onto {destination}"}}}')
    assert not [i for i in check_glossary(g) if i.code == "G-LEX"]


def test_name_lex_loaded(fx_copy):
    p = fx_copy / "glossary" / "names.yaml"
    p.write_text(p.read_text() + '- {key: "Dr. Who", class: card, labels: {en: "Dr. Who"}, lex: {en: {short: Doc}}}\n')
    g = load_glossary(fx_copy / "glossary")
    assert Lexicon(g, "en").name("Dr. Who") == {"short": "Doc"}


def test_keyword_falls_back_to_oracle():
    g = load_glossary(ROOT / "glossary")
    i = next(k for k, s in enumerate(g.symbols) if s.glyph == "🪽")
    assert Lexicon(g, "en").keyword(i) == "Flying"


def test_validate_warns_symbols_without_en_words(fx_copy):
    from mtglang.validate import validate_all
    issues, _ = validate_all(fx_copy)
    (w,) = [i for i in issues if i.code == "G-LEX-EN"]
    assert w.severity == "warning"
    assert "⊕" in w.message or "Ad" in w.message or "symbol" in w.message
