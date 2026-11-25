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
    return s if "\n" in s else s + "."


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
        if k.params:
            word += " " + " ".join(self.value(p) for p in k.params)
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
        first, rest = self.split_first(a.parts["effect"])
        conds = "".join(f", if {self.inline(c)}" for c in a.parts["conds"])
        out = f"{head} {self.inline(ev)}{conds}, {fin(first)}"
        return out + "".join(f" {fin(cap(s))}" for s in rest)

    def _once(self, ev) -> bool:
        clauses = ev.clauses if isinstance(ev, SentencePlan) else (ev,)
        def once(c):
            if not (isinstance(c, ClausePlan) and isinstance(c.pred, A.SymRef)):
                return False
            if c.pred.glyph in ONCE_VERBS and c.subject is not None and c.subject.ref == "self":
                return True
            obj = self.arg(c, "object")
            return self.op(c.pred) == "cast" and isinstance(obj, PhrasePlan) and obj.ref == "self"
        return all(once(c) for c in clauses)

    _limit_kind = "activate"

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
            return f"{sign}{c.value}"
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
            out = []
            for c, j in zip(p.clauses, (None,) + p.joins):
                if j is not None and j.kind == "where":
                    out[-1] += f", where {self.inline(c)}"
                else:
                    out.append(self.inline(c))
            return out
        return [self.inline(p)]

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
        return self.value(p)

    def sentence_plan(self, p: SentencePlan) -> str:
        if p.lead is not None:
            return gap(f"lead:{p.lead}")
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
            a, b = (self.inline(c) for c in p.clauses)
            if j == "if":
                return f"if {a}, {b}"
            if j == "unless":
                return f"{a} unless {b}"
            if j == "until":
                return f"{a} until {b}"
            if j == "during":
                return f"{a} {b}"
        return gap("join:" + "+".join(j.kind for j in p.joins))

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
        else:
            body = gap(f"pred:{type(c.pred).__name__}")
        rest = self.trailing(c)
        return " ".join(x for x in (subj, body, rest) if x)

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
        g = v.glyph
        op = self.op(v)
        if op == "transfer":
            return self.transfer(c, third)
        if op == "has":
            state = self.static and not self.ctx.is_spell and self.arg(c, "time") is None
            word = ("has" if third else "have") if state else self.verb(v, third)
            ab = self.arg(c, "ability")
            return f"{word} {self.ability_arg(ab)}"
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
            else:
                words.append(self.value(a))
        del g
        return " ".join(words)

    def ability_arg(self, ab) -> str:
        if isinstance(ab, A.Keyword):
            return self.keyword(ab).lower()
        return gap("ability")

    def counted(self, n, noun: str) -> str:
        if isinstance(n, A.Count):
            return f"{article(noun)} {noun} for each {self.np(self._sg(n.of))}"
        if isinstance(n, A.Num) and n.value == 1:
            return f"{article(noun)} {noun}"
        return f"{self.number(n)} {noun}s"

    def mana(self, m) -> str:
        if isinstance(m, A.Mana):
            return m.text
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
            self._damage_dest = True
            try:
                return f"{'deals' if third else 'deal'} {self.number(amount, word=False)} damage to {self.np(dest)}"
            finally:
                self._damage_dest = False
        if hop == "counter":
            return f"{'puts' if third else 'put'} {self.counter_np(obj)} on {self.np(dest)}"
        if isinstance(dest, A.Zone):
            return self.move(obj, dest, third)
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

    def move(self, obj, dest: A.Zone, third: bool) -> str:
        """Zone changes: exile X / return X to … / put X into / onto / on top of …"""
        z = dest.zone.glyph
        src = self.from_zone(obj)
        o = self.np(obj, moving=True)
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
            words = self_phrase(self.ctx, self.lex, p.self_as)
            z = self.from_zone(p) if moving else None
            return f"{words} from {self.zone(z)}" if z is not None else words
        if p.ref == "you":
            return "you"
        if p.ref == "anaphor":
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
        pre, post = self.modifiers(p, moving)
        another = "another" in pre
        pre = [w for w in pre if w != "another"]
        noun = self.premodified(pre, self.head_words(p))
        quant = self._mod(p, "quant")
        target = quant is not None and self.op(quant) == "target"
        core = f"target {noun}" if target else noun
        if q == "up_to":
            count = self._mod(p, "count")
            n = count.value if isinstance(count, A.Bound) else count
            out = f"up to {self.number(n)} {core}"
        elif q == "one":
            out = f"another {core}" if another else (core if target else f"{article(core)} {core}")
        elif q == "each":
            out = f"each {core}" if role == "subject" or self.is_player(p) or self._damage_dest else \
                f"all {self.head_words(dataclasses_replace(p, number='pl'))}"
        elif q == "exists":
            out = f"{article(core)} {core}"
        else:
            out = core
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

    def possessive(self, x) -> str:
        if isinstance(x, PhrasePlan):
            if x.ref == "you":
                return "your"
            if x.ref == "anaphor":
                return "their" if self.is_player(x.antecedent) else "its"
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
            quant = self._mod(a, "quant")
            if quant is not None and self.op(quant) == "target":
                return "it"
            if ".event." in a.path + "." and a.heads:
                return f"that {self.head_words(dataclasses_replace(a, number='sg', mods=()))}"
        return "it"

    def head_words(self, p: PhrasePlan) -> str:
        words, token = [], any(isinstance(h, A.SymRef) and h.glyph == "◌" for h in p.heads)
        heads = list(p.heads)
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
                and cond.other.ref == "self":
            return "another"
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
        num = items[0] if items and isinstance(items[0], A.Num) else None
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
        if num is not None and len(items) > 1:
            items = items[1:]
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
        if isinstance(v, A.Of):
            return self.of(v)
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
