"""Language-neutral planner: resolved AST → clause plans."""
from dataclasses import fields, is_dataclass
from pathlib import Path

import pytest

from mtglang import ast as A
from mtglang import planner
from mtglang.astexport import card_ast
from mtglang.glossary import load_glossary
from mtglang.planir import AbilityPlan, ClausePlan, Gap, PhrasePlan, SentencePlan

ROOT = Path(__file__).parent.parent
G = load_glossary(ROOT / "glossary")


def plan(ref):
    c = card_ast(ROOT, ref)
    return planner.plan_card(c, [planner.context_for(c, i, G) for i in range(len(c.faces))], G)


def nodes(obj):
    """Every dataclass instance reachable from obj."""
    if is_dataclass(obj) and not isinstance(obj, type):
        yield obj
        for f in fields(obj):
            yield from nodes(getattr(obj, f.name))
    elif isinstance(obj, (tuple, list)):
        for x in obj:
            yield from nodes(x)
    elif isinstance(obj, dict):
        for x in obj.values():
            yield from nodes(x)


def test_plan_keywords():
    a = plan("fra/aerid-konstrari").faces[0].abilities[0]
    assert a.shape == "keywords"
    (kw,) = a.parts["items"]
    assert kw.sym.glyph == "🪽"


def test_plan_triggered_parts():
    a = plan("fra/afterthought-sentry").faces[0].abilities[1]
    assert a.shape == "triggered"
    ev = a.parts["event"]
    assert isinstance(ev, ClausePlan)
    assert ev.subject.ref == "self"
    assert isinstance(a.parts["effect"], SentencePlan)


def test_implicit_controller_is_imperative_you():
    a = plan("trk/dal-rel-augment-orphan").faces[0].abilities[1]
    (cl,) = a.parts["effect"].clauses
    assert cl.mood == "imperative" and cl.subject.ref == "you" and cl.subject.implicit


def test_explicit_you_is_indicative():
    a = plan("fra/ajani-resolute").faces[0].abilities[1]
    (cl,) = a.parts["effect"].clauses
    assert cl.mood == "indicative" and cl.subject.ref == "you" and not cl.subject.implicit


def test_anaphor_keeps_antecedent():
    p = plan("fra/codie-ravenous-codex")
    ana = [n for n in nodes(p) if isinstance(n, PhrasePlan) and n.ref == "anaphor"]
    assert ana and all(isinstance(n.antecedent, PhrasePlan) and n.antecedent.ref != "anaphor" for n in ana)


def test_self_second_mention_is_pronoun():
    a = plan("fra/aerid-konstrari").faces[0].abilities[1]      # (◈↥ ∨ ◈☠) ⇒ …: "enters or dies"
    selfs = [n for n in nodes(a) if isinstance(n, PhrasePlan) and n.ref == "self"]
    assert [s.pronoun for s in selfs] == [False, True]
    assert selfs[1].reason


def test_bind_sentence_joins_with_where():
    a = plan("fra/aerid-konstrari").faces[0].abilities[2]      # …; X ≔ #⚙[⚑●]
    assert [j.kind for j in a.parts["effect"].joins] == ["sentence", "where"]


def test_unknown_kind_is_gap(monkeypatch):
    monkeypatch.delitem(planner.SENTENCE_KINDS, A.Modify)
    a = plan("fra/academic-ascent").faces[0].abilities[0]
    gaps = [n for n in nodes(a) if isinstance(n, Gap)]
    assert gaps and gaps[0].kind == "modify" and gaps[0].path


# str fields a plan may carry: AST spelling-free values, plan enums, and names (keys, not words)
_ALLOWED_STR = {"path", "kind", "reason", "shape", "mood", "tense", "number", "quantity", "ref", "lead",
                "name", "short", "cost", "glyph", "key", "sign", "op", "mode", "stat", "power", "toughness",
                "value", "text", "dash", "implicit_subject"}


def test_no_english_in_plan():
    from mtglang.astexport import corpus_asts
    for code, slug, c, err in corpus_asts(ROOT):
        assert c is not None, (code, slug, err)
        p = planner.plan_card(c, [planner.context_for(c, i, G) for i in range(len(c.faces))], G)
        for n in nodes(p):
            for f in fields(n):
                v = getattr(n, f.name)
                if isinstance(v, str):
                    assert f.name in _ALLOWED_STR, (slug, type(n).__name__, f.name, v)
