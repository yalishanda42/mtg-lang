import json
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_cli_ast_prints_card_json(capsys):
    from mtglang.cli import main
    assert main(["ast", "fra/ajani-resolute", "--root", str(ROOT)]) == 0
    card = json.loads(capsys.readouterr().out)
    assert card["kind"] == "card" and card["faces"][0]["name"]["key"] == "Ajani Resolute"
    assert len(card["faces"][0]["abilities"]) == 4


def test_cli_ast_unknown_card(capsys):
    from mtglang.cli import main
    assert main(["ast", "fra/no-such-card", "--root", str(ROOT)]) == 1


def test_cli_ast_coverage(capsys):
    from mtglang.cli import main
    assert main(["ast", "--coverage", "--root", str(ROOT)]) == 0
    out = capsys.readouterr().out
    assert "parsed 1242/1242" in out and "roundtrip 1242/1242" in out


def test_export_ast_json(tmp_path):
    from mtglang.astexport import export_ast
    paths = export_ast(ROOT, tmp_path)
    data = json.loads((tmp_path / "ast" / "fra.json").read_text(encoding="utf-8"))
    assert {p.name for p in paths} == {"fra.json", "trk.json"}
    assert any(e["slug"] == "ajani-resolute" and e["ast"]["kind"] == "card" for e in data)
