from conftest import DAL_FILE
from mtglang.migrate import rewrite_lines


def test_rewrite_lines_is_token_aware_and_counts(fx_copy):
    def fn(line, g):
        return line.replace("✋1", "✋2") if "✋1" in line else line
    assert rewrite_lines(fx_copy, fn) == 1
    text = (fx_copy / DAL_FILE).read_text()
    assert "{3}, ✝⛰ : ✋2" in text and text.startswith("# Dal R'El — fixture\n")
    assert rewrite_lines(fx_copy, fn) == 0          # idempotent


def test_rewrite_lines_skips_headers_and_comments(fx_copy):
    seen = []
    rewrite_lines(fx_copy, lambda line, g: seen.append(line) or line)
    assert not any(l.startswith("#") or l.startswith("«") for l in seen)
    assert "⛰⇡ ▸ ⛰[◉]↑ ⇒ ⊕ {R} ∨ {G}" in seen


def test_sub_tokens_matches_by_token_identity(fx_glossary):
    from mtglang.migrate import sub_tokens
    g = fx_glossary
    assert sub_tokens("{3}, ✝⛰ : ✋1", g, "✝ ⛰", "✝ ☺") == "{3}, ✝ ☺ : ✋1"
    assert sub_tokens("{3}, Sa Ld : Dr1", g, "✝⛰", "✝☺") == "{3}, ✝☺ : Dr1"     # ASCII spelling matches too
    assert sub_tokens("✋1", g, "✝⛰", "✝☺") == "✋1"
