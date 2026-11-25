"""English realizer: clause plans → Oracle-style English.

Word order, articles, inflection, punctuation and Oracle idioms live here; the words come from the glossary
(``lex.en``, keyword ``oracle``) through ``mtglang.lexicon.Lexicon``. A plan node this realizer doesn't handle
yet is written ``⟦kind⟧`` so the eval can count it.
"""
from __future__ import annotations

import re
from dataclasses import replace as dataclasses_replace
from pathlib import Path

from mtglang import ast as A
from mtglang.lexicon import Lexicon
from mtglang.planir import AbilityPlan, CardContext, CardPlan, ClausePlan, Gap, PhrasePlan, SentencePlan

# subtypes a card names itself by ("this Saga"); otherwise the card type decides ("this creature")
SELF_SUBTYPES = ("Saga", "Aura", "Equipment", "Spacecraft", "Vehicle")
SELF_TYPES = ("Creature", "Land", "Artifact", "Enchantment", "Planeswalker", "Battle")
ROMAN = ("", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")
COLOR_WORDS = {"{W}": "white", "{U}": "blue", "{B}": "black", "{R}": "red", "{G}": "green", "{C}": "colorless"}
NUM_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
             "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty")
# events that happen to an object once: their triggers say "When", not "Whenever"
ONCE_VERBS = frozenset({"↥", "☠", "↧"})


def _type_noun(lex: Lexicon, index: int) -> str:
    return lex.sym(index).get("noun") or lex.g.symbols[index].labels["en"].lower()


def self_phrase(ctx: CardContext, lex: Lexicon, as_: str = "permanent", in_token: bool = False) -> str:
    """How the card names itself: its (short) name if legendary, else "this <type>"; "this card" / "this
    spell" when it is a card in a zone or a spell; "this token" inside an ability granted to a token."""
    if in_token:
        return "this token"
    if as_ == "card":
        return "this card"
    if as_ == "spell":
        return "this spell"
    if ctx.is_spell:
        return ctx.name
    if ctx.legendary:
        return ctx.short
    for sub in SELF_SUBTYPES:
        if sub in ctx.subtype_keys:
            return f"this {sub}"
    labels = {lex.g.symbols[i].labels["en"]: i for i in ctx.type_syms}
    for t in SELF_TYPES:
        if t in labels:
            return f"this {_type_noun(lex, labels[t])}"
    return "this permanent"


def cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def gap(kind: str) -> str:
    return f"⟦{kind}⟧"


def fin(s: str) -> str:
    """End a sentence with a period, unless it ends in mode lines (which carry their own)."""
    return s if ("\n" in s or s.endswith('."')) else s + "."


