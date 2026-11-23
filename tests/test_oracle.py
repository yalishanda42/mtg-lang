from mtglang.oracle import normalize_for_consistency, oracle_lines, strip_reminder
from mtglang.scryfall import ScryFace


def face(oracle_text: str, name: str = "Test") -> ScryFace:
    return ScryFace(name=name, mana_cost="", type_line="", oracle_text=oracle_text)


def test_reminder_only_line_dropped():
    f = face("({T}: Add {G}.)\nFlying (This creature can't be blocked except by creatures with flying or reach.)")
    assert oracle_lines(f) == ["Flying"]


def test_station_line_kept():
    f = face("Station (Tap another creature you control: Put charge counters equal to its power on this Spacecraft. Station only as a sorcery.)\n9+ | Creatures you control get +3/+3.")
    assert oracle_lines(f) == ["Station", "9+ | Creatures you control get +3/+3."]


def test_vanilla_has_no_lines():
    assert oracle_lines(face("")) == []


def test_strip_reminder_midline():
    assert strip_reminder("Ward {2} (Whenever this becomes the target...) and more") == "Ward {2} and more"


def test_normalize_short_name():
    assert normalize_for_consistency("When Hoshi Sato enters, draw a card.", "Hoshi Sato, Exolinguist") == "When ~ enters, draw a card."
    assert normalize_for_consistency("When Hoshi Sato, Exolinguist  enters, draw.", "Hoshi Sato, Exolinguist") == "When ~ enters, draw."


def test_reminder_spanning_lines_is_dropped():
    f = face("(As this Saga enters and after your draw\nstep, add a lore counter. Sacrifice after III.)\nI — Draw two cards.")
    assert oracle_lines(f) == ["I — Draw two cards."]
