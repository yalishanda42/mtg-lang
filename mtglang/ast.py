"""Semantic AST for MTG-Lang.

About 20 grammatical node kinds. The specific word in each node is a glossary reference (``SymRef``,
``NameRef``, ``EffectRef``); children always sit in named fields (or named ``(slot, node)`` pairs in
``args`` / ``mods``) that state their grammatical role, so renderers can reorder and inflect.

Fields that only record how the source was written (``paren``, ``glued`` …) never change meaning; the
resolution fields (``quantity``, ``number``, ``antecedent``, ``implicit_subject``) are filled in by
``mtglang.resolve`` and never change the written form.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, ClassVar, Iterator


@dataclass(frozen=True, kw_only=True)
class Node:
    kind: ClassVar[str] = "node"
    paren: int = 0          # redundant parentheses written around this node in the source


# ---------------------------------------------------------------- leaves

@dataclass(frozen=True)
class SymRef(Node):
    """A glossary symbol, by its index in symbols.yaml (stable across glyph/ASCII edits)."""
    kind: ClassVar[str] = "sym"
    index: int
    glyph: str


@dataclass(frozen=True)
class NameRef(Node):
    kind: ClassVar[str] = "name"
    key: str


@dataclass(frozen=True)
class EffectRef(Node):
    kind: ClassVar[str] = "effect"
    key: str


@dataclass(frozen=True)
class Mana(Node):
    kind: ClassVar[str] = "mana"
    text: str


@dataclass(frozen=True)
class Num(Node):
    kind: ClassVar[str] = "num"
    value: int
    sign: str = ""          # "", "+", "-" or "−" (as written)


@dataclass(frozen=True)
class Var(Node):
    kind: ClassVar[str] = "var"
    name: str
    sign: str = ""


# ---------------------------------------------------------------- phrases

@dataclass(frozen=True)
class NP(Node):
    """Object / player phrase: quantifier, count, head(s), filters, name, postfix markers."""
    kind: ClassVar[str] = "np"
    quant: SymRef | None = None          # ◎ target, ∀ each, ∃ there is (◎ is written after the count)
    each: SymRef | None = None           # ∀ in ∀(1 ∨ 2)◎♞ — each of the targets
    count: Node | None = None            # 2, X, Bound (≤1), Or (1 ∨ 2)
    count_after: bool = False            # source detail: amount written after the head (✸3)
    heads: tuple = ()                    # SymRef / NameRef / Or / Of …
    filters: tuple = ()                  # Filter, in order
    name: NameRef | None = None          # token name «Cadet»
    post: tuple = ()                     # glued postfix markers (◈⊺ kicked, ≢ different names …)
    neg: bool = False                    # ¬☞ "other than it"
    # resolution
    quantity: str | None = None
    number: str | None = None
    antecedent: str | None = None


@dataclass(frozen=True)
class Bound(Node):
    """Count bound: ≤1 (up to one), ≥1 (one or more)."""
    kind: ClassVar[str] = "bound"
    op: SymRef
    value: Node


@dataclass(frozen=True)
class Of(Node):
    """Relation-noun of something: ☞⚑ (its controller), ◈⌂ (its owner), ◁⚑☞ (its previous controller)."""
    kind: ClassVar[str] = "of"
    rel: SymRef
    of: Node
    prefix: bool = False                 # source detail: ⚑☞ vs ☞⚑
    mods: tuple = ()                     # e.g. ◁ previous
    antecedent: str | None = None


@dataclass(frozen=True)
class Filter(Node):
    kind: ClassVar[str] = "filter"
    conds: tuple = ()


@dataclass(frozen=True)
class Rel(Node):
    """Relation condition inside a filter: ⚑● (controlled by you), ≠◈ (other than this), ⚭◈ …"""
    kind: ClassVar[str] = "rel"
    rel: SymRef
    other: Node | None = None


@dataclass(frozen=True)
class Zone(Node):
    kind: ClassVar[str] = "zone"
    zone: SymRef
    owner: Node | None = None
    pos: SymRef | None = None            # ⌃ top / ⌄ bottom
    count: Node | None = None
    pos_alt: SymRef | None = None        # (⌃ ∨ ⌄)▤ — top or bottom


@dataclass(frozen=True)
class Characteristic(Node):
    kind: ClassVar[str] = "char"
    char: SymRef                         # △ power, ▽ toughness, ⌀ mana value, ♥ life, ♦ colour, ⊤ types …
    of: Node | None = None
    sub: SymRef | None = None            # ⊤▭ card types, ⊤⊡ basic land types
    agg: SymRef | None = None            # Σ total, ⇑ greatest
    prefix: bool = False                 # source detail: ♥● vs ◈△


@dataclass(frozen=True)
class Count(Node):
    """# — the number of …"""
    kind: ClassVar[str] = "count"
    of: Node
    mods: tuple = ()                     # ≢ with different names, ∩ shared


