import json
from mtglang.scryfall import parse_card, slugify


def test_slugify():
    assert slugify("Dal R'El, Augment Orphan") == "dal-rel-augment-orphan"
    assert slugify("70,000 Light-Years from Home") == "70-000-light-years-from-home"
    assert slugify("Vigorbloom Vanguard // Seed Suture") == "vigorbloom-vanguard-seed-suture"
    assert slugify("U.S.S. Reliant, From Hell’s Heart") == "u-s-s-reliant-from-hells-heart"


def test_parse_single_face(dal_raw):
    c = parse_card(dal_raw)
    assert (c.slug, c.set_code, c.layout) == ("dal-rel-augment-orphan", "trk", "normal")
    assert len(c.faces) == 1 and c.faces[0].power == "3" and c.faces[0].mana_cost == "{1}{R}{G}"
    assert c.keywords == ["Landfall"]


def test_parse_prepare_two_faces(vigorbloom_raw):
    c = parse_card(vigorbloom_raw)
    assert [f.name for f in c.faces] == ["Vigorbloom Vanguard", "Seed Suture"]
    assert c.faces[1].power is None and c.faces[1].type_line == "Sorcery"
    assert c.faces[0].power == "2"


def test_parse_null_oracle_is_empty():
    c = parse_card({"name": "Vanilla", "set": "fra", "layout": "normal", "mana_cost": "{G}",
                    "type_line": "Creature — Bear", "oracle_text": None, "power": "2", "toughness": "2"})
    assert c.faces[0].oracle_text == ""


def test_issue_str():
    from mtglang.issues import Issue
    assert str(Issue("error", "V-X", "bad", "a.mtgl", 3, 5)) == "a.mtgl:3:5: error V-X: bad"
    assert str(Issue("warning", "V-Y", "meh")) == "warning V-Y: meh"


from conftest import FIXTURES
from mtglang.scryfall import fetch_set, load_snapshot, load_subtypes, split_subtypes


def test_fetch_set_paginates():
    pages = {"https://api.scryfall.com/cards/search?q=e%3Atrk&unique=cards":
                 {"data": [{"name": "A"}], "has_more": True, "next_page": "P2"},
             "P2": {"data": [{"name": "B"}], "has_more": False}}
    assert [c["name"] for c in fetch_set("trk", pages.__getitem__)] == ["A", "B"]


def test_split_subtypes_multiword():
    assert split_subtypes("Time Lord Scientist", ["Time Lord", "Scientist", "Lord"]) == ["Time Lord", "Scientist"]
    assert split_subtypes("Unknownling", []) == ["Unknownling"]


def test_load_snapshot_fixture():
    snap = load_snapshot(FIXTURES / "data")
    assert ("trk", "dal-rel-augment-orphan") in snap and len(snap) == 1
    assert load_subtypes(FIXTURES / "data") == ["Human", "Mutant", "Rogue"]


def test_fetch_catalogs_union():
    from mtglang.scryfall import fetch_catalogs, CATALOGS
    data = {f"https://api.scryfall.com/catalog/{c}": {"data": ["Human"] if c == "creature-types" else ["Cave"] if c == "land-types" else []} for c in CATALOGS}
    assert fetch_catalogs(data.__getitem__) == {"subtypes": ["Cave", "Human"]}


def test_cli_fetch_writes_files(tmp_path, monkeypatch):
    import mtglang.scryfall as sf
    from mtglang.cli import main
    monkeypatch.setattr(sf, "fetch_set", lambda code, get_json=None: [{"name": code}])
    monkeypatch.setattr(sf, "fetch_catalogs", lambda get_json=None: {"subtypes": []})
    assert main(["fetch", "--root", str(tmp_path)]) == 0
    import json
    assert json.loads((tmp_path / "data/trk.json").read_text()) == [{"name": "trk"}]
    assert (tmp_path / "data/catalogs.json").exists()


def test_fetch_symbols_writes_svgs_and_index(tmp_path):
    from mtglang.scryfall import fetch_symbols
    pages = {"https://api.scryfall.com/symbology": {"data": [
        {"symbol": "{T}", "svg_uri": "https://svgs.scryfall.io/card-symbols/T.svg", "english": "tap this permanent"},
        {"symbol": "{G/W}", "svg_uri": "https://svgs.scryfall.io/card-symbols/GW.svg", "english": "one green or white mana"},
        {"symbol": "{HALF}", "svg_uri": None, "english": "no svg"}]}}
    blobs = {"https://svgs.scryfall.io/card-symbols/T.svg": b"<svg>T</svg>",
             "https://svgs.scryfall.io/card-symbols/GW.svg": b"<svg>GW</svg>"}
    n = fetch_symbols(tmp_path, pages.__getitem__, blobs.__getitem__)
    assert n == 2
    assert (tmp_path / "GW.svg").read_bytes() == b"<svg>GW</svg>"
    index = json.loads((tmp_path / "index.json").read_text())
    assert index["{G/W}"] == {"file": "GW.svg", "english": "one green or white mana"} and "{HALF}" not in index


def test_load_symbols_missing_dir_is_empty(tmp_path):
    from mtglang.scryfall import load_symbols
    assert load_symbols(tmp_path / "nope") == {}
    assert load_symbols(FIXTURES / "data" / "symbols")["{T}"]["file"] == "T.svg"


def test_cli_fetch_symbols(tmp_path, monkeypatch):
    import mtglang.scryfall as sf
    from mtglang.cli import main
    seen = {}
    monkeypatch.setattr(sf, "fetch_symbols", lambda out_dir, *a, **k: seen.setdefault("dir", out_dir) and 7)
    assert main(["fetch-symbols", "--root", str(tmp_path)]) == 0
    assert seen["dir"] == tmp_path / "data" / "symbols"
