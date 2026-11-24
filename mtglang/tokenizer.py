"""Longest-match tokenizer driven by the glossary."""
from __future__ import annotations

import re
from dataclasses import dataclass

from mtglang.glossary import GRAMMAR_ROLES, Glossary, Symbol

FIXED = {"[": "LSQB", "]": "RSQB", "(": "LPAR", ")": "RPAR", ",": "COMMA", "/": "SLASH",
         "+": "PLUS", "-": "MINUS", "−": "MINUS", "—": "DASH"}
ASCII_PUNCT = {"−": "-", "—": "-"}
_MANA = re.compile(r"\{[^{}\s]+\}")
_NUMBER = re.compile(r"\d+")
_LETTERS = re.compile(r"[A-Za-z]+")


@dataclass(frozen=True)
class Tok:
    type: str
    value: str
    col: int
    symbol: Symbol | None = None
    text: str = ""          # exact source text of the token

    @property
    def end(self) -> int:   # 0-based exclusive end offset
        return self.col - 1 + len(self.text)


class TokenizeError(Exception):
    def __init__(self, col: int, message: str):
        super().__init__(f"col {col}: {message}")
        self.col = col
        self.message = message


class _Vocab:
    def __init__(self, g: Glossary):
        self.g = g
        strings = {s: g.lookup[s] for s in g.lookup}
        self.by_len = sorted(set(strings) | set(FIXED), key=len, reverse=True)
        self.delims = []  # (open, close, kind)
        for kind, o, c in (("NAME", "name_open", "name_close"), ("EFFECT", "effect_open", "effect_close")):
            so, sc = g.role(o), g.role(c)
            self.delims.append((so.glyph, sc.glyph, kind))
            if so.ascii != so.glyph:
                self.delims.append((so.ascii, sc.ascii, kind))
        self.delims.sort(key=lambda d: len(d[0]), reverse=True)
        self.delim_roles = {"name_open", "name_close", "effect_open", "effect_close"}

    def longest(self, text: str, pos: int) -> str | None:
        for s in self.by_len:
            if text.startswith(s, pos):
                return s
        return None


_VOCAB_CACHE: dict[int, _Vocab] = {}


def _vocab(g: Glossary) -> _Vocab:
    v = _VOCAB_CACHE.get(id(g))
    if v is None or v.g is not g:
        v = _VOCAB_CACHE[id(g)] = _Vocab(g)
    return v


def _segmentable(text: str, pos: int, run_len: int, v: _Vocab) -> bool:
    """Can the letter run at text[pos:pos+run_len] be covered by glossary codes / variables?

    Codes are matched against the full text, so an alias may extend past the letters (e.g. ``c.``).
    """
    i, end = pos, pos + run_len
    while i < end:
        s = v.longest(text, i)
        if s is None or not s[0].isalpha():
            if text[i] in "XYZ":
                i += 1
                continue
            return False
        i += len(s)
    return True


def tokenize(text: str, g: Glossary) -> list[Tok]:
    v = _vocab(g)
    toks: list[Tok] = []
    pos, n = 0, len(text)
    while pos < n:
        ch = text[pos]
        if ch.isspace():
            pos += 1
            continue
        col = pos + 1
        # natural-language word check at the start of each letter run
        if ch.isascii() and ch.isalpha() and (pos == 0 or not (text[pos - 1].isascii() and text[pos - 1].isalpha())):
            run = _LETTERS.match(text, pos).group()
            if len(run) >= 3 and not _segmentable(text, pos, len(run), v):
                raise TokenizeError(col, f"natural-language word {run!r} outside a name")
        # delimited names / effects
        matched = False
        for o, c, kind in v.delims:
            if text.startswith(o, pos):
                end = text.find(c, pos + len(o))
                if end == -1 or "\n" in text[pos:end]:
                    raise TokenizeError(col, f"unclosed {kind.lower()} delimiter {o!r}")
                inner = text[pos + len(o):end]
                toks.append(Tok(kind, inner, col, None, text[pos:end + len(c)]))
                pos = end + len(c)
                matched = True
                break
        if matched:
            continue
        m = _MANA.match(text, pos)
        if m:
            toks.append(Tok("MANA", m.group(), col, None, m.group()))
            pos = m.end()
            continue
        m = _NUMBER.match(text, pos)
        if m:
            toks.append(Tok("NUMBER", m.group(), col, None, m.group()))
            pos = m.end()
            continue
        s = v.longest(text, pos)
        if s is not None:
            if s in FIXED:
                toks.append(Tok(FIXED[s], s, col, None, s))
            else:
                sym = g.lookup[s]
                if sym.role in v.delim_roles:
                    raise TokenizeError(col, f"unmatched delimiter {s!r}")
                typ = sym.role.upper() if sym.role in GRAMMAR_ROLES else "SYMBOL"
                toks.append(Tok(typ, sym.glyph, col, sym, s))
            pos += len(s)
            continue
        if ch in "XYZ":
            toks.append(Tok("VAR", ch, col, None, ch))
            pos += 1
            continue
        raise TokenizeError(col, f"unknown symbol {ch!r}")
    return toks


def _ascii_of(t: Tok, g: Glossary) -> str:
    if t.symbol is not None:
        return t.symbol.ascii
    if t.type == "NAME":
        return g.role("name_open").ascii + t.value + g.role("name_close").ascii
    if t.type == "EFFECT":
        return g.role("effect_open").ascii + t.value + g.role("effect_close").ascii
    return ASCII_PUNCT.get(t.text, t.text)


def _key(t: Tok) -> tuple:
    """Identity of a token independent of glyph/ASCII spelling (— and − both count as '-')."""
    typ = "MINUS" if t.type == "DASH" else t.type
    return (typ, t.symbol.glyph if t.symbol else ASCII_PUNCT.get(t.value, t.value))


def ascii_pieces(text: str, g: Glossary) -> list[tuple[str, str, Tok | None]]:
    """(gap, ascii piece, token) triples of a line's ASCII form; the last triple carries the trailing text.

    Adjacent aliases that would merge into another symbol get a space."""
    toks = tokenize(text, g)
    out: list[tuple[str, str, Tok | None]] = []
    last = 0
    prev: Tok | None = None
    for t in toks:
        start = t.col - 1
        gap = text[last:start]
        piece = _ascii_of(t, g)
        if not gap and prev is not None:
            joined = _ascii_of(prev, g) + piece
            try:
                same = [_key(x) for x in tokenize(joined, g)] == [_key(prev), _key(t)]
            except TokenizeError:
                same = False
            if not same:
                gap = " "
        out.append((gap, piece, t))
        last = t.end
        prev = t
    out.append((text[last:], "", None))
    return out


def to_ascii(text: str, g: Glossary) -> str:
    """ASCII form of a line."""
    return "".join(gap + piece for gap, piece, _ in ascii_pieces(text, g))