class En:
    def __init__(self, lex: Lexicon, ctx: CardContext):
        self.lex, self.g, self.ctx = lex, lex.g, ctx
        self.static = False          # inside a static ability (states: "has", not "gains")

    # ------------------------------------------------------------ helpers
    def glyph(self, s) -> str:
        return s.glyph if isinstance(s, A.SymRef) else ""

    def op(self, s) -> str | None:
        return self.g.symbols[s.index].syntax.get("op") if isinstance(s, A.SymRef) else None

    def w(self, s: A.SymRef, key: str, default: str | None = None) -> str:
        v = self.lex.sym(s.index).get(key)
        if v is None:
            if default is not None:
                return default
            return gap(f"{s.glyph}.{key}")
        return v

    def number(self, n, word: bool = True) -> str:
        if isinstance(n, A.Num):
            if word and 0 <= n.value < len(NUM_WORDS):
                return NUM_WORDS[n.value]
            return str(n.value)
        if isinstance(n, A.Var):
            return n.name
        return self.value(n)

    # ------------------------------------------------------------ abilities
    def ability(self, a) -> str:
        if isinstance(a, Gap):
            return gap(a.kind)
        fn = getattr(self, f"ab_{a.shape}", None)
        return fn(a) if fn else gap(a.shape)

    def ab_keywords(self, a: AbilityPlan) -> str:
        words = [self.keyword(k) for k in a.parts["items"]]
        return cap(", ".join([words[0]] + [x[:1].lower() + x[1:] for x in words[1:]]))

    def keyword(self, k) -> str:
        if not isinstance(k, A.Keyword):
            return gap(getattr(k, "kind", "keyword"))
        try:
            word = self.lex.keyword(k.sym.index)
        except KeyError:
            return gap(f"{k.sym.glyph}.word")
        params = list(k.params)
        if params and isinstance(params[0], A.Filter) and k.sym.glyph == "♲":
            words = [self.premodifier(c) or self.value(c) for c in params[0].conds]
            word = " ".join(words[:-1] + [words[-1] + word.lower()]).capitalize()
            params = params[1:]
        if params:
            word += " " + " ".join(self.value(p) for p in params)
        return word

    def ab_static(self, a: AbilityPlan) -> str:
        self.static = True
        try:
            return self.text(a.parts["body"])
        finally:
            self.static = False

    def ab_triggered(self, a: AbilityPlan) -> str:
        ev = a.parts["event"]
        head = "When" if self._once(ev) else "Whenever"
        if isinstance(ev, A.Time):
            head = "At"
        self._limit_kind = "trigger"
        self._in_event = True
        try:
            ev_text = self.inline(ev)
        finally:
            self._in_event = False
        first, rest = self.split_first(a.parts["effect"])
        conds = "".join(f", if {self.inline(c)}" for c in a.parts["conds"])
        out = f"{head} {ev_text}{conds}, {fin(first)}"
        return out + "".join(f" {fin(cap(s))}" for s in rest)

    def _once(self, ev) -> bool:
        clauses = ev.clauses if isinstance(ev, SentencePlan) else (ev,)
        def once(c):
            if not (isinstance(c, ClausePlan) and isinstance(c.pred, A.SymRef)):
                return False
            if c.pred.glyph in ONCE_VERBS and c.subject is not None and (
                    c.subject.ref == "self" or self._attached_to_self(c.subject)):
                return True
            obj = self.arg(c, "object")
            return self.op(c.pred) == "cast" and isinstance(obj, PhrasePlan) and obj.ref == "self"
        return all(once(c) for c in clauses)

    _limit_kind = "activate"
    _in_event = False

    def _attached_to_self(self, p) -> bool:
        if not isinstance(p, PhrasePlan):
            return False
        return any(isinstance(c, A.Rel) and isinstance(c.other, PhrasePlan) and c.other.ref == "self"
                   and "adj" in self.lex.sym(c.rel.index)
                   for slot, f in p.mods if slot == "filters" for flt in f for c in getattr(flt, "conds", ()))

    def ab_activated(self, a: AbilityPlan) -> str:
        self._limit_kind = "activate"
        costs = ", ".join(cap(self.cost(c)) for c in a.parts["cost"])
        out = f"{costs}: {self.text(a.parts['effect'])}"
        if a.parts["limits"]:
            out += " Activate " + " and ".join(self.limit(l) for l in a.parts["limits"]) + "."
        return out

    def limit(self, l) -> str:
        """only as a sorcery / only once each turn / only if … / only during your turn."""
        if isinstance(l, SentencePlan):
            return " and ".join(self.limit(c) for c in l.clauses)
        if not isinstance(l, ClausePlan):
            return gap("limit")
        obj, t = self.arg(l, "object"), self.arg(l, "time")
        if t is not None:
            if t.items and isinstance(t.items[0], A.Bound):
                return "only once each turn"
            return f"only during {self.time(t)}"
        if isinstance(obj, PhrasePlan) and obj.heads and getattr(obj.heads[0], "glyph", "") == "✎":
            return "only as a sorcery"
        return f"only if {self.condition(obj)}"

    def condition(self, c) -> str:
        """A condition clause: perfect / past tense for things that happened ("you've scried this turn")."""
        if isinstance(c, A.Compare):
            return self.compare(c)
        return self.inline(c)

    def cost(self, c) -> str:
        if isinstance(c, A.Mana):
            return c.text
        if isinstance(c, A.Num):
            sign = {"-": "−", "−": "−", "+": "+"}.get(c.sign, "")
            return f"[{sign}{c.value}]" if self.in_quotes else f"{sign}{c.value}"
        return self.inline(c)

    def ab_modal(self, a: AbilityPlan) -> str:
        return cap(self.modal(a))

    def modal(self, a: AbilityPlan) -> str:
        choose = a.parts["choose"]
        amount = self.arg(choose, "amount") if isinstance(choose, ClausePlan) else None
        head = f"choose {self.number(amount) if amount is not None else gap('choose')} —"
        return head + "".join(f"\n{self.ability(m)}" for m in a.parts["modes"])

    def ab_mode(self, a: AbilityPlan) -> str:
        inner = a.parts["ability"]
        body = self.text(inner.parts["body"]) if getattr(inner, "shape", "") == "static" else self.ability(inner)
        return f"• {body}"

    def ab_chapter(self, a: AbilityPlan) -> str:
        nums = ", ".join(ROMAN[n] if n < len(ROMAN) else str(n) for n in a.parts["numbers"])
        return f"{nums} — {self.ability(a.parts['ability'])}"

    def ab_threshold(self, a: AbilityPlan) -> str:
        return f"{a.parts['n']}+ | {self.ability(a.parts['ability'])}"

    def ab_labelled(self, a: AbilityPlan) -> str:
        label = " ".join(self.label_word(x) for x in a.label)
        return f"{label} — {self.ability(a.parts['ability'])}"

    def label_word(self, x) -> str:
        if isinstance(x, A.NameRef):
            return x.key
        return self.lex.sym(x.index).get("word") or self.g.symbols[x.index].oracle or gap(f"{x.glyph}.word")

    # ------------------------------------------------------------ sentences
    def sentences(self, p) -> list[str]:
        """Top-level sentences of an effect (without final periods)."""
        if isinstance(p, SentencePlan) and p.lead is None and len(p.clauses) == 1:
            return self.sentences(p.clauses[0])
        if isinstance(p, SentencePlan) and p.lead is None and p.joins and all(j.kind in ("sentence", "where")
                                                                             for j in p.joins):
            out: list[str] = []
            chain = False           # inside a ", then" chain: the next simple clause may join it
            clauses = list(p.clauses)
            for i, (c, j) in enumerate(zip(clauses, (None,) + p.joins)):
                if j is not None and j.kind == "where":
                    out[-1] += f", where {self.inline(c)}"
                    continue
                text = self.inline(c)
                prev = clauses[i - 1] if i else None
                if prev is not None and self._search_chain(clauses[:i]) and self._simple(c):
                    out[-1] += f", {text}"      # R1: search …, put it …, (then) shuffle
                    chain = True
                    continue
                if prev is not None and self._card_flow(prev) and self._card_flow(c) and not chain:
                    out[-1] += f", then {text}"  # R2: draw a card, then discard a card
                    chain = True
                    continue
                out.append(text)
                chain = False
            return [self._then_last(x) for x in out]
        return [self.inline(p)]

    @staticmethod
    def _then_last(s: str) -> str:
        """In a search chain "a, b, c" the last item gets "then": "a, b, then c"."""
        if s.startswith("search ") and s.count(", ") >= 1 and ", then " not in s:
            k = s.rfind(", ")
            return s[:k] + ", then " + s[k + 2:]
        return s

    def _search_chain(self, before: list) -> bool:
        """The run of simple clauses ending here started with a library search."""
        for c in reversed(before):
            if not isinstance(c, ClausePlan):
                return False
            if isinstance(c.pred, A.SymRef) and c.pred.glyph == "⌖":
                return True
            if not self._simple(c):
                return False
        return False

    def _simple(self, c) -> bool:
        return isinstance(c, ClausePlan) and isinstance(c.pred, A.SymRef) and (c.mood == "imperative" or (
            c.subject is not None and c.subject.ref in ("you", "anaphor")))

    CARD_FLOW = frozenset({"⤓", "⌫", "⤋", "⌕", "◓"})

    def _card_flow(self, c) -> bool:
        return isinstance(c, ClausePlan) and isinstance(c.pred, A.SymRef) and c.pred.glyph in self.CARD_FLOW \
            and not c.optional

    def split_first(self, p) -> tuple[str, list[str]]:
        s = self.sentences(p)
        return s[0], s[1:]

    def text(self, p) -> str:
        """A full effect as text: capitalised sentences ending in periods."""
        return " ".join(fin(cap(s)) for s in self.sentences(p))

    def inline(self, p) -> str:
        if isinstance(p, Gap):
            return gap(p.kind)
        if isinstance(p, ClausePlan):
            return self.clause(p)
        if isinstance(p, SentencePlan):
            return self.sentence_plan(p)
        if isinstance(p, PhrasePlan):
            return self.np(p)
        if isinstance(p, A.Bind):
            return f"{p.var.name} is {self.value(p.value)}"
        if isinstance(p, AbilityPlan):
            return self.modal(p) if p.shape == "modal" else gap(f"ability:{p.shape}")
        if isinstance(p, A.Nested):
            return self.nested(p.ability)
        return self.value(p)

    def nested(self, a) -> str:
        """A triggered ability inside an effect: reflexive ("when you do, …"), delayed ("… at the beginning of
        the next end step"), or bounded ("until end of turn, whenever …")."""
        if not isinstance(a, AbilityPlan) or a.shape != "triggered":
            return gap("nested")
        ev, eff = a.parts["event"], a.parts["effect"]
        if isinstance(ev, A.Time):
            sents = self.sentences(eff)
            if len(sents) == 1:
                return f"{sents[0]} at {self.time(ev)}"
            return f"at {self.time(ev)}, " + ". ".join(cap(x) if i else x for i, x in enumerate(sents))
        if isinstance(ev, A.SymRef) and self.op(ev) in ("did", "didnt"):
            head = "when you do" if self.op(ev) == "did" else "when you don't"
            return f"{head}, " + ". ".join(cap(x) if i else x for i, x in enumerate(self.sentences(eff)))
        text = self.ab_triggered(a)
        return text[:1].lower() + text[1:].rstrip(".")

    def sentence_plan(self, p: SentencePlan) -> str:
        if p.lead is not None:
            body = self.inline(p.clauses[0])
            if p.lead == "if_do":
                return f"if you do, {body}"
            if p.lead == "if_dont":
                return f"if you don't, {body}"
            return f"{body} instead"
        if len(p.clauses) == 1:
            return self.inline(p.clauses[0])
        kinds = {j.kind for j in p.joins}
        if kinds <= {"and", "or"} and len(kinds) == 1:
            word = kinds.pop()
            merged = self.merge_objects(p, word)
            if merged is not None:
                return merged
            parts = [self.inline(c) for c in p.clauses]
            if len(parts) == 2:
                return f"{parts[0]} {word} {parts[1]}"
            return ", ".join(parts[:-1]) + f", {word} {parts[-1]}"
        if kinds <= {"sentence", "where"}:
            return ". ".join(cap(s) if i else s for i, s in enumerate(self.sentences(p)))
        if len(p.joins) == 1:
            j = p.joins[0].kind
            if j == "instead":
                return self.replacement(p)
            if j == "for_each":
                return f"for each {self.np(self._sg(p.clauses[0]))}, {self.inline(p.clauses[1])}"
            a, b = (self.inline(c) for c in p.clauses)
            if j == "while":
                return f"{a} as long as {self.condition(p.clauses[1])}"
            if j == "as_though":
                return f"{a} as though {b}"
            if j == "if":
                return f"if {a}, {b}"
            if j == "unless":
                return f"{a} unless {b}"
            first = p.clauses[0]
            if j in ("until", "during") and isinstance(first, A.Nested):
                lead = f"until {b}" if j == "until" else b
                return f"{lead}, {a}"
            if j == "until":
                return f"{a} until {b}"
            if j == "during":
                return f"{a} {b}"
        return gap("join:" + "+".join(j.kind for j in p.joins))

    def replacement(self, p: SentencePlan) -> str:
        """"As this land enters, …" (self entering) / "If <event> would …, <effect> instead"."""
        ev, eff = p.clauses
        if isinstance(ev, ClausePlan) and isinstance(ev.pred, A.SymRef) and ev.pred.glyph == "↥" \
                and ev.subject is not None and ev.subject.ref == "self" and not ev.args:
            return f"as {self.clause(ev)}, {self.inline(eff)}"
        self._modal = "would"
        try:
            cond = self.inline(ev)
        finally:
            self._modal = None
        return f"if {cond}, {self.inline(eff)} instead"

    _modal: str | None = None

    def merge_objects(self, p: SentencePlan, word: str) -> str | None:
        """"gains trample and lifelink": shared subject, same verb, one argument each, time only at the end."""
        cs = p.clauses
        if len(cs) != 2 or not all(isinstance(c, ClausePlan) and isinstance(c.pred, A.SymRef) for c in cs):
            return None
        a, b = cs
        if not b.subject_shared or a.pred.index != b.pred.index or self.arg(a, "time") is not None:
            return None
        if self.op(a.pred) != "has":
            return None
        first = self.clause(a)
        return f"{first} {word} {self.ability_arg(self.arg(b, 'ability'))}" + (
            f" {self.trailing(b)}" if self.trailing(b) else "")

    # ------------------------------------------------------------ clauses
    def subject_text(self, c: ClausePlan) -> tuple[str, bool]:
        """(subject words or "", third-person-singular?)"""
        if c.mood == "imperative":
            return "", False
        if c.subject_shared:
            return "", self._shared_3sg
        if c.subject is None:
            return "", False
        s = c.subject
        if not isinstance(s, PhrasePlan):
            return self.value(s), True
        third = s.ref != "you" and s.number == "sg"
        return self.np(s, role="subject"), third

    _shared_3sg = False

    def verb(self, s: A.SymRef, third: bool) -> str:
        return self.w(s, "s") if third else self.w(s, "verb")

    def clause(self, c: ClausePlan) -> str:
        subj, third = self.subject_text(c)
        if not c.subject_shared:
            self._shared_3sg = third
        if isinstance(c.pred, A.PT):
            body = f"{'gets' if third else 'get'} {self.pt(c.pred)}"
        elif isinstance(c.pred, A.Delta):
            body = self.delta(c.pred, third)
        elif isinstance(c.pred, A.SymRef):
            body = self.verb_phrase(c, third)
        elif isinstance(c.pred, A.EffectRef):
            body = self.value(c.pred)
        else:
            body = gap(f"pred:{type(c.pred).__name__}")
        rest = self.trailing(c)
        if self._modal and not c.optional:
            body = f"{self._modal} " + self.base_form(c, body)
        if c.optional:
            if not subj:
                subj = "you" if c.mood == "imperative" else subj
            body = "may " + self.base_form(c, body)
        return " ".join(x for x in (subj, body, rest) if x)

    def base_form(self, c: ClausePlan, body: str) -> str:
        """The body with its first verb in the base form ("may pay", not "may pays")."""
        if isinstance(c.pred, A.SymRef):
            third = self.w(c.pred, "s", "")
            if third and body.startswith(third):
                return self.w(c.pred, "verb") + body[len(third):]
        for a, b in (("gets ", "get "), ("gains ", "gain "), ("has ", "have "), ("deals ", "deal "),
                     ("puts ", "put "), ("returns ", "return ")):
            if body.startswith(a):
                return b + body[len(a):]
        return body

    def trailing(self, c: ClausePlan) -> str:
        out = []
        for slot, v in c.args:
            if slot == "time":
                out.append(self.value(v))
        return " ".join(out)

    def arg(self, c: ClausePlan, slot: str):
        for s, v in c.args:
            if s == slot:
                return v
        return None

    def verb_phrase(self, c: ClausePlan, third: bool) -> str:
        v = c.pred
        if self._in_event and v.glyph == "↷" and not c.args:
            return f"{'becomes' if third else 'become'} {self.w(v, 'ed')}"
        if c.negated and c.passive:
            by = self.arg(c, "object") or self.arg(c, "by") or next((a for s, a in c.args if s != "time"), None)
            out = f"can't be {self.w(v, 'pp', self.w(v, 'ed'))}"
            return out + (f" by {self.np(by)}" if by is not None else "")
        if c.negated:
            rest = self.verb_phrase(dataclasses_replace(c, negated=False), False)
            return f"can't {rest}"
        g = v.glyph
        op = self.op(v)
        if op == "transfer":
            return self.transfer(c, third)
        if op == "has":
            state = self.static and not self.ctx.is_spell and self.arg(c, "time") is None
            word = ("has" if third else "have") if state else self.verb(v, third)
            ab = self.arg(c, "ability")
            text = self.ability_arg(ab)
            if self.trailing(c) and text.endswith('."'):
                text = text[:-2] + '"'
            return f"{word} {text}"
        obj = self.arg(c, "object")
        if v.glyph == "⊳" and isinstance(obj, PhrasePlan) and obj.heads and isinstance(obj.heads[0], A.SymRef) \
                and self.g.symbols[obj.heads[0].index].syntax.get("kind") in ("stat", "keyword"):
            what = self.w(obj.heads[0], "noun", self.g.symbols[obj.heads[0].index].oracle or "").lower()
            return f"{self.verb(v, third)} {article(what)} {what} ability"
        if v.glyph == "⌖":
            z = self.arg(c, "zone")
            return f"{self.verb(v, third)} {self.value(z)} for {self.np(obj)}"
        holder = None
        if isinstance(obj, PhrasePlan) and obj.heads and isinstance(obj.heads[0], A.SymRef):
            holder = {"◌": "token", "✪": "emblem"}.get(obj.heads[0].glyph)
        if holder is None and isinstance(obj, PhrasePlan) and any(
                isinstance(h, A.SymRef) and h.glyph == "◌" for h in obj.heads):
            holder = "token"
        if holder == "emblem" and v.glyph == "✚":
            words = ["gets" if third else "get"]
        else:
            words = [self.verb(v, third)]
        counted = self.lex.sym(v.index).get("noun")
        for slot, a in c.args:
            if slot == "time":
                continue
            if slot == "amount" and counted:
                words.append(self.counted(a, counted))
            elif slot == "mana":
                words.append(self.mana(a))
            elif slot == "state" and isinstance(a, ClausePlan) and isinstance(a.pred, A.SymRef) and not a.args:
                words.append(self.w(a.pred, "ed"))
            elif slot == "restrict" and isinstance(a, A.Rel):
                clause = self.inline(a.other)
                words[-1] += f". Spend this mana only to {clause}"
            elif slot == "times" and isinstance(a, A.Rel) and isinstance(a.other, A.Count):
                words.append(f"for each {self.np(self._sg(a.other.of))}")
            elif slot == "state" and isinstance(a, ClausePlan) and self.op(a.pred) == "has":
                words.append(f"with {self.ability_arg(self.arg(a, 'ability'), holder)}")
            else:
                words.append(self.value(a))
        del g
        return " ".join(words)

    def ability_arg(self, ab, holder: str | None = None) -> str:
        """A granted ability: a keyword in lower case, or a whole ability in quotes."""
        if isinstance(ab, A.Keyword):
            return self.keyword(ab).lower()
        if isinstance(ab, A.Nested):
            ab = ab.ability
        if isinstance(ab, (AbilityPlan, ClausePlan, SentencePlan)):
            return f'"{self.quoted(ab, holder)}"'
        if isinstance(ab, A.Keywords) or (isinstance(ab, tuple)):
            return gap("ability")
        return gap("ability")

    def quoted(self, ab, holder: str | None) -> str:
        sub = En(self.lex, self.ctx)
        sub.holder, sub.in_quotes = holder, True
        if isinstance(ab, AbilityPlan):
            sub.static = ab.shape == "static" and holder is not None
            return sub.ability(ab)
        sub.static = True
        return sub.text(ab)

    holder: str | None = None       # "token" / "emblem": what "this …" means inside quotes
    in_quotes = False

    def counted(self, n, noun: str) -> str:
        if isinstance(n, A.Count):
            return f"{article(noun)} {noun} for each {self.np(self._sg(n.of))}"
        if isinstance(n, A.Num) and n.value == 1:
            return f"{article(noun)} {noun}"
        return f"{self.number(n)} {noun}s"

    def mana(self, m) -> str:
        if isinstance(m, A.Mana):
            return m.text
        if isinstance(m, A.SymRef) and m.glyph == "◆":
            return f"one {self.w(m, 'noun')}"
        if isinstance(m, PhrasePlan) and len(m.heads) == 1 and isinstance(m.heads[0], A.SymRef) \
                and m.heads[0].glyph == "◆":
            return f"one {self.w(m.heads[0], 'noun')}"
        if isinstance(m, A.Or):
            parts = [self.mana(x) for x in m.items]
            return " or ".join(parts) if len(parts) == 2 else ", ".join(parts[:-1]) + ", or " + parts[-1]
        return self.value(m)

    def transfer(self, c: ClausePlan, third: bool) -> str:
        obj, dest = self.arg(c, "object"), self.arg(c, "destination")
        head = obj.heads[0] if isinstance(obj, PhrasePlan) and obj.heads else None
        hop = self.op(head)
        if hop == "damage":
            amount = self._mod(obj, "count")
            kinds = [self.damage_kind(h) for h in obj.heads[1:]]
            pre, _ = self.modifiers(obj, False)
            dmg = " ".join([w for w in pre + kinds if w] + ["damage"])
            self._damage_dest = True
            try:
                d = self.np(dest, role="destination")
            finally:
                self._damage_dest = False
            verb = "deals" if third else "deal"
            if amount is None:
                return f"{verb} {dmg} to {d}"
            if isinstance(amount, (A.Num, A.Var)):
                return f"{verb} {self.number(amount, word=False)} {dmg} to {d}"
            return f"{verb} {dmg} equal to {self.value(amount)} to {d}"
        if hop == "counter":
            return f"{'puts' if third else 'put'} {self.counter_np(obj)} on {self.np(dest, role='destination')}"
        if isinstance(dest, A.Zone):
            extra = self.move_extras(c)
            return self.move(obj, dest, third) + (f" {extra}" if extra else "")
        return gap("transfer")

    def from_zone(self, obj) -> A.Zone | None:
        if not isinstance(obj, PhrasePlan):
            return None
        for slot, f in obj.mods:
            if slot == "filters":
                for flt in f:
                    for c in getattr(flt, "conds", ()):
                        if isinstance(c, A.Zone):
                            return c
        return None

    def _is_card(self, p) -> bool:
        if isinstance(p, PhrasePlan) and p.ref == "anaphor":
            p = p.antecedent
        return isinstance(p, PhrasePlan) and any(isinstance(h, A.SymRef) and h.glyph == "▭" for h in p.heads)

    def move_extras(self, c: ClausePlan) -> str:
        """After a zone change: tapped, under its owner's control, with a +1/+1 counter on it."""
        out = []
        for slot, a in c.args:
            if slot == "state" and isinstance(a, ClausePlan) and isinstance(a.pred, A.SymRef):
                out.append(self.w(a.pred, "ed"))
                cnt = self.arg(a, "object")
                if isinstance(cnt, PhrasePlan) and cnt.heads and self.op(cnt.heads[0]) == "counter":
                    out.append(f"with {self.counter_np(cnt)} on it")
            elif slot == "rel" and isinstance(a, A.Of) and self.op(a.rel) == "control":
                out.append(f"under {self.possessive(a.of)} control")
            elif slot == "rel" and isinstance(a, A.SymRef) and self.op(a) == "control":
                out.append("under your control")
        return " ".join(out)

    def move(self, obj, dest: A.Zone, third: bool) -> str:
        """Zone changes: exile X / return X to … / put X into / onto / on top of …"""
        z = dest.zone.glyph
        src = self.from_zone(obj)
        if src is None and isinstance(obj, PhrasePlan) and obj.ref == "anaphor":
            src = self.from_zone(obj.antecedent)
        o = self.np(obj, moving=True)
        if src is None and self._is_card(obj) and z in ("☚", "▦"):
            src = A.Zone(zone=A.SymRef(index=0, glyph="▤"))     # a card not on the battlefield: "put"
        put = "puts" if third else "put"
        ret = "returns" if third else "return"
        if z == "⊘":
            return f"{self.verb(dest.zone, third)} {o}"
        if z == "▦":
            if src is not None and src.zone.glyph == "⚰":
                return f"{ret} {o} to the battlefield"
            return f"{put} {o} onto the battlefield"
        if z == "☚":
            if src is None or src.zone.glyph in ("▦", "⚰"):
                return f"{ret} {o} to {self.zone(dest, obj)}"
            return f"{put} {o} into {self.zone(dest, obj)}"
        if z == "▤" and dest.pos is not None:
            where = "on top of" if dest.pos.glyph == "⌃" else "on the bottom of"
            return f"{put} {o} {where} {self.zone(dest, obj, bare=True)}"
        return f"{put} {o} into {self.zone(dest, obj)}"

    def damage_kind(self, h) -> str:
        if isinstance(h, A.SymRef) and h.glyph == "⨯":
            return "combat"
        return self.value(h)

    def counter_np(self, p: PhrasePlan) -> str:
        kind = p.heads[1] if len(p.heads) > 1 else None
        if isinstance(kind, A.PT):
            word = self.pt(kind)
        elif isinstance(kind, A.SymRef):
            word = self.w(kind, "noun").lower()
        else:
            word = ""
        noun = "counter" if p.number == "sg" else "counters"
        if p.quantity == "one" and not self._mod(p, "count"):
            return f"{article(word or noun)} {word} {noun}".replace("  ", " ")
        return f"{self.number(self._mod(p, 'count'))} {word} {noun}".replace("  ", " ")

    def delta(self, d: A.Delta, third: bool) -> str:
        if d.char is not None and d.char.glyph == "♥":
            gain = d.sign != "-" and d.sign != "−"
            verb = ("gains" if third else "gain") if gain else ("loses" if third else "lose")
            if d.amount is None:
                return f"{verb} life"
            return f"{verb} {self.number(d.amount, word=False)} life"
        return gap("delta")

    def pt(self, p: A.PT) -> str:
        return f"{self.signed(p.power)}/{self.signed(p.toughness)}"

    def signed(self, n) -> str:
        if isinstance(n, A.Num):
            return f"{'-' if n.sign in ('-', '−') else n.sign}{n.value}"
        if isinstance(n, A.Var):
            return f"{n.sign}{n.name}"
        return self.value(n)

    # ------------------------------------------------------------ phrases
    @staticmethod
    def _sg(p):
        import dataclasses
        return dataclasses.replace(p, number="sg", quantity="kind") if isinstance(p, PhrasePlan) else p

    def _mod(self, p: PhrasePlan, slot: str):
        for s, v in p.mods:
            if s == slot:
                return v
        return None

    def np(self, p, role: str = "object", moving: bool = False) -> str:
        if isinstance(p, A.Zone):
            return self.zone(p)
        if not isinstance(p, PhrasePlan):
            return self.value(p)
        if p.ref == "self":
            if p.pronoun and p.self_as == "permanent":
                return "it"
            words = f"this {self.holder}" if self.holder else self_phrase(self.ctx, self.lex, p.self_as)
            z = self.from_zone(p) if moving else None
            return f"{words} from {self.zone(z)}" if z is not None else words
        if p.ref == "you":
            return "you"
        if p.ref == "anaphor":
            if p.quantity == "each" and isinstance(p.antecedent, PhrasePlan) and p.antecedent.heads:
                return f"each of those {self.head_words(dataclasses_replace(p.antecedent, number='pl', mods=()))}"
            return self.anaphor(p)
        if not p.heads and self._mod(p, "quant") is not None and self.op(self._mod(p, "quant")) == "target":
            return "any target"
        q = p.quantity
        if q == "exists":
            ctl = self.control_rel(p)
            if ctl is not None:
                who = ctl.other
                rest = dataclasses_replace(p, mods=self._without(p.mods, ctl), quantity="one")
                verb = "control" if (isinstance(who, PhrasePlan) and (who.ref == "you" or who.number == "pl")) \
                    else "controls"
                return f"{self.np(who, role='subject')} {verb} {self.np(rest)}"
        each_all = q == "each" and not (role in ("subject", "destination") or self.is_player(p) or self._damage_dest)
        if each_all:
            p = dataclasses_replace(p, number="pl")
        pre, post = self.modifiers(p, moving)
        other = "another" in pre
        definite = any(w in ("enchanted", "equipped") for w in pre)
        pre = [w for w in pre if w != "another"]
        noun = self.premodified(pre, self.head_words(p))
        for m in self._mod(p, "post") or ():
            if isinstance(m, A.SymRef) and m.glyph == "≢":
                post = f"with different names {post}".strip()
        name = self._mod(p, "name")
        if name is not None:
            post = f"named {self.value(name)} {post}".strip()
        quant = self._mod(p, "quant")
        target = quant is not None and self.op(quant) == "target"
        core = f"target {noun}" if target else noun
        oth = "other " if other else ""
        if q == "up_to":
            count = self._mod(p, "count")
            n = count.value if isinstance(count, A.Bound) else count
            out = f"up to {self.number(n)} {oth}{core}"
        elif q == "one":
            if other:
                out = f"another {core}"
            elif target or definite:
                out = core
            else:
                out = f"{article(core)} {core}"
        elif q == "each":
            out = f"all {oth}{core}" if each_all else f"each {oth}{core}"
        elif q == "exists":
            out = f"{article(core)} {core}"
        elif q == "exactly":
            out = f"{self.number(self._mod(p, 'count'))} {oth}{core}"
        else:
            out = f"{oth}{core}"
        return f"{out} {post}".strip()

    def control_rel(self, p: PhrasePlan):
        for slot, f in p.mods:
            if slot == "filters":
                for flt in f:
                    for c in getattr(flt, "conds", ()):
                        if isinstance(c, A.Rel) and self.op(c.rel) == "control":
                            return c
        return None

    @staticmethod
    def _without(mods: tuple, cond) -> tuple:
        out = []
        for slot, v in mods:
            if slot == "filters":
                v = tuple(dataclasses_replace(f, conds=tuple(c for c in f.conds if c is not cond)) for f in v)
                v = tuple(f for f in v if f.conds)
                if not v:
                    continue
            out.append((slot, v))
        return tuple(out)

    @staticmethod
    def premodified(pre: list[str], noun: str) -> str:
        """Premodifiers before the noun; consecutive "non-" words are separated by commas."""
        out = ""
        for i, w in enumerate(pre):
            if i:
                out += ", " if (w.startswith("non") and pre[i - 1].startswith("non")) else " "
            out += w
        return f"{out} {noun}".strip()

    def of(self, v: A.Of) -> str:
        """"its controller", "your opponents' …", "Fblthp's owner"."""
        noun = self.w(v.rel, "noun")
        return f"{self.possessive(v.of)} {noun}"

    def characteristic(self, ch: A.Characteristic) -> str:
        """its power / that creature's power / the number of basic land types among lands you control."""
        if ch.sub is not None and ch.char.glyph == "⊤":
            what = {"⊡": "basic land types", "▭": "card types"}.get(ch.sub.glyph, gap("types"))
            return f"{what} among {self.np(ch.of)}" if ch.of is not None else what
        name = self.char_name(ch)
        if ch.agg is not None:
            agg = {"Σ": "total", "⇑": "greatest"}.get(ch.agg.glyph, gap("agg"))
            return f"the {agg} {name} among {self.np(ch.of)}" if ch.of is not None else f"the {agg} {name}"
        if ch.of is None:
            return name
        return f"{self.possessive(ch.of)} {name}"

    def possessive(self, x) -> str:
        if isinstance(x, PhrasePlan):
            if x.ref == "you":
                return "your"
            if x.ref == "anaphor":
                if self.is_player(x.antecedent):
                    return "their"
                words = self.anaphor(x)
                return "its" if words == "it" else words + "'s"
            if x.ref == "self" and x.pronoun:
                return "its"
            words = self.np(x)
            return words + ("'" if words.endswith("s") and x.number == "pl" else "'s")
        return gap("possessive")

    def is_player(self, p) -> bool:
        return isinstance(p, PhrasePlan) and any(
            isinstance(h, A.SymRef) and self.g.symbols[h.index].syntax.get("kind") == "player" for h in p.heads)

    _damage_dest = False

    def anaphor(self, p: PhrasePlan) -> str:
        """"it" for a target or a just-named object; "that player" for players; "that <noun>" for a trigger's
        subject."""
        a = p.antecedent
        if isinstance(a, PhrasePlan):
            if self.is_player(a):
                return "that player"
            if a.number == "pl" or a.quantity in ("up_to", "exactly", "all") and a.number == "pl":
                return "them"
            quant = self._mod(a, "quant")
            if quant is not None and self.op(quant) == "target":
                return "it"
            if ".event." in a.path + "." and a.heads:
                return f"that {self.head_words(dataclasses_replace(a, number='sg', mods=()))}"
        return "it"

    def head_words(self, p: PhrasePlan) -> str:
        words, token = [], any(isinstance(h, A.SymRef) and h.glyph == "◌" for h in p.heads)
        def rank(h):
            if isinstance(h, A.NameRef):
                return 0
            if isinstance(h, A.SymRef) and self.g.symbols[h.index].syntax.get("kind") == "object":
                return 2
            return 1
        heads = sorted(p.heads, key=rank)
        for i, h in enumerate(heads):
            last = i == len(heads) - 1
            if isinstance(h, A.NameRef):
                words.append(h.key)
            elif isinstance(h, A.SymRef):
                lx = self.lex.sym(h.index)
                if h.glyph == "◌":
                    continue
                if "adj" in lx and "noun" not in lx:
                    words.append(lx["adj"])
                elif last and p.number == "pl" and not token:
                    words.append(lx.get("pl") or gap(f"{h.glyph}.pl"))
                else:
                    words.append(lx.get("noun") or gap(f"{h.glyph}.noun"))
            elif isinstance(h, A.Or):
                joiner = " and " if p.quantity in ("each", "all") or p.number == "pl" else " or "
                sub = [self.head_words(dataclasses_replace(p, heads=(x,))) for x in h.items]
                words.append(joiner.join(sub))
            else:
                words.append(self.value(h))
        if token:
            words.append("tokens" if p.number == "pl" else "token")
        return " ".join(words)

    def modifiers(self, p: PhrasePlan, moving: bool) -> tuple[list[str], str]:
        """(premodifier words, postmodifier text) from the phrase's filters."""
        pre, post = [], []
        for slot, f in p.mods:
            if slot != "filters":
                continue
            for flt in f:
                for cond in getattr(flt, "conds", ()):
                    word = self.premodifier(cond)
                    if word is not None:
                        pre.append(word)
                    else:
                        post.append(self.filter_cond(cond, p, moving))
        return pre, " ".join(post)

    def premodifier(self, cond) -> str | None:
        """A filter condition written before the noun (non-creature, 2/2, white, legendary), else None."""
        if isinstance(cond, A.Rel) and self.op(cond.rel) == "other" and isinstance(cond.other, PhrasePlan) \
                and cond.other.ref in ("self", "anaphor"):
            return "another"
        if isinstance(cond, A.Rel) and isinstance(cond.other, PhrasePlan) and cond.other.ref == "self" \
                and "adj" in self.lex.sym(cond.rel.index):
            return self.lex.sym(cond.rel.index)["adj"]
        if isinstance(cond, A.Or) and all(self.premodifier(x) is not None for x in cond.items):
            return " or ".join(self.premodifier(x) for x in cond.items)
        if isinstance(cond, A.Not) and isinstance(cond.item, PhrasePlan) and cond.item.quantity == "kind":
            return "non" + self.head_words(cond.item)
        if isinstance(cond, PhrasePlan) and cond.quantity == "kind" and cond.ref == "new" and not cond.mods:
            return self.head_words(cond)
        if isinstance(cond, A.PT):
            return self.pt(cond)
        if isinstance(cond, A.Characteristic) and cond.char.glyph == "♦" and cond.of is not None:
            return self.color(cond.of)
        if isinstance(cond, A.SymRef):
            lx = self.lex.sym(cond.index)
            if "adj" in lx:
                return lx["adj"]
        if isinstance(cond, A.Not) and isinstance(cond.item, A.Time) and len(cond.item.items) == 1 \
                and getattr(cond.item.items[0], "glyph", "") == "⨯":
            return "noncombat"
        return None

    def color(self, v) -> str:
        if isinstance(v, A.Mana):
            words = [COLOR_WORDS.get(m, gap(f"color:{m}")) for m in re.findall(r"\{[^}]*\}", v.text)]
            return " and ".join(words)
        if isinstance(v, A.SymRef) and v.glyph == "∅":
            return "colorless"
        if isinstance(v, A.And):
            return " and ".join(self.color(x) for x in v.items)
        return gap("color")

    def filter_cond(self, cond, p: PhrasePlan, moving: bool) -> str:
        if isinstance(cond, A.Rel) and self.op(cond.rel) == "control":
            who = cond.other
            if isinstance(who, PhrasePlan) and who.ref == "you":
                return "you control"
            return f"{self.np(who, role='subject')} {'controls' if getattr(who, 'number', 'sg') == 'sg' else 'control'}"
        if isinstance(cond, A.Zone):
            return f"{'from' if moving else 'in'} {self.zone(cond)}"
        if isinstance(cond, A.Compare):
            return self.compare(cond, in_filter=True)
        return gap(f"filter:{getattr(cond, 'kind', type(cond).__name__)}")

    def zone(self, z: A.Zone, obj=None, bare: bool = False) -> str:
        noun = self.w(z.zone, "noun")
        if z.pos is not None and not bare:
            n = z.count
            if n is None or (isinstance(n, A.Num) and n.value == 1):
                card = "the top card" if z.pos.glyph == "⌃" else "the bottom card"
            else:
                card = f"the {'top' if z.pos.glyph == '⌃' else 'bottom'} {self.number(n)} cards"
            return f"{card} of {self.zone(dataclasses_replace(z, pos=None, count=None), obj)}"
        owner = z.owner
        if owner is None:
            if z.zone.glyph in ("⚰", "▤", "☚"):
                return f"{article(noun)} {noun}"
            return f"the {noun}" if z.zone.glyph == "▦" else noun
        if isinstance(owner, A.SymRef) and self.op(owner) == "own":
            pron = "their" if obj is not None and getattr(obj, "number", "sg") == "pl" else "its"
            return f"{pron} owner's {noun}" if not (obj is not None and getattr(obj, "number", "sg") == "pl") \
                else f"their owners' {self.w(z.zone, 'pl', noun)}"
        return f"{self.possessive(owner)} {noun}"

    # ------------------------------------------------------------ comparisons
    BOUND_WORDS = {"≤": ("or less", "less than or equal to"), "≥": ("or greater", "greater than or equal to"),
                   "=": ("", "equal to"), ">": ("", "greater than"), "<": ("", "less than")}

    def char_name(self, ch: A.Characteristic) -> str:
        return self.w(ch.char, "noun")

    def bound(self, op: str, v) -> str:
        """"3 or less", "less than or equal to the amount …", "equal to that number plus 1"."""
        short, long = self.BOUND_WORDS.get(op, ("", gap(f"op:{op}")))
        if isinstance(v, (A.Num, A.Var)) and short:
            return f"{self.value(v)} {short}"
        if isinstance(v, (A.Num, A.Var)) and op == "=":
            return self.value(v)
        return f"{long} {self.value(v)}"

    def compare(self, c: A.Compare, in_filter: bool = False) -> str:
        if len(c.items) != 2 or len(c.ops) != 1:
            return gap("compare")
        a, b = c.items
        op = c.ops[0].glyph
        if isinstance(a, A.Characteristic) and a.of is None:
            return f"{'with ' if in_filter else ''}{self.char_name(a)} {self.bound(op, b)}"
        if isinstance(a, A.Characteristic):
            return f"{self.possessive(a.of)} {self.char_name(a)} is {self.bound(op, b)}"
        if isinstance(a, A.Count) and isinstance(b, A.Num):
            return self.count_cond(a, op, b)
        if isinstance(a, A.Characteristic) and isinstance(b, A.Count):
            return f"{self.characteristic(a)} is equal to {self.value(b)}"
        return gap("compare")

    def count_cond(self, a: A.Count, op: str, b: A.Num) -> str:
        n = self.number(b)
        qty = {"≥": f"{n} or more", "≤": f"{n} or fewer", "=": n}.get(op, gap(f"op:{op}"))
        of = a.of
        if isinstance(of, ClausePlan) and isinstance(of.pred, A.SymRef):
            by = self.arg(of, "by")
            t = self.arg(of, "time")
            when = f" {self.time(t)}" if t is not None else ""
            if of.subject is not None:
                return f"{qty} {self.np(of.subject)} {self.w(of.pred, 'ed')}{when}"
            if isinstance(by, PhrasePlan) and by.ref == "you":
                counted = self.lex.sym(of.pred.index).get("noun", "")
                past = self.w(of.pred, "pp", "") or self.w(of.pred, "ed")
                return f"you've {past} {qty} {counted}s{when}".replace("  ", " ")
            return gap("count-of")
        if isinstance(of, PhrasePlan):
            ctl = self.control_rel(of)
            plural = dataclasses_replace(of, number="pl", quantity="all")
            if ctl is not None:
                rest = dataclasses_replace(plural, mods=self._without(of.mods, ctl))
                if op == "=" and b.value == 0:
                    return f"{self.np(ctl.other, role='subject')} control no {self.np(rest)}"
                return f"{self.np(ctl.other, role='subject')} control {qty} {self.np(rest)}"
            z = self.from_zone(of)
            if z is not None:
                rest = dataclasses_replace(plural, mods=self._without(of.mods, z))
                if op == "=" and b.value == 0:
                    return f"{self.zone(z)} has no {self.np(rest)} in it"
                return f"there are {qty} {self.np(rest)} in {self.zone(z)}"
        return gap("count-of")

    # ------------------------------------------------------------ time
    PHASES = frozenset({"☾", "☼", "⨯", "☉", "◒", "⤓"})

    def phase_noun(self, s: A.SymRef) -> str:
        return "draw step" if s.glyph == "⤓" else self.w(s, "noun")

    def time(self, t: A.Time) -> str:
        """Time phrases: until end of turn, this turn, the beginning of your end step, …"""
        items = list(t.items)
        g = [x.glyph if isinstance(x, A.SymRef) else None for x in items]
        if g == ["⧗"]:
            return self.w(items[0], "word")
        if g and g[0] == "⧗":
            return f"until the end of {self.time(A.Time(items=tuple(items[1:])))}"
        if g and g[0] == "⊢":
            return f"the beginning of {self.period(items[1:])}"
        return self.period(items)

    def period(self, items: list) -> str:
        g = [x.glyph if isinstance(x, A.SymRef) else None for x in items]
        owner = items[-1] if items and isinstance(items[-1], (PhrasePlan, A.Of)) else None
        if owner is not None:
            items, g = items[:-1], g[:-1]
        each = bool(g) and g[0] == "∀"
        if each:
            items, g = items[1:], g[1:]
        nxt = bool(g) and g[0] == "▷"
        last = bool(g) and g[0] == "◁"
        if nxt or last:
            items, g = items[1:], g[1:]
        bound = items[0] if items and isinstance(items[0], A.Bound) else None
        if bound is not None:
            items, g = items[1:], g[1:]
        num = next((x for x in items if isinstance(x, A.Num)), None)
        if num is not None:
            k = items.index(num)
            items, g = items[:k] + items[k + 1:], g[:k] + g[k + 1:]
        phase = items[0] if items and g[0] in self.PHASES else None
        turn = "◷" in g
        if phase is not None:
            noun = self.phase_noun(phase)
            if num is not None:
                noun = f"{['', 'first', 'second'][num.value] if num.value < 3 else num.value} {noun}"
            if owner is not None and phase.glyph == "⨯":
                return f"combat on {self.possessive(owner)} turn"
            if owner is not None:
                if each:
                    return f"each {self.np(owner)}'s {noun}"
                return f"{self.possessive(owner)} {noun}"
            if nxt:
                return f"the next {noun}" + (" this turn" if turn else "")
            if turn:
                return f"{noun} this turn"
            return f"each {noun}" if not each else f"each {noun}"
        if turn:
            if bound is not None:
                return "each turn" if owner is None else f"each of {self.possessive(owner)} turns"
            if owner is not None:
                if each:
                    return f"each of {self.possessive(owner)} turns"
                if nxt:
                    return f"{self.possessive(owner)} next turn"
                return f"{self.possessive(owner)} turn"
            if each:
                return "each turn"
            if last:
                return "last turn"
            return "this turn"
        if g == ["⧗"] and each:
            return "each end of turn"
        if g == ["∞"]:
            return "this game"
        return gap("time")

    # ------------------------------------------------------------ values
    def value(self, v) -> str:
        if isinstance(v, Gap):
            return gap(v.kind)
        if isinstance(v, A.Num):
            return f"{v.sign}{v.value}"
        if isinstance(v, A.Var):
            return f"{v.sign}{v.name}"
        if isinstance(v, A.Mana):
            return v.text
        if isinstance(v, A.Time):
            if v.items and isinstance(v.items[0], A.Bound) and self._limit_kind == "trigger":
                return "this ability triggers only once each turn"
            return self.time(v)
        if isinstance(v, A.Compare):
            return self.compare(v)
        if isinstance(v, A.NameRef):
            return v.key
        if isinstance(v, A.Characteristic):
            return self.characteristic(v)
        if isinstance(v, A.Delta) and v.char is not None and v.char.glyph == "♥" and v.amount is not None:
            return f"{self.number(v.amount, word=False)} life"
        if isinstance(v, A.EffectRef):
            e = self.g.effects.get(v.key)
            return e.labels.get("en", v.key) if e else gap("effect")
        if isinstance(v, A.Of):
            return self.of(v)
        if isinstance(v, (A.Or, A.And)):
            word = " or " if isinstance(v, A.Or) else " and "
            parts = [self.value(x) for x in v.items]
            return word.join(parts) if len(parts) == 2 else ", ".join(parts[:-1]) + "," + word + parts[-1]
        if isinstance(v, A.Count):
            return f"the number of {self.np(v.of)}"
        if isinstance(v, PhrasePlan):
            return self.np(v)
        if isinstance(v, (ClausePlan, SentencePlan)):
            return self.inline(v)
        if isinstance(v, A.Zone):
            return self.zone(v)
        if isinstance(v, A.Keyword):
            return self.keyword(v)
        return gap(getattr(v, "kind", type(v).__name__))


