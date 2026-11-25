"""Bulgarian spelling: modern → Ivanchev (pre-1945) orthography, fully offline."""
from __future__ import annotations

from pathlib import Path

DATA = Path(__file__).parent / "data"
LISTS = ("yatRoots", "yatExclusions", "usRoots", "usExclusions", "nonYatPrefixRoots", "abbreviations",
         "masculine_soft_ending", "feminine_soft_ending", "nouns_in_te", "verbs-te", "verbs_only_homonyms")


def data_path(name: str) -> Path:
    """Path of a vendored data file (``yatRoots`` → ``data/yatRoots.txt``; other names verbatim)."""
    p = DATA / name
    return p if p.suffix else DATA / f"{name}.txt"
