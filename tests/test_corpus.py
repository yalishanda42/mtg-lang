"""Checks over the real translated corpus (skipped if the repo has no cards)."""
from pathlib import Path

import pytest

from mtglang.glossary import load_glossary
from mtglang.tokenizer import TokenizeError, _key, to_ascii, tokenize

ROOT = Path(__file__).parent.parent
CARDS = sorted((ROOT / "cards").glob("*/*.mtgl"))


@pytest.mark.skipif(not CARDS, reason="no corpus")
def test_every_card_line_roundtrips_through_ascii():
    g = load_glossary(ROOT / "glossary")
    bad = []
    for p in CARDS:
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            s = line.strip()
            if not s or s.startswith("#") or s == "//":
                continue
            try:
                orig = [_key(t) for t in tokenize(s, g)]
                back = [_key(t) for t in tokenize(to_ascii(s, g), g)]
            except TokenizeError as e:
                bad.append(f"{p.name}:{n}: {e}")
                continue
            if orig != back:
                bad.append(f"{p.name}:{n}: {s!r} -> {to_ascii(s, g)!r}")
    assert bad == []


@pytest.mark.skipif(not CARDS, reason="no corpus")
def test_every_card_parses_and_roundtrips():
    from mtglang.validate import validate_all
    issues, _ = validate_all(ROOT)
    bad = [f"{i.file}:{i.line}: {i.code} {i.message}" for i in issues if i.code in ("S-PARSE", "S-ROUNDTRIP")]
    assert bad == []


@pytest.mark.skipif(not CARDS, reason="no corpus")
def test_every_card_resolves():
    from mtglang.validate import validate_all
    issues, _ = validate_all(ROOT)
    bad = [f"{i.file}:{i.line}: {i.message}" for i in issues if i.code == "S-RESOLVE"]
    assert bad == []
