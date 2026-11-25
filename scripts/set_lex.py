"""Merge lex entries into glossary/symbols.yaml by glyph: uv run python scripts/set_lex.py lang file.yaml

file.yaml maps glyph → {key: word}; existing keys are overwritten, others kept. One flow line per entry."""
import sys

import yaml


def main(lang, src):
    want = yaml.safe_load(open(src, encoding="utf-8"))
    p = "glossary/symbols.yaml"
    lines = open(p, encoding="utf-8").read().split("\n")
    done = set()
    for i, l in enumerate(lines):
        if not l.startswith("- "):
            continue
        e = yaml.safe_load(l)[0]
        g = str(e["glyph"])
        if g in want:
            lex = dict(e.get("lex") or {})
            lex[lang] = dict(lex.get(lang) or {}, **want[g])
            e["lex"] = lex
            lines[i] = "- " + yaml.safe_dump(e, allow_unicode=True, sort_keys=False, default_flow_style=True,
                                             width=10_000).strip()
            done.add(g)
    open(p, "w", encoding="utf-8").write("\n".join(lines))
    missing = set(want) - done
    if missing:
        sys.exit(f"no such glyph(s): {' '.join(sorted(missing))}")


if __name__ == "__main__":
    main(*sys.argv[1:])
