import pytest

from conftest import DAL_RAW
from mtglang.sample import card_features, pick_sample
from mtglang.scryfall import ScryCard, ScryFace, parse_card


def synth(slug, kws):
    return ScryCard(slug=slug, set_code="trk", name=slug, layout="normal", keywords=kws,
                    faces=[ScryFace(name=slug, mana_cost="", type_line="Creature", oracle_text="")])


@pytest.fixture
def cards3():
    return [synth("a", ["f1", "f2"]), synth("b", ["f2"]), synth("c", ["f3"])]


def test_features_dal():
    assert {"layout:normal", "kw:Landfall", "triggered", "activated"} <= card_features(parse_card(DAL_RAW))


def test_features_modal_token_saga():
    c = ScryCard("s", "trk", "S", "saga", [], [ScryFace("S", "", "Enchantment — Saga",
        "I — Create a 1/1 token.\nII — Choose one —\n• Draw a card.\n• Gain 2 life.")])
    f = card_features(c)
    assert {"saga", "token", "modal"} <= f and "activated" not in f


def test_pick_is_greedy_and_deterministic(cards3):
    assert [c.slug for c in pick_sample(cards3, k=2)] == ["a", "c"]
    assert [c.slug for c in pick_sample(cards3, k=2)] == [c.slug for c in pick_sample(list(reversed(cards3)), k=2)]


def test_pick_fills_to_k(cards3):
    assert [c.slug for c in pick_sample(cards3, k=3)] == ["a", "c", "b"]


def test_mode_label_keywords_are_not_features():
    c = ScryCard("p", "trk", "P", "normal", ["Kill", "Stun", "Surveil"], [ScryFace("P", "", "Instant",
        "Choose one —\n• Stun — Tap target creature.\n• Kill — Surveil 2.")])
    f = card_features(c)
    assert "kw:Surveil" in f and "kw:Kill" not in f and "kw:Stun" not in f
