"""AST → canonical MTG-Lang notation (glyph form). ``unparse(parse(x))`` is token-identical to ``x``.

Spacing is canonical (phrases glued, clauses spaced); round-trip checks compare tokens, not spaces.
"""
from __future__ import annotations

from mtglang import ast as A
from mtglang.glossary import Glossary


class Unparser:
    def __init__(self, g: Glossary):
        self.g = g
        self.opg: dict[str, str] = {}
        for s in g.symbols:
            o = s.syntax.get("op")
            if o and o not in self.opg:
                self.opg[o] = s.glyph

    # ------------------------------------------------ helpers
    def sym(self, s: A.SymRef) -> str:
        return self.g.symbols[s.index].glyph

    def o(self, name: str) -> str:
        """Glyph of the symbol whose syntax op is ``name``."""
        try:
            return self.opg[name]
        except KeyError:
            raise TypeError(f"glossary has no symbol with syntax op {name!r}") from None

    def role(self, r: str) -> str:
        return self.g.role(r).glyph

    def node(self, n) -> str:
        if n is None:
            return ""
        meth = getattr(self, "u_" + type(n).__name__, None)
        if meth is None:
            raise TypeError(f"cannot unparse {type(n).__name__}")
        text = meth(n)
        return "(" * n.paren + text + ")" * n.paren

    def join(self, parts) -> str:
        return " ".join(p for p in parts if p)

    # ------------------------------------------------ leaves
    def u_SymRef(self, n):
        return self.sym(n)

    def u_NameRef(self, n):
        return self.role("name_open") + n.key + self.role("name_close")

    def u_EffectRef(self, n):
        return self.role("effect_open") + n.key + self.role("effect_close")

    def u_Mana(self, n):
        return n.text

    def u_Num(self, n):
        return f"{n.sign}{n.value}"

    def u_Var(self, n):
        return f"{n.sign}{n.name}"

    # ------------------------------------------------ phrases
    def u_NP(self, n: A.NP):
        out = "".join(self.sym(x) for x in n.pre)
        is_target = n.quant is not None and self.g.symbols[n.quant.index].syntax.get("op") == "target"
        if n.each is not None:
            out += self.sym(n.each)
        if n.quant is not None and not is_target:
            out += self.sym(n.quant)
        if n.neg:
            out += self.o("not")
        if n.count is not None and not n.count_after:
            out += self.node(n.count)
        if is_target:
            out += self.sym(n.quant)
        for k, h in enumerate(n.heads):
            out += self.node(h)
            if k == 0 and n.count_after and n.count is not None:
                out += self.node(n.count)
        for f in n.filters:
            out += self.node(f)
        if n.name is not None:
            out += " " + self.node(n.name)
        for p in n.post:
            out += self.node(p)
        return out

    def u_Bound(self, n):
        return self.sym(n.op) + self.node(n.value)

    def u_Of(self, n):
        mods = "".join(self.node(m) for m in n.mods)
        if n.prefix:
            return mods + self.sym(n.rel) + self.node(n.of)
        return self.node(n.of) + self.sym(n.rel)

    def u_Filter(self, n):
        return "[" + self.join(self.node(c) for c in n.conds) + "]"

    def u_Rel(self, n):
        return self.sym(n.rel) + self.node(n.other)

    def u_Zone(self, n):
        out = ""
        if n.pos_alt is not None:
            out += "(" + self.sym(n.pos) + " " + self.o("or") + " " + self.sym(n.pos_alt) + ")"
        elif n.pos is not None:
            out += self.sym(n.pos)
        out += self.sym(n.zone) if n.pos_alt is None or True else ""
        if n.count is not None:
            # count follows the position (⌃4▤) or a bare position (⌄1)
            if n.pos is not None and n.pos_alt is None:
                out = self.sym(n.pos) + self.node(n.count) + self.sym(n.zone)
            else:
                out = out + self.node(n.count)
        if n.owner is not None:
            out += self.node(n.owner)
        return out

    def u_Characteristic(self, n):
        if not n.prefix:
            return self.node(n.of) + self.sym(n.char)
        out = (self.sym(n.agg) if n.agg else "") + self.sym(n.char) + (self.sym(n.sub) if n.sub else "")
        if n.of is not None:
            out += (" " if n.agg is not None or n.sub is not None else "") + self.node(n.of)
        return out

    def u_Count(self, n):
        return self.o("count") + "".join(self.sym(m) for m in n.mods) + self.node(n.of)

    def u_Arith(self, n):
        o = {"×": self.o("times"), "÷": self.o("div"), "+": "+"}[n.op]
        return self.join([self.node(n.left), o, self.node(n.right)])

    def u_PT(self, n):
        return (self.sym(n.base) if n.base else "") + self.node(n.power) + "/" + self.node(n.toughness)

    def u_Time(self, n):
        return "".join(self.node(i) for i in n.items)

    def u_Or(self, n):
        return (" " + self.o("or") + " ").join(self.node(i) for i in n.items)

    def u_And(self, n):
        if n.juxtaposed:
            return " ".join(self.node(i) for i in n.items)
        return (" " + self.o("and") + " ").join(self.node(i) for i in n.items)


    def u_Not(self, n):
        return self.o("not") + self.node(n.item)

    def u_Compare(self, n):
        parts = [self.node(n.items[0])]
        for o, it in zip(n.ops, n.items[1:]):
            parts += [self.sym(o), self.node(it)]
        return self.join(parts)

    def u_Keyword(self, n):
        return self.sym(n.sym) + "".join(self.node(p) for p in n.params)

    def u_CostList(self, n):
        return ", ".join(self.node(i) for i in n.items)

    # ------------------------------------------------ sentences
    def arg(self, slot: str, node) -> str:
        if slot.startswith("arrow:") or slot in ("times", "restrict"):
            return self.sym(node.rel) + " " + self.node(node.other)
        if slot == "restrict_not":
            return self.o("not") + self.sym(node.rel) + " " + self.node(node.other)
        return self.node(node)

    def u_Action(self, n: A.Action):
        parts = []
        if n.negated and n.neg_first:
            parts.append(self.o("not"))
        parts.append(self.node(n.subject))
        if n.optional:
            parts.append(self.o("may"))
        parts += [self.arg(s, x) for s, x in n.args[:n.before]]
        verb = self.node(n.verb) if n.verb is not None else ""
        if n.negated and not n.neg_first and n.verb is None:
            parts.insert(1 if n.subject is not None else 0, self.o("not"))
        elif n.negated and not n.neg_first:
            verb = self.o("not") + verb
        if n.passive:
            verb += self.o("passive")
        parts.append(verb)
        parts += [self.arg(s, x) for s, x in n.args[n.before:]]
        return self.join(parts)

    def u_Modify(self, n: A.Modify):
        parts = [self.node(n.subject)]
        if n.optional:
            parts.append(self.o("may"))
        ch = self.node(n.change)
        if n.negated:
            ch = self.o("not") + ch
        parts.append(ch)
        parts += [self.arg(s, x) for s, x in n.args]
        return self.join(parts)

    def u_Delta(self, n: A.Delta):
        out = (self.sym(n.char) if n.char else "") + n.sign + (self.node(n.amount) if n.amount else "")
        if n.times is not None:
            out += " " + self.o("times") + " " + self.node(n.times)
        return out

    def u_Scoped(self, n: A.Scoped):
        parts = [self.node(n.subject)]
        if n.optional:
            parts.append(self.o("may"))
        if n.negated:
            parts.append(self.o("not"))
        parts.append(self.node(n.body))
        return self.join(parts)

    def u_Coord(self, n):
        return (" " + self.sym(n.op) + " ").join(self.node(i) for i in n.items)

    def u_Conditional(self, n: A.Conditional):
        if_ = self.o("if")
        if n.mode == "unless":
            return self.join([self.node(n.then), self.o("not") + if_, self.node(n.cond)])
        if n.mode == "if_do":
            return self.join([self.o("did"), if_, self.node(n.then)])
        if n.mode == "if_dont":
            return self.join([self.o("didnt"), if_, self.node(n.then)])
        return self.join([self.node(n.cond), if_, self.node(n.then)])

    def u_Replace(self, n):
        return self.join([self.node(n.event), self.o("replace"), self.node(n.effect)])

    def u_While(self, n):
        return self.join([self.node(n.body), self.sym(n.op), self.node(n.cond)])

    def u_Until(self, n):
        return self.join([self.node(n.body), self.o("until") + self.node(n.until)])

    def u_Timed(self, n):
        return self.join([self.node(n.body), self.node(n.time)])

    def u_Bind(self, n):
        return self.join([self.node(n.var), self.o("bind"), self.node(n.value)])

    def u_ForEach(self, n):
        return self.join(["(" + self.node(n.over) + ")", self.node(n.body)])

    def u_Nested(self, n):
        return self.node(n.ability)

    def u_Effects(self, n):
        parts = [self.node(s) for s in n.sentences]
        return parts[0] if len(parts) == 1 else (" " + self.o("then") + " ").join(parts)

    # ------------------------------------------------ abilities
    def u_Keywords(self, n):
        return ", ".join(self.node(k) for k in n.items)

    def u_Triggered(self, n: A.Triggered):
        parts = [self.node(n.event)]
        for c in n.conds:
            parts += [self.o("and"), self.node(c)]
        if n.while_ is not None:
            parts += [self.o("while"), self.node(n.while_)]
        parts += [self.role("implies"), self.node(n.effect)]
        return self.join(parts)

    def u_Activated(self, n: A.Activated):
        eff = self.node(n.effect)
        for lim in n.limits:
            eff += " " + self.o("then") + " " + self.node(lim)
        return self.join([", ".join(self._cost(c) for c in n.cost), self.role("cost_sep"), eff])

    def _cost(self, c) -> str:
        """Loyalty costs are written with the minus sign −."""
        if isinstance(c, (A.Num, A.Var)) and c.sign == "-":
            return "−" + (str(c.value) if isinstance(c, A.Num) else c.name)
        return self.node(c)

    def u_Static(self, n):
        return self.node(n.body)

    def u_Labelled(self, n):
        return self.join([self.join(self.node(x) for x in n.label), self.role("label_sep"), self.node(n.ability)])

    def u_Chapter(self, n):
        return self.join([self.role("chapter") + ",".join(str(x) for x in n.numbers), self.role("label_sep"),
                          self.node(n.ability)])

    def u_Threshold(self, n):
        return self.join([f"{n.n}+", self.role("threshold_sep"), self.node(n.ability)])

    def u_Mode(self, n):
        return self.join([self.role("mode_bullet"), self.node(n.ability)])

    # ------------------------------------------------ card
    def u_TypeLine(self, n: A.TypeLine):
        left = self.join(self.node(t) for t in n.types)
        if n.dash is None:
            return left
        return self.join([left, n.dash, self.join(self.node(t) for t in n.subtypes)])

    def u_Stats(self, n: A.Stats):
        if n.stat == "pt":
            return f"{n.power}/{n.toughness}"
        return self.sym(n.sym) + n.value

    def face_lines(self, f: A.Face) -> list[str]:
        lines = [self.join([self.node(f.name), "".join(self.node(c) for c in f.cost)]), self.node(f.types)]
        if f.stats is not None:
            lines.append(self.node(f.stats))
        for ab in f.abilities:
            lines += self.ability_lines(ab)
        return lines

    def ability_lines(self, ab) -> list[str]:
        """A Modal (inside any wrapper) spans several lines: the ⊻n line, then one • line per mode."""
        modal = _find_modal(ab)
        if modal is None:
            return [self.node(ab)]
        head = self.node(_replace_modal(ab, modal.choose))
        return [head] + [self.node(m) for m in modal.modes]


