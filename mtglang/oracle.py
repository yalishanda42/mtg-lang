"""Oracle text normalization: reminder stripping, line alignment, consistency keys."""
from __future__ import annotations

import re

from mtglang.scryfall import ScryFace

_REMINDER = re.compile(r"\s*\([^()]*\)")
_REMINDER_MULTILINE = re.compile(r"\([^()]*\n[^()]*\)")  # Scryfall data quirk: reminder split across lines


def strip_reminder(text: str) -> str:
    prev = None
    while prev != text:
        prev, text = text, _REMINDER.sub("", text)
    return text.strip()


def oracle_lines(face: ScryFace) -> list[str]:
    text = _REMINDER_MULTILINE.sub("", face.oracle_text)
    lines = (strip_reminder(l) for l in text.split("\n"))
    return [l for l in lines if l]


def normalize_for_consistency(line: str, card_name: str) -> str:
    line = line.replace(card_name, "~")
    if "," in card_name:
        line = line.replace(card_name.split(",", 1)[0], "~")
    return re.sub(r"\s+", " ", line).strip()
