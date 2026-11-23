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


def test_render_survives_non_utf8_card(fx_copy, tmp_path):
    (fx_copy / "cards/trk/dal-rel-augment-orphan.mtgl").write_bytes(b"\xff\xfe\x00bad")
    render_site(fx_copy, tmp_path / "out")
    assert "C-ENCODING" in (tmp_path / "out/trk.html").read_text()


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
    s = (tmp_path / "trk.html").read_text()
    assert s.count('src="https://cards.example/large/dal.jpg"') == 2      # original + overlaid copy
    assert '<div class="cv normal pt" style="--bar: #d0bc84;' in s
    assert 'title="{3}, Sacrifice a land: Draw a card."' in s             # oracle line on hover
    assert '<details><summary>Line by line</summary>' in s
