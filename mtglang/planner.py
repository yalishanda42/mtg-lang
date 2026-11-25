"""Planner: resolved AST → language-neutral clause plans (see ``mtglang.planir``)."""
from __future__ import annotations

import dataclasses
from typing import Any

from mtglang import ast as A
from mtglang.glossary import Glossary
from mtglang.planir import (AbilityPlan, CardContext, CardPlan, ClausePlan, FacePlan, Gap, Join, PhrasePlan,
                            SentencePlan)


def _child_paths(node: A.Node, path: str):
    """(field name, value, path) for each field, with ``args``-style pairs named as ``A.walk`` names them."""
    for f in dataclasses.fields(node):
        v = getattr(node, f.name)
        sub = f"{path}.{f.name}" if path else f.name
        yield f.name, v, sub


def _pair_paths(pairs: tuple, base: str):
    seen: dict[str, int] = {}
    for slot, child in pairs:
        k = seen.get(slot, 0)
        seen[slot] = k + 1
        yield slot, child, f"{base}.{slot}" + (str(k + 1) if k else "")


def context_for(card: A.Card, face: int, g: Glossary) -> CardContext:
    f = card.faces[face]
    types = tuple(t.index for t in f.types.types if isinstance(t, A.SymRef))
    subs = tuple(t.key for t in f.types.subtypes if isinstance(t, A.NameRef))
    words = {g.symbols[i].labels.get("en", "") for i in types}
    legendary = "Legendary" in words
    is_spell = bool(words & {"Instant", "Sorcery"})
    name = f.name.key
    short = g.names[name].lex.get("en", {}).get("short") if name in g.names else None
    if not short:
        if "Planeswalker" in words and subs:
            short = subs[0]
        else:
            short = name.split(",", 1)[0]
    return CardContext(name=name, short=short, legendary=legendary, type_syms=types, subtype_keys=subs,
                       face=face, is_spell=is_spell)