@dataclass(frozen=True)
class Arith(Node):
    kind: ClassVar[str] = "arith"
    op: str                              # "+", "×", "÷"
    left: Node
    right: Node


@dataclass(frozen=True)
class PT(Node):
    """+2/+0, ⊥1/1 (base), 2/2 (token stats)."""
    kind: ClassVar[str] = "pt"
    power: Node
    toughness: Node
    base: SymRef | None = None


@dataclass(frozen=True)
class Time(Node):
    """A time phrase: ⧗, ◷, ◷●, ∀◷●, ⊢☼◷●, ▷◷●, ⧗▷◷●, ⊢▷☾ … (items in written order)."""
    kind: ClassVar[str] = "time"
    items: tuple = ()


@dataclass(frozen=True)
class Or(Node):
    kind: ClassVar[str] = "or"
    items: tuple = ()


@dataclass(frozen=True)
class And(Node):
    kind: ClassVar[str] = "and"
    items: tuple = ()


@dataclass(frozen=True)
class Not(Node):
    kind: ClassVar[str] = "not"
    item: Node


@dataclass(frozen=True)
class Compare(Node):
    """a op b (op c …): ◈△ = X, #▭[⚰●] ≥ 7, 0 ≤ Y ≤ 10."""
    kind: ClassVar[str] = "compare"
    items: tuple
    ops: tuple


@dataclass(frozen=True)
class Keyword(Node):
    kind: ClassVar[str] = "keyword"
    sym: SymRef
    params: tuple = ()
    glued: bool = True                   # source detail: ⊠{2} vs ⚭ ♞


# ---------------------------------------------------------------- sentences

@dataclass(frozen=True)
class Action(Node):
    """subject [?] [¬] verb args mods — slots come from the verb's glossary frame."""
    kind: ClassVar[str] = "action"
    verb: Node | None                    # SymRef or EffectRef
    subject: Node | None = None
    args: tuple = ()                     # ((slot, node), …) in written order; slots name the role:
                                         # amount/object/destination/… from the verb frame, plus modifier
                                         # slots: time, times, marker, filter, restrict, state, additional, rel
    optional: bool = False               # ?
    negated: bool = False                # ¬
    passive: bool = False                # ←
    before: int = 0                      # source detail: how many args are written before the verb
    neg_first: bool = False              # source detail: ¬ written before the subject
    implicit_subject: str | None = None


@dataclass(frozen=True)
class Modify(Node):
    """Characteristic change: ◎♞ +2/+0 ⧗, ● ♥+1, ◈ ⊥7/9, ◈△ × 2."""
    kind: ClassVar[str] = "modify"
    subject: Node | None
    change: Node                         # PT, or Delta
    args: tuple = ()                     # modifier slots, as in Action
    optional: bool = False
    negated: bool = False
    implicit_subject: str | None = None


@dataclass(frozen=True)
class Delta(Node):
    """Signed change of a characteristic: ♥+1 (gain 1 life), ♥-X, ♥ × 2, △ × 2."""
    kind: ClassVar[str] = "delta"
    char: SymRef | None
    amount: Node | None = None           # Num/Var with sign, or None for the bare event ♥+
    sign: str = ""
    times: Node | None = None


@dataclass(frozen=True)
class Scoped(Node):
    """subject [?] (body) — a subject shared by a parenthesised group: ∀◐ ? (⌫☚ ∧ ⤓7)."""
    kind: ClassVar[str] = "scoped"
    subject: Node
    body: Node
    optional: bool = False
    negated: bool = False


@dataclass(frozen=True)
class CostList(Node):
    """Comma-separated costs inside a keyword parameter: ↺({1}{U/R}{U/R}, ⌫1)."""
    kind: ClassVar[str] = "costs"
    items: tuple = ()


@dataclass(frozen=True)
class Coord(Node):
    kind: ClassVar[str] = "coord"
    op: SymRef                           # ∧ / ∨
    items: tuple = ()


@dataclass(frozen=True)
class Conditional(Node):
    kind: ClassVar[str] = "cond"
    mode: str                            # "if" (C ⊃ X), "unless" (X ¬⊃ C), "if_do" (✓ ⊃), "if_dont" (✗ ⊃)
    cond: Node | None
    then: Node


@dataclass(frozen=True)
class Replace(Node):
    """event ⤳ effect; event None = "… instead"."""
    kind: ClassVar[str] = "replace"
    event: Node | None
    effect: Node


@dataclass(frozen=True)
class While(Node):
    """body ∵ cond (as long as / while), body ≈ cond (as though)."""
    kind: ClassVar[str] = "while"
    op: SymRef
    body: Node
    cond: Node


@dataclass(frozen=True)
class Until(Node):
    """body ⊣ until (an event, or a time like ▷◷●)."""
    kind: ClassVar[str] = "until"
    body: Node
    until: Node


@dataclass(frozen=True)
class Bind(Node):
    """X ≔ value — where X is …"""
    kind: ClassVar[str] = "bind"
    var: Var
    value: Node


