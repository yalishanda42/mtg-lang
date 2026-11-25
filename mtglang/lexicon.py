"""Per-language words for glossary entries: the ``lex:`` maps of symbols and names."""
from __future__ import annotations

from mtglang.glossary import Glossary


class Lexicon:
    def __init__(self, g: Glossary, lang: str):
        self.g, self.lang = g, lang

    def sym(self, index: int) -> dict:
        return self.g.symbols[index].lex.get(self.lang, {})

    def name(self, key: str) -> dict:
        n = self.g.names.get(key)
        return n.lex.get(self.lang, {}) if n else {}

    def keyword(self, index: int) -> str:
        """A keyword's printed word: ``lex[lang].word``, else the glossary's ``oracle`` (English only)."""
        s = self.g.symbols[index]
        word = s.lex.get(self.lang, {}).get("word") or (s.oracle if self.lang == "en" else None)
        if not word:
            raise KeyError(f"no {self.lang} word for keyword {s.glyph!r}")
        return word
