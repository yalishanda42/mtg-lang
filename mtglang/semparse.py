"""Semantic parser: MTG-Lang line → typed AST (``mtglang.ast``).

Hand-written precedence parser over the glossary tokenizer. Symbol behaviour comes from each glossary
symbol's ``syntax`` (``kind``, ``op``, verb ``args`` frame); the only glyphs it knows are the structural
roles (via ``Glossary.role``) and Magic's fixed punctuation. Whitespace is never significant.

Precedence, loosest first (one sentence):
    ;   ⊃ / ¬⊃ / ✓⊃ / ✗⊃   ⤳   ∵   ≈   ⊣   ∨   ∧   clause
"""
from __future__ import annotations

from dataclasses import replace

from mtglang import ast as A
from mtglang.glossary import Glossary
from mtglang.tokenizer import Tok, TokenizeError, tokenize

OPEN = {"LSQB": "RSQB", "LPAR": "RPAR"}
VALUE_TYPES = (A.Num, A.Var, A.Count, A.Arith, A.Characteristic, A.Bound)


class SemSyntaxError(Exception):
    def __init__(self, col: int, message: str):
        super().__init__(f"col {col}: {message}")
        self.col = col
        self.message = message


# ---------------------------------------------------------------- token helpers

def kind(t: Tok | None) -> str | None:
    if t is None:
        return None
    if t.symbol is not None and t.type == "SYMBOL":
        return t.symbol.syntax.get("kind")
    return t.type


def op(t: Tok | None) -> str | None:
    if t is None or t.symbol is None:
        return None
    return t.symbol.syntax.get("op")


def is_value(n) -> bool:
    return isinstance(n, VALUE_TYPES)


def _close(toks: list[Tok], i: int) -> int:
    """Index of the bracket closing toks[i]; raises if unmatched."""
    want = OPEN[toks[i].type]
    depth = 0
    for j in range(i, len(toks)):
        if toks[j].type in OPEN:
            depth += 1
        elif toks[j].type in ("RSQB", "RPAR"):
            depth -= 1
            if depth == 0:
                if toks[j].type != want:
                    raise SemSyntaxError(toks[j].col, f"mismatched {toks[j].text!r}")
                return j
    raise SemSyntaxError(-1, "line ends unexpectedly")


def split_top(toks: list[Tok], pred) -> list[int]:
    """Indices of tokens at bracket depth 0 matching pred."""
    out, depth = [], 0
    for i, t in enumerate(toks):
        if t.type in OPEN:
            depth += 1
        elif t.type in ("RSQB", "RPAR"):
            depth -= 1
        elif depth == 0 and pred(t):
            out.append(i)
    return out


def split_by(toks: list[Tok], idx: list[int]) -> list[list[Tok]]:
    parts, last = [], 0
    for i in idx:
        parts.append(toks[last:i])
        last = i + 1
    parts.append(toks[last:])
    return parts


class _S:
    """Cursor over a token list."""

    def __init__(self, toks: list[Tok], end_col: int):
        self.toks = toks
        self.pos = 0
        self.end_col = end_col

    def peek(self, k: int = 0) -> Tok | None:
        i = self.pos + k
        return self.toks[i] if 0 <= i < len(self.toks) else None

    def next(self) -> Tok:
        t = self.peek()
        if t is None:
            raise SemSyntaxError(self.end_col, "line ends unexpectedly")
        self.pos += 1
        return t

    @property
    def eof(self) -> bool:
        return self.pos >= len(self.toks)

    def col(self) -> int:
        t = self.peek()
        return t.col if t else self.end_col

    def group(self) -> list[Tok]:
        """Consume a bracketed group starting at the cursor; return the inner tokens."""
        try:
            j = _close(self.toks, self.pos)
        except SemSyntaxError as e:
            raise SemSyntaxError(self.end_col if e.col == -1 else e.col, e.message) from None
        inner = self.toks[self.pos + 1:j]
        self.pos = j + 1
        return inner


# ---------------------------------------------------------------- parser

