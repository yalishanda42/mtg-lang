"""Bulgarian realizer (sample round)."""
from pathlib import Path

import pytest

from mtglang.realize.bg import load_sample, render_card_bg

ROOT = Path(__file__).parent.parent
SAMPLE = load_sample(ROOT)


def test_sample_list():
    assert 20 <= len(SAMPLE) <= 30
    assert {r.split("/")[0] for r in SAMPLE} == {"fra", "trk"}
    for r in SAMPLE:
        assert (ROOT / "cards" / f"{r}.mtgl").exists(), r


def test_cli_bg_prints_name_and_lines(capsys):
    from mtglang.cli import main
    assert main(["bg", "fra/unsummon", "--root", str(ROOT), "--modern"]) == 0
    out = capsys.readouterr().out.strip().split("\n")
    assert len(out) >= 6          # old: name, type, line; modern: name, type, line


@pytest.mark.parametrize("ref", SAMPLE)
def test_sample_has_no_gaps(ref):
    for f in render_card_bg(ROOT, ref):
        for text in (f.name, f.type_line, *f.lines, f.old.name, f.old.type_line, *f.old.lines):
            assert "⟦" not in text, (ref, text)


def lines(ref, face=0):
    return render_card_bg(ROOT, ref)[face].lines


def test_feminine_agreement():
    assert lines("fra/academic-ascent")[0].startswith("Посочена твар получава")       # adjective
    assert "до една посочена карта" in lines("fra/afterthought-sentry")[1]            # numeral
    assert "Когато тая твар встъпи" in lines("fra/archive-arbiter")[1]               # demonstrative
    assert lines("fra/charge-the-sanctum")[2].endswith("Сложи белег +1/+1 на нея.")  # pronoun
    assert lines("trk/blood-crypt")[0].endswith("тя встъпва наклонена.")             # participle
    assert "две или повече твари са загинали" in lines("fra/darklight-phoenix")[1]


def test_neuter_and_masculine_agreement():
    assert lines("trk/batleth")[0].startswith("Когато туй Снаряжение встъпи")
    assert "посочен трайник, който не е нито твар, нито земя" in lines("fra/archive-arbiter")[2]
    assert "Принеси го в жертва" in lines("trk/lrell-fierce-visionary")[0]           # the token: образ (m)


def test_old_spelling_keeps_symbols():
    from mtglang.realize.bg import to_old
    out = to_old("Сложи белег +1/+1 на {G} — тварта, 2/2.", ROOT)
    assert "+1/+1" in out and "{G}" in out and "—" in out and "2/2" in out
    assert "тварьта" in out or "тварта" in out


def test_edit_preserves_lex_bg(fx_copy):
    from mtglang.edit import apply_symbol_edits
    from mtglang.glossary import load_glossary
    p = fx_copy / "glossary" / "symbols.yaml"
    lines_ = p.read_text().split("\n")
    g = load_glossary(fx_copy / "glossary")
    i = next(k for k, s in enumerate(g.symbols) if s.cls == "action")
    entry_lines = [k for k, l in enumerate(lines_) if l.startswith("- ")]
    lines_[entry_lines[i]] = lines_[entry_lines[i]].rstrip()[:-1] + ", lex: {bg: {imp: изтегли, gender: f}}}"
    p.write_text("\n".join(lines_))
    s = load_glossary(fx_copy / "glossary").symbols[i]
    apply_symbol_edits(fx_copy, [{"index": i, "orig": s.glyph, "glyph": s.glyph, "ascii": s.ascii, "label": "x"}])
    assert load_glossary(fx_copy / "glossary").symbols[i].lex == {"bg": {"imp": "изтегли", "gender": "f"}}


def test_unhandled_ability_shows_marker(monkeypatch, capsys):
    from mtglang.cli import main
    from mtglang.realize import bg
    monkeypatch.setattr(bg.Bg, "ab_keywords", lambda self, a: bg.gap("keywords"))
    main(["bg", "fra/archive-arbiter", "--root", str(ROOT)])
    assert "⟦keywords⟧" in capsys.readouterr().out
    monkeypatch.setattr(bg.Bg, "ab_keywords", lambda self, a: 1 / 0)
    faces = render_card_bg(ROOT, "fra/archive-arbiter")
    assert faces[0].lines[0].startswith("⟦crash:ZeroDivisionError")
    assert faces[0].lines[1].startswith("Когато")


def test_plural_token_colour():
    from mtglang.realize.bg import COLORS
    import mtglang.realize.bg as bg
    assert COLORS["{W}"][3] == "бели"
    src = open(bg.__file__, encoding="utf-8").read()
    assert 'color[:-1] + "и"' not in src


def test_token_is_obraz():
    l = lines("fra/ajani-resolute")
    assert "Сътвори бял образ-твар 2/2 Котка Войник на име Аджаниев побратим" in l[2]
    assert "на тоя образ" in l[2]
    assert lines("trk/lrell-fierce-visionary")[0].count("червен образ-твар 2/1") == 1
    assert "Землепад —" in lines("trk/dal-rel-augment-orphan")[0]


def test_token_is_obraz():
    l = lines("fra/ajani-resolute")
    assert "Сътвори бял образ-твар 2/2 Котка Войник на име Аджаниев побратим" in l[2]
    assert "на тоя образ" in l[2]
    assert "червен образ-твар 2/1" in lines("trk/lrell-fierce-visionary")[0]
    assert "Землепад —" in lines("trk/dal-rel-augment-orphan")[0]
