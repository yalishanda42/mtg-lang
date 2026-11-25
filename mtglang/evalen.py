"""AST → English evaluation against Scryfall Oracle text."""
from __future__ import annotations

import re

_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})


def normalize(s: str) -> str:
    """Collapse whitespace and unify typographic quotes; nothing else (articles, commas, order all count)."""
    return re.sub(r"\s+", " ", s.translate(_QUOTES)).strip()