class Planner:
    def __init__(self, g: Glossary, card: A.Card):
        self.g = g
        self.card = card
        self.at = dict(A.walk(card))
        self._self_seen = False

    # ------------------------------------------------------------ helpers
    def op(self, s) -> str | None:
        return self.g.symbols[s.index].syntax.get("op") if isinstance(s, A.SymRef) else None

    # ------------------------------------------------------------ abilities
    def ability(self, node: A.Node, path: str) -> AbilityPlan | Gap:
        fn = ABILITY_KINDS.get(type(node))
        return fn(self, node, path) if fn else Gap(node.kind, path)

    def ab_keywords(self, n: A.Keywords, path):
        return AbilityPlan(path, "keywords", {"items": self.conv(n.items, f"{path}.items")})

    def ab_static(self, n: A.Static, path):
        return AbilityPlan(path, "static", {"body": self.sentence(n.body, f"{path}.body")})

    def ab_triggered(self, n: A.Triggered, path):
        parts = {"event": self.sentence(n.event, f"{path}.event"),
                 "conds": tuple(self.sentence(c, f"{path}.conds.{i}") for i, c in enumerate(n.conds)),
                 "while_": self.sentence(n.while_, f"{path}.while_") if n.while_ is not None else None,
                 "effect": self.sentence(n.effect, f"{path}.effect")}
        return AbilityPlan(path, "triggered", parts)

    def ab_activated(self, n: A.Activated, path):
        cost = tuple(self._cost(c, f"{path}.cost.{i}") for i, c in enumerate(n.cost))
        parts = {"cost": cost, "effect": self.sentence(n.effect, f"{path}.effect"),
                 "limits": tuple(self.sentence(c, f"{path}.limits.{i}") for i, c in enumerate(n.limits))}
        return AbilityPlan(path, "activated", parts)

    def _cost(self, c, path):
        """A cost is paid by the ability's controller: a subject-less cost action is an imperative to them."""
        if type(c) not in SENTENCE_KINDS:
            return self.conv(c, path)
        p = self.sentence(c, path)
        if isinstance(p, ClausePlan) and p.subject is None and not p.subject_shared:
            p = dataclasses.replace(p, mood="imperative", subject=PhrasePlan(
                f"{path}.subject", ref="you", person=2, definite=True, implicit=True, reason="cost payer"))
        return p

    def ab_labelled(self, n: A.Labelled, path):
        return AbilityPlan(path, "labelled", {"ability": self.ability(n.ability, f"{path}.ability")}, label=n.label)

    def ab_chapter(self, n: A.Chapter, path):
        return AbilityPlan(path, "chapter", {"numbers": n.numbers, "ability": self.ability(n.ability, f"{path}.ability")})

    def ab_threshold(self, n: A.Threshold, path):
        return AbilityPlan(path, "threshold", {"n": n.n, "ability": self.ability(n.ability, f"{path}.ability")})

    def ab_mode(self, n: A.Mode, path):
        return AbilityPlan(path, "mode", {"ability": self.ability(n.ability, f"{path}.ability")})

    def ab_modal(self, n: A.Modal, path):
        return AbilityPlan(path, "modal", {
            "choose": self.conv(n.choose, f"{path}.choose"),
            "modes": tuple(self.ability(m, f"{path}.modes.{i}") for i, m in enumerate(n.modes))})

    # ------------------------------------------------------------ sentences
    def sentence(self, node: A.Node, path: str):
        """A sentence-level node → SentencePlan / ClausePlan / Gap."""
        fn = SENTENCE_KINDS.get(type(node))
        if fn is None:
            if type(node) in PHRASE_ONLY or isinstance(node, A.SymRef):
                return self.conv(node, path)
            return Gap(node.kind, path)
        return fn(self, node, path)

    def s_effects(self, n: A.Effects, path):
        clauses, joins = [], []
        for i, s in enumerate(n.sentences):
            p = self.sentence(s, f"{path}.sentences.{i}")
            if clauses:
                joins.append(Join("where", "variable definition") if isinstance(s, A.Bind) else Join("sentence"))
            clauses.append(p)
        return SentencePlan(path, tuple(clauses), tuple(joins))

    def s_coord(self, n: A.Coord, path):
        if all(isinstance(x, _VALUES) for x in n.items):
            return self.conv(n, path)
        kind = "or" if self.op(n.op) == "or" else "and"
        clauses = []
        for i, x in enumerate(n.items):
            c = self.sentence(x, f"{path}.items.{i}")
            prev = clauses[-1] if clauses else None
            if (isinstance(c, ClausePlan) and isinstance(prev, ClausePlan) and not c.subject_shared
                    and c.subject is not None and prev.subject is not None
                    and _same_phrase(c.subject, prev.subject)):
                c = dataclasses.replace(c, subject_shared=True)
            clauses.append(c)
        return SentencePlan(path, tuple(clauses), tuple(Join(kind) for _ in clauses[1:]))

    def _subject(self, n, path, prev_subject=None):
        if n.subject is not None:
            return self.phrase(n.subject, f"{path}.subject"), "indicative", False
        if n.implicit_subject == "controller":
            return PhrasePlan(f"{path}.subject", ref="you", person=2, definite=True, implicit=True,
                              reason="ability controller"), "imperative", False
        if n.implicit_subject == "shared":
            return None, "indicative", True
        return None, "indicative", False

    def s_action(self, n: A.Action, path):
        subject, mood, shared = self._subject(n, path)
        args = tuple((slot, self.sentence(c, p) if type(c) in SENTENCE_KINDS else self.conv(c, p))
                     for slot, c, p in _pair_paths(n.args, f"{path}.args"))
        verb = self.conv(n.verb, f"{path}.verb") if n.verb is not None else None
        vop = self.op(n.verb)
        if vop == "cast":           # the object of "cast" is a spell
            args = tuple((s, _as_spell(v)) if s == "object" else (s, v) for s, v in args)
        if vop == "cost_change" and subject is not None:
            subject = _as_spell(subject)
        return ClausePlan(path, verb, subject, args, optional=n.optional, negated=n.negated, passive=n.passive,
                          mood=mood, subject_shared=shared)

    def s_modify(self, n: A.Modify, path):
        subject, mood, shared = self._subject(n, path)
        args = tuple((slot, self.conv(c, p)) for slot, c, p in _pair_paths(n.args, f"{path}.args"))
        return ClausePlan(path, self.conv(n.change, f"{path}.change"), subject, args, optional=n.optional,
                          negated=n.negated, mood=mood, subject_shared=shared)

    def s_cond(self, n: A.Conditional, path):
        then = self.sentence(n.then, f"{path}.then")
        if n.mode in ("if_do", "if_dont"):
            return SentencePlan(path, (then,), (), lead=n.mode)
        cond = self.sentence(n.cond, f"{path}.cond")
        if n.mode == "unless":
            return SentencePlan(path, (then, cond), (Join("unless"),))
        return SentencePlan(path, (cond, then), (Join("if"),))

    def s_replace(self, n: A.Replace, path):
        if n.event is None:
            return SentencePlan(path, (self.sentence(n.effect, f"{path}.effect"),), (), lead="instead")
        return SentencePlan(path, (self.sentence(n.event, f"{path}.event"), self.sentence(n.effect, f"{path}.effect")),
                            (Join("instead"),))

    def s_while(self, n: A.While, path):
        kind = "as_though" if self.op(n.op) == "as_though" else "while"
        return SentencePlan(path, (self.sentence(n.body, f"{path}.body"), self.sentence(n.cond, f"{path}.cond")),
                            (Join(kind),))

    def s_until(self, n: A.Until, path):
        return SentencePlan(path, (self.sentence(n.body, f"{path}.body"), self.sentence(n.until, f"{path}.until")),
                            (Join("until"),))

    def s_timed(self, n: A.Timed, path):
        return SentencePlan(path, (self.sentence(n.body, f"{path}.body"), self.conv(n.time, f"{path}.time")),
                            (Join("during"),))

    def s_foreach(self, n: A.ForEach, path):
        return SentencePlan(path, (self.conv(n.over, f"{path}.over"), self.sentence(n.body, f"{path}.body")),
                            (Join("for_each"),))

    def s_bind(self, n: A.Bind, path):
        return dataclasses.replace(n, value=self.sentence(n.value, f"{path}.value")
                                   if type(n.value) in SENTENCE_KINDS else self.conv(n.value, f"{path}.value"))

    def s_scoped(self, n: A.Scoped, path):
        return dataclasses.replace(n, subject=self.phrase(n.subject, f"{path}.subject"),
                                   body=self.sentence(n.body, f"{path}.body"))

    def s_nested(self, n: A.Nested, path):
        saved = self._self_seen
        plan = self.ability(n.ability, f"{path}.ability")
        self._self_seen = saved
        return dataclasses.replace(n, ability=plan)

    # ------------------------------------------------------------ phrases
    def phrase(self, n: A.Node, path: str):
        if not isinstance(n, A.NP):
            return self.conv(n, path)
        heads = self.conv(n.heads, f"{path}.heads")
        head_ops = [self.op(h) for h in n.heads]
        mods = []
        for name in ("pre", "quant", "each", "count", "filters", "name", "post"):
            v = getattr(n, name)
            if v is None or v == ():
                continue
            if name == "filters":        # a mention inside a filter ("another …") isn't a mention of the object
                saved = self._self_seen
                mods.append((name, self.conv(v, f"{path}.{name}")))
                self._self_seen = saved
                continue
            mods.append((name, self.conv(v, f"{path}.{name}")))
        if n.neg:
            mods.append(("neg", True))
        ref, person, definite, pronoun, reason, ante = "new", 3, False, False, "", None
        self_as = "permanent"
        if head_ops == ["self"]:
            ref, definite = "self", True
            if any(isinstance(c, A.Zone) and self.op(c.zone) is None and c.zone.glyph in CARD_ZONES
                   for f in n.filters for c in getattr(f, "conds", ())):
                self_as = "card"
            if self._self_seen:
                pronoun, reason = True, "this object was mentioned earlier in the ability"
            self._self_seen = True
        elif head_ops == ["you"]:
            ref, person, definite = "you", 2, True
        elif n.antecedent:
            ref, definite, pronoun, reason = "anaphor", True, True, "refers back to an earlier phrase"
            target = self.at.get(n.antecedent)
            if target is not None:
                saved = self._self_seen
                ante = self.phrase(target, n.antecedent)
                self._self_seen = saved
                if isinstance(ante, PhrasePlan) and ante.ref == "anaphor" and ante.antecedent is not None:
                    ante = ante.antecedent
        return PhrasePlan(path, heads, tuple(mods), number=n.number or "sg", quantity=n.quantity or "one",
                          definite=definite, ref=ref, antecedent=ante, person=person, pronoun=pronoun, reason=reason,
                          self_as=self_as)

    def conv(self, v: Any, path: str):
        """Convert children generically: NPs → PhrasePlan, sentence nodes → plans, other nodes kept."""
        if isinstance(v, tuple):
            if v and all(isinstance(x, tuple) and len(x) == 2 and isinstance(x[0], str) for x in v):
                return tuple((slot, self.conv(c, p)) for slot, c, p in _pair_paths(v, path))
            return tuple(self.conv(x, f"{path}.{i}") for i, x in enumerate(v))
        if isinstance(v, A.NP):
            return self.phrase(v, path)
        if not isinstance(v, A.Node) or isinstance(v, (A.SymRef, A.NameRef, A.EffectRef, A.Mana, A.Num, A.Var)):
            return v
        if type(v) in SENTENCE_KINDS and type(v) not in (A.Coord,):
            return self.sentence(v, path)
        changes = {}
        for name, child, sub in _child_paths(v, path):
            if isinstance(child, (A.Node, tuple)):
                new = self.conv(child, sub)
                if new is not child:
                    changes[name] = new
        return dataclasses.replace(v, **changes) if changes else v


