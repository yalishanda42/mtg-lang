"""AST → canonical MTG-Lang notation (glyph form). ``unparse(parse(x))`` is token-identical to ``x``."""
from __future__ import annotations

from mtglang import ast as A
from mtglang.glossary import Glossary


class Unparser:
    def __init__(self, g: Glossary):
        self.g = g

    def sym(self, s: A.SymRef) -> str:
        return self.g.symbols[s.index].glyph

    def node(self, n) -> str:
        meth = getattr(self, "u_" + type(n).__name__, None)
        if meth is None:
            raise TypeError(f"cannot unparse {type(n).__name__}")
        text = meth(n)
        return "(" * n.paren + text + ")" * n.paren

    def u_SymRef(self, n: A.SymRef) -> str:
        return self.sym(n)

    def u_NameRef(self, n: A.NameRef) -> str:
        return self.g.role("name_open").glyph + n.key + self.g.role("name_close").glyph

    def u_EffectRef(self, n: A.EffectRef) -> str:
        return self.g.role("effect_open").glyph + n.key + self.g.role("effect_close").glyph

    def u_Mana(self, n: A.Mana) -> str:
        return n.text

    def u_Num(self, n: A.Num) -> str:
        return f"{n.sign}{n.value}"

    def u_Var(self, n: A.Var) -> str:
        return f"{n.sign}{n.name}"


def unparse_ability(node: A.Node, g: Glossary) -> str:
    return Unparser(g).node(node)
