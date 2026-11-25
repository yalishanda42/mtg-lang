"""Resolution pass: NP quantity/number, ☞ antecedents, implicit subjects."""
from pathlib import Path

from mtglang import ast as A
from mtglang.ast import walk
from mtglang.glossary import load_glossary
from mtglang.resolve import resolve_card
from mtglang.semparse import SemParser
from mtglang.unparse import Unparser

ROOT = Path(__file__).parent.parent
G = load_glossary(ROOT / "glossary")
P = SemParser(G)
U = Unparser(G)


def card(*lines):
    return A.Card((A.Face(A.NameRef("T"), (), A.TypeLine(), None, tuple(P.parse_ability(l) for l in lines)),))


def resolved(*lines):
    c, problems = resolve_card(card(*lines), G)
    return c, problems


def nps(c, text):
    """Resolved NPs whose unparse equals text."""
    return [n for _, n in walk(c) if isinstance(n, A.NP) and U.node(n) == text]


def at(c, path):
    return dict(walk(c))[path]


def test_static_bare_np_is_all():
    c, _ = resolved("♞[⚑●] +1/+0 ⧗")
    (np,) = nps(c, "♞[⚑●]")
    assert (np.quantity, np.number) == ("all", "pl")


def test_trigger_bare_np_is_one():
    c, _ = resolved("⛰[⚑●]↥ ⇒ ● ♥+1")
    (np,) = nps(c, "⛰[⚑●]")
    assert (np.quantity, np.number) == ("one", "sg")


def test_target_is_one():
    c, _ = resolved("✖ ◎▣[⚑○]")
    (np,) = nps(c, "◎▣[⚑○]")
    assert (np.quantity, np.number) == ("one", "sg")


def test_up_to():
    c, _ = resolved("↶ ≤2◎⛰")
    (np,) = nps(c, "≤2◎⛰")
    assert (np.quantity, np.number) == ("up_to", "pl")


def test_each_is_singular():
    c, _ = resolved("∀○ ⌫1")
    (np,) = nps(c, "∀○")
    assert (np.quantity, np.number) == ("each", "sg")


def test_count_is_plural():
    c, _ = resolved("⤓X ; X ≔ #≢ ⛰[⚑●]")
    (np,) = nps(c, "⛰[⚑●]")
    assert (np.quantity, np.number) == ("count", "pl")


def test_that_refers_to_previous_target():
    c, problems = resolved("◎♞ +2/+0 ∧ ∋↟ ⧗ ; ⊞+1/+1 → ☞")
    assert problems == []
    (that,) = nps(c, "☞")
    assert at(c, that.antecedent) == nps(c, "◎♞")[0]


def test_that_controller_refers_to_object():
    c, problems = resolved("✖ ◎♞ ; ¬☞➹ ⊃ ☞⚑ ⤓1")
    assert problems == []
    targets = {at(c, n.antecedent) for n in nps(c, "☞")}
    assert targets == {nps(c, "◎♞")[0]}


def test_that_in_trigger_refers_to_event():
    c, problems = resolved("⛶ ▸ ⛰[⚑●]↥ ⇒ ◈ ✸1 → ∀○ ; ☞ ∈ «Mountain» ⊃ ⊕{R}")
    assert problems == []
    (that,) = nps(c, "☞")
    assert at(c, that.antecedent) == nps(c, "⛰[⚑●]")[0]


def test_that_player_in_filter():
    c, problems = resolved("(∀○) ✖ ≤1◎♞[⚑☞]")
    (that,) = nps(c, "☞")
    assert at(c, that.antecedent) == nps(c, "∀○")[0]


def test_unless_condition_refers_back_to_then():
    c, problems = resolved("⊗ ◎✦[¬♞] ¬⊃ ☞⚑ ⊷{2}")
    assert problems == []
    (that,) = nps(c, "☞")
    assert at(c, that.antecedent) == nps(c, "◎✦[¬♞]")[0]


def test_unresolvable_that_is_problem():
    c, problems = resolved("✖ ☞")
    assert len(problems) == 1 and "☞" in problems[0].message


def test_implicit_subject():
    c, _ = resolved("◎♞ +2/+0 ∧ ∋↟ ⧗ ; ⤓1")
    acts = [n for _, n in walk(c) if isinstance(n, A.Action)]
    has, draw = acts
    assert has.implicit_subject == "shared" and draw.implicit_subject == "controller"


def test_resolution_does_not_change_unparse():
    lines = ["◎♞ +2/+0 ∧ ∋↟ ⧗ ; ⊞+1/+1 → ☞", "⛶ ▸ ⛰[⚑●]↥ ⇒ ◈ ✸1 → ∀○ ; ☞ ∈ «Mountain» ⊃ ⊕{R}"]
    before = card(*lines)
    after, _ = resolve_card(before, G)
    assert [U.node(a) for a in after.faces[0].abilities] == [U.node(a) for a in before.faces[0].abilities]


def test_that_refers_to_result_of_keyword_action():
    c, problems = resolved("⌕1 ; ☞ ∈ ▭[¬♞ ¬⛰] ∧ ☞ → ⚰ ⊃ ☞ → ☚●")
    assert problems == []
    act = next(n for _, n in walk(c) if isinstance(n, A.Action) and U.node(n.verb) == "⌕")
    assert all(at(c, n.antecedent) == act for n in nps(c, "☞"))


