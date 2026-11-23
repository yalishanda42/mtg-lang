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
