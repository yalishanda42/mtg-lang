"""Parse single MTG-Lang lines (abilities, type lines) with Lark on top of the glossary tokenizer."""
from __future__ import annotations

from importlib.resources import files

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedEOF, UnexpectedInput, UnexpectedToken
from lark.lexer import Lexer

from mtglang.glossary import Glossary
from mtglang.tokenizer import TokenizeError, tokenize


class LineSyntaxError(Exception):
    def __init__(self, col: int, message: str):
        super().__init__(f"col {col}: {message}")
        self.col = col
        self.message = message


class _PassThroughLexer(Lexer):
    """Lark lexer that yields pre-built tokens (the 'text' handed to parse() is a token list)."""

    def __init__(self, lexer_conf):
        pass

    def lex(self, data):
        yield from data


_GRAMMAR = files("mtglang").joinpath("grammar.lark").read_text(encoding="utf-8")


class LineParser:
    def __init__(self, g: Glossary):
        self.g = g
        self._lark = Lark(_GRAMMAR, parser="earley", lexer=_PassThroughLexer,
                          start=["ability", "type_line"], ambiguity="resolve")

    def _parse(self, text: str, start: str) -> Tree:
        try:
            toks = tokenize(text, self.g)
        except TokenizeError as e:
            raise LineSyntaxError(e.col, e.message) from None
        lark_toks = [Token(t.type, t.value, start_pos=t.col - 1, line=1, column=t.col) for t in toks]
        try:
            return self._lark.parse(lark_toks, start=start)
        except UnexpectedEOF:
            raise LineSyntaxError(len(text) + 1, "line ends unexpectedly") from None
        except UnexpectedToken as e:
            if e.token.type == "$END":
                raise LineSyntaxError(len(text) + 1, "line ends unexpectedly") from None
            raise LineSyntaxError(e.token.column, f"unexpected {e.token.value!r}") from None
        except UnexpectedInput as e:
            raise LineSyntaxError(getattr(e, "column", 1) or 1, str(e).splitlines()[0]) from None

    def parse_ability(self, text: str) -> Tree:
        return self._parse(text, "ability")

    def parse_type_line(self, text: str) -> Tree:
        return self._parse(text, "type_line")
