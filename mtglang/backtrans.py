"""Back-translation bundle: notation + legend only (no English), plus an answer key."""
from __future__ import annotations

import random
from pathlib import Path

from mtglang.glossary import Glossary, load_glossary
from mtglang.scryfall import load_snapshot


def legend_text(g: Glossary, lang: str = "en") -> str:
    lines = ["# Legend", "", "glyph | ascii | meaning | definition", "--- | --- | --- | ---"]
    for s in g.symbols:
        lines.append(f"{s.glyph} | {s.ascii} | {g.label(s, lang)} | {s.definition or ''}".rstrip())
    if g.effects:
        lines += ["", "## Named effects", ""]
        lines += [f"⟨{e.key}⟩ | {g.label(e, lang)}" for e in g.effects.values()]
    return "\n".join(lines) + "\n"


def _strip_comments(text: str) -> str:
    return "\n".join(l for l in text.replace("\r\n", "\n").split("\n") if not l.lstrip().startswith("#")).strip()


def backtrans_bundle(root: Path, n: int, seed: int) -> tuple[str, str]:
    root = Path(root)
    g = load_glossary(root / "glossary")
    snap = load_snapshot(root / "data")
    files = sorted((root / "cards").glob("*/*.mtgl"), key=lambda p: (p.parent.name, p.stem))
    picked = random.Random(seed).sample(files, min(n, len(files)))
    bundle = [legend_text(g), "# Cards", "",
              "For each card #k, write its rules text in English, Oracle style. Use only the legend above.", ""]
    key = ["# Answer key", ""]
    for k, path in enumerate(picked, start=1):
        bundle += [f"## #{k}", "```", _strip_comments(path.read_text(encoding="utf-8")), "```", ""]
        card = snap.get((path.parent.name, path.stem))
        oracle = "\n//\n".join(f.oracle_text for f in card.faces) if card else "(no Scryfall card)"
        key += [f"## #{k} — {card.name if card else path.stem}", "```", oracle, "```", ""]
    return "\n".join(bundle), "\n".join(key)
