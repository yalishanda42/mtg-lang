"""Print the clause plan of card abilities as indented text: uv run python scripts/plan_dump.py fra/x#0.1 [...]

Only the plan (no English) — the input a Bulgarian realizer would get. Glossary words are shown as
glyph + Bulgarian label."""
import sys
from dataclasses import fields, is_dataclass
from pathlib import Path

from mtglang import ast as A
from mtglang import planner
from mtglang.astexport import card_ast
from mtglang.glossary import load_glossary

G = load_glossary(Path("glossary"))
QUIET = {"path", "paren", "count_after", "before", "neg_first", "glued", "prefix", "juxtaposed"}


def word(n):
    if isinstance(n, A.SymRef):
        return f"{n.glyph} „{G.symbols[n.index].labels.get('bg', '?')}“"
    if isinstance(n, A.NameRef):
        nm = G.names.get(n.key)
        return f"«{n.key}» „{nm.labels.get('bg', '?') if nm else '?'}“"
    if isinstance(n, A.Num):
        return f"{n.sign}{n.value}"
    if isinstance(n, A.Var):
        return f"{n.sign}{n.name}"
    if isinstance(n, A.Mana):
        return n.text
    return None


def dump(n, ind=0, out=None, label=""):
    pad = "  " * ind
    w = word(n)
    if w is not None:
        out.append(f"{pad}{label}{w}")
        return
    if isinstance(n, tuple):
        if n and all(isinstance(x, tuple) and len(x) == 2 and isinstance(x[0], str) for x in n):
            for k, v in n:
                dump(v, ind, out, f"{k}: ")
        else:
            for x in n:
                dump(x, ind, out, label)
        return
    if isinstance(n, dict):
        for k, v in n.items():
            if v not in (None, (), {}):
                dump(v, ind, out, f"{k}: ")
        return
    if is_dataclass(n):
        simple, nested = [], []
        for f in fields(n):
            v = getattr(n, f.name)
            if f.name in QUIET or v in (None, (), False, "", {}):
                continue
            if f.name == "antecedent":
                nested.append((f.name, v))
            elif isinstance(v, (str, int, bool)) and not isinstance(v, A.Node):
                simple.append(f"{f.name}={v}")
            else:
                nested.append((f.name, v))
        out.append(f"{pad}{label}{type(n).__name__}" + (f" [{', '.join(simple)}]" if simple else ""))
        for k, v in nested:
            dump(v, ind + 1, out, f"{k}: ")
        return
    out.append(f"{pad}{label}{n!r}")


if __name__ == "__main__":
    for ref in sys.argv[1:]:
        card, pos = ref.split("#")
        fi, ai = (int(x) for x in pos.split("."))
        c = card_ast(Path("."), card)
        p = planner.plan_card(c, [planner.context_for(c, i, G) for i in range(len(c.faces))], G)
        # ai is a line number: a modal ability spans its "choose" line plus one line per mode
        node, line = None, 0
        for ab in p.faces[fi].abilities:
            modal = ab if getattr(ab, "shape", "") == "modal" else None
            if modal is None and getattr(ab, "shape", "") == "triggered":
                eff = ab.parts["effect"]
                last = eff.clauses[-1] if getattr(eff, "clauses", ()) else None
                modal = last if getattr(last, "shape", "") == "modal" else None
            span = 1 + (len(modal.parts["modes"]) if modal is not None else 0)
            if line <= ai < line + span:
                node = ab if ai == line else modal.parts["modes"][ai - line - 1]
                break
            line += span
        out = []
        dump(node, 0, out)
        print(f"== {ref}")
        print("\n".join(out))