def _find_modal(n):
    import dataclasses
    if isinstance(n, A.Modal):
        return n
    if not isinstance(n, A.Node) or isinstance(n, (A.NP, A.Filter)):
        return None
    for f in dataclasses.fields(n):
        v = getattr(n, f.name)
        if isinstance(v, A.Node):
            m = _find_modal(v)
            if m is not None:
                return m
        elif isinstance(v, tuple):
            for x in v:
                if isinstance(x, A.Node):
                    m = _find_modal(x)
                    if m is not None:
                        return m
    return None


def _replace_modal(n, by):
    import dataclasses
    if isinstance(n, A.Modal):
        return by
    if not isinstance(n, A.Node):
        return n
    changes = {}
    for f in dataclasses.fields(n):
        v = getattr(n, f.name)
        if isinstance(v, A.Node):
            nv = _replace_modal(v, by)
            if nv is not v:
                changes[f.name] = nv
        elif isinstance(v, tuple) and any(isinstance(x, A.Node) for x in v):
            nv = tuple(_replace_modal(x, by) for x in v)
            if nv != v:
                changes[f.name] = nv
    return dataclasses.replace(n, **changes) if changes else n


def unparse_ability(node: A.Node, g: Glossary) -> str:
    return Unparser(g).node(node)


def unparse_card(card: A.Card, g: Glossary) -> str:
    u = Unparser(g)
    faces = ["\n".join(u.face_lines(f)) for f in card.faces]
    return "\n//\n".join(faces) + "\n"
