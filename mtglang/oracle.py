"""Oracle text normalization: reminder stripping, line alignment, consistency keys."""
from __future__ import annotations

import re

from mtglang.scryfall import ScryFace

_REMINDER = re.compile(r"\s*\([^()]*\)")


def strip_reminder(text: str) -> str:
    prev = None
    while prev != text:
        prev, text = text, _REMINDER.sub("", text)
    return text.strip()


def oracle_lines(face: ScryFace) -> list[str]:
    lines = (strip_reminder(l) for l in face.oracle_text.split("\n"))
    return [l for l in lines if l]


def normalize_for_consistency(line: str, card_name: str) -> str:
    line = line.replace(card_name, "~")
    if "," in card_name:
        line = line.replace(card_name.split(",", 1)[0], "~")
    return re.sub(r"\s+", " ", line).strip()
