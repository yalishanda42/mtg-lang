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