class SemParser:
    def __init__(self, g: Glossary):
        self.g = g
        self._end = 1

    # ------------------------------------------------ entry points
    def _toks(self, text: str) -> list[Tok]:
        try:
            toks = tokenize(text, self.g)
        except TokenizeError as e:
            raise SemSyntaxError(e.col, e.message) from None
        self._end = len(text) + 1
        return toks

    def _s(self, toks: list[Tok]) -> _S:
        return _S(toks, self._end_of(toks))

    def _end_of(self, toks: list[Tok]) -> int:
        return self._end

    def sym(self, t: Tok) -> A.SymRef:
        return A.SymRef(self.g.index(t.symbol), t.symbol.glyph)

    def parse_phrase(self, text: str) -> A.Node:
        s = self._s(self._toks(text))
        node = self.p_operand(s)
        if node is None:
            raise SemSyntaxError(s.col(), f"expected a phrase, got {s.peek().text!r}" if s.peek() else "empty")
        if not s.eof:
            raise SemSyntaxError(s.col(), f"unexpected {s.peek().text!r}")
        return node

    def parse_effects(self, text: str) -> A.Effects:
        return self.p_effects(self._toks(text))

    def parse_ability(self, text: str) -> A.Node:
        toks = self._toks(text)
        if not toks:
            raise SemSyntaxError(1, "empty line")
        return self.p_ability(toks)

    def parse_type_line(self, text: str) -> A.TypeLine:
        toks = self._toks(text)
        types, subs, dash = [], [], None
        for t in toks:
            if t.type in ("DASH", "MINUS"):
                if dash is not None:
                    raise SemSyntaxError(t.col, "second dash in type line")
                dash = t.text
            elif t.type == "NAME" and dash is not None:
                subs.append(A.NameRef(t.value))
            elif t.type == "SYMBOL" and dash is None:
                types.append(self.sym(t))
            elif t.type == "NAME":
                types.append(A.NameRef(t.value))
            else:
                raise SemSyntaxError(t.col, f"unexpected {t.text!r} in type line")
        return A.TypeLine(tuple(types), tuple(subs), dash)

    def parse_stats(self, text: str) -> A.Stats:
        toks = self._toks(text)
        if toks and toks[0].symbol is not None and toks[0].symbol.role in ("loyalty", "defense"):
            if len(toks) != 2 or toks[1].type != "NUMBER":
                raise SemSyntaxError(toks[0].col, "expected a number after the stat symbol")
            return A.Stats(toks[0].symbol.role, value=toks[1].value, sym=self.sym(toks[0]))
        p, _, q = text.replace(" ", "").partition("/")
        if not p or not q:
            raise SemSyntaxError(1, "expected power/toughness")
        return A.Stats("pt", power=p, toughness=q)

    # ------------------------------------------------ abilities
    def p_ability(self, toks: list[Tok]) -> A.Node:
        t0 = toks[0]
        if t0.type == "MODE_BULLET":
            if len(toks) == 1:
                raise SemSyntaxError(self._end, "empty mode")
            return A.Mode(self.p_ability(toks[1:]))
        if t0.type == "CHAPTER":
            seps = split_top(toks, lambda t: t.type == "LABEL_SEP")
            if not seps:
                raise SemSyntaxError(t0.col, "chapter needs ▸")
            nums = [int(t.value) for t in toks[1:seps[0]] if t.type == "NUMBER"]
            if not nums:
                raise SemSyntaxError(t0.col, "chapter needs a number")
            return A.Chapter(tuple(nums), self.p_body(toks[seps[0] + 1:]))
        if len(toks) > 3 and t0.type == "NUMBER" and toks[1].type == "PLUS" and toks[2].type == "THRESHOLD_SEP":
            return A.Threshold(int(t0.value), self.p_ability(toks[3:]))
        seps = split_top(toks, lambda t: t.type == "LABEL_SEP")
        if seps:
            label = []
            for t in toks[:seps[0]]:
                if t.type == "NAME":
                    label.append(A.NameRef(t.value))
                elif t.symbol is not None:
                    label.append(self.sym(t))
                else:
                    raise SemSyntaxError(t.col, f"unexpected {t.text!r} in label")
            if not label:
                raise SemSyntaxError(toks[seps[0]].col, "empty label")
            return A.Labelled(tuple(label), self.p_body(toks[seps[0] + 1:]))
        return self.p_body(toks)

    def p_body(self, toks: list[Tok]) -> A.Node:
        if not toks:
            raise SemSyntaxError(self._end, "empty ability")
        seps = split_top(toks, lambda t: t.type in ("IMPLIES", "COST_SEP"))
        if seps:
            i = seps[0]
            left, right = toks[:i], toks[i + 1:]
            if not left:
                raise SemSyntaxError(toks[i].col, f"nothing before {toks[i].text!r}")
            if not right:
                raise SemSyntaxError(self._end, "line ends unexpectedly")
            if toks[i].type == "IMPLIES":
                return self._triggered(left, right)
            return self._activated(left, right)
        eff = self.p_effects(toks)
        if len(eff.sentences) == 1 and isinstance(eff.sentences[0], A.Keywords):
            return eff.sentences[0]
        return A.Static(eff)

    def _triggered(self, left, right) -> A.Triggered:
        ev = self.p_sentence(left)
        while_ = None
        conds: tuple = ()
        if isinstance(ev, A.While) and not ev.paren and self.g.symbols[ev.op.index].syntax.get("op") == "while":
            ev, while_ = ev.body, ev.cond
        if isinstance(ev, A.Coord) and not ev.paren and self._op(ev.op) == "and":
            ev, conds = ev.items[0], ev.items[1:]
        return A.Triggered(ev, self.p_effects(right), conds, while_)

    def _activated(self, left, right) -> A.Activated:
        costs = tuple(self.p_cost_item(part, left) for part in split_by(left, split_top(left, lambda t: t.type == "COMMA")))
        eff = self.p_effects(right)
        sents = list(eff.sentences)
        limits = []
        while len(sents) > 1 and self._is_limit(sents[-1]):
            limits.insert(0, sents.pop())
        return A.Activated(costs, replace(eff, sentences=tuple(sents)), tuple(limits))

    def _op(self, s: A.SymRef) -> str | None:
        return self.g.symbols[s.index].syntax.get("op")

    def _is_limit(self, n) -> bool:
        if isinstance(n, A.Action) and isinstance(n.verb, A.SymRef) and self._op(n.verb) == "only" and n.subject is None:
            return True
        return isinstance(n, A.Coord) and not n.paren and all(self._is_limit(x) for x in n.items)

    def p_cost_item(self, toks: list[Tok], whole: list[Tok]) -> A.Node:
        if not toks:
            raise SemSyntaxError(whole[0].col if whole else self._end, "empty cost")
        if all(t.type == "MANA" for t in toks):
            return A.Mana("".join(t.value for t in toks))
        if len(toks) <= 2 and toks[-1].type in ("NUMBER", "VAR") and (len(toks) == 1 or toks[0].type in ("PLUS", "MINUS")):
            sign = toks[0].text if len(toks) == 2 else ""
            last = toks[-1]
            return A.Num(int(last.value), sign) if last.type == "NUMBER" else A.Var(last.value, sign)
        return self.p_sentence(toks)

    # ------------------------------------------------ sentences
    def p_effects(self, toks: list[Tok]) -> A.Effects:
        idx = split_top(toks, lambda t: op(t) == "then")
        parts = split_by(toks, idx)
        for k, part in enumerate(parts):
            if not part:
                col = toks[idx[k - 1]].col if k else (toks[idx[0]].col if idx else self._end)
                raise SemSyntaxError(col if k < len(parts) - 1 or not idx else self._end, "empty sentence")
        return A.Effects(tuple(self.p_sentence(p) for p in parts))

    def p_sentence(self, toks: list[Tok]) -> A.Node:
        if not toks:
            raise SemSyntaxError(self._end, "empty sentence")
        # keyword list
        kw = self._try_keywords(toks)
        if kw is not None:
            return kw
        # X ≔ value
        if len(toks) > 2 and toks[0].type == "VAR" and op(toks[1]) == "bind":
            return A.Bind(A.Var(toks[0].value), self.p_clause(toks[2:]))
        # C ⊃ X / X ¬⊃ C / ✓ ⊃ X / ✗ ⊃ X
        idx = split_top(toks, lambda t: op(t) == "if")
        if idx:
            i = idx[0]
            left, right = toks[:i], toks[i + 1:]
            if not right:
                raise SemSyntaxError(self._end, "line ends unexpectedly")
            if left and op(left[-1]) == "not":
                if len(left) == 1:
                    raise SemSyntaxError(toks[i].col, "nothing before ¬⊃")
                return A.Conditional("unless", self.p_sentence(right), self.p_sentence(left[:-1]))
            if len(left) == 1 and op(left[0]) in ("did", "didnt"):
                return A.Conditional("if_do" if op(left[0]) == "did" else "if_dont", None, self.p_sentence(right))
            if not left:
                raise SemSyntaxError(toks[i].col, "condition missing before ⊃")
            return A.Conditional("if", self.p_sentence(left), self.p_sentence(right))
        idx = split_top(toks, lambda t: op(t) == "replace")
        if idx:
            i = idx[0]
            left, right = toks[:i], toks[i + 1:]
            if not right:
                raise SemSyntaxError(self._end, "line ends unexpectedly")
            return A.Replace(self.p_sentence(left) if left else None, self.p_sentence(right))
        for name in ("while", "as_though"):
            idx = split_top(toks, lambda t, n=name: op(t) == n)
            if idx:
                i = idx[0]
                if i == 0 or i == len(toks) - 1:
                    raise SemSyntaxError(toks[i].col, f"{toks[i].text!r} needs two sides")
                return A.While(self.sym(toks[i]), self.p_sentence(toks[:i]), self.p_sentence(toks[i + 1:]))
        idx = split_top(toks, lambda t: op(t) == "until")
        if idx:
            i = idx[0]
            if i == 0 or i == len(toks) - 1:
                raise SemSyntaxError(toks[i].col, "⊣ needs two sides")
            right = toks[i + 1:]
            s = self._s(right)
            t = self.p_time(s) if self._time_start(s) else None
            until = t if t is not None and s.eof else self.p_sentence(right)
            return A.Until(self.p_sentence(toks[:i]), until)
        return self.p_coord(toks)

    def p_coord(self, toks: list[Tok]) -> A.Node:
        for name in ("or", "and"):
            idx = split_top(toks, lambda t, n=name: op(t) == n)
            if not idx:
                continue
            parts = split_by(toks, idx)
            segs: list[list[Tok]] = []
            for k, part in enumerate(parts):
                if k and segs and not self._is_predicate(part):
                    segs[-1] = segs[-1] + [toks[idx[k - 1]]] + part
                else:
                    segs.append(part)
            if len(segs) > 1:
                return A.Coord(self.sym(toks[idx[0]]), tuple(self.p_coord(sg) for sg in segs))
        return self.p_clause(toks)

    def _is_predicate(self, toks: list[Tok]) -> bool:
        if not toks:
            return False
        try:
            n = self.p_sentence(toks)
        except SemSyntaxError:
            return False
        return self._predicate_node(n)

    def _predicate_node(self, n) -> bool:
        if isinstance(n, A.Not):
            return self._predicate_node(n.item) or isinstance(n.item, A.NP)
        if isinstance(n, A.NP):
            return n.quant is not None and self._op(n.quant) == "exists"
        if isinstance(n, A.Time):
            return bool(n.items) and isinstance(n.items[0], A.SymRef) and self._op(n.items[0]) == "begin"
        return isinstance(n, (A.Action, A.Modify, A.Compare, A.Scoped, A.Nested, A.Coord, A.Conditional,
                              A.Replace, A.While, A.Until, A.Bind, A.ForEach, A.Keywords, A.Timed))

    def _try_keywords(self, toks: list[Tok]) -> A.Keywords | None:
        if kind(toks[0]) != "keyword":
            return None
        items = []
        for part in split_by(toks, split_top(toks, lambda t: t.type == "COMMA")):
            if not part or kind(part[0]) != "keyword":
                return None
            s = self._s(part)
            try:
                k = self.p_keyword(s, line=True)
            except SemSyntaxError:
                return None
            if not s.eof:
                return None
            items.append(k)
        return A.Keywords(tuple(items))

    def p_keyword(self, s: _S, line: bool) -> A.Keyword:
        t = s.next()
        params = []
        while not s.eof:
            n = s.peek()
            if n.type == "MANA":
                params.append(self._mana(s))
            elif n.type in ("NUMBER", "VAR") and not self._pt_ahead(s):
                params.append(self._numvar(s))
            elif n.type == "LSQB":
                params.append(self.p_filter(s))
            elif kind(n) == "characteristic":
                params.append(self.sym(s.next()))
            elif line and n.type == "LPAR":
                save = s.pos
                np = self.p_np(s)
                if np is not None:
                    params.append(np)
                    continue
                s.pos = save
                inner = s.group()
                parts = split_by(inner, split_top(inner, lambda t: t.type == "COMMA"))
                params.append(A.CostList(tuple(self.p_cost_item(p, inner) for p in parts), paren=1))
            elif line and kind(n) in ("type", "object"):
                np = self.p_np(s)
                if np is None:
                    break
                params.append(np)
            else:
                break
        return A.Keyword(self.sym(t), tuple(params))

    # ------------------------------------------------ clauses
    def p_clause(self, toks: list[Tok]) -> A.Node:
        chunks = self.p_chunks(self._s(toks), "clause")
        return self.assemble(chunks, toks)

    def p_chunks(self, s: _S, mode: str) -> list[tuple]:
        """Chunks: (type, node, col). Types: may not and or times restrict passive marker verb arrow kw
        filter group foreach pt delta plus rel time zone np value mana."""
        out: list[tuple] = []
        while not s.eof:
            t = s.peek()
            c = t.col
            o, kd = op(t), kind(t)
            if o == "may":
                s.next(); out.append(("may", self.sym(t), c))
            elif o == "not":
                s.next(); out.append(("not", self.sym(t), c))
            elif o in ("and", "or"):
                s.next(); out.append((o, self.sym(t), c))
            elif o == "times":
                s.next()
                v = self.p_value(s)
                if v is None:
                    raise SemSyntaxError(s.col(), "expected a number after ×")
                out.append(("times", (self.sym(t), v), c))
            elif o == "restrict":
                s.next()
                rest = s.toks[s.pos:]
                if not rest:
                    raise SemSyntaxError(self._end, "line ends unexpectedly")
                s.pos = len(s.toks)
                out.append(("restrict", (self.sym(t), self.p_sentence(rest)), c))
            elif o == "passive":
                s.next(); out.append(("passive", self.sym(t), c))
            elif kd == "marker":
                s.next(); out.append(("marker", self.sym(t), c))
            elif o == "transfer":
                s.next(); out.append(("arrow", self.sym(t), c))
            elif kd == "verb" or o == "bind":
                s.next(); out.append(("verb", self.sym(t), c))
            elif t.type == "EFFECT":
                s.next(); out.append(("verb", A.EffectRef(t.value), c))
            elif kd == "keyword":
                nxt = s.peek(1)
                if op(nxt) == "passive":
                    s.next(); out.append(("verb", self.sym(t), c))
                else:
                    out.append(("kw", self.p_keyword(s, line=False), c))
            elif t.type == "LSQB":
                out.append(("filter", self.p_filter(s), c))
            elif t.type == "LPAR" and self._verb_group(s):
                inner = s.group()
                out.append(("verb", A.Or(tuple(self.sym(x) for x in inner if op(x) != "or"), paren=1), c))
            elif t.type == "LPAR":
                out.append(self._group_chunk(s, mode, not out))
            elif self._pt_ahead(s):
                out.append(("pt", self.p_pt(s), c))
            elif o == "life" and kind(s.peek(1)) not in ("player", "reference", "quantifier"):
                out.append(("delta", self.p_delta(s), c))
            elif t.type == "PLUS" and s.peek(1) is not None and s.peek(1).type in ("NUMBER", "VAR"):
                s.next()
                n = s.next()
                out.append(("plus", A.Num(int(n.value), "+") if n.type == "NUMBER" else A.Var(n.value, "+"), c))
            elif op(t) in ("next", "last") and kind(s.peek(1)) == "relation":
                m = self.sym(s.next())
                r = s.next()
                other = self._rel_other(s)
                out.append(("np", A.Of(self.sym(r), other, prefix=True, mods=(m,)), c))
            elif kd == "relation":
                s.next()
                other = self._rel_other(s)
                out.append(("rel", A.Rel(self.sym(t), other), c))
            elif o == "other" and self._np_start(s, 1):
                s.next()
                np = self.p_np(s)
                if np is None:
                    raise SemSyntaxError(c, "expected a phrase after ≠")
                out.append(("rel", A.Rel(self.sym(t), self._postfix(s, np, chars=False)), c))
            elif self._time_start(s):
                out.append(("time", self.p_time(s), c))
            elif self._zone_start(s):
                out.append(("zone", self.p_zone(s), c))
            else:
                n = self.p_value(s)
                if n is None:
                    raise SemSyntaxError(c, f"unexpected {t.text!r}")
                typ = "mana" if isinstance(n, A.Mana) else "value" if self.isval(n) else "np"
                out.append((typ, n, c))
        return out

    def _verb_group(self, s: _S) -> bool:
        """(⊶ ∨ ⌕) — alternative verbs, not followed by a filter."""
        try:
            e = _close(s.toks, s.pos)
        except SemSyntaxError:
            return False
        inner = s.toks[s.pos + 1:e]
        if len(inner) < 3 or any(kind(x) != "verb" for x in inner[::2]) or any(op(x) != "or" for x in inner[1::2]):
            return False
        nxt = s.toks[e + 1] if e + 1 < len(s.toks) else None
        return nxt is None or nxt.type != "LSQB"

    def _rel_other(self, s: _S):
        n = s.peek()
        if n is None:
            return None
        if kind(n) == "relation":
            return self.sym(s.next())
        if self._time_start(s) or self._zone_start(s):
            return self.p_operand(s)
        if self._np_start(s, 0):
            save = s.pos
            np = self.p_np(s)
            if np is not None:
                return self._postfix(s, np, chars=False)
            s.pos = save
            return self.p_operand(s)
        return None

    def _group_chunk(self, s: _S, mode: str, first: bool) -> tuple:
        c = s.col()
        save = s.pos
        node = self.p_operand(s)
        if node is not None:
            typ = "mana" if isinstance(node, A.Mana) else "value" if self.isval(node) else "np"
            return (typ, node, c)
        s.pos = save
        inner = s.group()
        if not inner:
            raise SemSyntaxError(c, "empty parentheses")
        if split_top(inner, lambda t: t.type in ("IMPLIES", "COST_SEP")):
            return ("group", A.Nested(self.p_body(inner), paren=1), c)
        if mode == "filter":
            alts = []
            for part in split_by(inner, split_top(inner, lambda t: op(t) == "or")):
                if not part:
                    raise SemSyntaxError(c, "empty alternative")
                conds = self._conds(part)
                alts.append(conds[0] if len(conds) == 1 else A.And(tuple(conds), juxtaposed=True))
            node = A.Or(tuple(alts), paren=1) if len(alts) > 1 else replace(alts[0], paren=alts[0].paren + 1)
            return ("group", node, c)
        alts = split_by(inner, split_top(inner, lambda t: op(t) == "or"))
        if len(alts) > 1 and all(len(a) == 1 and kind(a[0]) == "keyword" for a in alts):
            return ("kw", A.Or(tuple(A.Keyword(self.sym(a[0])) for a in alts), paren=1), c)
        if first and mode == "clause" and not s.eof:
            s2 = self._s(inner)
            np = self.p_np(s2)
            if np is not None and s2.eof and np.quant is not None and self._op(np.quant) == "each":
                return ("foreach", np, c)
        node = self.p_sentence(inner)
        return ("group", replace(node, paren=node.paren + 1), c)

    # ------------------------------------------------ assembly
    def assemble(self, chunks: list[tuple], toks: list[Tok]) -> A.Node:
        if not chunks:
            raise SemSyntaxError(toks[0].col if toks else self._end, "empty clause")
        chunks = self._combine(chunks)
        if chunks[0][0] == "foreach":
            if len(chunks) == 1:
                raise SemSyntaxError(chunks[0][2], "nothing after (∀…)")
            return A.ForEach(chunks[0][1], self.assemble(chunks[1:], toks))
        # ◎← : "be the target of"
        for i, ch in enumerate(chunks[:-1]):
            if ch[0] == "np" and isinstance(ch[1], A.NP) and ch[1].quant is not None and not ch[1].heads \
                    and not ch[1].filters and chunks[i + 1][0] == "passive":
                chunks[i] = ("verb", ch[1].quant, ch[2])
        # noun use of a verb / keyword before the main verb: ⊳ ⊖{X}, ⚒ ⊖{1}
        if len(chunks) > 1 and chunks[0][0] in ("verb", "kw") and chunks[1][0] == "verb" and \
                "cost" in self._frame(chunks[1][1], False) and \
                not (chunks[0][0] == "verb" and "cost" in self._frame(chunks[0][1], False)):
            n = chunks[0][1]
            chunks[0] = ("np", A.NP(heads=(n.sym if isinstance(n, A.Keyword) else n,)), chunks[0][2])
        m = next((i for i, ch in enumerate(chunks) if ch[0] == "verb"), None)
        a = next((i for i, ch in enumerate(chunks) if ch[0] == "arrow"), None)
        if m is None or (a is not None and a < m and not any(ch[0] == "verb" for ch in chunks[:a])):
            m = a if m is None or (a is not None and a < m) else m
        if m is None:
            return self._verbless(chunks)
        verb = chunks[m][1]
        is_arrow = chunks[m][0] == "arrow"
        optional = negated = neg_first = False
        operands = []
        for k, ch in enumerate(chunks[:m]):
            if ch[0] == "may":
                optional = True
            elif ch[0] == "not":
                negated = True
                neg_first = k == 0 and m > 1 and any(c2[0] in ("np", "value", "zone", "group", "rel") for c2 in chunks[1:m])
            elif ch[0] == "times" and operands:
                operands.append(ch)
            elif ch[0] in ("np", "zone", "group", "kw", "rel") or (ch[0] == "value" and is_arrow):
                operands.append(ch)
            else:
                raise SemSyntaxError(ch[2], "unexpected item before the verb")
        subject = None
        args: list[tuple[str, A.Node]] = []
        if is_arrow:
            nouns = [o for o in operands if o[0] != "times" and not self._is_per(o[1])]
            if len(nouns) > 2:
                raise SemSyntaxError(nouns[2][2], "too many items before →")
            for o in operands:
                if o[0] == "times":
                    args.append(("times", A.Rel(o[1][0], o[1][1])))
                elif self._is_per(o[1]):
                    args.append(("per", o[1]))
                elif len(nouns) == 2 and o is nouns[0]:
                    subject = self._as_subject(o[1])
                else:
                    args.append(("object", o[1]))
        else:
            if len(operands) > 1:
                raise SemSyntaxError(operands[1][2], "too many items before the verb")
            if operands:
                subject = self._as_subject(operands[0][1])
        before = len(args)
        post = chunks[m + 1:]
        passive = False
        if post and post[0][0] == "passive":
            passive = True
            post = post[1:]
        frame = list(self._frame(verb, is_arrow))
        if passive and "object" in frame:
            frame[frame.index("object")] = "by"
        rest = self._rest_clause(post, toks, verb, frame)
        if rest is not None:
            args += rest
            return A.Action(verb, subject, tuple(args), optional, negated, passive, before, neg_first)
        if is_arrow:
            frame = []
            if post and post[0][0] in ("np", "value", "zone", "group", "mana", "rel"):
                args.append(("destination", post[0][1]))
                post = post[1:]
            else:
                raise SemSyntaxError(chunks[m][2], "→ needs a destination")
        args += self._args(post, frame, verb, prev_dest=is_arrow)
        return A.Action(verb, subject, tuple(args), optional, negated, passive, before, neg_first)

    def _rest_clause(self, post, toks, verb, frame):
        """Verbs whose argument is a whole clause: ⊹ ✝♞ (cost), ∋ ● ⊻ (…) (ability). Trailing times stay."""
        if not post or isinstance(verb, A.EffectRef):
            return None
        slot = None
        if "cost" in frame and (post[0][0] in ("verb", "kw") or any(c[0] == "or" for c in post)):
            slot = "cost"
        elif "ability" in frame and len(post) > 1 and post[0][0] == "np" and post[1][0] == "verb":
            slot = "ability"
        if slot is None:
            return None
        end = len(post)
        while end > 1 and post[end - 1][0] == "time":
            end -= 1
        first = next(k for k, t in enumerate(toks) if t.col == post[0][2])
        last = next(k for k, t in enumerate(toks) if t.col == post[end][2]) if end < len(post) else len(toks)
        sub = toks[first:last]
        node = self.p_cost_expr(sub) if slot == "cost" else self.p_clause(sub)
        return [(slot, node)] + [("time", c[1]) for c in post[end:]]

    def p_cost_expr(self, toks: list[Tok]) -> A.Node:
        parts = split_by(toks, split_top(toks, lambda t: op(t) == "or"))
        if len(parts) == 1:
            return self.p_cost_item(toks, toks)
        return A.Or(tuple(self.p_cost_item(p, toks) for p in parts))

    def _is_per(self, n) -> bool:
        """∀⊤▭ — "for each card type" written before the verb."""
        return isinstance(n, A.NP) and n.quant is not None and self._op(n.quant) == "each" and bool(n.heads) \
            and isinstance(n.heads[0], A.Characteristic)

    def _as_subject(self, n):
        if isinstance(n, A.Rel) and n.other is not None:
            return A.Of(n.rel, n.other, prefix=True)
        return n

    def _frame(self, verb, is_arrow) -> list[str]:
        if isinstance(verb, A.EffectRef):
            return ["object"]
        if isinstance(verb, A.Or):
            verb = verb.items[0]
        syn = self.g.symbols[verb.index].syntax
        return list(syn.get("args", ["object"] if syn.get("kind") != "verb" else []))

    def _args(self, post: list[tuple], frame: list[str], verb, prev_dest: bool = False) -> list[tuple[str, A.Node]]:
        args: list[tuple[str, A.Node]] = []
        free = list(frame)
        i = 0
        while i < len(post):
            ch = post[i]
            typ, node, col = ch
            if typ == "arrow":
                if i + 1 >= len(post) or post[i + 1][0] not in ("np", "value", "zone", "group", "mana", "rel"):
                    raise SemSyntaxError(col, "→ needs a destination")
                slot = "destination"
                args.append(("arrow:" + slot, A.Rel(node, post[i + 1][1])))
                i += 2
                continue
            if typ == "times":
                args.append(("times", A.Rel(node[0], node[1])))
            elif typ == "time":
                args.append(("time", node))
            elif typ == "marker":
                args.append(("marker", node))
            elif typ == "filter":
                args.append(("filter", node))
            elif typ == "restrict":
                args.append(("restrict", A.Rel(node[0], node[1])))
            elif typ == "plus":
                args.append(("additional", node))
            elif typ == "not" and i + 1 < len(post) and post[i + 1][0] == "restrict":
                i += 1
                r = post[i][1]
                args.append(("restrict_not", A.Rel(r[0], r[1])))
            elif typ in ("verb", "not"):
                neg = typ == "not"
                if neg:
                    if i + 1 >= len(post) or post[i + 1][0] != "verb":
                        raise SemSyntaxError(col, "unexpected ¬")
                    i += 1
                    node = post[i][1]
                    col = post[i][2]
                sub_args = []
                sub_free = self._frame(node, False)
                while i + 1 < len(post) and post[i + 1][0] in ("np", "value", "kw", "group", "mana"):
                    slot = self._slot(sub_free, post[i + 1][1], post[i + 1][0])
                    if slot is None:
                        break
                    i += 1
                    sub_args.append((slot, post[i][1]))
                sub = A.Action(node, None, tuple(sub_args), negated=neg)
                if not args and "object" in free and sub_args and not neg:
                    del free[:free.index("object") + 1]
                    args.append(("object", sub))      # ✚ ❐◈ — create a copy of this
                else:
                    args.append(("state", sub))
            elif typ == "pt":
                args.append(("pt", node))
            elif typ in ("np", "value", "zone", "group", "mana", "kw", "rel", "delta"):
                slot = self._slot(free, node, typ)
                if slot is None:
                    if typ == "rel":
                        slot = "rel"
                    elif typ in ("np", "value") and (args and args[-1][0] in ("arrow:destination", "destination")
                                                     or prev_dest):
                        slot = "with"
                    else:
                        raise SemSyntaxError(col, "unexpected item after the verb")
                args.append((slot, node))
            else:
                raise SemSyntaxError(col, f"unexpected {typ}")
            i += 1
        return args

    def _slot(self, free: list[str], node, typ) -> str | None:
        for k, slot in enumerate(free):
            if slot == "amount" and not is_value(node):
                continue
            if slot == "destination":
                continue
            del free[:k + 1]
            return slot
        return None

    def _verbless(self, chunks: list[tuple]) -> A.Node:
        idx = next((i for i, ch in enumerate(chunks) if ch[0] in ("pt", "delta")), None)
        if idx is not None:
            optional = negated = False
            subject = None
            for ch in chunks[:idx]:
                if ch[0] == "may":
                    optional = True
                elif ch[0] == "not":
                    negated = True
                elif ch[0] in ("np", "value", "zone", "group") and subject is None:
                    subject = ch[1]
                else:
                    raise SemSyntaxError(ch[2], "unexpected item before the change")
            args = self._args(chunks[idx + 1:], [], None)
            return A.Modify(subject, chunks[idx][1], tuple(args), optional, negated)
        if len(chunks) == 1:
            typ, node, col = chunks[0]
            if typ in ("np", "value", "zone", "group", "time", "mana", "marker", "kw", "rel"):
                return node
            raise SemSyntaxError(col, f"unexpected {typ}")
        # X△ × 2 (characteristic multiplied) / ● ♥ × 2 handled by delta
        if len(chunks) >= 1 and chunks[0][0] == "value" and isinstance(chunks[0][1], A.Arith) \
                and chunks[0][1].op == "×" and isinstance(chunks[0][1].left, A.Characteristic) \
                and not chunks[0][1].left.prefix and chunks[0][1].left.of is not None and not chunks[0][1].paren:
            ar = chunks[0][1]
            args = self._args(chunks[1:], [], None)
            return A.Modify(ar.left.of, A.Delta(ar.left.char, times=ar.right), tuple(args))
        if chunks[0][0] == "not" and len(chunks) == 2:
            return A.Not(chunks[1][1])
        # X ✸… — X deals damage (no recipient written)
        rest = [ch for ch in chunks if ch[0] not in ("may", "not")]
        if len(rest) >= 2 and rest[0][0] == "np" and self._damage_like(rest[1][1]):
            negated = any(c[0] == "not" for c in chunks)
            args = [("object", rest[1][1])] + self._args(rest[2:], [], None)
            return A.Action(None, rest[0][1], tuple(args), negated=negated,
                            neg_first=negated and chunks[0][0] == "not")
        # (ability) time — "until end of turn, whenever …"
        if len(chunks) == 2 and chunks[0][0] == "group" and chunks[1][0] == "time":
            return A.Timed(chunks[0][1], chunks[1][1])
        # subject [?] [¬] (group)
        if len(rest) == 2 and rest[0][0] in ("np", "value") and rest[1][0] == "group":
            return A.Scoped(rest[0][1], rest[1][1], any(c[0] == "may" for c in chunks),
                            any(c[0] == "not" for c in chunks))
        raise SemSyntaxError(chunks[1][2], "no verb in this clause")

    def _damage_like(self, n) -> bool:
        if isinstance(n, A.NP):
            return self._is_damage(n)
        return isinstance(n, A.Compare) and isinstance(n.items[0], A.NP) and self._is_damage(n.items[0])

    def _combine(self, chunks: list[tuple]) -> list[tuple]:
        """Merge X ∧ Y / X ∨ Y operand chunks (∧ binds tighter), and ¬X operands after them."""
        operand = ("np", "value", "zone", "group", "mana", "kw", "rel", "time", "filter")
        for name, cls in (("and", A.And), ("or", A.Or)):
            out: list[tuple] = []
            i = 0
            while i < len(chunks):
                ch = chunks[i]
                if ch[0] == name:
                    if not out or out[-1][0] not in operand:
                        raise SemSyntaxError(ch[2], f"nothing before {ch[1].glyph!r}")
                    j = i + 1
                    neg = False
                    if j < len(chunks) and chunks[j][0] == "not":
                        neg = True
                        j += 1
                    if j >= len(chunks) or chunks[j][0] not in operand:
                        raise SemSyntaxError(ch[2], f"nothing after {ch[1].glyph!r}")
                    right = chunks[j][1]
                    if neg:
                        right = A.Not(right)
                    left = out.pop()
                    lnode = left[1]
                    if isinstance(lnode, cls) and not lnode.paren:
                        node = cls(lnode.items + (right,))
                    else:
                        node = cls((lnode, right))
                    out.append((left[0], node, left[2]))
                    i = j + 1
                else:
                    out.append(ch)
                    i += 1
            chunks = out
        return chunks

    # ------------------------------------------------ filters
    def p_filter(self, s: _S) -> A.Filter:
        inner = s.group()
        return A.Filter(tuple(self._conds(inner)))

    def _conds(self, toks: list[Tok]) -> list[A.Node]:
        chunks = self.p_chunks(self._s(toks), "filter")
        conds: list = []
        i = 0
        while i < len(chunks):
            typ, node, col = chunks[i]
            if typ in ("and", "or"):
                conds.append((typ, node, col))
                i += 1
                continue
            if typ == "not":
                if i + 1 >= len(chunks):
                    raise SemSyntaxError(col, "¬ needs something after it")
                sub = self._cond_one(chunks, i + 1)
                conds.append(A.Not(sub[0]))
                i = sub[1]
                continue
            if typ == "arrow":
                if i + 1 >= len(chunks):
                    raise SemSyntaxError(col, "→ needs a destination")
                dest = chunks[i + 1][1]
                prev = conds.pop() if conds else None
                if isinstance(prev, A.Action):
                    conds.append(replace(prev, args=prev.args + (("arrow:destination", A.Rel(node, dest)),)))
                else:
                    args = (("from", prev),) if prev is not None else ()
                    conds.append(A.Action(node, None, args + (("destination", dest),), before=len(args)))
                i += 2
                continue
            c, i = self._cond_one(chunks, i)
            conds.append(c)
        # X ∧ Y / X ∨ Y between conditions (∧ binds tighter)
        for name, cls in (("and", A.And), ("or", A.Or)):
            out: list = []
            k = 0
            while k < len(conds):
                c = conds[k]
                if isinstance(c, tuple) and c[0] == name:
                    if not out or isinstance(out[-1], tuple) or k + 1 >= len(conds) or isinstance(conds[k + 1], tuple):
                        raise SemSyntaxError(c[2], f"{c[1].glyph!r} needs a condition on each side")
                    left = out.pop()
                    right = conds[k + 1]
                    out.append(cls(left.items + (right,)) if isinstance(left, cls) and not left.paren
                               and not getattr(left, "juxtaposed", False) else cls((left, right)))
                    k += 2
                else:
                    out.append(c)
                    k += 1
            conds = out
        return conds

    def _cond_one(self, chunks, i):
        typ, node, col = chunks[i]
        if typ in ("verb", "kw"):
            sym = node.sym if isinstance(node, A.Keyword) else node
            if typ == "kw" and node.params:
                return node, i + 1
            if i + 1 < len(chunks) and chunks[i + 1][0] in ("np", "value", "zone"):
                return A.Rel(sym, chunks[i + 1][1]), i + 2
            if typ == "verb" and i + 1 < len(chunks) and chunks[i + 1][0] == "time":
                return A.Action(sym, None, (("time", chunks[i + 1][1]),)), i + 2
            return (A.Action(sym, None) if typ == "verb" else node), i + 1
        if typ == "group":
            return node, i + 1
        if typ in ("np", "value", "zone", "time", "rel", "pt", "mana", "marker", "filter", "delta"):
            return node, i + 1
        if typ == "times":
            return A.Rel(node[0], node[1]), i + 1
        raise SemSyntaxError(col, f"unexpected {typ} in filter")

    # ------------------------------------------------ phrases
    def p_operand(self, s: _S):
        if self._time_start(s):
            return self.p_time(s)
        if self._zone_start(s):
            return self.p_zone(s)
        return self.p_value(s)

    def _np_start(self, s: _S, k: int) -> bool:
        t = s.peek(k)
        if t is None:
            return False
        if op(t) in ("next", "last") and self._head_ok(s.peek(k + 1)):
            return True
        kd = kind(t)
        return kd in ("type", "object", "player", "reference", "quantifier", "stat") or t.type in ("NAME", "LPAR") \
            or op(t) == "anymana"

    def _head_ok(self, t: Tok | None) -> bool:
        if t is None:
            return False
        kd = kind(t)
        return kd in ("type", "object", "player", "reference", "stat") or t.type == "NAME" or op(t) == "anymana"

    def p_value(self, s: _S):
        left = self.p_arith(s)
        if left is None:
            return None
        if not self.isval(left):
            return left
        items, ops = [left], []
        while kind(s.peek()) == "comparison" and op(s.peek()) != "other" or \
                (op(s.peek()) == "other" and items and self.isval(items[-1])):
            ops.append(self.sym(s.next()))
            r = self.p_arith(s)
            if r is None:
                raise SemSyntaxError(s.col(), "expected a value after the comparison")
            items.append(r)
        if ops:
            return A.Compare(tuple(items), tuple(ops))
        return left

    def isval(self, n) -> bool:
        return is_value(n) or (isinstance(n, A.NP) and self._is_damage(n))

    def _is_damage(self, n: A.NP) -> bool:
        return bool(n.heads) and isinstance(n.heads[0], A.SymRef) and self._op(n.heads[0]) == "damage"

    def p_arith(self, s: _S):
        left = self.p_atom(s)
        if left is None:
            return None
        while True:
            t = s.peek()
            if t is None or not self.isval(left):
                return left
            if op(t) in ("times", "div"):
                save = s.pos
                s.next()
                r = self.p_atom(s)
                if r is None:
                    s.pos = save
                    return left
                left = A.Arith("×" if op(t) == "times" else "÷", left, r)
            elif t.type == "PLUS" and s.peek(1) is not None and s.peek(1).type in ("NUMBER", "VAR", "SYMBOL") \
                    and not self._pt_ahead(s):
                save = s.pos
                s.next()
                r = self.p_atom(s)
                if r is None or not self.isval(r):
                    s.pos = save
                    return left
                left = A.Arith("+", left, r)
            else:
                return left

    def p_atom(self, s: _S):
        t = s.peek()
        if t is None:
            return None
        o, kd = op(t), kind(t)
        if o == "count":
            s.next()
            mods = []
            while op(s.peek()) in ("distinct", "shared"):
                mods.append(self.sym(s.next()))
            of = self._relative(s)
            if of is None:
                raise SemSyntaxError(s.col(), "expected something to count after #")
            return A.Count(of, tuple(mods))
        if o == "agg":
            s.next()
            c = s.peek()
            if kind(c) not in ("characteristic", "stat"):
                raise SemSyntaxError(s.col(), "expected a characteristic after the aggregate")
            s.next()
            of = self._np_or_none(s)
            return A.Characteristic(self.sym(c), of, None, self.sym(t), prefix=True)
        if o == "anymana":
            np = self.p_np(s)
            return self._postfix(s, np) if np is not None else None
        if kd == "stat" and kind(s.peek(1)) != "comparison":
            np = self.p_np(s)
            if np is not None:
                return self._postfix(s, np)
        if kd in ("characteristic", "stat") and o not in ("base",):
            s.next()
            sub = None
            if o == "types" and kind(s.peek()) in ("type", "object") and \
                    (s.peek(1) is None or s.peek(1).type != "LSQB"):
                sub = self.sym(s.next())
            of = None
            n = s.peek()
            if n is not None and (n.type == "MANA" or op(n) == "none" or kind(n) in ("player", "reference")
                                  or (kind(n) == "quantifier" and kind(s.peek(1)) in ("player", "reference"))):
                if n.type == "MANA":
                    of = self._mana(s)
                elif op(n) == "none":
                    of = self.sym(s.next())
                else:
                    of = self.p_np(s)
            elif o == "types" and self._np_start(s, 0):
                of = self._np_or_none(s)
            return A.Characteristic(self.sym(t), of, sub, None, prefix=True)
        if t.type in ("NUMBER", "VAR"):
            if self._pt_ahead(s):
                return self.p_pt(s)
            save = s.pos
            np = self.p_np(s)
            if np is not None:
                return self._postfix(s, np)
            s.pos = save
            return self._numvar(s)
        if o in ("at_most", "at_least") and s.peek(1) is not None and s.peek(1).type in ("NUMBER", "VAR"):
            save = s.pos
            np = self.p_np(s)
            if np is not None:
                return self._postfix(s, np)
            s.pos = save
            s.next()
            return A.Bound(self.sym(t), self._numvar(s))
        if t.type == "LPAR":
            save = s.pos
            np = self.p_np(s)
            if np is not None:
                return self._postfix(s, np)
            s.pos = save
            inner = s.group()
            s2 = self._s(inner)
            v = self.p_value(s2)
            if v is not None and s2.eof and (self.isval(v) or isinstance(v, A.Compare)):
                return replace(v, paren=v.paren + 1)
            s.pos = save
            return None
        if t.type == "MANA":
            return self._mana(s)
        if self._np_start(s, 0) or o == "anymana":
            np = self.p_np(s)
            if np is None:
                return None
            return self._postfix(s, np)
        return None

    def _np_or_none(self, s: _S):
        if self._np_start(s, 0):
            save = s.pos
            np = self.p_np(s)
            if np is not None:
                return self._postfix(s, np)
            s.pos = save
        return None

    def _postfix(self, s: _S, np, chars: bool = True):
        """Glued postfix on a player/reference phrase: ☞⚑ (controller), ◈△ (power), ◈⊺ (kicked)."""
        while isinstance(np, (A.NP, A.Of)) and self._refish(np):
            t = s.peek()
            if t is None:
                break
            kd = kind(t)
            if kd == "relation":
                s.next()
                np = A.Of(self.sym(t), np)
            elif chars and kd in ("characteristic", "stat") and op(t) not in ("life", "base", "anymana", "none"):
                s.next()
                return A.Characteristic(self.sym(t), np)
            else:
                break
        return np

    def _refish(self, n) -> bool:
        if isinstance(n, A.Of):
            return True
        return bool(n.heads) and isinstance(n.heads[-1], A.SymRef) and \
            self.g.symbols[n.heads[-1].index].syntax.get("kind") == "reference" and not n.filters

    def _relative(self, s: _S):
        """What # counts: a phrase, optionally with a glued verb, object and time (♞☠◷, ▭⌫● ◷, ♥+ ◷)."""
        start = s.pos
        stop_ops = {"and", "or", "if", "then", "replace", "while", "until", "times", "div"}
        chunks: list[tuple] = []
        while not s.eof:
            t = s.peek()
            if op(t) in stop_ops or kind(t) == "comparison" and op(t) != "other" or op(t) == "transfer" \
                    or t.type in ("COMMA", "PLUS") and chunks:
                break
            if op(t) == "life":
                chunks.append(("delta", self.p_delta(s, bare=True), t.col))
                continue
            if kind(t) == "verb":
                s.next()
                chunks.append(("verb", self.sym(t), t.col))
                continue
            if op(t) in ("distinct", "shared") or kind(t) == "marker":
                s.next()
                chunks.append(("marker", self.sym(t), t.col))
                continue
            if self._time_start(s):
                chunks.append(("time", self.p_time(s), t.col))
                continue
            if chunks and chunks[-1][0] in ("np", "time", "delta"):
                break
            n = self.p_atom(s)
            if n is None:
                break
            if isinstance(n, A.Characteristic) and n.of is None and n.agg is None and self._np_start(s, 0):
                n = replace(n, of=self._np_or_none(s))
            chunks.append(("np", n, t.col))
            if isinstance(n, A.Characteristic):
                break
        if not chunks:
            s.pos = start
            return None
        if len(chunks) == 1 and chunks[0][0] == "np":
            return chunks[0][1]
        return self._relative_node(chunks)

    def _relative_node(self, chunks: list[tuple]):
        """[thing] [verb [agent]] [time]: ♞☠◷, ▭⌫● ◷, ⤓● ◷, ♥+ ◷, ⇢◈ ◷."""
        if chunks[0][0] == "delta":
            return A.Modify(None, chunks[0][1], tuple(self._args(chunks[1:], [], None)))
        v = next((i for i, c in enumerate(chunks) if c[0] == "verb"), None)
        if v is None:
            raise SemSyntaxError(chunks[0][2], "cannot count this")
        args: list = []
        subject = None
        has_agent = any(c[0] == "np" for c in chunks[v + 1:])
        if v == 1 and chunks[0][0] == "np":
            if has_agent:
                args.append(("object", chunks[0][1]))
            else:
                subject = chunks[0][1]
        elif v != 0:
            raise SemSyntaxError(chunks[0][2], "cannot count this")
        before = len(args)
        for typ, node, col in chunks[v + 1:]:
            if typ == "np":
                args.append(("by", node))
            elif typ == "time":
                args.append(("time", node))
            elif typ == "marker":
                args.append(("marker", node))
            else:
                raise SemSyntaxError(col, f"unexpected {typ} after #")
        return A.Action(chunks[v][1], subject, tuple(args), before=before)

    def p_np(self, s: _S) -> A.NP | None:
        start = s.pos
        quant = count = None
        neg = False
        pre = []
        while op(s.peek()) in ("next", "last") and self._head_ok(s.peek(1)):
            pre.append(self.sym(s.next()))
        t = s.peek()
        if op(t) in ("each", "target", "exists"):
            if op(t) == "each" and self._time_start(s, 1):
                return None
            quant = self.sym(s.next())
            if op(t) == "each" and op(s.peek()) == "not":
                s.next()
                neg = True
        # count
        t = s.peek()
        if t is not None and (t.type in ("NUMBER", "VAR") or (op(t) in ("at_most", "at_least")
                                                              and s.peek(1) is not None
                                                              and s.peek(1).type in ("NUMBER", "VAR"))):
            save = s.pos
            if t.type in ("NUMBER", "VAR"):
                cnt = self._numvar(s)
            else:
                o = self.sym(s.next())
                cnt = A.Bound(o, self._numvar(s))
            if self._head_ok(s.peek()) or op(s.peek()) in ("target", "anymana") or s.peek() is not None and s.peek().type == "LPAR":
                count = cnt
            else:
                s.pos = save
        elif t is not None and t.type == "LPAR":
            save = s.pos
            inner = s.group()
            if inner and all(x.type in ("NUMBER", "VAR") or op(x) == "or" for x in inner) and \
                    (op(s.peek()) == "target" or self._head_ok(s.peek())):
                nums = [self._numvar(self._s([x])) for x in inner if x.type in ("NUMBER", "VAR")]
                count = A.Or(tuple(nums), paren=1)
            else:
                s.pos = save
        each = None
        if count is not None and op(s.peek()) == "target":
            if quant is not None:
                each = quant          # ∀(1 ∨ 2)◎♞ — each of one or two targets
            quant = self.sym(s.next())
        np = self._np_rest(s, quant, count, neg)
        if np is None:
            s.pos = start
            return None
        if pre:
            np = replace(np, pre=tuple(pre))
        return replace(np, each=each) if each is not None else np

    def _np_rest(self, s: _S, quant, count, neg) -> A.NP | None:
        heads: list = []
        count_after = False
        while not s.eof:
            t = s.peek()
            kd, o = kind(t), op(t)
            if t.type == "NAME":
                heads.append(A.NameRef(s.next().value))
            elif kd in ("player", "reference"):
                if heads:
                    break
                heads.append(self.sym(s.next()))
                break
            elif o == "counter":
                heads.append(self.sym(s.next()))
                n = s.peek()
                if n is not None and kind(n) in ("counter_kind", "stat"):
                    heads.append(self.sym(s.next()))
                elif self._pt_ahead(s):
                    heads.append(self.p_pt(s))
                elif n is not None and kind(n) == "comparison" and op(n) is None:
                    s.next()
                    heads.append(A.Rel(self.sym(n), self.p_operand(s)))
            elif o == "damage":
                heads.append(self.sym(s.next()))
                n = s.peek()
                if count is None and n is not None and (n.type in ("NUMBER", "VAR", "LPAR") or kind(n) == "reference"):
                    v = self.p_atom(s)
                    if v is None:
                        raise SemSyntaxError(s.col(), "expected a damage amount")
                    count, count_after = v, True
                if kind(s.peek()) == "time":
                    heads.append(self.sym(s.next()))
            elif kd in ("type", "object", "stat") or o == "anymana":
                heads.append(self.sym(s.next()))
            elif o == "types" and quant is not None and self._op(quant) == "each" and not heads:
                s.next()
                sub = self.sym(s.next()) if kind(s.peek()) in ("type", "object") else None
                heads.append(A.Characteristic(self.sym(t), None, sub, None, prefix=True))
                break
            elif t.type == "LPAR":
                save = s.pos
                inner = s.group()
                alt = self._head_group(inner)
                if alt is None:
                    s.pos = save
                    break
                heads.append(alt)
            else:
                break
        if not heads and not (quant is not None and self._op(quant) in ("target", "each") and count is None):
            return None
        filters, post = [], []
        name = None
        while not s.eof:
            t = s.peek()
            if t.type == "LSQB":
                filters.append(self.p_filter(s))
            elif t.type == "NAME" and heads and isinstance(heads[0], A.SymRef) and self._op(heads[0]) == "token" \
                    and name is None and filters:
                name = A.NameRef(s.next().value)
            elif op(t) in ("distinct", "excess"):
                post.append(self.sym(s.next()))
            elif kind(t) == "keyword" and heads and self._refish(A.NP(heads=tuple(heads))) \
                    and not self._head_ok(s.peek(1)) and (s.peek(1) is None or s.peek(1).type != "LSQB"):
                post.append(self.sym(s.next()))
            else:
                break
        return A.NP(quant=quant, count=count, heads=tuple(heads), filters=tuple(filters), name=name,
                    post=tuple(post), neg=neg, count_after=count_after)

    def _head_group(self, inner: list[Tok]):
        """(♞ ∨ ⚝), (⊳ ∨ ⇢), («Equipment» ∨ «Spacecraft») — alternatives of heads."""
        parts = split_by(inner, split_top(inner, lambda t: op(t) == "or"))
        if len(parts) < 2:
            return None
        items = []
        for p in parts:
            if not p:
                return None
            if len(p) == 1 and kind(p[0]) == "verb":
                items.append(self.sym(p[0]))
                continue
            s2 = self._s(p)
            np = self.p_np(s2)
            if np is None or not s2.eof:
                return None
            if np.quant is None and np.count is None and not np.filters and len(np.heads) == 1 and not np.post:
                items.append(np.heads[0])
            else:
                items.append(np)
        return A.Or(tuple(items), paren=1)

    def p_pt(self, s: _S) -> A.PT:
        base = None
        if op(s.peek()) == "base":
            base = self.sym(s.next())
        p = self._signed(s)
        t = s.next()
        if t.type != "SLASH":
            raise SemSyntaxError(t.col, "expected /")
        q = self._signed(s)
        return A.PT(p, q, base)

    def _signed(self, s: _S):
        sign = ""
        if s.peek() is not None and s.peek().type in ("PLUS", "MINUS"):
            sign = s.next().text
        t = s.next()
        if t.type == "NUMBER":
            return A.Num(int(t.value), sign)
        if t.type == "VAR":
            return A.Var(t.value, sign)
        raise SemSyntaxError(t.col, "expected a number")

    def _pt_ahead(self, s: _S) -> bool:
        k = 0
        if op(s.peek(k)) == "base":
            k += 1
        if s.peek(k) is not None and s.peek(k).type in ("PLUS", "MINUS"):
            k += 1
        if s.peek(k) is None or s.peek(k).type not in ("NUMBER", "VAR"):
            return False
        return s.peek(k + 1) is not None and s.peek(k + 1).type == "SLASH"

    def p_delta(self, s: _S, bare: bool = False) -> A.Delta:
        t = s.next()
        sign = ""
        amount = times = None
        n = s.peek()
        if n is not None and n.type in ("PLUS", "MINUS"):
            sign = s.next().text
            n = s.peek()
        if n is not None and not bare and (n.type in ("NUMBER", "VAR") or op(n) == "count"):
            amount = self.p_atom(s)
        elif n is not None and bare and n.type in ("NUMBER", "VAR"):
            amount = self.p_atom(s)
        if not sign and amount is None and op(s.peek()) == "times" and not bare:
            s.next()
            times = self.p_atom(s)
            if times is None:
                raise SemSyntaxError(s.col(), "expected a number after ×")
        return A.Delta(self.sym(t), amount, sign, times)

    def _numvar(self, s: _S):
        t = s.next()
        if t.type == "NUMBER":
            return A.Num(int(t.value))
        if t.type == "VAR":
            return A.Var(t.value)
        raise SemSyntaxError(t.col, "expected a number")

    def _mana(self, s: _S) -> A.Mana:
        parts = []
        while s.peek() is not None and s.peek().type == "MANA":
            parts.append(s.next().value)
        return A.Mana("".join(parts))

    # ------------------------------------------------ time
    def _time_start(self, s: _S, k: int = 0) -> bool:
        t = s.peek(k)
        if t is None:
            return False
        if op(t) in ("next", "last") and (self._head_ok(s.peek(k + 1)) or kind(s.peek(k + 1)) == "relation"):
            return False
        if kind(t) == "time" and op(t) not in ("only", "until"):
            return True
        if op(t) == "each" or t.type in ("NUMBER",) or op(t) == "at_most":
            j = k + 1
            if op(t) == "at_most":
                j += 1
            n = s.peek(j)
            return n is not None and kind(n) == "time" and op(n) not in ("only", "until")
        return False

    def p_time(self, s: _S) -> A.Time:
        items: list = []
        t = s.peek()
        if op(t) == "each":
            items.append(self.sym(s.next()))
        elif t.type == "NUMBER":
            items.append(self._numvar(s))
        elif op(t) == "at_most":
            o = self.sym(s.next())
            items.append(A.Bound(o, self._numvar(s)))
        while not s.eof:
            t = s.peek()
            if kind(t) == "time" and op(t) not in ("only", "until"):
                s.next()
                items.append(self.sym(t))
                if op(t) == "begin" and s.peek() is not None and kind(s.peek()) != "time":
                    items.append(self.sym(s.next()))
                elif op(t) == "turn" and s.peek() is not None and (
                        kind(s.peek()) in ("player", "reference")
                        or (op(s.peek()) == "target" and kind(s.peek(1)) == "player")):
                    np = self.p_np(s)
                    items.append(self._postfix(s, np))
                elif op(t) == "phase" and s.peek() is not None and s.peek().type == "NUMBER":
                    items.append(self._numvar(s))
            elif self._time_start(s) and op(t) in ("each",):
                items.append(self.sym(s.next()))
            else:
                break
        if not items:
            raise SemSyntaxError(s.col(), "expected a time")
        return A.Time(tuple(items))

    # ------------------------------------------------ zones
    def _zone_start(self, s: _S, k: int = 0) -> bool:
        t = s.peek(k)
        if t is None:
            return False
        if kind(t) == "zone":
            return True
        if t.type == "LPAR":
            j = s.pos + k
            try:
                e = _close(s.toks, j)
            except SemSyntaxError:
                return False
            inner = s.toks[j + 1:e]
            return bool(inner) and all(op(x) in ("pos", "or") for x in inner) and e + 1 < len(s.toks) \
                and kind(s.toks[e + 1]) == "zone"
        return False

    def p_zone(self, s: _S) -> A.Zone:
        pos = pos_alt = count = zone = owner = None
        paren = 0
        t = s.peek()
        if t.type == "LPAR":
            inner = s.group()
            ps = [x for x in inner if op(x) == "pos"]
            pos, pos_alt = self.sym(ps[0]), (self.sym(ps[1]) if len(ps) > 1 else None)
            paren = 1
        elif op(t) == "pos":
            pos = self.sym(s.next())
        if pos is not None and s.peek() is not None and s.peek().type in ("NUMBER", "VAR"):
            count = self._numvar(s)
        if kind(s.peek()) == "zone" and op(s.peek()) != "pos":
            zone = self.sym(s.next())
        if zone is None and pos is None:
            raise SemSyntaxError(s.col(), "expected a zone")
        n = s.peek()
        if n is not None and (kind(n) in ("player", "reference")
                              or (op(n) in ("target", "each") and kind(s.peek(1)) in ("player", "reference"))):
            np = self.p_np(s)
            owner = self._postfix(s, np)
        elif n is not None and op(n) == "own" and zone is not None:
            owner = self.sym(s.next())
        if zone is None:
            return A.Zone(pos, owner, None, count, pos_alt, paren=0)
        return A.Zone(zone, owner, pos, count, pos_alt)


