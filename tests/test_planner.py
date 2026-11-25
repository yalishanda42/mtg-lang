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


def test_coordinated_same_subject_is_shared():
    ev = plan("fra/aerid-konstrari").faces[0].abilities[1].parts["event"]
    assert [c.subject_shared for c in ev.clauses] == [False, True]
    assert ev.clauses[1].subject.ref == "self"                  # the full subject is kept


def test_self_as_spell_when_cast():
    ev = plan("fra/emrakul-the-exigent-doom").faces[0].abilities[0].parts["event"]
    (obj,) = [v for s, v in ev.args if s == "object"]
    assert obj.ref == "self" and obj.self_as == "spell"


def test_self_as_card_in_a_zone():
    a = plan("fra/emrakul-the-exigent-doom").faces[0].abilities[3]   # {3}, exile this card from your hand
    cost = a.parts["cost"][1]
    (obj,) = [v for s, v in cost.args if s == "object"]
    assert obj.self_as == "card"


def test_modal_inside_effect():
    eff = plan("fra/archive-arbiter").faces[0].abilities[1].parts["effect"]
    (m,) = eff.clauses
    assert isinstance(m, AbilityPlan) and m.shape == "modal" and len(m.parts["modes"]) == 2


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
                "value", "text", "dash", "implicit_subject", "self_as", "aspect"}


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


def test_cost_action_is_imperative():
    a = plan("trk/dal-rel-augment-orphan").faces[0].abilities[1]      # {3}, ✝⛰ : ⤓1
    sac = a.parts["cost"][1]
    assert sac.mood == "imperative" and sac.subject.implicit


def test_has_in_static_ability_of_permanent_is_state():
    a = plan("fra/ferocity-of-the-hunt").faces[0].abilities[2]      # Enchanted creature gets +1/+0 and has deathtouch.
    has = [n for n in nodes(a) if isinstance(n, ClausePlan) and getattr(n.pred, "glyph", "") == "∋"]
    assert has and all(c.aspect == "state" for c in has)


def test_gains_with_duration_is_change():
    a = plan("fra/academic-ascent").faces[0].abilities[0]           # … gains flying until end of turn (instant)
    has = [n for n in nodes(a) if isinstance(n, ClausePlan) and getattr(n.pred, "glyph", "") == "∋"]
    assert has and all(c.aspect == "change" for c in has)


def test_condition_this_turn_is_past():
    a = plan("fra/traxos-academy-guardian").faces[0].abilities[0]   # … if you've cast a noncreature spell this turn
    cond = a.parts["body"].clauses[0].clauses[0] if isinstance(a.parts["body"].clauses[0], SentencePlan) \
        else a.parts["body"].clauses[0]
    past = [n for n in nodes(a) if isinstance(n, ClausePlan) and n.tense == "past"]
    assert past and getattr(past[0].pred, "glyph", "") == "✷"
    del cond


def test_mode_body_is_an_effect():
    a = plan("fra/fateshaper-aspirant")                             # • … It gains vigilance and indestructible …
    has = [n for n in nodes(a) if isinstance(n, ClausePlan) and getattr(n.pred, "glyph", "") == "∋"]
    assert has and all(c.aspect == "change" for c in has)


def test_trigger_once_vs_repeated():
    assert plan("fra/aerid-konstrari").faces[0].abilities[1].parts["once"] is True        # enters or dies
    assert plan("fra/afterthought-sentry").faces[0].abilities[1].parts["once"] is False   # attacks
    assert plan("fra/emrakul-the-exigent-doom").faces[0].abilities[0].parts["once"] is True  # cast this spell
    assert plan("fra/ferocity-of-the-hunt").faces[0].abilities[3].parts["once"] is True   # enchanted creature dies
