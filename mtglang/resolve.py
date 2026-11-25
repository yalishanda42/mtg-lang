"""Resolution pass: fill in meaning the notation leaves implicit.

1. Every noun phrase gets ``quantity`` (one, all, each, up_to, exactly, at_least, choice, exists, count,
   kind, amount) and grammatical ``number`` (sg / pl).
2. Every ``☞`` gets an ``antecedent``: the ``walk`` path of the phrase it refers to.
3. Subject-less actions get ``implicit_subject``: "controller" (the ability's controller) or "shared"
   (the subject of the previous conjunct).

Only resolution fields change; the written form (and so ``unparse``) never does.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from mtglang import ast as A


@dataclass(frozen=True)
class ResolveProblem:
    path: str
    message: str


@dataclass
class _Rec:
    path: str
    node: A.Node
    parent: A.Node | None
    slot: str            # field / arg slot this node sits in
    ctx: dict


# ---------------------------------------------------------------- traversal in written order

def _children(n: A.Node):
    """(path suffix, child, slot) in the order the child is written."""
    out = []

    def field(name):
        v = getattr(n, name)
        if isinstance(v, A.Node):
            out.append((name, v, name))
        elif isinstance(v, tuple):
            if name == "args":
                seen: dict[str, int] = {}
                for slot, child in v:
                    k = seen.get(slot, 0)
                    seen[slot] = k + 1
                    out.append((f"args.{slot}" + (str(k + 1) if k else ""), child, slot))
            else:
                for i, child in enumerate(v):
                    if isinstance(child, A.Node):
                        out.append((f"{name}.{i}", child, name))

    if isinstance(n, A.Triggered):
        order = ["event", "conds", "while_", "effect"]
    elif isinstance(n, A.Conditional) and n.mode == "unless":
        order = ["then", "cond"]
    else:
        order = [f.name for f in dataclasses.fields(n)]
    for name in order:
        field(name)
    return out


def _records(root: A.Node, path: str, ctx: dict, out: list, parent=None, slot=""):
    out.append(_Rec(path, root, parent, slot, ctx))
    for suffix, child, cslot in _children(root):
        c = dict(ctx)
        if isinstance(root, A.Triggered):
            c["event"] = cslot in ("event", "conds", "while_")
            if cslot == "effect":
                c["event"] = False
        if isinstance(root, A.Replace) and cslot == "event":
            c["event"] = True
        if isinstance(root, A.Filter):
            c["filter"] = True
        if isinstance(root, A.Count):
            c["count"] = True
        if isinstance(root, A.Characteristic) and root.prefix and cslot == "of":
            c["among"] = True
        if isinstance(root, A.Keyword):
            c["kw"] = True
        if isinstance(root, A.Time):
            c["time"] = True
        if isinstance(root, A.Nested):
            c = {"nested": True}
        if isinstance(root, (A.Action, A.Modify, A.Scoped)) and cslot == "subject":
            c["role"] = "subject"
        elif isinstance(root, A.Action) and cslot not in ("verb",):
            c["role"] = cslot
        elif isinstance(root, A.ForEach) and cslot == "over":
            c["role"] = "over"
        _records(child, f"{path}.{suffix}" if path else suffix, c, out, root, cslot)


# ---------------------------------------------------------------- resolution

class _Resolver:
    def __init__(self, g):
        self.g = g

    def kind_of(self, s: A.SymRef) -> str | None:
        return self.g.symbols[s.index].syntax.get("kind") if self.g else None

    def op_of(self, s: A.SymRef) -> str | None:
        return self.g.symbols[s.index].syntax.get("op") if self.g else None

    def head_kind(self, np: A.NP) -> str | None:
        if not np.heads or not isinstance(np.heads[0], A.SymRef):
            return None
        return self.kind_of(np.heads[0])

    def head_op(self, np: A.NP) -> str | None:
        if not np.heads or not isinstance(np.heads[0], A.SymRef):
            return None
        return self.op_of(np.heads[0])

    def classify(self, np: A.NP, ctx: dict) -> tuple[str, str | None]:
        q = self.op_of(np.quant) if np.quant is not None else None
        hk, ho = self.head_kind(np), self.head_op(np)
        if ho == "damage":
            return "amount", None
        if q == "target":
            return self._counted(np.count, default=("one", "sg"))
        if q == "each" or np.each is not None:
            return "each", "sg"
        if q == "exists":
            return "exists", "sg"
        if np.count is not None:
            return self._counted(np.count, default=("one", "sg"))
        if hk in ("player", "reference"):
            return "one", "sg"
        if ctx.get("kw"):
            return "kind", None
        if ctx.get("filter"):
            return "kind", None
        if ctx.get("count"):
            return "count", "pl"
        if ctx.get("among"):
            return "all", "pl"
        if ho == "counter":
            return "one", "sg"
        if ctx.get("event"):
            return "one", "sg"
        if ctx.get("role") == "subject":
            return "all", "pl"
        return "one", "sg"

    def _counted(self, count, default):
        if count is None:
            return default
        if isinstance(count, A.Num):
            return "exactly", "sg" if count.value == 1 else "pl"
        if isinstance(count, A.Var):
            return "exactly", "pl"
        if isinstance(count, A.Bound):
            o = self.op_of(count.op)
            one = isinstance(count.value, A.Num) and count.value.value == 1
            if o == "at_most":
                return "up_to", "sg" if one else "pl"
            return "at_least", "pl"
        if isinstance(count, A.Or):
            return "choice", "pl"
        return "exactly", "pl"

    # ------------------------------------------------ ☞
    def is_that(self, n) -> bool:
        return isinstance(n, A.NP) and len(n.heads) == 1 and isinstance(n.heads[0], A.SymRef) \
            and self.op_of(n.heads[0]) == "that"

    def candidate_kind(self, rec: _Rec) -> str | None:
        n = rec.node
        p = rec.parent
        if isinstance(n, A.Zone):
            return "object" if not rec.ctx.get("filter") and rec.slot in ("object", "zone") else None
        if isinstance(n, A.Of):
            return "player"
        if isinstance(n, A.Characteristic):
            return "value" if self._is_choice(p) else None
        if isinstance(n, A.Action) and isinstance(n.verb, A.SymRef) and not rec.ctx.get("filter") \
                and self.g.symbols[n.verb.index].syntax.get("yields") \
                and any(s == "amount" for s, _ in n.args) and not any(s == "object" for s, _ in n.args):
            return "object"            # ⌕1, ⤋4, ⤓ (X ÷ 5): the cards it acted on
        if isinstance(n, A.Action) and rec.slot == "object":
            return "object"            # ✚ ❐◈ — the copy
        if not isinstance(n, A.NP):
            return None
        hk, ho = self.head_kind(n), self.head_op(n)
        if isinstance(p, A.Not) or (n.quant is not None and self.op_of(n.quant) == "exists"):
            return None               # ¬⚜ "isn't legendary", ∃♞ "there is a creature"
        if rec.ctx.get("filter") and not (n.quant is not None and self.op_of(n.quant) == "target"):
            return None
        if not n.heads and n.quant is not None and self.op_of(n.quant) == "each":
            return None               # ∌∀ — "all abilities"
        if n.heads and isinstance(n.heads[0], A.Characteristic):
            return None               # ∀⊤▭ — "for each card type"
        if rec.ctx.get("count"):
            return None               # the things a # counts
        if rec.ctx.get("kw") or rec.slot in ("types", "pt"):
            return None               # ☞ ∈ ▭[…] — a predicate, not a new thing
        if ho == "counter":
            return "counter"
        if ho in ("self", "damage") or hk == "stat":
            return None
        if hk == "player":
            return None if self._is_you(n) else "player"
        if n.quant is not None and self.op_of(n.quant) == "target" and not n.heads:
            return "any"
        return "object"

    def _is_choice(self, p) -> bool:
        return isinstance(p, A.Action) and isinstance(p.verb, A.SymRef) and self.op_of(p.verb) == "choose"

    def _is_you(self, n: A.NP) -> bool:
        # the first player symbol in the glossary is "you"
        if not self.g or n.quant is not None:
            return False
        h = n.heads[0]
        players = [i for i, s in enumerate(self.g.symbols) if s.syntax.get("kind") == "player"]
        return bool(players) and h.index == players[0]

    def expected(self, rec: _Rec) -> str | None:
        p = rec.parent
        if isinstance(p, A.Of) and rec.slot == "of":
            return "object"
        if isinstance(p, A.Characteristic) and not p.prefix:
            return "object"
        if isinstance(p, A.Rel):
            o = self.op_of(p.rel)
            if o in ("control", "own"):
                return "player"
            if o == "other":
                return "object"
            if self.kind_of(p.rel) == "comparison":
                return "counter"      # ⊞=☞ — a counter of that kind
            if self.kind_of(p.rel) in ("verb", "keyword"):
                return "object"       # ❐☞ a copy of it, ◉☞ revealed this way
        if isinstance(p, A.Zone) or isinstance(p, A.Time):
            return "player"
        if isinstance(p, A.Compare) and any(isinstance(x, A.Characteristic) for x in p.items):
            return "value"            # ⁿ = ☞ — the chosen name
        if isinstance(p, A.Modify) and isinstance(p.change, A.Delta) and p.change.char is not None \
                and self.op_of(p.change.char) == "life" and rec.slot == "subject":
            return "player"
        if isinstance(p, A.Modify) and isinstance(p.change, A.PT) and rec.slot == "subject":
            return "object"
        if isinstance(p, A.Action) and rec.slot == "subject" and isinstance(p.verb, A.SymRef) \
                and (self.op_of(p.verb) == "has" or self.op_of(p.verb) == "transfer"
                     and any(s == "object" and isinstance(x, A.NP) and self.head_op(x) == "damage"
                             for s, x in p.args)):
            return "object"
        if isinstance(p, A.Action) and rec.slot == "subject" and isinstance(p.verb, A.SymRef) \
                and self.op_of(p.verb) == "is":
            return "object"
        if isinstance(p, A.Action) and rec.slot == "object":
            return "object"
        return None


def resolve_card(card: A.Card, g) -> tuple[A.Card, list[ResolveProblem]]:
    """Return a copy of ``card`` with resolution fields filled in, plus the problems found."""
    r = _Resolver(g)
    changes: dict[str, dict] = {}
    problems: list[ResolveProblem] = []
    for fi, face in enumerate(card.faces):
        choices: list = []
        for ai, ability in enumerate(face.abilities):
            recs: list[_Rec] = []
            _records(ability, f"faces.{fi}.abilities.{ai}", {}, recs)
            _resolve_ability(r, recs, changes, problems, choices)
    return _apply(card, "", changes), problems




def _resolve_ability(r: _Resolver, recs: list[_Rec], changes: dict, problems: list, choices: list):
    by_path = {rec.path: rec for rec in recs}
    by_path.update({c.path: c for c, _ in choices})
    candidates: list[tuple[_Rec, str]] = []
    # event participants of each trigger / replacement: the first ☞ of its effect prefers them
    events: list[tuple[str, list]] = []
    for rec in recs:
        n = rec.node
        ev_node = n.event if isinstance(n, (A.Triggered, A.Replace)) else None
        if isinstance(ev_node, A.Action):
            eff = rec.path + (".effect")
            parts = []
            ev_path = rec.path + ".event"
            if ev_node.subject is not None:
                parts.append(ev_path + ".subject")
            seen: dict[str, int] = {}
            for slot, _x in ev_node.args:
                k = seen.get(slot, 0)
                seen[slot] = k + 1
                if slot == "object":
                    parts.append(f"{ev_path}.args.{slot}" + (str(k + 1) if k else ""))
            cands = [(by_path[p_], r.candidate_kind(by_path[p_])) for p_ in parts if p_ in by_path]
            events.append((eff, [(c_, k_) for c_, k_ in cands if k_ is not None]))
    first_seen: dict[str, bool] = {}

    def event_of(path: str):
        best = None
        for eff, cands in events:
            if path.startswith(eff + ".") and (best is None or len(eff) > len(best[0])):
                best = (eff, cands)
        return best

    antecedent: dict[str, str] = {}
    for rec in recs:
        n = rec.node
        if isinstance(n, A.NP):
            quantity, number = r.classify(n, rec.ctx)
            changes.setdefault(rec.path, {}).update(quantity=quantity, number=number)
            if r.is_that(n):
                want = r.expected(rec)
                target = None
                own_subject = None
                own_root = None
                if isinstance(rec.parent, A.Action) and rec.slot not in ("subject",) \
                        and rec.parent.subject is not None:
                    own_subject = rec.path.rsplit(".args.", 1)[0] + ".subject"
                    own_root = antecedent.get(own_subject)
                ev = event_of(rec.path)
                if ev is not None and not first_seen.get(ev[0]):
                    first_seen[ev[0]] = True
                    for cand, kind in ev[1]:
                        if kind == want or (want is None and kind not in ("counter", "value")):
                            target = cand
                            break
                for cand, kind in reversed(candidates):
                    if target is not None:
                        break
                    if rec.path.startswith(cand.path + "."):
                        continue           # an enclosing phrase
                    root_ = antecedent.get(cand.path, cand.path)
                    if own_subject and (cand.path == own_subject or (own_root is not None and root_ == own_root)
                                        or root_ == own_subject):
                        continue           # "X deals damage to it" — it isn't X
                    if kind == want or (want is None and kind != "counter") or (kind == "any" and want != "counter"):
                        target = cand
                        break
                if target is None:
                    for cand, kind in reversed(choices):       # a choice made by another ability of the card
                        if want in (None, kind):
                            target = cand
                            break
                if target is None:
                    problems.append(ResolveProblem(rec.path, "☞ has no antecedent"))
                else:
                    root = antecedent.get(target.path, target.path)
                    antecedent[rec.path] = root
                    tgt = by_path.get(root)
                    num = changes.get(root, {}).get("number") if tgt is not None else None
                    changes[rec.path].update(antecedent=root, number=num or "sg")
                    if not isinstance(rec.parent, (A.Zone, A.Rel, A.Characteristic, A.Of, A.Time)) \
                            and not rec.ctx.get("filter"):
                        candidates.append((rec, r.candidate_kind(by_path[root]) or "object"))
                continue
        kind = r.candidate_kind(rec)
        if kind is not None:
            candidates.append((rec, kind))
            if r._is_choice(rec.parent):
                choices.append((rec, kind))
        if isinstance(n, A.Coord):
            items = n.items
            first_subj = getattr(items[0], "subject", None) if items else None
            for k, item in enumerate(items[1:], start=1):
                if isinstance(item, (A.Action, A.Modify)) and item.subject is None and first_subj is not None:
                    changes.setdefault(f"{rec.path}.items.{k}", {})["implicit_subject"] = "shared"
        if isinstance(n, (A.Action, A.Modify)) and n.subject is None and not rec.ctx.get("filter") \
                and not rec.ctx.get("count") and rec.slot not in ("state", "restrict", "restrict_not", "cost") \
                and not (isinstance(n, A.Action) and n.verb is not None and _is_limit(r, n)):
            changes.setdefault(rec.path, {}).setdefault("implicit_subject", "controller")


def _is_limit(r: _Resolver, n: A.Action) -> bool:
    return isinstance(n.verb, A.SymRef) and r.op_of(n.verb) == "only"


def _apply(node, path: str, changes: dict):
    if not isinstance(node, A.Node):
        return node
    upd = {}
    for suffix, child, slot in _children(node):
        sub = f"{path}.{suffix}" if path else suffix
        new = _apply(child, sub, changes)
        if new is not child:
            upd[suffix] = new
    fields: dict = {}
    for suffix, new in upd.items():
        name, _, rest = suffix.partition(".")
        if name == "args":
            fields.setdefault("args", list(node.args))
            seen: dict[str, int] = {}
            for i, (slot, child) in enumerate(node.args):
                k = seen.get(slot, 0)
                seen[slot] = k + 1
                if slot + (str(k + 1) if k else "") == rest:
                    fields["args"][i] = (slot, new)
        elif rest:
            fields.setdefault(name, list(getattr(node, name)))
            fields[name][int(rest)] = new
        else:
            fields[name] = new
    for k, v in list(fields.items()):
        if isinstance(v, list):
            fields[k] = tuple(v)
    own = changes.get(path, {})
    valid = {f.name for f in dataclasses.fields(node)}
    fields.update({k: v for k, v in own.items() if k in valid})
    return dataclasses.replace(node, **fields) if fields else node