# ---------------------------------------------------------------- cards

def english_type_line(tl: A.TypeLine, g) -> str:
    from mtglang.validate import english_type_line as etl
    return etl(tl, g)


def stats_text(st: A.Stats | None) -> str | None:
    if st is None:
        return None
    if st.stat == "pt":
        return f"{st.power}/{st.toughness}"
    return st.value


class FaceText:
    def __init__(self, name: str, type_line: str, stats: str | None, lines: tuple[str, ...]):
        self.name, self.type_line, self.stats, self.lines = name, type_line, stats, lines

    def __repr__(self) -> str:
        return f"FaceText({self.name!r}, {self.type_line!r}, {self.stats!r}, {self.lines!r})"


def realize_card(plan: CardPlan, lex: Lexicon) -> list[FaceText]:
    out = []
    for f in plan.faces:
        en = En(lex, f.ctx)
        lines = tuple(line for a in f.abilities for line in en.ability(a).split("\n"))
        out.append(FaceText(f.name, english_type_line(f.types, lex.g), stats_text(f.stats), lines))
    return out


def render_card(card: A.Card, g) -> list[FaceText]:
    from mtglang import planner
    plan = planner.plan_card(card, [planner.context_for(card, i, g) for i in range(len(card.faces))], g)
    return realize_card(plan, Lexicon(g, "en"))


def render_card_en(root: Path, ref: str) -> list[FaceText]:
    from mtglang.astexport import card_ast
    from mtglang.glossary import load_glossary
    card = card_ast(Path(root), ref)
    if card is None:
        raise FileNotFoundError(ref)
    return render_card(card, load_glossary(Path(root) / "glossary"))
