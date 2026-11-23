from conftest import (BEAR_RAW, FIXTURES as FX, VIGORBLOOM_RAW, add_name, add_raw_card, codes_of, drop_last_line,
                      edit, only, write_card)
from mtglang.glossary import sync_names
from mtglang.validate import validate_all


def errors(result):
    return [i for i in result[0] if i.severity == "error"]


def test_fixture_project_valid():
    issues, stats = validate_all(FX)
    assert [i for i in issues if i.severity == "error"] == []
    assert stats["cards"] == 1 and stats["ability_lines"] == 2 and stats["named_effect_rate"] == 0.0


def test_header_mismatches(fx_copy):
    edit(fx_copy, "{1}{R}{G}", "{R}{G}")
    edit(fx_copy, "3/3", "3/4")
    edit(fx_copy, "«Rogue»", "«Human»")
    assert {"V-MANA", "V-STATS", "V-TYPE"} <= codes_of(validate_all(fx_copy))


def test_card_name_mismatch(fx_copy):
    edit(fx_copy, "«Dal R'El, Augment Orphan» {1}", "«Human» {1}")
    assert "V-CARDNAME" in codes_of(validate_all(fx_copy))


def test_alignment_and_missing_and_orphan(fx_copy):
    drop_last_line(fx_copy)
    add_raw_card(fx_copy, "trk", BEAR_RAW)
    write_card(fx_copy, "trk/ghost.mtgl", "«Ghost» {1}\n☺\n1/1\n")
    result = validate_all(fx_copy)
    assert {"V-ALIGN", "V-MISSING", "V-ORPHAN", "V-NAME-UNKNOWN"} <= codes_of(result)
    assert "1 notation line(s) but 2 Oracle line(s)" in only(result, "V-ALIGN").message
    assert "V-MISSING" not in codes_of(validate_all(fx_copy, only_existing=True))


def test_vanilla_card_passes(fx_copy):
    add_raw_card(fx_copy, "trk", BEAR_RAW)
    add_name(fx_copy, "Test Bear", "card")
    add_name(fx_copy, "Bear")
    write_card(fx_copy, "trk/test-bear.mtgl", "«Test Bear» {1}{G}\n☺ — «Bear»\n2/2\n")
    assert errors(validate_all(fx_copy)) == []


def test_face_count_mismatch_is_issue_not_crash(fx_copy):
    add_raw_card(fx_copy, "fra", VIGORBLOOM_RAW)
    write_card(fx_copy, "fra/vigorbloom-vanguard-seed-suture.mtgl", "«Vigorbloom Vanguard» {1}{G/W}\n☺\n2/2\n\nF\nF\n")
    assert "V-FACES" in codes_of(validate_all(fx_copy))


def test_word_in_line_reports_position(fx_copy):
    edit(fx_copy, "✋1", "Draw 1")
    issue = only(validate_all(fx_copy), "C-SYNTAX")
    assert (issue.line, issue.col) == (7, 11) and "natural-language word" in issue.message


def test_unknown_effect(fx_copy):
    edit(fx_copy, "✋1", "⟨no-such⟩")
    assert "V-EFFECT-UNKNOWN" in codes_of(validate_all(fx_copy))


def test_consistency(fx_copy):
    other = dict(BEAR_RAW, name="Other Land Eater", oracle_text="{3}, Sacrifice a land: Draw a card.")
    add_raw_card(fx_copy, "trk", other)
    write_card(fx_copy, "trk/other-land-eater.mtgl", "«Other Land Eater» {1}{G}\n☺ — «Bear»\n2/2\n\n{3}, Sa Ld : Dr 1\n")
    add_name(fx_copy, "Bear")
    assert "V-CONSISTENCY" not in codes_of(validate_all(fx_copy))
    edit(fx_copy, "Dr 1", "Dr 2", rel="cards/trk/other-land-eater.mtgl")
    issue = only(validate_all(fx_copy), "V-CONSISTENCY")
    assert "other-land-eater" in issue.message and "dal-rel-augment-orphan" in issue.message


def test_effect_rate_warning(fx_copy):
    p = fx_copy / "glossary" / "named_effects.yaml"
    p.write_text('- {key: "x", card: "Dal", labels: {en: "x"}}\n')
    edit(fx_copy, "✋1", "⟨x⟩")
    result = validate_all(fx_copy)
    assert "V-EFFECT-RATE" in codes_of(result) and result[1]["named_effect_rate"] == 0.5


def test_bad_definition(fx_copy):
    edit(fx_copy, '"◈ ≤ [☺ F]"', '"◈ fly"', rel="glossary/symbols.yaml")
    assert "G-DEF" in codes_of(validate_all(fx_copy))


def test_sync_names_adds_once(fx_copy):
    add_raw_card(fx_copy, "trk", BEAR_RAW)
    assert sync_names(fx_copy) == 2
    assert sync_names(fx_copy) == 0
    assert "Test Bear" in (fx_copy / "glossary/names.yaml").read_text()


def test_cli_validate_exit_codes(fx_copy, capsys):
    from mtglang.cli import main
    assert main(["validate", "--root", str(FX)]) == 0
    drop_last_line(fx_copy)
    assert main(["validate", "--root", str(fx_copy)]) == 1
    assert "V-ALIGN" in capsys.readouterr().out


def test_ascii_type_line_validates(fx_copy):
    edit(fx_copy, "⚜☺ — «Human» «Mutant» «Rogue»", "LgCr - <<Human>> <<Mutant>> <<Rogue>>")
    assert errors(validate_all(fx_copy)) == []
