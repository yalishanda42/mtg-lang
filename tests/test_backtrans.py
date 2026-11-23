from conftest import FIXTURES as FX
from mtglang.backtrans import backtrans_bundle, legend_text


def test_bundle_has_no_oracle_and_key_does():
    b, k = backtrans_bundle(FX, n=1, seed=7)
    assert "Draw a card" not in b and "✋1" in b and "⇒ | => | then" in b
    assert "Draw a card" in k and "#1" in b and "#1" in k
    assert "fixture" not in b  # comments stripped


def test_bundle_n_capped_and_deterministic():
    assert backtrans_bundle(FX, n=5, seed=1) == backtrans_bundle(FX, n=5, seed=1)


def test_legend_text_lists_definitions(fx_glossary):
    t = legend_text(fx_glossary)
    assert "F | F | Flying | ◈ ≤ [☺ F]" in t


def test_cli_backtrans(tmp_path):
    from mtglang.cli import main
    assert main(["backtrans", "--root", str(FX), "--n", "1", "--seed", "7", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "bundle.md").exists() and (tmp_path / "key.md").exists()
