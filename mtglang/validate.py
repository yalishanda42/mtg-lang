"""Validate all card files against the grammar, the glossary and the Scryfall snapshot."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from lark import Token, Tree

from mtglang.cardfile import CardDoc, FaceDoc, parse_card_file
from mtglang import ast as A
from mtglang.glossary import Glossary, check_glossary, load_glossary
from mtglang.issues import Issue
from mtglang.lineparser import LineParser
from mtglang.oracle import normalize_for_consistency, oracle_lines
from mtglang.scryfall import ScryCard, ScryFace, load_snapshot
from mtglang.tokenizer import ASCII_PUNCT, TokenizeError, tokenize

EFFECT_RATE_LIMIT = 0.05
MANA_SYMBOL = re.compile(r"^\{(\d+|[WUBRGCXYZSTQE]|[WUBRGC2]/[WUBRGP]|[WUBRG]/[WUBRG]/P|½|∞)\}$")


def _err(code, msg, file=None, line=None, col=None, severity="error"):
    return Issue(severity, code, msg, file, line, col)


def check_definitions(g: Glossary) -> list[Issue]:
    out = []
    for s in g.symbols:
        if s.definition:
            try:
                tokenize(s.definition, g)
            except TokenizeError as e:
                out.append(_err("G-DEF", f"definition of {s.glyph!r}: {e.message}"))
    return out


def check_refs(doc: CardDoc, g: Glossary, known_names: set[str]) -> list[Issue]:
    out = []
    file = str(doc.path)
    for f in doc.faces:
        if f.name not in known_names:
            out.append(_err("V-NAME-UNKNOWN", f"name «{f.name}» is not in the glossary", file, f.header_lineno, 1))
        texts = [(f.header_lineno + 1, f.type_line)] + [(a.lineno, a.text) for a in f.abilities]
        for ln, text in texts:
            try:
                toks = tokenize(text, g)
            except TokenizeError:
                continue  # already reported as C-SYNTAX
            for t in toks:
                if t.type == "NAME" and t.value not in known_names:
                    out.append(_err("V-NAME-UNKNOWN", f"name «{t.value}» is not in the glossary", file, ln, t.col))
                if t.type == "MANA" and not MANA_SYMBOL.match(t.value):
                    out.append(_err("V-MANA-UNKNOWN", f"{t.value} is not a Magic mana/game symbol", file, ln, t.col))
                if t.type == "EFFECT" and t.value not in g.effects:
                    out.append(_err("V-EFFECT-UNKNOWN", f"named effect ⟨{t.value}⟩ is not defined", file, ln, t.col))
    return out


def english_type_line(tl, g: Glossary) -> str:
    """English type line from the semantic TypeLine (used to compare against Scryfall)."""
    def word(n) -> str:
        if isinstance(n, A.NameRef):
            return g.label(g.names[n.key]) if n.key in g.names else n.key
        return g.label(g.symbols[n.index])
    left = " ".join(word(t) for t in tl.types)
    return left + (" — " + " ".join(word(t) for t in tl.subtypes) if tl.dash is not None else "")


def _stats_ok(face: FaceDoc, sf: ScryFace, g: Glossary) -> str | None:
    """Return None when stats match, else the expected text."""
    got = face.stats.replace(" ", "") if face.stats else None
    if sf.power is not None:
        want = f"{sf.power}/{sf.toughness}"
        return None if got == want else want
    for role, value in (("loyalty", sf.loyalty), ("defense", sf.defense)):
        if value is not None:
            s = g.role(role)
            ok = got is not None and any(got == m + value for m in {s.glyph, s.ascii})
            return None if ok else s.glyph + value
    return None if got is None else "(no stats line)"


def check_against_scryfall(doc: CardDoc, card: ScryCard, g: Glossary) -> list[Issue]:
    file = str(doc.path)
    if len(doc.faces) != len(card.faces):
        return [_err("V-FACES", f"{len(doc.faces)} face(s) in file but {len(card.faces)} on Scryfall", file)]
    out = []
    for f, sf in zip(doc.faces, card.faces):
        hl = f.header_lineno
        if f.name != sf.name:
            out.append(_err("V-CARDNAME", f"name «{f.name}» ≠ Scryfall {sf.name!r}", file, hl))
        if f.mana != sf.mana_cost:
            out.append(_err("V-MANA", f"mana {f.mana or '(none)'} ≠ Scryfall {sf.mana_cost or '(none)'}", file, hl))
        if f.type_ast is not None:
            eng = english_type_line(f.type_ast, g)
            if eng != sf.type_line:
                out.append(_err("V-TYPE", f"type line reads {eng!r} ≠ Scryfall {sf.type_line!r}", file, hl + 1))
        want = _stats_ok(f, sf, g)
        if want is not None:
            out.append(_err("V-STATS", f"stats {f.stats or '(none)'} ≠ expected {want}", file, hl + 2))
        n_or = len(oracle_lines(sf))
        if len(f.abilities) != n_or:
            out.append(_err("V-ALIGN", f"face «{f.name}»: {len(f.abilities)} notation line(s) but {n_or} Oracle line(s)", file, hl))
    return out


def canonical(text: str, g: Glossary) -> tuple:
    return tuple((t.type, ASCII_PUNCT.get(t.value, t.value)) for t in tokenize(text, g))


def check_consistency(pairs: list[tuple[str, str, str, int]], g: Glossary) -> list[Issue]:
    """pairs: (normalized oracle line, notation text, file, line)."""
    groups: dict[str, dict[tuple, list[str]]] = defaultdict(lambda: defaultdict(list))
    for oracle, notation, file, line in pairs:
        try:
            key = canonical(notation, g)
        except TokenizeError:
            continue
        groups[oracle][key].append(f"{file}:{line}")
    out = []
    for oracle, variants in sorted(groups.items()):
        if len(variants) > 1:
            where = "; ".join(", ".join(locs) for locs in variants.values())
            out.append(_err("V-CONSISTENCY", f"Oracle line {oracle!r} has {len(variants)} different notations: {where}"))
    return out


def validate_all(root: Path, sets: Iterable[str] | None = None, only_existing: bool = False) -> tuple[list[Issue], dict]:
    root = Path(root)
    g = load_glossary(root / "glossary")
    issues = check_glossary(g)
    stats = {"cards": 0, "ability_lines": 0, "ast_lines": 0, "named_effect_lines": 0, "named_effect_rate": 0.0}
    if any(i.code == "G-ROLE" for i in issues):
        return issues, stats  # tokenizer cannot work without the structural roles
    issues += check_definitions(g)
    parser = LineParser(g)
    from mtglang.semparse import SemParser
    sem = SemParser(g)
    snap = load_snapshot(root / "data")
    wanted = set(sets) if sets else None
    if wanted:
        snap = {k: v for k, v in snap.items() if k[0] in wanted}
    known_names = set(g.names) | {c.name for c in snap.values()} | {f.name for c in snap.values() for f in c.faces}

    files = sorted((root / "cards").glob("*/*.mtgl"))
    if wanted:
        files = [p for p in files if p.parent.name in wanted]
    seen: set[tuple[str, str]] = set()
    pairs: list[tuple[str, str, str, int]] = []
    for path in files:
        doc, file_issues = parse_card_file(path, parser, sem)
        issues += file_issues
        if doc is None:
            continue
        key = (doc.set_code, doc.slug)
        seen.add(key)
        stats["cards"] += 1
        for f in doc.faces:
            stats["ability_lines"] += len(f.abilities)
            stats["ast_lines"] += sum(1 for a in f.abilities if a.ast is not None)
            for a in f.abilities:
                try:
                    if any(t.type == "EFFECT" for t in tokenize(a.text, g)):
                        stats["named_effect_lines"] += 1
                except TokenizeError:
                    pass
        issues += check_refs(doc, g, known_names)
        card = snap.get(key)
        if card is None:
            issues.append(_err("V-ORPHAN", "no Scryfall card in scope for this file", str(path)))
            continue
        sc = check_against_scryfall(doc, card, g)
        issues += sc
        if not any(i.code in ("V-FACES", "V-ALIGN") for i in sc):
            for f, sf in zip(doc.faces, card.faces):
                for a, o in zip(f.abilities, oracle_lines(sf)):
                    pairs.append((normalize_for_consistency(o, sf.name), a.text, str(path), a.lineno))
    if not only_existing:
        for key in sorted(set(snap) - seen):
            issues.append(_err("V-MISSING", f"no card file for {key[0]}/{key[1]} ({snap[key].name})"))
    issues += check_consistency(pairs, g)
    if stats["ability_lines"]:
        stats["named_effect_rate"] = stats["named_effect_lines"] / stats["ability_lines"]
    if stats["named_effect_rate"] >= EFFECT_RATE_LIMIT:
        issues.append(_err("V-EFFECT-RATE", f"named effects on {stats['named_effect_rate']:.1%} of ability lines "
                                            f"(target < {EFFECT_RATE_LIMIT:.0%})", severity="warning"))
    return issues, stats