@dataclass(frozen=True)
class ForEach(Node):
    """(∀○) body — for each opponent, …"""
    kind: ClassVar[str] = "foreach"
    over: Node
    body: Node


@dataclass(frozen=True)
class Nested(Node):
    """A whole ability inside an effect: reflexive (✓ ⇒ …), delayed (⊢▷☾ ⇒ …), granted, bounded."""
    kind: ClassVar[str] = "nested"
    ability: Node


@dataclass(frozen=True)
class Effects(Node):
    kind: ClassVar[str] = "effects"
    sentences: tuple = ()


# ---------------------------------------------------------------- abilities

@dataclass(frozen=True)
class Keywords(Node):
    kind: ClassVar[str] = "keywords"
    items: tuple = ()


@dataclass(frozen=True)
class Triggered(Node):
    kind: ClassVar[str] = "triggered"
    event: Node
    effect: Node
    conds: tuple = ()                    # intervening-if conditions (∧ before ⇒)
    while_: Node | None = None           # trigger-time "while" (∵ before ⇒)


@dataclass(frozen=True)
class Activated(Node):
    kind: ClassVar[str] = "activated"
    cost: tuple
    effect: Node
    limits: tuple = ()                   # ≡✎, ≡ ≤1◷, ≡(cond), ≡◷● — written as trailing "; ≡…" sentences


@dataclass(frozen=True)
class Static(Node):
    kind: ClassVar[str] = "static"
    body: Node


@dataclass(frozen=True)
class Labelled(Node):
    kind: ClassVar[str] = "labelled"
    label: tuple                         # SymRef / NameRef items before ▸
    ability: Node


@dataclass(frozen=True)
class Chapter(Node):
    kind: ClassVar[str] = "chapter"
    numbers: tuple
    ability: Node


@dataclass(frozen=True)
class Threshold(Node):
    kind: ClassVar[str] = "threshold"
    n: int
    ability: Node


@dataclass(frozen=True)
class Mode(Node):
    kind: ClassVar[str] = "mode"
    ability: Node


@dataclass(frozen=True)
class Modal(Node):
    """⊻n followed by • mode lines (built at card level)."""
    kind: ClassVar[str] = "modal"
    choose: Node
    modes: tuple = ()


# ---------------------------------------------------------------- card

@dataclass(frozen=True)
class TypeLine(Node):
    kind: ClassVar[str] = "typeline"
    types: tuple = ()
    subtypes: tuple = ()
    dash: str | None = None


@dataclass(frozen=True)
class Stats(Node):
    kind: ClassVar[str] = "stats"
    stat: str                            # "pt", "loyalty", "defense"
    power: str | None = None
    toughness: str | None = None
    value: str | None = None
    sym: SymRef | None = None


@dataclass(frozen=True)
class Face(Node):
    kind: ClassVar[str] = "face"
    name: NameRef
    cost: tuple
    types: TypeLine
    stats: Stats | None
    abilities: tuple = ()


@dataclass(frozen=True)
class Card(Node):
    kind: ClassVar[str] = "card"
    faces: tuple = ()


# ---------------------------------------------------------------- utilities

_PAIRS = {"args"}


def _fields(node: Node):
    for f in fields(node):
        yield f.name, getattr(node, f.name)


def to_json(node: Any) -> Any:
    """JSON-ready dict for a node (``args``/``mods`` become objects keyed by slot)."""
    if isinstance(node, SymRef):
        out = {"kind": "sym", "sym": node.glyph, "index": node.index}
        if node.paren:
            out["paren"] = node.paren
        return out
    if isinstance(node, Node):
        out: dict[str, Any] = {"kind": node.kind}
        for name, value in _fields(node):
            if name == "paren" and not value:
                continue
            if name in _PAIRS and isinstance(value, tuple):
                obj: dict[str, Any] = {}
                for slot, child in value:
                    key = slot
                    n = 2
                    while key in obj:
                        key = f"{slot}{n}"
                        n += 1
                    obj[key] = to_json(child)
                out[name] = obj
            else:
                out[name] = to_json(value)
        return out
    if isinstance(node, tuple):
        return [to_json(x) for x in node]
    return node


def walk(node: Any, path: str = "") -> Iterator[tuple[str, Node]]:
    """Yield ``(path, node)`` for every node; paths look like ``effect.sentences.0.args.object``."""
    if not isinstance(node, Node):
        return
    yield path, node
    for name, value in _fields(node):
        sub = f"{path}.{name}" if path else name
        if name in _PAIRS and isinstance(value, tuple):
            seen: dict[str, int] = {}
            for slot, child in value:
                k = seen.get(slot, 0)
                seen[slot] = k + 1
                yield from walk(child, f"{sub}.{slot}" + (str(k + 1) if k else ""))
        elif isinstance(value, tuple):
            for i, child in enumerate(value):
                yield from walk(child, f"{sub}.{i}")
        else:
            yield from walk(value, sub)
