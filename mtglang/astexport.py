"""Build card ASTs for the corpus: per-card lookup, coverage counts, JSON export."""
from __future__ import annotations

import json
from pathlib import Path

from mtglang import ast as A
from mtglang.cardfile import parse_card_file
from mtglang.glossary import load_glossary
from mtglang.lineparser import LineParser
from mtglang.semparse import SemParser, SemSyntaxError, build_card


class _Ctx:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.g = load_glossary(self.root / "glossary")
        self.lp = LineParser(self.g)
        self.sem = SemParser(self.g)

    def files(self):
        return sorted((self.root / "cards").glob("*/*.mtgl"))


def card_ast(root: Path, ref: str) -> A.Card | None:
    """Resolved AST of ``<set>/<slug>``; None if the file doesn't exist. Raises SemSyntaxError on a bad line."""
    ctx = _Ctx(root)
    path = ctx.root / "cards" / (ref + ".mtgl")
    if not path.exists():
        return None
    doc, _ = parse_card_file(path, ctx.lp)
    if doc is None:
        return None
    from mtglang.resolve import resolve_card
    return resolve_card(build_card(doc, ctx.sem), ctx.g)[0]


def coverage(root: Path) -> dict:
    """Counts of ability lines that parse / round-trip, plus the first failures grouped by message."""
    ctx = _Ctx(root)
    total = parsed = roundtrip = 0
    failures: dict[str, list[str]] = {}
    for path in ctx.files():
        doc, issues = parse_card_file(path, ctx.lp, ctx.sem)
        if doc is None:
            continue
        for f in doc.faces:
            total += len(f.abilities)
            roundtrip += sum(1 for a in f.abilities if a.ast is not None)
        bad_parse = {i.line for i in issues if i.code == "S-PARSE"}
        parsed += sum(1 for f in doc.faces for a in f.abilities if a.lineno not in bad_parse)
        for i in issues:
            if i.code in ("S-PARSE", "S-ROUNDTRIP"):
                failures.setdefault(f"{i.code}: {i.message}", []).append(f"{path.parent.name}/{path.stem}:{i.line}")
    return {"total": total, "parsed": parsed, "roundtrip": roundtrip, "failures": failures}


def export_ast(root: Path, out: Path) -> list[Path]:
    """Write ``<out>/ast/<set>.json`` — a list of ``{slug, ast}`` for every card that parses."""
    from mtglang.ast import to_json
    ctx = _Ctx(root)
    by_set: dict[str, list] = {}
    for path in ctx.files():
        doc, _ = parse_card_file(path, ctx.lp)
        if doc is None:
            continue
        try:
            card = build_card(doc, ctx.sem)
        except SemSyntaxError:
            continue
        from mtglang.resolve import resolve_card
        card = resolve_card(card, ctx.g)[0]
        by_set.setdefault(doc.set_code, []).append({"slug": doc.slug, "ast": to_json(card)})
    written = []
    for code, cards in sorted(by_set.items()):
        p = Path(out) / "ast" / f"{code}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cards, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        written.append(p)
    return written
