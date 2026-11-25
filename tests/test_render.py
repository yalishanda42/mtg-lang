from conftest import FIXTURES as FX
from mtglang.render import notation_html, render_site


def test_notation_html_escapes_and_titles(fx_glossary):
    h = notation_html("«Dal R'El, Augment Orphan» ⇒ ✋1", fx_glossary)
    assert '<span class="sym" data-s="0" title="then">⇒</span>' in h
    assert "Dal R&#x27;El, Augment Orphan" in h and "<script" not in h
    assert ('<span class="name" title="Dal R&#x27;El, Augment Orphan"><span data-s="6">«</span>'
            'Dal R&#x27;El, Augment Orphan<span data-s="7">»</span></span>') in h


def test_notation_html_preserves_spacing_and_bad_input(fx_glossary):
    assert notation_html("{3}, ✝⛰", fx_glossary).startswith(
        '<span class="mana">{3}</span>, <span class="sym" data-s="20" title="sacrifice">✝</span><span')
    bad = notation_html("Draw <b>", fx_glossary)
    assert bad == '<span class="bad">Draw &lt;b&gt;</span>'


def test_ascii_html_tags_aliases(fx_glossary):
    from mtglang.render import ascii_html
    h = ascii_html("«Human» ✝⛰ : ✋1", fx_glossary)
    assert h == ('<span data-a="6">&lt;&lt;</span>Human<span data-a="7">&gt;&gt;</span> '
                 '<span data-a="20">Sa</span><span data-a="16">Ld</span> <span data-a="1">:</span> '
                 '<span data-a="19">Dr</span>1')


def _page(tmp_path):
    return (tmp_path / "index.html").read_text()


def test_render_site_fixture(tmp_path):
    assert render_site(FX, tmp_path) == tmp_path / "index.html"
    s = _page(tmp_path)
    assert "Sacrifice a land: Draw a card." in s
    assert '<section class="page" id="trk" hidden>' in s and '<section class="page" id="legend" hidden>' in s
    assert '<input class="g" data-f="glyph" value="⛰⇡"' in s                       # legend editor
    assert "Landfall" in s and '<tr><td><a href="#trk">trk</a></td><td>1 / 1</td></tr>' in s
    assert (tmp_path / "ascii/trk.txt").read_text().splitlines()[1] == "<<Dal R'El, Augment Orphan>> {1}{R}{G}"
    assert not (tmp_path / "trk.html").exists() and not (tmp_path / "legend.html").exists()


def test_render_removes_stale_pages(tmp_path):
    (tmp_path / "trk.html").write_text("old")
    render_site(FX, tmp_path)
    assert not (tmp_path / "trk.html").exists()


def test_render_shows_issues(fx_copy, tmp_path):
    from conftest import drop_last_line
    drop_last_line(fx_copy)
    render_site(fx_copy, tmp_path / "out")
    assert "V-ALIGN" in _page(tmp_path / "out")


def test_notation_html_uses_symbol_images(fx_glossary):
    from mtglang.scryfall import load_symbols
    syms = load_symbols(FX / "data" / "symbols")
    h = notation_html("{3}, ✝⛰ : {U}", fx_glossary, symbols=syms)
    assert '<span class="ms m-3" role="img" aria-label="{3}" title="three generic mana"></span>' in h
    assert '<span class="mana">{U}</span>' in h  # no svg known → text fallback


def test_oracle_html_icons_and_escaping():
    from mtglang.render import oracle_html
    h = oracle_html("{T}: Add {R} <b>.", {"{T}": {"file": "T.svg", "english": "tap"}})
    assert h == '<span class="ms m-T" role="img" aria-label="{T}" title="tap"></span>: Add {R} &lt;b&gt;.'


def test_render_site_inlines_icons(tmp_path):
    render_site(FX, tmp_path)
    assert not (tmp_path / "symbols").exists()
    s = _page(tmp_path)
    assert ".m-T{background-image:url(\"data:image/svg+xml;base64," in s
    assert 'class="ms m-1"' in s and 'aria-label="{3}"' in s
    assert s.count('class="ms ') >= 6   # header {1}{R}{G}, ability {R} {G} {3}, oracle icons


def test_render_survives_non_utf8_card(fx_copy, tmp_path):
    (fx_copy / "cards/trk/dal-rel-augment-orphan.mtgl").write_bytes(b"\xff\xfe\x00bad")
    render_site(fx_copy, tmp_path / "out")
    assert "C-ENCODING" in _page(tmp_path / "out")


def test_parse_card_image_and_colors(dal_raw, vigorbloom_raw):
    from mtglang.scryfall import parse_card
    assert parse_card(dal_raw).image is None and parse_card(dal_raw).colors == []
    dal_raw.update(colors=["R", "G"], image_uris={"large": "L.jpg", "normal": "N.jpg"})
    c = parse_card(dal_raw)
    assert c.image == "L.jpg" and c.colors == ["R", "G"]
    vigorbloom_raw["card_faces"] = [dict(f, colors=["G", "W"], image_uris={"large": f"{i}.jpg"})
                                    for i, f in enumerate(vigorbloom_raw["card_faces"])]
    v = parse_card(vigorbloom_raw)   # transform-style: images/colours live on the faces
    assert v.image == "0.jpg" and v.colors == ["G", "W"]


