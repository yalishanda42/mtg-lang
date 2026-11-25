"""Print card ASTs as compact s-expressions: uv run python scripts/ast_sexpr.py fra/x [fra/y …]"""
import sys
from dataclasses import fields
from pathlib import Path

from mtglang import ast as A
from mtglang.astexport import card_ast

SKIP = {"paren", "count_after", "before", "neg_first", "glued", "prefix", "juxtaposed"}


def sx(n):
    if isinstance(n, A.SymRef):
        return n.glyph
    if isinstance(n, A.NameRef):
        return f"«{n.key}»"
    if isinstance(n, A.EffectRef):
        return f"⟨{n.key}⟩"
    if isinstance(n, A.Num):
        return f"{n.sign}{n.value}"
    if isinstance(n, A.Var):
        return f"{n.sign}{n.name}"
    if isinstance(n, A.Mana):
        return n.text
    if isinstance(n, tuple):
        if n and isinstance(n[0], tuple) and len(n[0]) == 2 and isinstance(n[0][0], str):
            return " ".join(f"{k}={sx(v)}" for k, v in n)
        return "[" + " ".join(sx(x) for x in n) + "]"
    if isinstance(n, A.Node):
        parts = []
        for f in fields(n):
            v = getattr(n, f.name)
            if f.name in SKIP or v in (None, (), False, ""):
                continue
            parts.append(f"{f.name}={sx(v)}")
        return f"({n.kind} " + " ".join(parts) + ")"
    return repr(n)


if __name__ == "__main__":
    for ref in sys.argv[1:]:
        c = card_ast(Path("."), ref)
        print("==", ref)
        for f in c.faces:
            for a in f.abilities:
                print("  ", sx(a))
