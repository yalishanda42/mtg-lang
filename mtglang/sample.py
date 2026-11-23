"""Pick a small, feature-covering sample of cards for notation design."""
from __future__ import annotations

import re
from typing import Iterable

from mtglang.oracle import oracle_lines
from mtglang.scryfall import ScryCard

_ABILITY_WORD = r"(?:[A-Z][\w' ,]*? — )?"
_TRIGGER = re.compile(rf"^{_ABILITY_WORD}(When|Whenever|At)\b")


def card_features(c: ScryCard) -> set[str]:
    lines = [l for f in c.faces for l in oracle_lines(f)]
    mode_labels = {k for k in c.keywords if any(l.startswith(f"• {k} —") for l in lines)}
    feats = {f"layout:{c.layout}"} | {f"kw:{k}" for k in c.keywords if k not in mode_labels}
    text = "\n".join(f.oracle_text for f in c.faces)
    types = " ".join(f.type_line for f in c.faces)
    if any(_TRIGGER.match(l) for l in lines):
        feats.add("triggered")
    if any(":" in l.split("(")[0] and not l.startswith("•") and not re.match(r"^[IVX]+(, [IVX]+)* —", l) for l in lines):
        feats.add("activated")
    if "Choose one" in text or "Choose two" in text:
        feats.add("modal")
    if "token" in text:
        feats.add("token")
    for t in ("Saga", "Planeswalker", "Spacecraft", "Planet"):
        if t in types:
            feats.add(t.lower())
    if len(c.faces) > 1:
        feats.add("multiface")
    if not lines:
        feats.add("vanilla")
    return feats


def pick_sample(cards: Iterable[ScryCard], k: int = 30) -> list[ScryCard]:
    pool = sorted(cards, key=lambda c: (c.set_code, c.slug))
    feats = {(c.set_code, c.slug): card_features(c) for c in pool}
    covered: set[str] = set()
    picked: list[ScryCard] = []
    while len(picked) < k:
        best, gain = None, 0
        for c in pool:
            if c in picked:
                continue
            g = len(feats[(c.set_code, c.slug)] - covered)
            if g > gain:
                best, gain = c, g
        if best is None:
            break
        picked.append(best)
        covered |= feats[(best.set_code, best.slug)]
    rest = sorted((c for c in pool if c not in picked),
                  key=lambda c: (sum(len(f.oracle_text) for f in c.faces), c.set_code, c.slug))
    picked.extend(rest[: k - len(picked)])
    return picked
