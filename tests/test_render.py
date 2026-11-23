from conftest import FIXTURES as FX
from mtglang.render import notation_html, render_site


def test_notation_html_escapes_and_titles(fx_glossary):
    h = notation_html("«Dal R'El, Augment Orphan» ⇒ ✋1", fx_glossary)
    assert '<span class="sym" title="then">⇒</span>' in h
    assert "Dal R&#x27;El, Augment Orphan" in h and "<script" not in h
    assert '<span class="name" title="Dal R&#x27;El, Augment Orphan">«Dal R&#x27;El, Augment Orphan»</span>' in h


def test_notation_html_preserves_spacing_and_bad_input(fx_glossary):
    assert notation_html("{3}, ✝⛰", fx_glossary).startswith('<span class="mana">{3}</span>, <span class="sym" title="sacrifice">✝</span><span')
    bad = notation_html("Draw <b>", fx_glossary)
    assert bad == '<span class="bad">Draw &lt;b&gt;</span>'


def test_render_site_fixture(tmp_path):
    render_site(FX, tmp_path)
    s = (tmp_path / "trk.html").read_text()
    assert "Sacrifice a land: Draw a card." in s and "{3}, SaLd : Dr1" in s
    assert "Landfall" in (tmp_path / "legend.html").read_text()
    assert (tmp_path / "ascii/trk.txt").read_text().splitlines()[1] == "<<Dal R'El, Augment Orphan>> {1}{R}{G}"
    idx = (tmp_path / "index.html").read_text()
    assert "1 / 1" in idx and "0 / 0" in idx


def test_render_shows_issues(fx_copy, tmp_path):
    from conftest import drop_last_line
    drop_last_line(fx_copy)
    render_site(fx_copy, tmp_path / "out")
    assert "V-ALIGN" in (tmp_path / "out/trk.html").read_text()


def test_notation_html_uses_symbol_images(fx_glossary):
    from mtglang.scryfall import load_symbols
    syms = load_symbols(FX / "data" / "symbols")
    h = notation_html("{3}, ✝⛰ : {U}", fx_glossary, symbols=syms)
    assert '<img class="ms" src="symbols/3.svg" alt="{3}" title="three generic mana">' in h
    assert '<span class="mana">{U}</span>' in h  # no svg known → text fallback


def test_oracle_html_icons_and_escaping():
    from mtglang.render import oracle_html
    h = oracle_html("{T}: Add {R} <b>.", {"{T}": {"file": "T.svg", "english": "tap"}})
    assert h == '<img class="ms" src="symbols/T.svg" alt="{T}" title="tap">: Add {R} &lt;b&gt;.'


def test_render_site_copies_symbols_and_uses_icons(tmp_path):
    render_site(FX, tmp_path)
    assert (tmp_path / "symbols/T.svg").exists()
    s = (tmp_path / "trk.html").read_text()
    assert 'src="symbols/1.svg"' in s and 'alt="{3}"' in s
    assert s.count('class="ms"') >= 6   # header {1}{R}{G}, ability {R} {G} {3}, oracle icons
