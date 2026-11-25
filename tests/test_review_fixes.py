"""Regression tests for the final-review findings."""
from pathlib import Path

import pytest

from mtglang.ast import to_json
from mtglang.glossary import load_glossary
from mtglang.semparse import SemParser, SemSyntaxError

ROOT = Path(__file__).parent.parent
G = load_glossary(ROOT / "glossary")
P = SemParser(G)


@pytest.mark.parametrize("line", ["⊢ 1", "⊢ (", "⊢ [", "◈ ⊢ 1 → ◎ ○", "✖ (∨)▤", "→ (∨)▤"])
def test_malformed_lines_raise_syntax_errors_not_crashes(line):
    with pytest.raises(SemSyntaxError):
        P.parse_ability(line)


def test_mode_without_choice_is_s_parse_not_a_crash(tmp_path):
    import shutil
    from mtglang.validate import validate_all
    root = tmp_path / "r"
    shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(".git", "build", ".venv", ".superpowers"))
    p = root / "cards/fra/archive-arbiter.mtgl"
    p.write_text(p.read_text(encoding="utf-8").replace("◈↥ ⇒ ⊻1", "◈↥ ⇒ ✖ ◎♞"), encoding="utf-8")
    issues, _ = validate_all(root, sets=["fra"])
    bad = [i for i in issues if i.code == "S-PARSE" and i.file.endswith("archive-arbiter.mtgl")]
    assert bad and bad[0].line == 7


@pytest.mark.parametrize("line", ["✖ ◎♞ ⤓1", "✖ ◎♞ ✖ ◎♞"])
def test_verb_after_arguments_is_an_error(line):
    with pytest.raises(SemSyntaxError):
        P.parse_ability(line)


def test_loyalty_minus_same_ast_in_ascii():
    from mtglang.tokenizer import to_ascii
    line = "−4 : ✚ ◌«Treasure»"
    assert to_json(P.parse_ability(line)) == to_json(P.parse_ability(to_ascii(line, G)))
    tl = "⚜♞ — «Human»"
    assert to_json(P.parse_type_line(tl)) == to_json(P.parse_type_line(to_ascii(tl, G)))


def test_you_is_declared_not_positional():
    assert G.lookup["●"].syntax.get("op") == "you"


def test_passive_agent_and_types_number():
    from mtglang import ast as A
    from mtglang.ast import walk
    from mtglang.resolve import resolve_card
    from mtglang.unparse import Unparser
    U = Unparser(G)
    card = A.Card((A.Face(A.NameRef("T"), (), A.TypeLine(), None,
                          (P.parse_ability("◈ ¬⛉← ♞[△ ≤ 2]"), P.parse_ability("◈ ≔ ♞«Construct»"))),))
    c, _ = resolve_card(card, G)
    got = {U.node(n): (n.quantity, n.number) for _, n in walk(c) if isinstance(n, A.NP)}
    assert got["♞[△ ≤ 2]"] == ("all", "pl")
    assert got["♞«Construct»"][0] == "kind"
