"""Scryfall data: card model, parsing, fetching and snapshot I/O."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScryFace:
    name: str
    mana_cost: str
    type_line: str
    oracle_text: str
    power: str | None = None
    toughness: str | None = None
    loyalty: str | None = None
    defense: str | None = None


@dataclass(frozen=True)
class ScryCard:
    slug: str
    set_code: str
    name: str
    layout: str
    keywords: list[str] = field(default_factory=list)
    faces: list[ScryFace] = field(default_factory=list)


def slugify(name: str) -> str:
    s = name.lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _face(d: dict, fallback: dict | None = None) -> ScryFace:
    fb = fallback or {}

    def get(k):
        v = d.get(k)
        return v if v is not None else fb.get(k)

    return ScryFace(
        name=d["name"],
        mana_cost=d.get("mana_cost") or "",
        type_line=d.get("type_line") or "",
        oracle_text=d.get("oracle_text") or "",
        power=get("power"),
        toughness=get("toughness"),
        loyalty=get("loyalty"),
        defense=get("defense"),
    )


def parse_card(raw: dict) -> ScryCard:
    if raw.get("card_faces"):
        faces = [_face(f, raw if i == 0 else None) for i, f in enumerate(raw["card_faces"])]
    else:
        faces = [_face(raw)]
    return ScryCard(
        slug=slugify(raw["name"]),
        set_code=raw["set"],
        name=raw["name"],
        layout=raw.get("layout", "normal"),
        keywords=list(raw.get("keywords") or []),
        faces=faces,
    )


# --- network -----------------------------------------------------------------
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Sequence

API = "https://api.scryfall.com"
HEADERS = {"User-Agent": "mtg-lang/0.1", "Accept": "application/json"}
SETS = ("trk", "fra")
CATALOGS = ("creature-types", "artifact-types", "land-types", "enchantment-types",
            "spell-types", "planeswalker-types", "battle-types")


def http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    time.sleep(0.1)
    return data


def fetch_set(code: str, get_json: Callable[[str], dict] = http_get_json) -> list[dict]:
    url: str | None = f"{API}/cards/search?q={urllib.parse.quote('e:' + code)}&unique=cards"
    cards: list[dict] = []
    while url:
        page = get_json(url)
        cards.extend(page.get("data", []))
        url = page.get("next_page") if page.get("has_more") else None
    return cards


def fetch_catalogs(get_json: Callable[[str], dict] = http_get_json) -> dict:
    subtypes: set[str] = set()
    for name in CATALOGS:
        subtypes.update(get_json(f"{API}/catalog/{name}").get("data", []))
    return {"subtypes": sorted(subtypes)}


# --- snapshot ----------------------------------------------------------------

def load_snapshot(data_dir: Path, sets: Sequence[str] = SETS) -> dict[tuple[str, str], ScryCard]:
    snap: dict[tuple[str, str], ScryCard] = {}
    for code in sets:
        path = Path(data_dir) / f"{code}.json"
        if not path.exists():
            continue
        for raw in json.loads(path.read_text(encoding="utf-8")):
            card = parse_card(raw)
            snap[(card.set_code, card.slug)] = card
    return snap


def load_subtypes(data_dir: Path) -> list[str]:
    path = Path(data_dir) / "catalogs.json"
    return json.loads(path.read_text(encoding="utf-8"))["subtypes"] if path.exists() else []


def split_subtypes(text: str, known: Sequence[str]) -> list[str]:
    words = text.split()
    known_set = set(known)
    max_len = max((len(k.split()) for k in known), default=1)
    out: list[str] = []
    i = 0
    while i < len(words):
        for n in range(min(max_len, len(words) - i), 0, -1):
            cand = " ".join(words[i:i + n])
            if n == 1 or cand in known_set:
                out.append(cand)
                i += n
                break
    return out