def _same_phrase(a, b) -> bool:
    return isinstance(a, PhrasePlan) and isinstance(b, PhrasePlan) and a.ref == b.ref and (
        a.ref in ("self", "you") or (a.heads, a.mods) == (b.heads, b.mods)) and a.ref != "new"


def _as_spell(p):
    return dataclasses.replace(p, self_as="spell") if isinstance(p, PhrasePlan) and p.ref == "self" else p


# zones where the object is a card, not a permanent or spell (hand, graveyard, library)
CARD_ZONES = frozenset({"☚", "⚰", "▤"})

ABILITY_KINDS = {A.Keywords: Planner.ab_keywords, A.Static: Planner.ab_static, A.Triggered: Planner.ab_triggered,
                 A.Activated: Planner.ab_activated, A.Labelled: Planner.ab_labelled, A.Chapter: Planner.ab_chapter,
                 A.Threshold: Planner.ab_threshold, A.Mode: Planner.ab_mode, A.Modal: Planner.ab_modal}
SENTENCE_KINDS = {A.Effects: Planner.s_effects, A.Coord: Planner.s_coord, A.Action: Planner.s_action,
                  A.Modify: Planner.s_modify, A.Conditional: Planner.s_cond, A.Replace: Planner.s_replace,
                  A.While: Planner.s_while, A.Until: Planner.s_until, A.Timed: Planner.s_timed,
                  A.ForEach: Planner.s_foreach, A.Bind: Planner.s_bind, A.Scoped: Planner.s_scoped,
                  A.Nested: Planner.s_nested, A.Modal: Planner.ab_modal}
_VALUES = (A.NP, A.SymRef, A.NameRef, A.Mana, A.Num, A.Var, A.Characteristic, A.Count, A.Arith, A.PT, A.Zone)
# phrase-level nodes that may stand where a sentence is expected (conditions, trigger events)
PHRASE_ONLY = {A.Compare, A.NP, A.Not, A.And, A.Or, A.Time, A.Keyword, A.Keywords, A.Characteristic, A.Count}


def plan_card(card: A.Card, ctxs: list[CardContext], g: Glossary) -> CardPlan:
    p = Planner(g, card)
    faces = []
    for fi, f in enumerate(card.faces):
        abilities = []
        for ai, a in enumerate(f.abilities):
            p._self_seen = False
            abilities.append(p.ability(a, f"faces.{fi}.abilities.{ai}"))
        faces.append(FacePlan(ctxs[fi], f.name.key, f.cost, f.types, f.stats, tuple(abilities)))
    return CardPlan(tuple(faces))
