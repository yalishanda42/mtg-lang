"""Rendered English must equal Oracle for these lines (grows with every coverage task)."""
from functools import lru_cache
from pathlib import Path

import pytest

from mtglang.oracle import oracle_lines
from mtglang.realize.en import render_card_en
from mtglang.scryfall import load_snapshot

ROOT = Path(__file__).parent.parent

MUST_MATCH = [
    "fra/aerid-konstrari#0.0",
    "fra/academic-ascent#0.0",
    "trk/dal-rel-augment-orphan#0.1",
    "fra/ajani-resolute#0.1",
    "fra/chandra-torch-of-defiance#0.2",
    "fra/afterthought-sentry#0.0",
    "fra/afterthought-sentry#0.1",
    # Task 6: events, triggers, references
    "fra/aerid-konstrari#0.1",
    "fra/apex-witchstalker#0.1",
    "fra/archive-arbiter#0.1",
    "fra/archive-arbiter#0.2",
    "fra/archive-arbiter#0.3",
    "fra/craftwork-crusher#0.4",
    "fra/cast-away-doubt#0.0",
    "fra/emrakul-the-exigent-doom#0.0",
    "fra/ingris-stingerquill#0.1",
    "fra/dedicated-commons#0.0",
    "fra/gideons-memorial#0.0",
    "fra/bloombrute#0.1",
    "fra/ajanis-anguish#0.0",
    "fra/charge-the-sanctum#0.2",
    # Task 7: noun phrases, zones, time, comparisons
    "fra/darklight-phoenix#0.1",
    "fra/jiang-yanggu-never-alone#0.1",
    "fra/blessed-ghoul#0.1",
    "fra/diviner-of-victory-unwind-history#1.0",
    "fra/edgar-ancient-bloodlord#0.0",
    "fra/greenhouse-propagator#0.0",
    "fra/cryotheory-adept#0.1",
    "fra/rescue-girl-first-responder#0.1",
    "fra/solarium-sentry#0.0",
    "fra/fatehold-charm#0.2",
    "fra/unsummon#0.0",
    "fra/craftwork-crusher#0.1",
    # Task 9: ability shapes
    "trk/year-of-hell#0.0",
    "trk/borg-cube#0.3",
    "fra/pompous-battlemage-improvised-act#1.0",
    "fra/mind-meanderer#0.1",
    "fra/lichs-relic#0.0",
    "trk/captains-tutelage#0.2",
    "fra/ferocity-of-the-hunt#0.2",
    "fra/craftwork-crusher#0.3",
    # Task 8: sentences, joins
    "fra/ajani-unrelenting#0.2",
    "fra/carnivorous-cultivator-enroot#0.2",
    "fra/compel-brutality#0.1",
    "fra/chandra-chill-of-compliance#0.1",
    "fra/apex-witchstalker#0.2",
    "trk/blood-crypt#0.0",
    # Task 10: long tail
    "trk/erica-ortegas-plucky-pilot#0.1",
    "fra/ajani-unrelenting#0.0",
    "fra/fblthp-knows-the-way#0.1",
    "fra/hapatra-the-desert-frost#0.0",
    "fra/geist-of-saint-thalia#0.1",
    "fra/traxos-academy-guardian#0.0",
    "fra/gallia-the-merrymaker#0.2",
]


@lru_cache(maxsize=None)
def _snap():
    return load_snapshot(ROOT / "data")


def _norm(s):
    from mtglang.evalen import normalize
    return normalize(s)


def _split(ref):
    card, pos = ref.split("#")
    code, slug = card.split("/")
    face, k = pos.split(".")
    return card, code, slug, int(face), k


@pytest.mark.parametrize("ref", MUST_MATCH)
def test_line_matches_oracle(ref):
    card, code, slug, face, k = _split(ref)
    got = render_card_en(ROOT, card)[face]
    want = oracle_lines(_snap()[(code, slug)].faces[face])
    assert _norm(got.lines[int(k)]) == _norm(want[int(k)])


@pytest.mark.parametrize("card", ["fra/aerid-konstrari", "fra/ajani-resolute", "trk/dal-rel-augment-orphan",
                                  "fra/afterthought-sentry", "fra/vigorbloom-vanguard-seed-suture"])
def test_headers_match_scryfall(card):
    code, slug = card.split("/")
    sc = _snap()[(code, slug)]
    for ft, sf in zip(render_card_en(ROOT, card), sc.faces):
        assert ft.name == sf.name
        assert ft.type_line == sf.type_line
        want = f"{sf.power}/{sf.toughness}" if sf.power is not None else (sf.loyalty or sf.defense)
        assert ft.stats == want
