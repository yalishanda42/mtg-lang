"""Glossary: the closed vocabulary (symbols) plus proper names and named effects."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from mtglang.issues import Issue

ROLES: tuple[str, ...] = (
    "implies", "cost_sep", "label_sep", "mode_bullet", "threshold_sep", "chapter",
    "name_open", "name_close", "effect_open", "effect_close", "self", "loyalty", "defense",
)
GRAMMAR_ROLES: tuple[str, ...] = ("implies", "cost_sep", "label_sep", "mode_bullet", "threshold_sep", "chapter")
RESERVED_CHARS = set("[](){},/+-—−")
RESERVED_EXACT = {"X", "Y", "Z"}
_WORD = re.compile(r"[A-Za-z]{3,}")


@dataclass(frozen=True)
class Symbol:
    glyph: str
    ascii: str
    cls: str
    labels: dict[str, str]
    role: str | None = None
    oracle: str | None = None
    definition: str | None = None


@dataclass(frozen=True)
class Name:
    key: str
    cls: str
    labels: dict[str, str]


@dataclass(frozen=True)
class NamedEffect:
    key: str
    card: str
    labels: dict[str, str]


@dataclass
class Glossary:
    symbols: list[Symbol]
    names: dict[str, Name] = field(default_factory=dict)
    effects: dict[str, NamedEffect] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.lookup: dict[str, Symbol] = {}
        for s in self.symbols:
            self.lookup.setdefault(s.glyph, s)
            self.lookup.setdefault(s.ascii, s)

    def role(self, r: str) -> Symbol:
        for s in self.symbols:
            if s.role == r:
                return s
        raise KeyError(f"glossary has no symbol with role {r!r}")

    def label(self, obj: Symbol | Name | NamedEffect, lang: str = "en") -> str:
        fallback = obj.glyph if isinstance(obj, Symbol) else obj.key
        return obj.labels.get(lang) or obj.labels.get("en") or fallback


def _read_yaml(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


def load_glossary(dir: Path) -> Glossary:
    dir = Path(dir)
    symbols = [Symbol(glyph=str(d["glyph"]), ascii=str(d["ascii"]), cls=d["class"], labels=d.get("labels") or {},
                      role=d.get("role"), oracle=d.get("oracle"), definition=d.get("definition"))
               for d in _read_yaml(dir / "symbols.yaml")]
    names = {str(d["key"]): Name(str(d["key"]), d["class"], d.get("labels") or {}) for d in _read_yaml(dir / "names.yaml")}
    effects = {str(d["key"]): NamedEffect(str(d["key"]), d.get("card", ""), d.get("labels") or {})
               for d in _read_yaml(dir / "named_effects.yaml")}
    return Glossary(symbols, names, effects)


def check_glossary(g: Glossary) -> list[Issue]:
    issues: list[Issue] = []
    owner: dict[str, int] = {}
    for i, s in enumerate(g.symbols):
        for text in {s.glyph, s.ascii}:
            if text in owner and owner[text] != i:
                issues.append(Issue("error", "G-DUP", f"{text!r} used by two symbols"))
            owner.setdefault(text, i)
            if _WORD.search(text):
                issues.append(Issue("error", "G-WORD", f"{text!r} contains a run of 3+ letters"))
            if (set(text) & RESERVED_CHARS) or text in RESERVED_EXACT or text.isdigit() or not text.strip():
                issues.append(Issue("error", "G-RESERVED", f"{text!r} uses reserved punctuation, a variable letter or digits"))
        if not s.labels.get("en"):
            issues.append(Issue("error", "G-LABEL", f"symbol {s.glyph!r} has no 'en' label"))
    for r in ROLES:
        n = sum(1 for s in g.symbols if s.role == r)
        if n != 1:
            issues.append(Issue("error", "G-ROLE", f"role {r!r} defined {n} times (need exactly 1)"))
    for coll in (g.names.values(), g.effects.values()):
        for o in coll:
            if not o.labels.get("en"):
                issues.append(Issue("error", "G-LABEL", f"{o.key!r} has no 'en' label"))
    return issues
