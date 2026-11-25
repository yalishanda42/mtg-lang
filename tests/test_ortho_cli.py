import io
import sys

import yaml

from mtglang.ortho.glossary import regenerate, review_markdown


def _glossary(tmp_path, names_extra=""):
    g = tmp_path / "glossary"
    g.mkdir()
    (g / "symbols.yaml").write_text(
        '- {glyph: "⇒", ascii: "=>", role: implies, class: structural, labels: {en: then, bg: тогава}}\n'
        '- {glyph: "✋", ascii: "Dr", class: action, labels: {en: draw}}\n', encoding="utf-8")
    (g / "names.yaml").write_text(
        '- {key: Warrior, class: subtype, labels: {en: Warrior, bg: Воин}}\n'
        '- {key: Road, class: card, labels: {en: Road, bg: Път}}\n' + names_extra, encoding="utf-8")
    (g / "named_effects.yaml").write_text("", encoding="utf-8")
    (g / "ortho_overrides.yaml").write_text("words: {}\nentries: {}\n", encoding="utf-8")
    return tmp_path


def _labels(root, file):
    return [d["labels"] for d in yaml.safe_load((root / "glossary" / file).read_text(encoding="utf-8")) or []]


def test_cli_converts_argument_and_stdin(capsys, monkeypatch):
    from mtglang.cli import main
    assert main(["ortho", "Почиват яростни вълни"]) == 0
    assert capsys.readouterr().out.strip() == "Почиватъ яростни вълни"
    monkeypatch.setattr(sys, "stdin", io.StringIO("за път"))
    assert main(["ortho"]) == 0
    assert capsys.readouterr().out.strip() == "за пѫть"


def test_regenerate_fills_and_is_idempotent(tmp_path):
    root = _glossary(tmp_path)
    r = regenerate(root)
    assert r.conflicts == [] and r.changed == 3
    assert _labels(root, "names.yaml")[0]["bg-ivanchev"] == "Воинъ"
    assert _labels(root, "symbols.yaml")[1] == {"en": "draw"}
    assert regenerate(root).changed == 0
    lines = (root / "glossary" / "names.yaml").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and all(l.startswith("- {") for l in lines)


def test_regenerate_refuses_hand_edit_and_honours_entries(tmp_path):
    root = _glossary(tmp_path, '- {key: Bell, class: card, labels: {en: Bell, bg: Звън, bg-ivanchev: Звѫнъ}}\n')
    r = regenerate(root)
    assert r.conflicts == ["names:Bell"] and r.changed == 0
    (root / "glossary" / "ortho_overrides.yaml").write_text("words: {}\nentries: {'names:Bell': Звѫнъ}\n",
                                                            encoding="utf-8")
    r = regenerate(root)
    assert r.conflicts == [] and _labels(root, "names.yaml")[2]["bg-ivanchev"] == "Звѫнъ"


def test_word_override_applies(tmp_path):
    root = _glossary(tmp_path)
    (root / "glossary" / "ortho_overrides.yaml").write_text("words: {воин: воинь}\nentries: {}\n", encoding="utf-8")
    regenerate(root)
    assert _labels(root, "names.yaml")[0]["bg-ivanchev"] == "Воинь"


def test_review_markdown(tmp_path):
    root = _glossary(tmp_path)
    regenerate(root)
    md = review_markdown(root)
    assert "| en | bg | bg-ivanchev | note |" in md
    assert "| Warrior | Воин | Воинъ |" in md and "## Names — subtype" in md and "## Symbols — structural" in md
    assert "draw" not in md       # entries without bg are listed in the missing section only
    assert "Missing" in md


def test_broken_overrides_file_is_a_clear_error(tmp_path, capsys):
    from mtglang.cli import main
    root = _glossary(tmp_path)
    (root / "glossary" / "ortho_overrides.yaml").write_text("words: {}\n# c\nentries: x\n  bad\n", encoding="utf-8")
    assert main(["ortho", "--glossary", "--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert out.startswith("error:") and "ortho_overrides.yaml" in out
    (root / "glossary" / "ortho_overrides.yaml").write_text("words: [\n", encoding="utf-8")
    assert main(["ortho", "--glossary", "--root", str(root)]) == 1
    assert "not valid YAML" in capsys.readouterr().out


def test_overwrite_replaces_listed_conflicts(tmp_path, capsys):
    from mtglang.cli import main
    root = _glossary(tmp_path, '- {key: Bell, class: card, labels: {en: Bell, bg: Звън, bg-ivanchev: Звѫнъ}}\n')
    assert main(["ortho", "--glossary", "--root", str(root)]) == 1
    assert main(["ortho", "--glossary", "--overwrite", "--root", str(root)]) == 0
    out = capsys.readouterr().out
    assert "overwrote names:Bell: Звѫнъ →" in out
    assert _labels(root, "names.yaml")[2]["bg-ivanchev"] != "Звѫнъ"
