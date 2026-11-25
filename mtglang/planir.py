"""Clause plans: the language-neutral layer between the semantic AST and a language realizer.

A plan is the resolved AST with its sentence- and phrase-level nodes replaced by plan nodes that carry the
decisions every language needs (who the subject is, imperative vs statement, how clauses join, when a phrase
refers back to an earlier one, number and quantity). Phrase-level AST nodes without such decisions (filters,
zones, characteristics, counts, P/T …) stay as AST nodes, with their child phrases converted.

No plan node holds a word of any language. Every decision is a default that keeps the full information
(an anaphor keeps its antecedent's whole phrase; a pronoun choice keeps its reason), so a realizer may
override it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mtglang import ast as A

JOIN_KINDS = frozenset({"sentence", "and", "or", "if", "unless", "instead", "while", "as_though", "until",
                        "during", "for_each", "where"})
LEADS = frozenset({"if_do", "if_dont", "instead"})


@dataclass(frozen=True)
class CardContext:
    """What a realizer needs to know about the card to refer to it."""
    name: str                       # full name (a names.yaml key)
    short: str                      # how the card names itself when legendary
    legendary: bool
    type_syms: tuple[int, ...]      # glossary indexes of the card types (♞, ⚙ …)
    subtype_keys: tuple[str, ...]   # names.yaml keys of the subtypes
    face: int
    is_spell: bool                  # instant / sorcery


@dataclass(frozen=True)
class Gap:
    """An AST node the planner doesn't handle (yet)."""
    kind: str
    path: str


@dataclass(frozen=True)
class Join:
    kind: str                       # one of JOIN_KINDS
    reason: str = "default"


@dataclass(frozen=True)
class PhrasePlan:
    path: str
    heads: tuple = ()
    mods: tuple = ()                # ((slot, value), …): quant, each, count, filter, name, post, pre, neg
    number: str = "sg"              # sg / pl
    quantity: str = "one"           # one / all / each / up_to / exactly / at_least / choice / exists / count / kind / amount
    definite: bool = False
    ref: str = "new"                # new / self / anaphor / you
    antecedent: Any = None         # the full plan of what an anaphor refers to (a phrase, zone, value …)
    person: int = 3
    implicit: bool = False          # an unwritten subject (the ability's controller)
    pronoun: bool = False           # default: refer back with a pronoun
    reason: str = ""


@dataclass(frozen=True)
class ClausePlan:
    path: str
    pred: Any                       # SymRef / EffectRef (a verb) or Delta / PT (a characteristic change) or None
    subject: PhrasePlan | None = None
    args: tuple = ()                # ((slot, value), …)
    optional: bool = False
    negated: bool = False
    passive: bool = False
    mood: str = "indicative"        # imperative (to the ability's controller) / indicative
    tense: str = "present"
    subject_shared: bool = False    # same subject as the previous clause


@dataclass(frozen=True)
class SentencePlan:
    path: str
    clauses: tuple = ()
    joins: tuple = ()               # len(clauses) - 1 Joins
    lead: str | None = None         # if_do / if_dont / instead: a clause-less opener


@dataclass(frozen=True)
class AbilityPlan:
    path: str
    shape: str                      # keywords, static, triggered, activated, modal, mode, chapter, threshold, labelled
    parts: dict = field(default_factory=dict)
    label: tuple = ()


@dataclass(frozen=True)
class FacePlan:
    ctx: CardContext
    name: str
    cost: tuple
    types: A.TypeLine
    stats: A.Stats | None
    abilities: tuple = ()


@dataclass(frozen=True)
class CardPlan:
    faces: tuple = ()