# ---------------------------------------------------------------- card level

def _find_choose(n, g: Glossary):
    """First ⊻n action (choose without an object) in an ability — the head of a modal."""
    import dataclasses
    if isinstance(n, A.Action) and isinstance(n.verb, A.SymRef) \
            and g.symbols[n.verb.index].syntax.get("op") == "choose" \
            and not any(slot == "object" for slot, _ in n.args):
        return n
    if not isinstance(n, A.Node) or isinstance(n, (A.NP, A.Filter, A.Nested)):
        return None
    for f in dataclasses.fields(n):
        v = getattr(n, f.name)
        for x in (v if isinstance(v, tuple) else (v,)):
            if isinstance(x, tuple) and len(x) == 2 and isinstance(x[1], A.Node):
                x = x[1]
            if isinstance(x, A.Node):
                found = _find_choose(x, g)
                if found is not None:
                    return found
    return None


def _swap(n, old, new):
    import dataclasses
    if n is old:
        return new
    if not isinstance(n, A.Node):
        return n
    changes = {}
    for f in dataclasses.fields(n):
        v = getattr(n, f.name)
        if isinstance(v, A.Node):
            nv = _swap(v, old, new)
            if nv is not v:
                changes[f.name] = nv
        elif isinstance(v, tuple):
            nv = tuple((x[0], _swap(x[1], old, new)) if isinstance(x, tuple) else _swap(x, old, new) for x in v)
            if any(a is not b for a, b in zip(nv, v)):
                changes[f.name] = nv
    return dataclasses.replace(n, **changes) if changes else n


