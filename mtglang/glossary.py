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

SYNTAX_KINDS: frozenset[str] = frozenset({
    "verb", "type", "object", "player", "reference", "zone", "duration", "time", "keyword", "ability_word",
    "counter_kind", "characteristic", "comparison", "infix", "prefix", "postfix", "marker", "structural", "stat",
    "quantifier", "relation",
})
ARG_SLOTS: frozenset[str] = frozenset({
    "object", "amount", "recipient", "destination", "source", "subject", "counter", "ability", "cost", "mana",
    "player", "number", "value", "zone", "types", "filter", "with", "from", "of", "among", "as", "body",
})
PARAM_KINDS: frozenset[str] = frozenset({"cost", "number", "filter", "name"})
SYNTAX_KEYS: frozenset[str] = frozenset({"kind", "args", "subject", "params", "prec", "op", "yields", "state"})
_CLASS_SYNTAX: dict[str, dict] = {
    "action": {"kind": "verb", "args": ["amount", "object"]},
    "keyword": {"kind": "keyword", "params": []},
    "comparison": {"kind": "infix"},
    "logic": {"kind": "marker"},
}


def default_syntax(cls: str) -> dict:
    """Syntactic behaviour a symbol of class ``cls`` has unless its ``syntax:`` field overrides it."""
    if cls in _CLASS_SYNTAX:
        return {k: (list(v) if isinstance(v, list) else v) for k, v in _CLASS_SYNTAX[cls].items()}
    return {"kind": cls if cls in SYNTAX_KINDS else "marker"}


@dataclass(frozen=True)
class Symbol:
    glyph: str
    ascii: str
    cls: str
    labels: dict[str, str]
    role: str | None = None
    oracle: str | None = None
    definition: str | None = None
    syntax: dict | None = None

    def __post_init__(self) -> None:
        merged = default_syntax(self.cls)
        merged.update(self.syntax or {})
        object.__setattr__(self, "syntax", merged)


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
        self._index: dict[int, int] = {id(s): i for i, s in enumerate(self.symbols)}
        for s in self.symbols:
            self.lookup.setdefault(s.glyph, s)
            self.lookup.setdefault(s.ascii, s)

    def index(self, s: Symbol) -> int:
        """Position of a symbol in symbols.yaml (stable identity across glyph/ASCII edits)."""
        return self._index[id(s)]

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
                      role=d.get("role"), oracle=d.get("oracle"), definition=d.get("definition"),
                      syntax=d.get("syntax"))
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
        for problem in _syntax_problems(s.syntax):
            issues.append(Issue("error", "G-SYNTAX", f"symbol {s.glyph!r}: {problem}"))
    for r in ROLES:
        n = sum(1 for s in g.symbols if s.role == r)
        if n != 1:
            issues.append(Issue("error", "G-ROLE", f"role {r!r} defined {n} times (need exactly 1)"))
    issues += _bg_coverage(g)
    for coll in (g.names.values(), g.effects.values()):
        for o in coll:
            if not o.labels.get("en"):
                issues.append(Issue("error", "G-LABEL", f"{o.key!r} has no 'en' label"))
    return issues


BG_LANGS = ("bg", "bg-ivanchev")


def _bg_coverage(g: Glossary) -> list[Issue]:
    """G-LABEL-BG (warning): once any Bulgarian label exists, report entries still missing one — one summary
    per glossary file."""
    groups = (("symbols.yaml", [(s.glyph, s.labels) for s in g.symbols]),
              ("names.yaml", [(n.key, n.labels) for n in g.names.values()]),
              ("named_effects.yaml", [(e.key, e.labels) for e in g.effects.values()]))
    if not any(lang in labels for _, items in groups for _, labels in items for lang in BG_LANGS):
        return []
    out = []
    for fname, items in groups:
        missing = [k for k, labels in items if not all(labels.get(lang) for lang in BG_LANGS)]
        if missing:
            more = f" … (+{len(missing) - 5})" if len(missing) > 5 else ""
            out.append(Issue("warning", "G-LABEL-BG",
                             f"{fname}: {len(missing)} entr(y/ies) without bg / bg-ivanchev: "
                             f"{', '.join(missing[:5])}{more}"))
    return out


def _syntax_problems(syn: dict) -> list[str]:
    out = []
    if not isinstance(syn, dict):
        return ["syntax must be a map"]
    for k in syn:
        if k not in SYNTAX_KEYS:
            out.append(f"unknown syntax key {k!r}")
    if syn.get("kind") not in SYNTAX_KINDS:
        out.append(f"unknown syntax kind {syn.get('kind')!r}")
    for key, allowed in (("args", ARG_SLOTS), ("params", PARAM_KINDS)):
        if key in syn:
            v = syn[key]
            if not isinstance(v, list) or any(x not in allowed for x in v):
                out.append(f"syntax {key} must be a list drawn from {sorted(allowed)}")
    if "subject" in syn and syn["subject"] not in ARG_SLOTS:
        out.append(f"unknown subject slot {syn['subject']!r}")
    for flag in ("yields", "state"):
        if flag in syn and not isinstance(syn[flag], bool):
            out.append(f"syntax {flag} must be true or false")
    if "op" in syn and not isinstance(syn["op"], str):
        out.append("syntax op must be a name")
    if "prec" in syn and (not isinstance(syn["prec"], int) or isinstance(syn["prec"], bool)):
        out.append("syntax prec must be an integer")
    return out


def sync_names(root: Path) -> int:
    """Append missing card names, face names and subtypes from the snapshot to glossary/names.yaml."""
    from mtglang.scryfall import load_snapshot, load_subtypes, split_subtypes

    root = Path(root)
    path = root / "glossary" / "names.yaml"
    entries = _read_yaml(path)
    have = {str(e["key"]) for e in entries}
    known = load_subtypes(root / "data")
    added = 0

    def add(key: str, cls: str) -> None:
        nonlocal added
        if key and key not in have:
            entries.append({"key": key, "class": cls, "labels": {"en": key}})
            have.add(key)
            added += 1

    for card in sorted(load_snapshot(root / "data").values(), key=lambda c: (c.set_code, c.slug)):
        for face in card.faces:
            add(face.name, "card")
        for face in card.faces:
            if " — " in face.type_line:
                for sub in split_subtypes(face.type_line.split(" — ", 1)[1], known):
                    add(sub, "subtype")
    if added:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for e in entries:
            lines.append("- " + yaml.safe_dump(e, allow_unicode=True, sort_keys=False, default_flow_style=True,
                                               width=10_000).strip())
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return added
