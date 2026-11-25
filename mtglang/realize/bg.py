"""Bulgarian realizer: clause plans → Bulgarian card text (modern spelling), then Ivanchev (pre-1945) spelling.

Words come from the glossary (``bg`` labels and ``lex.bg``: gender, definite and count forms, adjective and verb
forms). Grammar lives here: gender/number agreement, definite article, perfective vs imperfective, clitics,
relative clauses. Register follows the glossary's labels (late-19th-century literary). A construct this realizer
doesn't handle yet is written ``⟦kind⟧``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import replace as dreplace
from pathlib import Path

from mtglang import ast as A
from mtglang.lexicon import Lexicon
from mtglang.planir import AbilityPlan, CardContext, CardPlan, ClausePlan, Gap, PhrasePlan, SentencePlan

SAMPLE_FILE = "data/bg-sample.txt"

# subtypes a card names itself by (as in English: "this Saga")
SELF_SUBTYPES = ("Saga", "Aura", "Equipment", "Spacecraft", "Vehicle")
SELF_TYPE_ORDER = ("♞", "⛰", "⚙", "✧", "⚝")
ROMAN = ("", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")
COLORS = {"{W}": ("бял", "бяла", "бяло", "бели"), "{U}": ("син", "синя", "синьо", "сини"),
          "{B}": ("черен", "черна", "черно", "черни"), "{R}": ("червен", "червена", "червено", "червени"),
          "{G}": ("зелен", "зелена", "зелено", "зелени"), "∅": ("безцветен", "безцветна", "безцветно", "безцветни")}
NUMS = {1: ("един", "една", "едно"), 2: ("два", "две", "две")}
NUM_WORDS = ("нула", "", "", "три", "четири", "пет", "шест", "седем", "осем", "девет", "десет")
GI = {"m": 0, "f": 1, "n": 2, "pl": 3}


def gap(kind: str) -> str:
    return f"⟦{kind}⟧"


def cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def fin(s: str) -> str:
    return s if ("\n" in s or s.endswith(".“")) else s + "."


@dataclass(frozen=True)
class Np:
    """A rendered noun phrase with what agreement needs."""
    text: str
    gender: str = "m"           # m / f / n
    number: str = "sg"          # sg / pl

    @property
    def g(self) -> str:
        return "pl" if self.number == "pl" else self.gender


def demonstrative(g: str) -> str:
    return {"m": "тоя", "f": "тая", "n": "туй", "pl": "тия"}[g]


def relative(g: str) -> str:
    return {"m": "който", "f": "която", "n": "което", "pl": "които"}[g]


def pronoun(g: str, case: str = "subj") -> str:
    if case == "subj":
        return {"m": "той", "f": "тя", "n": "то", "pl": "те"}[g]
    if case == "clitic":
        return {"m": "го", "f": "я", "n": "го", "pl": "ги"}[g]
    if case == "poss":
        return {"m": "му", "f": "ѝ", "n": "му", "pl": "им"}[g]
    return {"m": "него", "f": "нея", "n": "него", "pl": "тях"}[g]      # after a preposition


def number_word(n: int, g: str) -> str:
    if n in NUMS:
        return NUMS[n][GI[g] if g != "pl" else 1]
    return NUM_WORDS[n] if 0 <= n < len(NUM_WORDS) else str(n)


class Bg:
    def __init__(self, lex: Lexicon, ctx: CardContext):
        self.lex, self.g, self.ctx = lex, lex.g, ctx
        self.holder: str | None = None       # "token" / "emblem" inside quotes
        self._condition = False              # inside a condition / trigger event: perfective forms

    # ------------------------------------------------------------ words
    def L(self, s) -> dict:
        return self.lex.sym(s.index) if isinstance(s, A.SymRef) else {}

    def w(self, s, key: str, default: str | None = None) -> str:
        v = self.L(s).get(key)
        if v is None:
            return default if default is not None else gap(f"{getattr(s, 'glyph', '?')}.{key}")
        return v

    def label(self, s) -> str:
        if isinstance(s, A.NameRef):
            n = self.g.names.get(s.key)
            return n.labels.get("bg", s.key) if n else s.key
        return self.g.symbols[s.index].labels.get("bg", s.glyph)

    def op(self, s) -> str | None:
        return self.g.symbols[s.index].syntax.get("op") if isinstance(s, A.SymRef) else None

    def adj(self, s, g: str) -> str:
        lx = self.L(s)
        return {"m": lx.get("adj"), "f": lx.get("adj_f"), "n": lx.get("adj_n"), "pl": lx.get("adj_pl")}[g] \
            or gap(f"{getattr(s, 'glyph', '?')}.adj")

    def pasv(self, s, g: str) -> str:
        lx = self.L(s)
        return {"m": lx.get("pasv"), "f": lx.get("pasv_f"), "n": lx.get("pasv_n"), "pl": lx.get("pasv_pl")}[g] \
            or gap(f"{getattr(s, 'glyph', '?')}.pasv")

    def noun(self, s, number: str = "sg", definite: bool = False) -> Np:
        if isinstance(s, A.NameRef):
            nm = self.g.names.get(s.key)
            return Np(self.label(s), (nm.lex.get("bg", {}).get("gender") if nm else None) or "m", number)
        lx = self.L(s)
        if number == "pl":
            word = lx.get("pl_def" if definite else "pl")
        else:
            word = lx.get("def" if definite else "noun")
        return Np(word or gap(f"{s.glyph}.noun"), lx.get("gender", "m"), number)

    def verb(self, s, form: str) -> str:
        return self.w(s, form)

    # ------------------------------------------------------------ abilities
    def ability(self, a) -> str:
        if isinstance(a, Gap):
            return gap(a.kind)
        fn = getattr(self, f"ab_{a.shape}", None)
        return fn(a) if fn else gap(a.shape)

    def ab_keywords(self, a: AbilityPlan) -> str:
        return ", ".join(self.keyword(k) for k in a.parts["items"])

    def keyword(self, k) -> str:
        if not isinstance(k, A.Keyword):
            return gap("keyword")
        word = self.label(k.sym)
        params = list(k.params)
        if params and isinstance(params[0], A.Filter):            # Basic landcycling → Обмяна на основна земя
            conds = [h for c in params[0].conds for h in (c.heads if isinstance(c, PhrasePlan) else (c,))]
            noun = next((c for c in conds if isinstance(c, A.SymRef) and "noun" in self.L(c)), None)
            adjs = [c for c in conds if isinstance(c, A.SymRef) and "adj" in self.L(c)]
            if noun is not None:
                n = self.noun(noun)
                word += " на " + " ".join([self.adj(x, n.g) for x in adjs] + [n.text])
            params = params[1:]
        for p in params:
            if isinstance(p, PhrasePlan):
                word += " " + self.np(p, role="kind").text
            else:
                word += " " + self.value(p)
        return word

    def ab_static(self, a: AbilityPlan) -> str:
        return self.text(a.parts["body"])

    def ab_triggered(self, a: AbilityPlan) -> str:
        ev = a.parts["event"]
        self._condition = True
        try:
            if isinstance(ev, A.Time):
                head = f"В {self.time(ev, begin_cap=False)}"
            else:
                head = ("Когато " if a.parts.get("once") else "Щом ") + self.inline(ev)
            conds = "".join(f", ако {self.condition(c)}" for c in a.parts["conds"])
        finally:
            self._condition = False
        sents = self.sentences(a.parts["effect"])
        out = f"{head}{conds}, {fin(sents[0])}"
        return out + "".join(f" {fin(cap(s))}" for s in sents[1:])

    def ab_activated(self, a: AbilityPlan) -> str:
        costs = ", ".join(cap(self.cost(c)) for c in a.parts["cost"])
        out = f"{costs}: {self.text(a.parts['effect'])}"
        if a.parts["limits"]:
            out += " " + gap("limit")
        return out

    def cost(self, c) -> str:
        if isinstance(c, A.Mana):
            return c.text
        if isinstance(c, (A.Num, A.Var)):
            sign = {"-": "−", "−": "−", "+": "+"}.get(c.sign, "")
            v = c.value if isinstance(c, A.Num) else c.name
            return f"[{sign}{v}]" if self.holder else f"{sign}{v}"
        return self.inline(c)

    def ab_modal(self, a: AbilityPlan) -> str:
        return cap(self.modal(a))

    def modal(self, a: AbilityPlan) -> str:
        choose = a.parts["choose"]
        amount = next((v for s, v in choose.args if s == "amount"), None) if isinstance(choose, ClausePlan) else None
        n = number_word(amount.value, "n") if isinstance(amount, A.Num) else gap("choose")
        return f"избери {n} —" + "".join(f"\n{self.ability(m)}" for m in a.parts["modes"])

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
        label = " ".join(self.label(x) for x in a.label)
        return f"{label} — {self.ability(a.parts['ability'])}"

    # ------------------------------------------------------------ sentences
    def sentences(self, p) -> list[str]:
        if isinstance(p, SentencePlan) and p.lead is None and len(p.clauses) == 1:
            return self.sentences(p.clauses[0])
        if isinstance(p, SentencePlan) and p.lead is None and p.joins and \
                all(j.kind in ("sentence", "where") for j in p.joins):
            out: list[str] = []
            chain = False
            for i, (c, j) in enumerate(zip(p.clauses, (None,) + p.joins)):
                if j is not None and j.kind == "where":
                    out[-1] += f", дето {self.inline(c)}"
                    continue
                prev = p.clauses[i - 1] if i else None
                text = self.inline(c)
                if prev is not None and (self._search_chain(p.clauses[:i]) or
                                         (self._card_flow(prev) and self._card_flow(c) and not chain)):
                    out[-1] += f", сетне {text}" if not self._search_chain(p.clauses[:i]) or \
                        i == len(p.clauses) - 1 else f", {text}"
                    chain = True
                    continue
                out.append(text)
                chain = False
            return out
        return [self.inline(p)]

    def _search_chain(self, before) -> bool:
        for c in reversed(before):
            if not isinstance(c, ClausePlan):
                return False
            if isinstance(c.pred, A.SymRef) and c.pred.glyph == "⌖":
                return True
        return False

    def _card_flow(self, c) -> bool:
        return isinstance(c, ClausePlan) and isinstance(c.pred, A.SymRef) and c.pred.glyph in ("⤓", "⌫") \
            and not c.optional

    def text(self, p) -> str:
        return " ".join(fin(cap(s)) for s in self.sentences(p))

    def inline(self, p) -> str:
        if isinstance(p, Gap):
            return gap(p.kind)
        if isinstance(p, ClausePlan):
            return self.clause(p)
        if isinstance(p, SentencePlan):
            return self.sentence_plan(p)
        if isinstance(p, AbilityPlan):
            return self.modal(p) if p.shape == "modal" else gap(f"ability:{p.shape}")
        if isinstance(p, A.Nested):
            return self.nested(p.ability)
        if isinstance(p, A.Time):
            if p.items and isinstance(p.items[0], A.Bound):
                return "тая способност се подбужда само веднъж на ход"
            return self.time(p)
        return self.value(p)

    def nested(self, a) -> str:
        if not isinstance(a, AbilityPlan) or a.shape != "triggered":
            return gap("nested")
        ev, eff = a.parts["event"], a.parts["effect"]
        if isinstance(ev, A.Time):
            sents = self.sentences(eff)
            if len(sents) == 1:
                return f"{sents[0]} в {self.time(ev)}"
        return gap("nested")

    def sentence_plan(self, p: SentencePlan) -> str:
        if p.lead is not None:
            body = self.inline(p.clauses[0])
            if p.lead == "if_do":
                return f"сториш ли го, {body}"
            if p.lead == "if_dont":
                return f"не сториш ли го, {body}"
            return gap("lead:instead")
        if len(p.clauses) == 1:
            return self.inline(p.clauses[0])
        kinds = {j.kind for j in p.joins}
        if kinds <= {"and", "or"} and len(kinds) == 1:
            word = " и " if kinds == {"and"} else " или "
            merged = self.merge(p, word)
            if merged is not None:
                return merged
            return word.join(self.inline(c) for c in p.clauses)
        if kinds <= {"sentence", "where"}:
            return ". ".join(cap(s) if i else s for i, s in enumerate(self.sentences(p)))
        if len(p.joins) == 1:
            j = p.joins[0].kind
            if j == "instead":
                ev, eff = p.clauses
                if isinstance(ev, ClausePlan) and getattr(ev.pred, "glyph", "") == "↥" and \
                        isinstance(ev.subject, PhrasePlan) and ev.subject.ref == "self":
                    return f"докато {self.np(ev.subject, role='subject').text} {self.verb(ev.pred, 'pr3')}, " \
                           f"{self.inline(eff)}"
                return gap("instead")
            if j == "while":
                return f"{self.inline(p.clauses[0])}, докле {self.condition(p.clauses[1])}"
            if j == "if":
                return f"ако {self.condition(p.clauses[0])}, {self.inline(p.clauses[1])}"
            if j == "during":
                return f"{self.inline(p.clauses[0])} {self.value(p.clauses[1])}"
        return gap("join:" + "+".join(j.kind for j in p.joins))

    def merge(self, p: SentencePlan, word: str) -> str | None:
        """«придобива Тъпчене и Живоносност»: shared subject, same verb, keyword arguments."""
        if len(p.clauses) != 2 or not all(isinstance(c, ClausePlan) for c in p.clauses):
            return None
        a, b = p.clauses
        if not b.subject_shared or not (isinstance(a.pred, A.SymRef) and isinstance(b.pred, A.SymRef)) or \
                a.pred.index != b.pred.index or self.op(a.pred) != "has" or self._arg(a, "time") is not None:
            return None
        return f"{self.clause(a)}{word}{self.ability_arg(self._arg(b, 'ability'))}" + \
            (f" {self.trailing(b)}" if self.trailing(b) else "")

    def condition(self, c) -> str:
        saved, self._condition = self._condition, True
        try:
            if isinstance(c, A.Compare):
                return self.compare(c)
            if isinstance(c, PhrasePlan) and c.quantity == "exists":
                ctl = self.control_rel(c)
                if ctl is not None:
                    rest = dreplace(c, mods=self._without(c.mods, ctl), quantity="one")
                    return f"{self.control_verb(ctl.other)} {self.np(rest).text}"
            return self.inline(c)
        finally:
            self._condition = saved

    # ------------------------------------------------------------ clauses
    def _arg(self, c: ClausePlan, slot: str):
        return next((v for s, v in c.args if s == slot), None)

    def trailing(self, c: ClausePlan) -> str:
        return " ".join(self.value(v) for s, v in c.args if s == "time")

    _shared: Np | None = None

    def clause(self, c: ClausePlan) -> str:
        """Subject (omitted for "you" and imperatives) + verb + arguments."""
        subj: Np | None = None
        if c.mood == "imperative":
            person = "imp"
        elif c.subject_shared:
            subj, person = None, ("2" if self._shared is None else "3")
            shared = self._shared
            person = "3" if shared is not None else "2"
            subj_np = shared
        elif isinstance(c.subject, PhrasePlan) and c.subject.ref == "you":
            person = "2"
        else:
            subj = self.np(c.subject, role="subject") if c.subject is not None else None
            person = "3"
        if not c.subject_shared:
            self._shared = subj if person == "3" else None
            subj_np = subj
        body = self.predicate(c, person, subj_np)
        rest = self.trailing(c)
        if c.optional:
            body = f"можеш да {body}"
        parts = [subj.text if subj is not None else "", body, rest]
        return " ".join(x for x in parts if x)

    def form(self, v, person: str, subj: Np | None) -> str:
        """The verb form: imperative, 2nd person, or 3rd person (singular/plural); perfective in conditions
        and trigger events (``Щом … нападне``)."""
        if person == "imp":
            return self.verb(v, "imp")
        pf = self._condition
        if person == "2":
            return self.verb(v, "pf2" if pf else "pr2")
        plural = subj is not None and subj.number == "pl"
        key = ("pf3pl" if plural else "pf3") if pf else ("pr3pl" if plural else "pr3")
        lx = self.L(v)
        return lx.get(key) or lx.get(key.replace("pf", "pr")) or gap(f"{v.glyph}.{key}")

    def predicate(self, c: ClausePlan, person: str, subj: Np | None) -> str:
        p = c.pred
        plural = subj is not None and subj.number == "pl"
        if c.optional and person in ("2", "imp"):
            person = "2"
            saved, self._condition = self._condition, True       # «можеш да изтеглиш»: perfective
            try:
                return self.predicate(dreplace(c, optional=False), person, subj)
            finally:
                self._condition = saved
        if isinstance(p, A.PT):
            verb = "получават" if plural else ("получи" if self._condition else "получава")
            return f"{verb} {self.pt(p)}"
        if isinstance(p, A.Delta):
            if p.char is not None and p.char.glyph == "♥" and p.sign not in ("-", "−"):
                verb = self.form(p.char, person, subj)
                if p.amount is None:
                    return f"{verb} живот"
                return f"{verb} {self.life(p.amount)}"
            return gap("delta")
        if not isinstance(p, A.SymRef):
            return gap("pred")
        op = self.op(p)
        if op == "transfer":
            return self.transfer(c, person, subj)
        if op == "has":
            state = c.aspect == "state"
            verb = (self.w(p, "state_pl" if plural else "state") if state else
                    self.form(p, person, subj))
            return f"{verb} {self.ability_arg(self._arg(c, 'ability'))}"
        obj = self._arg(c, "object")
        if p.glyph == "✚" and isinstance(obj, PhrasePlan) and obj.heads and getattr(obj.heads[0], "glyph", "") == "✪":
            ab = self._arg(dict(c.args).get("state"), "ability") if isinstance(dict(c.args).get("state"), ClausePlan) else None
            return f"получаваш знамение с {self.ability_arg(ab, 'emblem')}"
        if p.glyph == "⌖":
            z = self._arg(c, "zone")
            return f"{self.form(p, person, subj)} {self.zone_in(z)} {self.np(obj).text}"
        if p.glyph == "⟲":
            return f"{self.form(p, person, subj)} книгохранилището си"
        verb = self.form(p, person, subj)
        frame = self.L(p).get("frame")
        words = [verb]
        for slot, a in c.args:
            if slot == "time":
                continue
            if slot == "amount":
                words.append(self.counted(a, p))
            elif slot == "mana":
                words.append(self.mana(a))
            elif slot == "state" and isinstance(a, ClausePlan) and isinstance(a.pred, A.SymRef) and not a.args:
                g = subj.g if subj is not None else "m"
                lx = self.L(a.pred)
                words.append(lx.get("state") or self.pasv(a.pred, g))
            elif slot == "state" and isinstance(a, ClausePlan) and self.op(a.pred) == "has":
                holder = "token" if isinstance(obj, PhrasePlan) and any(
                    getattr(h, "glyph", "") == "◌" for h in obj.heads) else None
                words.append(f"с {self.ability_arg(self._arg(a, 'ability'), holder)}")
            elif slot == "object":
                o = self.np(a, role="object")
                if frame and "{object}" in frame:
                    words.append(frame.replace("{object}", o.text))
                else:
                    words.append(o.text)
            else:
                words.append(self.value(a))
        return " ".join(words)

    def counted(self, n, verb) -> str:
        """«карта», «две карти» for verbs that count a noun (draw, discard); a bare number otherwise."""
        lx = self.L(verb)
        if "noun" not in lx:
            return self.value(n)
        if isinstance(n, A.Num):
            if n.value == 1:
                return lx["noun"]
            return f"{number_word(n.value, lx.get('gender', 'm'))} {lx.get('pl', lx['noun'])}"
        return gap("count")

    def life(self, n) -> str:
        if isinstance(n, A.Num):
            return f"{n.value} точка живот" if n.value == 1 else f"{n.value} точки живот"
        return f"{self.value(n)} точки живот"

    def mana(self, m) -> str:
        if isinstance(m, A.Mana):
            return m.text
        if isinstance(m, A.Or):
            return " или ".join(self.mana(x) for x in m.items)
        return gap("mana")

    def ability_arg(self, ab, holder: str | None = None) -> str:
        if isinstance(ab, A.Keyword):
            return self.keyword(ab)
        if isinstance(ab, A.Nested):
            ab = ab.ability
        if isinstance(ab, (AbilityPlan, ClausePlan, SentencePlan)):
            sub = Bg(self.lex, self.ctx)
            sub.holder = holder
            text = sub.ability(ab) if isinstance(ab, AbilityPlan) else sub.text(ab)
            if not text.endswith((".", "—")):
                text += "."
            return f"„{text}“"
        return gap("ability")

    def transfer(self, c: ClausePlan, person: str, subj: Np | None) -> str:
        obj, dest = self._arg(c, "object"), self._arg(c, "destination")
        head = obj.heads[0] if isinstance(obj, PhrasePlan) and obj.heads else None
        hop = self.op(head)
        if hop == "damage":
            amount = next((v for s, v in obj.mods if s == "count"), None)
            combat = any(getattr(h, "glyph", "") == "⨯" for h in obj.heads[1:])
            verb = "нанеси" if person == "imp" else ("нанесе" if self._condition else "нанася")
            n = f"{amount.value} " if isinstance(amount, A.Num) else ""
            dmg = "щета" if isinstance(amount, A.Num) and amount.value == 1 else "щети"
            kind = " в бой" if combat else ""
            d = self.np(dest, role="destination")
            return f"{verb} {n}{dmg}{kind} на {d.text}".replace("  ", " ")
        if hop == "counter":
            verb = "сложи" if person == "imp" else "слага"
            return f"{verb} {self.counter(obj)} на {self.np(dest, role='destination').text}"
        if isinstance(dest, A.Zone):
            return self.move(obj, dest, person, subj)
        return gap("transfer")

    def counter(self, p: PhrasePlan) -> str:
        kind = p.heads[1] if len(p.heads) > 1 else None
        if isinstance(kind, A.PT):
            what = self.pt(kind)
        elif isinstance(kind, A.SymRef):
            what = self.label(kind).lower()
        else:
            what = ""
        return f"белег {what}".strip()

    def from_zone(self, p) -> A.Zone | None:
        if isinstance(p, PhrasePlan):
            for s, f in p.mods:
                if s == "filters":
                    for flt in f:
                        for c in getattr(flt, "conds", ()):
                            if isinstance(c, A.Zone):
                                return c
            if p.ref == "anaphor":
                return self.from_zone(p.antecedent)
        return None

    def move(self, obj, dest: A.Zone, person: str, subj: Np | None) -> str:
        z = dest.zone.glyph
        src = self.from_zone(obj)
        o = self.np(obj, role="object", moving=True)
        if z == "⊘":
            return f"{self.form(dest.zone, person, subj)} {o.text}"
        imp = person == "imp"
        if z == "☚":
            verb = "върни" if imp and (src is None or src.zone.glyph in ("▦", "⚰")) else "сложи"
            return f"{verb} {o.text} {self.zone_to(dest, obj)}"
        if z == "▦":
            verb = "върни" if src is not None and src.zone.glyph == "⚰" else "сложи"
            return f"{verb} {o.text} на бойното поле"
        if z == "⚰":
            return f"сложи {o.text} в {self.zone_name(dest)}"
        return gap("move")

    def zone_name(self, z: A.Zone) -> str:
        """«гробището си» (yours), «някое гробище» (any)."""
        lx = self.L(z.zone)
        if z.owner is None:
            return f"някое {lx.get('noun', gap('zone'))}" if z.zone.glyph == "⚰" else lx.get("def", gap("zone"))
        if isinstance(z.owner, PhrasePlan) and z.owner.ref == "you":
            return f"{lx.get('def', gap('zone'))} си"
        return gap("zone-owner")

    def zone_in(self, z) -> str:
        return f"в {self.zone_name(z)}" if isinstance(z, A.Zone) else gap("zone")

    def zone_to(self, dest: A.Zone, obj) -> str:
        lx = self.L(dest.zone)
        if isinstance(dest.owner, A.SymRef) and self.op(dest.owner) == "own":
            g = self._np_gender(obj)
            return f"в {lx.get('def')} на стопанина {pronoun(g, 'poss')}"
        return f"в {self.zone_name(dest)}"

    def _np_gender(self, p) -> str:
        try:
            return self.np(p).g
        except Exception:
            return "m"

    def pt(self, p: A.PT) -> str:
        def sgn(n):
            if isinstance(n, A.Num):
                return f"{'-' if n.sign in ('-', '−') else n.sign}{n.value}"
            if isinstance(n, A.Var):
                return f"{n.sign}{n.name}"
            return gap("pt")
        return f"{sgn(p.power)}/{sgn(p.toughness)}"

    # ------------------------------------------------------------ phrases
    def self_np(self, p: PhrasePlan, role: str) -> Np:
        ctx = self.ctx
        if self.holder in ("token", "emblem"):           # «тоя образ», «туй знамение»
            n = self.noun(A.SymRef(index=self._sym("◌" if self.holder == "token" else "✪"),
                                   glyph="◌" if self.holder == "token" else "✪"))
            return Np(f"{demonstrative(n.gender)} {n.text}", n.gender)
        if p.self_as == "card":
            return Np("тая карта", "f")
        if ctx.is_spell or ctx.legendary:
            nm = self.g.names.get(ctx.name)
            label = nm.labels.get("bg", ctx.name) if nm else ctx.name
            short = (nm.lex.get("bg", {}).get("short") if nm else None) or label.split(",", 1)[0]
            if ctx.planeswalker and ctx.subtype_keys:
                short = self.label(A.NameRef(key=ctx.subtype_keys[0]))
            gender = (nm.lex.get("bg", {}).get("gender") if nm else None) or "m"
            if ctx.is_spell:
                return Np(label, gender)
            return Np(short, gender)
        for sub in SELF_SUBTYPES:
            if sub in ctx.subtype_keys:
                n = self.noun(A.NameRef(key=sub))
                return Np(f"{demonstrative(n.g)} {n.text}", n.gender)
        for glyph in SELF_TYPE_ORDER:
            for i in ctx.type_syms:
                if self.g.symbols[i].glyph == glyph:
                    n = self.noun(A.SymRef(index=i, glyph=glyph))
                    return Np(f"{demonstrative(n.g)} {n.text.lower()}", n.gender)
        return Np("тоя трайник", "m")

    def np(self, p, role: str = "object", moving: bool = False) -> Np:
        if isinstance(p, A.Zone):
            return Np(self.zone_name(p), "n")
        if not isinstance(p, PhrasePlan):
            return Np(self.value(p))
        if p.ref == "self":
            full = self.self_np(p, role)
            if p.pronoun and p.self_as == "permanent" and not self.holder:
                return Np(pronoun(full.g, "subj" if role == "subject" else "obj"), full.gender)
            if moving and p.self_as == "card":
                z = self.from_zone(p)
                if z is not None:
                    return Np(f"{full.text} от {self.zone_name(z)}", full.gender)
            return full
        if p.ref == "you":
            return Np("ти", "m")
        if p.ref == "anaphor":
            return self.anaphor(p, role)
        return self.new_np(p, role, moving)

    def anaphor(self, p: PhrasePlan, role: str) -> Np:
        a = p.antecedent
        ante = self.np(dreplace(a, pronoun=False), role="kind") if isinstance(a, PhrasePlan) else Np("")
        if isinstance(a, PhrasePlan):
            quant = next((v for s, v in a.mods if s == "quant"), None)
            if quant is None or self.op(quant) != "target":
                if ".event." in a.path + "." and a.heads:            # the trigger's subject: «речената твар»
                    head = self.head(a)
                    return Np(f"{'речения' if head.g == 'm' else 'речената' if head.g == 'f' else 'реченото'} "
                              f"{head.text}", head.gender)
        case = "subj" if role == "subject" else ("obj" if role == "destination" else "clitic")
        return Np(pronoun(ante.g, case), ante.gender, ante.number)

    def head(self, p: PhrasePlan, number: str | None = None, definite: bool = False) -> Np:
        """The head noun(s): «твар», «карта-земя», «твар или мироходец», «образ»."""
        number = number or p.number
        heads = [h for h in p.heads]
        names = [h for h in heads if isinstance(h, A.NameRef)]
        syms = [h for h in heads if isinstance(h, A.SymRef)]
        objs = [h for h in syms if self.g.symbols[h.index].syntax.get("kind") == "object"]
        types = [h for h in syms if h not in objs and "noun" in self.L(h)]
        alts = [h for h in heads if isinstance(h, A.Or)]
        if alts:
            parts = [self.head(dreplace(p, heads=(x,)), number, definite) for x in alts[0].items]
            joiner = " и " if number == "pl" else " или "
            return Np(joiner.join(x.text for x in parts), parts[0].gender, number)
        if objs:
            main = self.noun(objs[0], number, definite)
            if types:            # карта-земя, карта-твар
                return Np(f"{main.text}-{self.noun(types[0]).text}", main.gender, number)
            if names:
                return Np(f"{main.text} {' '.join(self.label(n) for n in names)}", main.gender, number)
            return main
        if names and not types:
            return self.noun(names[0], number)
        if types:
            main = self.noun(types[0], number, definite)
            if names:            # Мироходец Джейс
                return Np(f"{main.text} {' '.join(self.label(n) for n in names)}", main.gender, number)
            return main
        return Np(gap("head"))

    def new_np(self, p: PhrasePlan, role: str, moving: bool) -> Np:
        q = p.quantity
        quant = next((v for s, v in p.mods if s == "quant"), None)
        target = quant is not None and self.op(quant) == "target"
        if not p.heads and target:
            return Np(f"{self.adj(quant, 'f')} цел", "f")
        token = any(getattr(h, "glyph", "") == "◌" for h in p.heads)
        if token:
            return self.token_np(p)
        plural = q in ("all",) and p.number == "pl"
        definite = plural and role == "subject"
        head = self.head(p, "pl" if plural else p.number, definite)
        g = head.g
        pre, rel, other = [], [], False
        for slot, f in p.mods:
            if slot != "filters":
                continue
            for flt in f:
                for c in getattr(flt, "conds", ()):
                    if isinstance(c, A.Rel) and self.op(c.rel) == "other":
                        other = True
                    elif isinstance(c, A.Rel) and isinstance(c.other, PhrasePlan) and c.other.ref == "self" \
                            and "adj" in self.L(c.rel):
                        pre.append(self.adj(c.rel, g))
                        definite = True
                    elif isinstance(c, A.Rel) and self.op(c.rel) == "control":
                        rel.append(f"{relative(g)} {self.control_verb(c.other)}")
                    elif isinstance(c, A.Zone):
                        rel.append(("от " if moving else "в ") + self.zone_name(c))
                    elif isinstance(c, A.Not) and isinstance(c.item, PhrasePlan):
                        rel.append(f"{relative(g)} не е {self.head(c.item).text.lower()}")
                    elif isinstance(c, A.Compare):
                        rel.append(self.compare(c, in_filter=True))
                    elif isinstance(c, A.SymRef) and "adj" in self.L(c):
                        pre.append(self.adj(c, g))
                    else:
                        rel.append(gap(f"filter:{getattr(c, 'kind', type(c).__name__)}"))
        rel_g = "pl" if any(isinstance(h, A.Or) for h in p.heads) else g
        rel = [r.replace(relative(g), relative(rel_g), 1) if r.startswith(relative(g) + " ") else r for r in rel]
        rel = self._join_nots(rel, rel_g)
        preps = [r for r in rel if not r.startswith(relative(rel_g) + " ")]
        rels = [r for r in rel if r.startswith(relative(rel_g) + " ")]
        if len(rels) > 1:          # «която владееш и не е образ»
            rels = [rels[0] + "".join(" и " + r[len(relative(rel_g)) + 1:] for r in rels[1:])]
        words = []
        if definite and pre:                         # «омаяната твар»
            pre = [pre[0] + {"m": "ият", "f": "та", "n": "то", "pl": "те"}[g]] + pre[1:]
            definite_done = True
        else:
            definite_done = False
        if q == "each":
            words.append({"m": "всеки", "f": "всяка", "n": "всяко", "pl": "всички"}[g])
        elif q == "up_to":
            count = next((v for s, v in p.mods if s == "count"), None)
            n = count.value if isinstance(count, A.Bound) else count
            words.append("до " + (number_word(n.value, g) if isinstance(n, A.Num) else self.value(n)))
        if q == "all" and role != "subject":
            words.append("всички")
        if other:
            words.append(self.adj(A.SymRef(index=self._sym("≠"), glyph="≠"), g))
        if target:
            words.append(self.adj(quant, g))
        words += pre
        noun = head.text
        if definite and not definite_done and not pre and role == "subject" and plural:
            noun = head.text
        words.append(noun)
        text = " ".join(words)
        if preps:
            text += " " + " ".join(preps)
        if rels:
            text += ", " + rels[0] + ("," if role == "subject" else "")
        return Np(text, head.gender, head.number)

    def _join_nots(self, rel: list[str], g: str) -> list[str]:  # noqa: D401
        """«…, който не е твар, …, който не е земя» → «който не е нито твар, нито земя»."""
        nots = [r for r in rel if r.startswith(f"{relative(g)} не е ")]
        if len(nots) < 2:
            return rel
        items = [r[len(f"{relative(g)} не е "):] for r in nots]
        joined = f"{relative(g)} не е нито " + ", нито ".join(items)
        return [r for r in rel if r not in nots] + [joined]

    def _sym(self, glyph: str) -> int:
        return next(i for i, s in enumerate(self.g.symbols) if s.glyph == glyph)

    def control_verb(self, who) -> str:
        if isinstance(who, PhrasePlan) and who.ref == "you":
            return "владееш"
        n = self.np(who, role="subject")
        return f"{n.text} {'владеят' if n.number == 'pl' else 'владее'}"

    def control_rel(self, p: PhrasePlan):
        for s, f in p.mods:
            if s == "filters":
                for flt in f:
                    for c in getattr(flt, "conds", ()):
                        if isinstance(c, A.Rel) and self.op(c.rel) == "control":
                            return c
        return None

    @staticmethod
    def _without(mods: tuple, cond) -> tuple:
        out = []
        for s, v in mods:
            if s == "filters":
                v = tuple(dreplace(f, conds=tuple(c for c in f.conds if c is not cond)) for f in v)
                v = tuple(f for f in v if f.conds)
                if not v:
                    continue
            out.append((s, v))
        return tuple(out)

    def token_np(self, p: PhrasePlan) -> Np:
        """«бял образ-твар 2/2 Котка Войник на име Аджаниев побратим»: the token noun and its gender come from
        the glossary (``◌``), colour and count agree with it."""
        color_forms, pt, kind, subs = None, "", "", []
        for s, f in p.mods:
            if s != "filters":
                continue
            for flt in f:
                for c in getattr(flt, "conds", ()):
                    if isinstance(c, A.PT):
                        pt = self.pt(c)
                    elif isinstance(c, A.Characteristic) and c.char.glyph == "♦":
                        key = c.of.text if isinstance(c.of, A.Mana) else getattr(c.of, "glyph", "")
                        forms = COLORS.get(key) or (gap("color"),) * 4
                        color_forms = forms
                    elif isinstance(c, PhrasePlan):
                        for h in c.heads:
                            if isinstance(h, A.NameRef):
                                subs.append(self.label(h))
                            elif isinstance(h, A.SymRef) and "noun" in self.L(h):
                                kind = self.L(h)["noun"]
        names = [h for h in p.heads if isinstance(h, A.NameRef)]
        count = next((v for s, v in p.mods if s == "count"), None)
        plural = isinstance(count, A.Num) and count.value > 1
        tok = next(h for h in p.heads if getattr(h, "glyph", "") == "◌")
        lx = self.L(tok)
        gender = lx.get("gender", "m")
        if plural:
            noun = lx.get("cnt" if gender == "m" else "pl") or gap("◌.pl")
        else:
            noun = lx.get("noun") or gap("◌.noun")
        words = []
        if plural:
            words.append(number_word(count.value, gender))
        if color_forms:
            words.append(color_forms[3] if plural else color_forms[GI[gender]])
        words.append(f"{noun}-{kind}" if kind else noun)
        if pt:
            words.append(pt)
        words += subs
        if names and not subs and not kind:          # a named token: «образ Сърцевина»
            words += [self.label(n) for n in names]
        name = next((v for s, v in p.mods if s == "name"), None)
        if name is not None:
            words.append(f"на име {self.label(name)}")
        return Np(" ".join(words), gender, "pl" if plural else "sg")

    # ------------------------------------------------------------ comparisons and time
    def compare(self, c: A.Compare, in_filter: bool = False) -> str:
        if len(c.items) != 2 or len(c.ops) != 1:
            return gap("compare")
        a, b = c.items
        op = c.ops[0].glyph
        if isinstance(a, A.Characteristic) and a.of is None and isinstance(b, A.Num):
            bound = {"≤": "или по-малко", "≥": "или повече"}.get(op)
            if bound:
                return f"{'с ' if in_filter else ''}{self.label(a.char).lower()} {b.value} {bound}"
        if isinstance(a, A.Count) and isinstance(b, A.Num) and op == "≥" and isinstance(a.of, ClausePlan):
            ev = a.of
            subj = self.head(ev.subject, "pl") if isinstance(ev.subject, PhrasePlan) else Np("")
            past = self.w(ev.pred, "part_pl")
            t = self._arg(ev, "time")
            when = f" {self.time(t)}" if t is not None else ""
            return f"{number_word(b.value, subj.gender)} или повече {subj.text} са {past}{when}"
        return gap("compare")

    def time(self, t: A.Time, begin_cap: bool = False) -> str:
        items = list(t.items)
        gl = [x.glyph if isinstance(x, A.SymRef) else None for x in items]
        if gl == ["⧗"]:
            return self.w(items[0], "word")
        if gl == ["◷"]:
            return "тоя ход"
        if gl and gl[0] == "⊢":
            return f"началото на {self.period(items[1:])}"
        return self.period(items)

    def period(self, items: list) -> str:
        gl = [x.glyph if isinstance(x, A.SymRef) else None for x in items]
        owner = items[-1] if items and isinstance(items[-1], PhrasePlan) else None
        if owner is not None:
            items, gl = items[:-1], gl[:-1]
        nxt = bool(gl) and gl[0] == "▷"
        if nxt:
            items, gl = items[1:], gl[1:]
        phase = items[0] if items and gl[0] in ("☾", "☼", "⨯", "☉") else None
        if phase is not None:
            lx = self.L(phase)
            if owner is not None and phase.glyph == "⨯":
                return f"{lx.get('def')} през твоя ход" if owner.ref == "you" else gap("time")
            if owner is not None and owner.ref == "you":
                return f"твоята {lx.get('noun')}" if lx.get("gender") == "f" else f"твоя {lx.get('noun')}"
            if nxt:
                word = {"m": "следващия", "f": "следващата", "n": "следващото"}[lx.get("gender", "m")]
                return f"{word} {lx.get('noun')}"
            return f"всяка {lx.get('noun')}" if lx.get("gender") == "f" else f"всеки {lx.get('noun')}"
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
        if isinstance(v, A.NameRef):
            return self.label(v)
        if isinstance(v, A.Time):
            return self.time(v)
        if isinstance(v, PhrasePlan):
            return self.np(v).text
        if isinstance(v, (ClausePlan, SentencePlan)):
            return self.inline(v)
        if isinstance(v, A.Keyword):
            return self.keyword(v)
        if isinstance(v, A.Delta) and v.char is not None and v.char.glyph == "♥" and v.amount is not None:
            return self.life(v.amount)
        if isinstance(v, A.Compare):
            return self.compare(v)
        return gap(getattr(v, "kind", type(v).__name__))


# ---------------------------------------------------------------- cards

@dataclass
class BgFace:
    name: str
    type_line: str
    stats: str | None
    lines: tuple[str, ...]
    old: "BgFace | None" = None


def type_line(tl: A.TypeLine, g) -> str:
    """«Прочута твар — Човек Вълшебник», «Изделие-твар — Сфинкс»: supertypes agree with the first card type;
    several card types are joined with hyphens."""
    def word(n) -> str:
        if isinstance(n, A.NameRef):
            return g.names[n.key].labels.get("bg", n.key) if n.key in g.names else n.key
        return g.symbols[n.index].labels.get("bg", n.glyph)
    lexes = [g.symbols[t.index].lex.get("bg", {}) if isinstance(t, A.SymRef) else {} for t in tl.types]
    nouns = [t for t, lx in zip(tl.types, lexes) if "noun" in lx]
    adjs = [lx for lx in lexes if "adj" in lx and "noun" not in lx]
    if nouns:
        gender = g.symbols[nouns[0].index].lex["bg"].get("gender", "m")
        first = [lx[{"m": "adj", "f": "adj_f", "n": "adj_n"}[gender]] for lx in adjs]
        main = "-".join([word(nouns[0])] + [word(n).lower() for n in nouns[1:]])
        if first:
            main = " ".join([cap(first[0])] + first[1:] + [main.lower()])
        left = main
    else:
        left = " ".join(word(t) for t in tl.types)
    return left + (" — " + " ".join(word(t) for t in tl.subtypes) if tl.dash is not None else "")


def to_old(text: str, root: Path | None = None) -> str:
    """Ivanchev (pre-1945) spelling of modern Bulgarian text; symbols, digits and punctuation untouched."""
    from mtglang.ortho.glossary import load_overrides
    from mtglang.ortho.ivanchev import to_ivanchev
    words = load_overrides(Path(root))[0] if root is not None and (Path(root) / "glossary").exists() else {}
    return to_ivanchev(text, words)


def realize_card(plan: CardPlan, lex: Lexicon, root: Path | None = None) -> list[BgFace]:
    from mtglang.realize.en import stats_text
    out = []
    g = lex.g
    for f in plan.faces:
        lines = []
        for a in f.abilities:
            r = Bg(lex, f.ctx)
            try:
                text = r.ability(a)
            except Exception as e:      # one ability the realizer can't handle never blanks the card
                text = f"⟦crash:{type(e).__name__}: {e}⟧"
            lines.extend(text.split("\n"))
        nm = g.names.get(f.name)
        name = nm.labels.get("bg", f.name) if nm else f.name
        modern = BgFace(name, type_line(f.types, g), stats_text(f.stats), tuple(lines))
        modern.old = BgFace(to_old(name, root), to_old(modern.type_line, root), modern.stats,
                            tuple(to_old(x, root) for x in lines))
        out.append(modern)
    return out


def render_card(card: A.Card, g, root: Path | None = None) -> list[BgFace]:
    from mtglang import planner
    plan = planner.plan_card(card, [planner.context_for(card, i, g) for i in range(len(card.faces))], g)
    return realize_card(plan, Lexicon(g, "bg"), root)


def render_card_bg(root: Path, ref: str) -> list[BgFace]:
    from mtglang.astexport import card_ast
    from mtglang.glossary import load_glossary
    card = card_ast(Path(root), ref)
    if card is None:
        raise FileNotFoundError(ref)
    return render_card(card, load_glossary(Path(root) / "glossary"), Path(root))


def load_sample(root: Path) -> list[str]:
    p = Path(root) / SAMPLE_FILE
    if not p.exists():
        return []
    return [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
