from conftest import FIXTURES as FX
from mtglang.cardfile import parse_card_file

DAL = FX / "cards/trk/dal-rel-augment-orphan.mtgl"


def test_card_file_fixture(lp):
    doc, issues = parse_card_file(DAL, lp)
    assert issues == [] and doc.slug == "dal-rel-augment-orphan" and doc.set_code == "trk"
    f = doc.faces[0]
    assert (f.name, f.mana, f.stats, len(f.abilities)) == ("Dal R'El, Augment Orphan", "{1}{R}{G}", "3/3", 2)
    assert f.abilities[1].lineno == 7 and f.header_lineno == 2
    assert f.type_line == "⚜☺ — «Human» «Mutant» «Rogue»"


def test_crlf_and_trailing_space_identical(lp, tmp_path):
    src = DAL.read_text()
    p = tmp_path / "trk" / "dal-rel-augment-orphan.mtgl"
    p.parent.mkdir()
    p.write_text(src.replace("\n", "  \r\n").rstrip())
    a, _ = parse_card_file(DAL, lp)
    b, ib = parse_card_file(p, lp)
    assert ib == [] and [x.text for x in a.faces[0].abilities] == [x.text for x in b.faces[0].abilities]
    assert b.faces[0].stats == "3/3"


def test_two_faces_and_syntax_issue(lp, tmp_path):
    p = tmp_path / "fra" / "two.mtgl"
    p.parent.mkdir()
    p.write_text("«A» {1}\n☺\n2/2\n\nF\n//\n«Seed Suture» {G/W}\n✎\n\n✋1 ⇒\n")
    doc, issues = parse_card_file(p, lp)
    assert [i.code for i in issues] == ["C-SYNTAX"]
    assert issues[0].line == 10 and issues[0].col == 5
    assert len(doc.faces) == 2 and doc.faces[1].mana == "{G/W}" and doc.faces[1].stats is None
    assert doc.faces[1].abilities[0].tree is None


def test_vanilla_land_no_mana(lp, tmp_path):
    p = tmp_path / "fra" / "forest.mtgl"
    p.parent.mkdir()
    p.write_text("«Forest»\n⛰ — «Forest»\n")
    doc, issues = parse_card_file(p, lp)
    assert issues == [] and doc.faces[0].mana == "" and doc.faces[0].abilities == []


def test_loyalty_stats_and_bad_header(lp, tmp_path):
    p = tmp_path / "fra" / "pw.mtgl"
    p.parent.mkdir()
    p.write_text("«A» {1}\n⚜☺\n◇ 4\n\n−1 : ✋1\n")
    doc, _ = parse_card_file(p, lp)
    assert doc.faces[0].stats == "◇ 4"
    p.write_text("{1} «A»\n☺\n")
    doc, issues = parse_card_file(p, lp)
    assert doc is None and [i.code for i in issues] == ["C-HEADER"] and issues[0].line == 1
    p.write_text("# only a comment\n\n")
    assert [i.code for i in parse_card_file(p, lp)[1]] == ["C-EMPTY"]


def test_indented_line_error_col_is_file_col(lp, tmp_path):
    p = tmp_path / "fra" / "ind.mtgl"
    p.parent.mkdir()
    p.write_text("«A» {1}\n☺\n\n  ✋1 ⇒ ⇒\n")
    issues = parse_card_file(p, lp)[1]
    assert (issues[0].line, issues[0].col) == (4, 8)