def test_frame_palette():
    from mtglang.render import frame_palette
    assert frame_palette(["U"], "Instant") == ("#b7d5e4", "#dbe9f2", "#dbe9f2")
    bar, box, solid = frame_palette(["W", "G"], "Creature")       # Selesnya frame runs green → white
    assert bar == "#d0bc84" and box.index("#d4e4db") < box.index("#f4f4ec") and solid.startswith("color-mix")
    assert frame_palette(["W", "U", "B"], "Creature")[0] == "#d0bc84"
    assert frame_palette([], "Artifact Creature — Golem")[1] == "#d0dce0"
    assert frame_palette([], "Land")[1] == "#e8e3dc"


def _view_inputs(fx_glossary, layout="normal", type_line="Legendary Creature — Human", oracle="A\nB", image="I.jpg"):
    from mtglang.cardfile import AbilityLine, CardDoc, FaceDoc
    from mtglang.scryfall import ScryCard, ScryFace
    card = ScryCard("x", "trk", "X", layout, [], [ScryFace("X", "{R}", type_line, oracle, "1", "1")], image, ["R"])
    face = FaceDoc("X", "{R}", "♞", None, "1/1", [AbilityLine(1, "⤓1", None), AbilityLine(2, "⤓2", None)])
    return card, CardDoc(FX, "trk", "x", [face])


def test_card_view_kinds(fx_glossary):
    from dataclasses import replace
    from mtglang.render import card_view
    card, doc = _view_inputs(fx_glossary)
    v = card_view(card, doc, fx_glossary, "en", None)
    assert v["kind"] == "normal" and v["pt"] and v["image"] == "I.jpg"
    assert [r["oracle"] for r in v["faces"][0]["rows"]] == ["A", "B"]
    assert card_view(replace(card, image=None), doc, fx_glossary, "en", None) is None
    assert card_view(replace(card, layout="transform"), doc, fx_glossary, "en", None) is None
    assert card_view(replace(card, layout="prepare"), doc, fx_glossary, "en", None) is None  # needs two faces
    pw, _ = _view_inputs(fx_glossary, type_line="Legendary Planeswalker — X", oracle="a\nb\nc")
    assert card_view(pw, doc, fx_glossary, "en", None)["kind"] == "pw pw3"
    pw4, _ = _view_inputs(fx_glossary, type_line="Legendary Planeswalker — X", oracle="a\nb\nc\nd")
    assert card_view(pw4, doc, fx_glossary, "en", None)["kind"] == "pw pw4"


def test_render_site_card_view(tmp_path):
    render_site(FX, tmp_path)
    s = _page(tmp_path)
    assert s.count('src="https://cards.example/large/dal.jpg"') == 2      # original + overlaid copy
    assert '<div class="cv normal pt" style="--bar: #d0bc84;' in s
    assert 'title="{3}, Sacrifice a land: Draw a card."' in s             # oracle line on hover
    assert '<details><summary>Line by line</summary>' in s


def test_render_ui_strings_follow_language(fx_copy, tmp_path):
    p = fx_copy / "glossary/symbols.yaml"
    p.write_text(p.read_text().replace('labels: {en: "draw"}', 'labels: {en: "draw", bg: "Изтегли"}'))
    html = render_site(fx_copy, tmp_path / "bg", lang="bg").read_text(encoding="utf-8")
    assert "<h1>Легенда</h1>" in html and 'title="Изтегли"' in html
    en = render_site(fx_copy, tmp_path / "xx", lang="xx").read_text(encoding="utf-8")
    assert "<h1>Legend</h1>" in en


def test_legend_bulgarian_tab(fx_copy, tmp_path):
    p = fx_copy / "glossary" / "names.yaml"
    p.write_text(p.read_text().replace('labels: {en: "Human"}',
                                       'labels: {en: "Human", bg: "Човек", bg-ivanchev: "Човѣкъ", bg-note: "бележка"}'))
    render_site(fx_copy, tmp_path / "out")
    s = _page(tmp_path / "out")
    assert 'data-tab="mtgl"' in s and 'data-tab="bg"' in s
    assert '<div class="tab" id="legend-bg" hidden>' in s
    assert "<td class=\"iv\">Човѣкъ</td><td>Човек</td><td>Human</td><td class=\"note\">бележка</td>" in s
    assert '<td class="g"><span data-s="0">⇒</span></td><td class="iv"></td>' in s   # glyphs follow live edits


def test_render_site_rendered_english_column(tmp_path):
    from pathlib import Path
    import re
    root = Path(__file__).parent.parent
    page = render_site(root, tmp_path).read_text()
    card = page[page.index('id="fra/academic-ascent"'):]
    card = card[:card.index('<div class="card"', 10)]
    assert '<td class="en">Target creature gets +2/+2 and gains flying until end of turn.</td>' in card
    assert re.search(r'<td class="en mismatch">[^<]+</td>', page)
    assert (tmp_path / "eval-en" / "index.html").exists()
