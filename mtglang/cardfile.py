"""Card files (`cards/<set>/<slug>.mtgl`): split into faces, headers and ability lines."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from lark import Tree

from mtglang.issues import Issue
from mtglang.lineparser import LineParser, LineSyntaxError
from mtglang.tokenizer import TokenizeError, tokenize

_PT = re.compile(r"^[0-9X*+\-]+/[0-9X*+\-]+$")


@dataclass
class AbilityLine:
    lineno: int
    text: str
    tree: Tree | None
    indent: int = 0
    ast: object | None = None


@dataclass
class FaceDoc:
    name: str
    mana: str
    type_line: str
    type_tree: Tree | None
    stats: str | None
    abilities: list[AbilityLine] = field(default_factory=list)
    header_lineno: int = 0
    type_lineno: int = 0
    type_ast: object | None = None


@dataclass
class CardDoc:
    path: Path
    set_code: str
    slug: str
    faces: list[FaceDoc]


def _is_stats(line: str, parser: LineParser) -> bool:
    if _PT.match(line.replace(" ", "")):
        return True
    for role in ("loyalty", "defense"):
        s = parser.g.role(role)
        for mark in {s.glyph, s.ascii}:
            if line.startswith(mark) and line[len(mark):].strip().isdigit():
                return True
    return False


def read_card_text(path: Path) -> str | None:
    """Read a card file as UTF-8 (a leading BOM is ignored); None if it isn't valid UTF-8."""
    try:
        return Path(path).read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def parse_card_file(path: Path, parser: LineParser, sem=None) -> tuple[CardDoc | None, list[Issue]]:
    """Read a card file. With ``sem`` (a SemParser), also attach the semantic AST to every line and report
    S-PARSE (line doesn't parse) and S-ROUNDTRIP (unparse differs from the source by token identity)."""
    doc, issues = _parse_card_file(path, parser)
    if doc is not None and sem is not None:
        issues += attach_ast(doc, sem)
    return doc, issues


def attach_ast(doc: "CardDoc", sem) -> list[Issue]:
    from mtglang.semparse import SemSyntaxError
    from mtglang.tokenizer import _key
    from mtglang.unparse import Unparser
    u = Unparser(sem.g)
    file = str(doc.path)
    issues: list[Issue] = []

    def same(a: str, b: str) -> bool:
        return [_key(t) for t in tokenize(a, sem.g)] == [_key(t) for t in tokenize(b, sem.g)]

    for f in doc.faces:
        try:
            f.type_ast = sem.parse_type_line(f.type_line)
        except SemSyntaxError as e:
            issues.append(Issue("error", "S-PARSE", f"type line: {e.message}", file, f.type_lineno, e.col))
        for a in f.abilities:
            try:
                node = sem.parse_ability(a.text)
            except SemSyntaxError as e:
                issues.append(Issue("error", "S-PARSE", e.message, file, a.lineno, e.col + a.indent))
                continue
            back = u.node(node)
            if not same(back, a.text):
                issues.append(Issue("error", "S-ROUNDTRIP", f"unparses as {back!r}", file, a.lineno))
                continue
            a.ast = node
    return issues


def _parse_card_file(path: Path, parser: LineParser) -> tuple[CardDoc | None, list[Issue]]:
    path = Path(path)
    file = str(path)
    issues: list[Issue] = []
    text = read_card_text(path)
    if text is None:
        return None, [Issue("error", "C-ENCODING", "file is not valid UTF-8", file)]
    raw = text.replace("\r\n", "\n").replace("\r", "\n")
    numbered = [(i, l.rstrip()) for i, l in enumerate(raw.split("\n"), start=1)]
    numbered = [(i, l) for i, l in numbered if l.strip() and not l.lstrip().startswith("#")]
    if not numbered:
        return None, [Issue("error", "C-EMPTY", "card file has no content", file)]

    groups: list[list[tuple[int, str]]] = [[]]
    for i, l in numbered:
        if l.strip() == "//":
            groups.append([])
        else:
            groups[-1].append((i, l))

    faces: list[FaceDoc] = []
    for group in groups:
        if not group:
            issues.append(Issue("error", "C-HEADER", "empty face", file))
            return None, issues
        (hl, header), rest = group[0], group[1:]
        try:
            htoks = tokenize(header, parser.g)
        except TokenizeError as e:
            return None, issues + [Issue("error", "C-HEADER", e.message, file, hl, e.col)]
        if not htoks or htoks[0].type != "NAME" or any(t.type != "MANA" for t in htoks[1:]):
            return None, issues + [Issue("error", "C-HEADER", "first line must be «Name» followed only by mana symbols", file, hl)]
        if not rest:
            return None, issues + [Issue("error", "C-HEADER", "missing type line", file, hl)]
        (tl, type_text), rest = rest[0], rest[1:]
        try:
            type_tree = parser.parse_type_line(type_text)
        except LineSyntaxError as e:
            type_tree = None
            issues.append(Issue("error", "C-SYNTAX", f"type line: {e.message}", file, tl, e.col))
        stats = None
        if rest and _is_stats(rest[0][1].strip(), parser):
            stats = rest[0][1].strip()
            rest = rest[1:]
        abilities = []
        for ln, original in rest:
            text = original.strip()
            indent = len(original) - len(original.lstrip())
            try:
                tree = parser.parse_ability(text)
            except LineSyntaxError as e:
                tree = None
                issues.append(Issue("error", "C-SYNTAX", e.message, file, ln, e.col + indent))
            abilities.append(AbilityLine(ln, text, tree, indent))
        faces.append(FaceDoc(htoks[0].value, "".join(t.value for t in htoks[1:]), type_text.strip(),
                             type_tree, stats, abilities, hl, tl))
    return CardDoc(path, path.parent.name, path.stem, faces), issues
