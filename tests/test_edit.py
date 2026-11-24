import json
import threading
import urllib.request

import pytest

from conftest import DAL_FILE
from mtglang.edit import EditError, apply_symbol_edits, migrate_line
from mtglang.glossary import load_glossary


def _edit(i, orig, glyph, ascii_, label):
    return {"index": i, "orig": orig, "glyph": glyph, "ascii": ascii_, "label": label}


def test_migrate_line_respells_glyphs_ascii_and_delimiters(fx_copy):
    from dataclasses import replace
    from mtglang.glossary import Glossary
    old = load_glossary(fx_copy / "glossary")
    syms = list(old.symbols)
    syms[0] = replace(syms[0], glyph="→", ascii="==>")        # implies
    syms[6] = replace(syms[6], glyph="‹", ascii="<[")         # name_open
    syms[7] = replace(syms[7], glyph="›", ascii="]>")         # name_close
    new = Glossary(syms, old.names, old.effects)
    assert migrate_line("⛰[◉]↑ ⇒ ⊕ {R}", old, new) == "⛰[◉]↑ → ⊕ {R}"
    assert migrate_line("Ld[Me]^ => Ad {R}", old, new) == "Ld[Me]^ ==> Ad {R}"        # ASCII stays ASCII
    assert migrate_line("  «Human» «Rogue»", old, new) == "  ‹Human› ‹Rogue›"         # indentation kept
    assert migrate_line("<<Human>>", old, new) == "<[Human]>"
    assert migrate_line("Draw a card", old, new) == "Draw a card"                    # invalid lines untouched


def test_migrate_line_separates_glued_tokens(fx_copy):
    from dataclasses import replace
    from mtglang.glossary import Glossary
    old = load_glossary(fx_copy / "glossary")
    syms = list(old.symbols)
    syms[19] = replace(syms[19], glyph="⇡")           # draw := "⇡" — "⛰✋" must not become "⛰⇡" (Landfall)
    new = Glossary(syms, old.names, old.effects)
    assert migrate_line("⛰✋1", old, new) == "⛰ ⇡1"
    assert migrate_line("⛰ ✋1", old, new) == "⛰ ⇡1"


def test_apply_symbol_edits_rewrites_glossary_and_cards(fx_copy):
    before = (fx_copy / "glossary/symbols.yaml").read_text().splitlines()
    r = apply_symbol_edits(fx_copy, [_edit(0, "⇒", "→", "==>", "then (trigger)")])
    assert r == {"files": 1, "lines": 1}
    card = (fx_copy / DAL_FILE).read_text()
    assert "⛰[◉]↑ → ⊕ {R} ∨ {G}" in card and card.startswith("# Dal R'El — fixture\n")
    after = (fx_copy / "glossary/symbols.yaml").read_text().splitlines()
    assert after[0] == "- {glyph: →, ascii: ==>, role: implies, class: structural, labels: {en: then (trigger)}}"
    assert after[1:] == before[1:]                       # other lines keep their hand formatting
    g = load_glossary(fx_copy / "glossary")
    assert g.symbols[0].glyph == "→" and g.label(g.symbols[0]) == "then (trigger)"
    from mtglang.validate import validate_all
    assert not [i for i in validate_all(fx_copy, only_existing=True)[0] if i.severity == "error"]


def test_apply_symbol_edits_migrates_definitions(fx_copy):
    apply_symbol_edits(fx_copy, [_edit(14, "☺", "♞", "Cr", "Creature")])
    g = load_glossary(fx_copy / "glossary")
    assert next(s for s in g.symbols if s.oracle == "Flying").definition == "◈ ≤ [♞ F]"
    assert "⚜♞ — «Human»" in (fx_copy / DAL_FILE).read_text()


def test_apply_symbol_edits_rejects_bad_edits_without_writing(fx_copy):
    snapshot = {p: p.read_bytes() for p in fx_copy.rglob("*") if p.is_file()}
    with pytest.raises(EditError, match="used by two symbols"):
        apply_symbol_edits(fx_copy, [_edit(0, "⇒", "∨", "=>", "then")])
    with pytest.raises(EditError, match="3\\+ letters"):
        apply_symbol_edits(fx_copy, [_edit(0, "⇒", "⇒", "then", "then")])
    with pytest.raises(EditError, match="changed on disk"):
        apply_symbol_edits(fx_copy, [_edit(0, "≠", "→", "==>", "then")])
    assert snapshot == {p: p.read_bytes() for p in fx_copy.rglob("*") if p.is_file()}


def test_serve_saves_and_rerenders(fx_copy, tmp_path):
    from http.server import ThreadingHTTPServer
    from mtglang.render import render_site
    from mtglang.serve import make_handler
    out = tmp_path / "out"
    render_site(fx_copy, out)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(fx_copy, out, "en"))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        assert json.load(urllib.request.urlopen(base + "/api/ping"))["ok"]

        def post(edits):
            req = urllib.request.Request(base + "/api/glossary", json.dumps({"edits": edits}).encode(),
                                         {"Content-Type": "application/json"})
            return json.load(urllib.request.urlopen(req))

        bad = post([_edit(0, "⇒", "∨", "=>", "then")])
        assert not bad["ok"] and any("two symbols" in e for e in bad["errors"])
        assert post([_edit(0, "⇒", "→", "==>", "then")]) == {"ok": True, "files": 1, "lines": 1}
        page = urllib.request.urlopen(base + "/").read().decode()
        assert '<span class="sym" data-s="0" title="then">→</span>' in page
    finally:
        httpd.shutdown()
        httpd.server_close()