def group_modes(abilities: list, g: Glossary, lines: list[int] | None = None) -> list:
    """Fold • mode lines into a Modal that replaces the preceding ⊻n action."""
    out: list = []
    chooser = None  # (index in out, choose action, modes list)
    for k, ab in enumerate(abilities):
        if isinstance(ab, A.Mode):
            if chooser is None:
                raise SemSyntaxError(1, "mode line without a preceding ⊻ choice")
            chooser[2].append(ab)
            i, act, modes = chooser
            out[i] = (out[i][0], act, modes)
            continue
        act = _find_choose(ab, g)
        out.append((ab, act, []))
        chooser = (len(out) - 1, act, []) if act is not None else None
        if chooser is not None:
            out[-1] = (ab, act, chooser[2])
    result = []
    for ab, act, modes in out:
        if act is not None and modes:
            ab = _swap(ab, act, A.Modal(act, tuple(modes)))
        result.append(ab)
    return result


def build_card(doc, p: SemParser) -> A.Card:
    """CardDoc (from cardfile) → Card AST. Raises SemSyntaxError with ``.line`` set on failure."""
    faces = []
    for f in doc.faces:
        abilities = []
        for line in f.abilities:
            try:
                abilities.append(p.parse_ability(line.text))
            except SemSyntaxError as e:
                e.line = line.lineno
                raise
        stats = p.parse_stats(f.stats) if f.stats else None
        faces.append(A.Face(A.NameRef(f.name), (A.Mana(f.mana),) if f.mana else (), p.parse_type_line(f.type_line),
                            stats, tuple(group_modes(abilities, p.g))))
    return A.Card(tuple(faces))