def test_that_refers_to_choice():
    c, problems = resolved("⊻ ⊤♞ ; ✖ ∀♞[¬☞]")
    assert problems == []
    (that,) = nps(c, "☞")
    assert isinstance(at(c, that.antecedent), A.Characteristic)


def test_that_refers_to_choice_in_earlier_ability():
    c, problems = resolved("◈↥ ⤳ ⊻♦", "{T} : ⊕♦☞")
    assert problems == []
    (that,) = nps(c, "☞")
    assert at(c, that.antecedent).char.glyph == "♦"


def test_copy_of_that_inside_filter():
    c, problems = resolved("(∀♞[⚑◎◐]) ✚ ◌[❐☞] ∋↯")
    assert problems == []
    (that,) = nps(c, "☞")
    assert U.node(at(c, that.antecedent)) == "∀♞[⚑◎◐]"


def test_counter_of_that_kind():
    c, problems = resolved("{2} : ⊻ ⊞[◎✧[⚑●]] ; ⊞=☞ → ☞ ; ≡✎")
    assert problems == []
    kind_ref, dest = nps(c, "☞")
    assert U.node(at(c, kind_ref.antecedent)) == "⊞[◎✧[⚑●]]"
    assert U.node(at(c, dest.antecedent)) == "◎✧[⚑●]"


def test_lone_all_is_not_a_referent():
    c, problems = resolved("♞[⚭◈] ∌∀ ∧ ¬↶ ◒☞⚑")
    (that,) = nps(c, "☞")
    assert U.node(at(c, that.antecedent)) == "♞[⚭◈]"


def test_trigger_effect_prefers_event_subject():
    c, _ = resolved("−4 : (♞➹ → ○ ⇒ ☞ +2/+2 ∧ ∋⇶ ⧗) ⊣▷◷●")
    (that,) = nps(c, "☞")
    assert U.node(at(c, that.antecedent)) == "♞"
    c, _ = resolved("♞[⚑●]➹∘ → ◐ ⇒ ☞ ∋⇈ ⧗")
    (that,) = nps(c, "☞")
    assert U.node(at(c, that.antecedent)) == "♞[⚑●]"


def test_object_is_not_its_own_subject():
    c, _ = resolved("◎(♞ ∨ ⚝)[⚑○] ∌∀ ⧗ ; ◎♞[⚑●] ✸☞△ → ☞")
    power_of, dest = nps(c, "☞")
    assert U.node(at(c, power_of.antecedent)) == "◎♞[⚑●]"
    assert U.node(at(c, dest.antecedent)) == "◎(♞ ∨ ⚝)[⚑○]"


def test_counted_things_are_not_referents():
    c, _ = resolved("✚2 ◌[2/2 ♦∅ «Wizard» «Soldier» ♞] «Cadet» ; ◈ ✷[⚰] ⊃ ⊞+1/+1 × (#▭[⚰●] ÷ 3) → ∀☞")
    (that,) = nps(c, "∀☞")
    assert at(c, that.antecedent).heads[0].glyph == "◌"


def test_only_yielding_actions_are_referents():
    c, _ = resolved("∀♞ → ⊘ ; ⟁X ; X ≔ #☞")
    (that,) = nps(c, "☞")
    assert U.node(at(c, that.antecedent)) == "∀♞"


def test_negated_type_and_exists_are_not_referents():
    c, _ = resolved("◈↥ ⤳ ● ? (◈ ❐ (⚙ ∨ ♞)[▦] ∧ ¬⚜) ; ✓ ⊃ ◈ ↥⊞[☞]")
    (that,) = nps(c, "☞")
    assert U.node(at(c, that.antecedent)) == "(⚙ ∨ ♞)[▦]"
    c, _ = resolved("♞[⚑●]↥ ∵ ∃♞[⚑● ➹] ⤳ ☞ ↥↷➹")
    (that,) = nps(c, "☞")
    assert U.node(at(c, that.antecedent)) == "♞[⚑●]"


def test_zone_wins_over_its_owner():
    c, _ = resolved("● ◓ ⌃2▤☞ ∧ ☞ → ⊘▼".replace("☞ ∧", "◎○ ∧", 1))
    (that,) = nps(c, "☞")
    assert U.node(at(c, that.antecedent)) == "⌃2▤◎○"


def test_object_slot_prefers_things():
    c, _ = resolved("◈↥ ⇒ (∀○) ● ⇄ ≤1◎♞[⚑☞ ⌀ ≤ 3] ⧗ ; ↶ ∀☞")
    (_, all_them) = [n for _, n in walk(c) if isinstance(n, A.NP) and n.antecedent]
    assert U.node(at(c, all_them.antecedent)) == "≤1◎♞[⚑☞ ⌀ ≤ 3]"


def test_its_owner_exiles_it():
    c, _ = resolved("● ? ⊻ ▭[¬⛰] ; ✓ ⊃ ☞⌂ ☞ → ⊘")
    a, b = [n for _, n in walk(c) if isinstance(n, A.NP) and n.antecedent]
    assert U.node(at(c, a.antecedent)) == U.node(at(c, b.antecedent)) == "▭[¬⛰]"


def test_create_a_copy_of_this():
    c, problems = resolved("▭[☚●] → ⊘ : ✚ ❐◈ ; ● ? ✷☞")
    assert problems == []
    act = next(n for _, n in walk(c) if isinstance(n, A.Action) and U.node(n.verb) == "✚")
    assert isinstance(dict(act.args)["object"], A.Action)
    (that,) = nps(c, "☞")
    assert isinstance(at(c, that.antecedent), A.Action)
