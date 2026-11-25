"""AST → English eval against Oracle."""
import json
from functools import lru_cache
from pathlib import Path

from conftest import DAL_FILE, drop_last_line, edit
from mtglang.evalen import evaluate, normalize, summary, write_report

ROOT = Path(__file__).parent.parent


@lru_cache(maxsize=None)
def corpus():
    return tuple(evaluate(ROOT))


def by_ref(results):
    return {r.ref: r for r in results}


def test_normalize():
    assert normalize("it’s  “x”\n") == 'it\'s "x"'


def test_match_line():
    r = by_ref(corpus())["fra/academic-ascent#0.0"]
    assert r.match and r.cause is None and r.field == "ability"
    assert r.rendered == "Target creature gets +2/+2 and gains flying until end of turn."
    assert r.notation.startswith("◎♞")


def test_headers_compared():
    rs = by_ref(corpus())
    assert rs["fra/aerid-konstrari#0.name"].match
    assert rs["fra/aerid-konstrari#0.type"].oracle == "Legendary Creature — Elder Sphinx"
    assert rs["fra/aerid-konstrari#0.stats"].match


def test_gap_cause():
    gaps = [r for r in corpus() if r.cause and r.cause.startswith("gap:")]
    assert gaps and all("⟦" in r.rendered for r in gaps)


def test_parse_failure_is_ast(fx_copy):
    edit(fx_copy, "{3}, ✝⛰ : ✋1", "{3}, ✝⛰ : ✋1 ⊕ ⊕ ⇒ ⇒")
    rs = evaluate(fx_copy)
    dal = [r for r in rs if r.ref.startswith("trk/dal-rel-augment-orphan#")]
    assert dal and all(r.cause == "ast" for r in dal if r.field == "ability")


def test_align(fx_copy):
    drop_last_line(fx_copy, DAL_FILE)
    rs = evaluate(fx_copy)
    dal = [r for r in rs if r.ref.startswith("trk/dal-rel-augment-orphan#0.") and r.field == "ability"]
    assert dal and all(r.cause == "align" for r in dal)


def test_accepted_category(fx_copy):
    (fx_copy / "data" / "eval-en-accepted.yaml").write_text(
        'categories:\n  - {id: join, description: d, tried: t, lines: ["trk/dal-rel-augment-orphan#0.1"]}\n'
        'accepted:\n  - {line: "trk/dal-rel-augment-orphan#0.0", reason: r}\n')
    rs = by_ref(evaluate(fx_copy))
    assert rs["trk/dal-rel-augment-orphan#0.1"].cause == "style:join"
    assert rs["trk/dal-rel-augment-orphan#0.0"].cause == "accepted"


def test_report_written(tmp_path):
    out = write_report(list(corpus()), tmp_path)
    assert out == tmp_path / "eval-en" / "index.html" and out.exists()
    data = json.loads((tmp_path / "eval-en" / "report.json").read_text())
    assert data["summary"]["lines"] == len(corpus())
    miss = next(r for r in corpus() if not r.match)
    assert miss.ref in out.read_text()


def test_eval_en_ratchet():
    base = json.loads((ROOT / "tests" / "eval_en_baseline.json").read_text())
    assert summary(corpus())["exact"] >= base["exact"]


def test_cli_en(capsys):
    from mtglang.cli import main
    assert main(["en", "fra/academic-ascent", "--root", str(ROOT)]) == 0
    out = capsys.readouterr().out
    assert "Academic Ascent" in out and "Target creature gets +2/+2 and gains flying until end of turn." in out


def test_cli_eval_en(tmp_path, capsys):
    from mtglang.cli import main
    assert main(["eval-en", "--root", str(ROOT), "--set", "fra", "--out", str(tmp_path)]) == 0
    assert "exact" in capsys.readouterr().out
    assert (tmp_path / "eval-en" / "index.html").exists()
