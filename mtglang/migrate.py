"""Scripted notation changes: apply a line rewrite to every ability line of every card file."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from mtglang.cardfile import parse_card_file, read_card_text
from mtglang.glossary import Glossary, load_glossary
from mtglang.lineparser import LineParser


def rewrite_lines(root: Path, fn: Callable[[str, Glossary], str]) -> int:
    """Call ``fn(line, glossary)`` on each ability line (headers, type/stat lines and comments are skipped)
    and write changed files back. Returns the number of lines changed."""
    root = Path(root)
    g = load_glossary(root / "glossary")
    lp = LineParser(g)
    changed = 0
    for path in sorted((root / "cards").glob("*/*.mtgl")):
        doc, _ = parse_card_file(path, lp)
        if doc is None:
            continue
        ability_lines = {a.lineno for f in doc.faces for a in f.abilities}
        text = read_card_text(path)
        lines = text.split("\n")
        dirty = False
        for k, line in enumerate(lines, start=1):
            if k not in ability_lines:
                continue
            indent = line[:len(line) - len(line.lstrip())]
            new = fn(line.strip(), g)
            if new != line.strip():
                lines[k - 1] = indent + new
                changed += 1
                dirty = True
        if dirty:
            path.write_text("\n".join(lines), encoding="utf-8")
    return changed


def sub_tokens(line: str, g: Glossary, pattern: str, repl: str) -> str:
    """Replace every token-identical occurrence of ``pattern`` (notation text) in ``line`` with ``repl``.

    Matching ignores spelling (glyph vs ASCII) and spacing; text outside the matches is kept verbatim."""
    from mtglang.tokenizer import _key, tokenize
    toks = tokenize(line, g)
    pat = [_key(t) for t in tokenize(pattern, g)]
    if not pat:
        return line
    keys = [_key(t) for t in toks]
    out, last, i = [], 0, 0
    while i <= len(toks) - len(pat):
        if keys[i:i + len(pat)] == pat:
            start = toks[i].col - 1
            end = toks[i + len(pat) - 1].end
            out.append(line[last:start] + repl)
            last = end
            i += len(pat)
        else:
            i += 1
    out.append(line[last:])
    return "".join(out)
