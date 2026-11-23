from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

DAL_RAW = {
    "name": "Dal R'El, Augment Orphan", "layout": "normal", "mana_cost": "{1}{R}{G}",
    "type_line": "Legendary Creature — Human Mutant Rogue",
    "oracle_text": "Landfall — Whenever a land you control enters, add {R} or {G}.\n{3}, Sacrifice a land: Draw a card.",
    "power": "3", "toughness": "3", "keywords": ["Landfall"], "set": "trk",
}

VIGORBLOOM_RAW = {
    "name": "Vigorbloom Vanguard // Seed Suture", "layout": "prepare", "mana_cost": "{1}{G/W} // {G/W}",
    "type_line": "Creature — Troll Druid // Sorcery", "oracle_text": None, "power": "2", "toughness": "2",
    "keywords": ["Prepared"], "set": "fra",
    "card_faces": [
        {"name": "Vigorbloom Vanguard", "mana_cost": "{1}{G/W}", "type_line": "Creature — Troll Druid",
         "oracle_text": "This creature enters prepared. (While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)\nEach creature you control with a +1/+1 counter on it has vigilance.",
         "power": "2", "toughness": "2"},
        {"name": "Seed Suture", "mana_cost": "{G/W}", "type_line": "Sorcery",
         "oracle_text": "Put a +1/+1 counter on target creature. You gain 1 life."},
    ],
}


@pytest.fixture
def dal_raw():
    return dict(DAL_RAW)


@pytest.fixture
def vigorbloom_raw():
    return dict(VIGORBLOOM_RAW)


@pytest.fixture
def fx_glossary():
    from mtglang.glossary import load_glossary
    return load_glossary(FIXTURES / "glossary")


@pytest.fixture
def lp(fx_glossary):
    from mtglang.lineparser import LineParser
    return LineParser(fx_glossary)


import json
import shutil

DAL_FILE = "cards/trk/dal-rel-augment-orphan.mtgl"


@pytest.fixture
def fx_copy(tmp_path):
    dst = tmp_path / "proj"
    shutil.copytree(FIXTURES, dst)
    return dst


def edit(root, old, new, rel=DAL_FILE):
    p = root / rel
    s = p.read_text()
    assert old in s, old
    p.write_text(s.replace(old, new, 1))


def drop_last_line(root, rel=DAL_FILE):
    p = root / rel
    p.write_text("\n".join(p.read_text().rstrip("\n").split("\n")[:-1]) + "\n")


def add_raw_card(root, set_code, raw):
    p = root / "data" / f"{set_code}.json"
    data = json.loads(p.read_text())
    data.append(dict(raw, set=set_code))
    p.write_text(json.dumps(data, ensure_ascii=False))


def write_card(root, rel, text):
    p = root / "cards" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def add_name(root, key, cls="subtype"):
    p = root / "glossary" / "names.yaml"
    p.write_text(p.read_text() + f'- {{key: "{key}", class: {cls}, labels: {{en: "{key}"}}}}\n')


def codes_of(result):
    issues, _ = result
    return {i.code for i in issues}


def only(result, code):
    found = [i for i in result[0] if i.code == code]
    assert len(found) == 1, found
    return found[0]


BEAR_RAW = {"name": "Test Bear", "layout": "normal", "mana_cost": "{1}{G}", "type_line": "Creature — Bear",
            "oracle_text": None, "power": "2", "toughness": "2", "keywords": []}
