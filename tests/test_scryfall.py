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
