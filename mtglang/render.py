"""Render the HTML gallery, the legend and the ASCII export."""
from __future__ import annotations

import html
from collections import defaultdict
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from mtglang.cardfile import parse_card_file
from mtglang.glossary import Glossary, load_glossary
from mtglang.lineparser import LineParser
from mtglang.oracle import oracle_lines
from mtglang.scryfall import SETS, load_snapshot
from mtglang.tokenizer import TokenizeError, to_ascii, tokenize
from mtglang.validate import validate_all


def _e(s: str) -> str:
    return html.escape(s, quote=True)


def notation_html(text: str, g: Glossary, lang: str = "en") -> str:
    try:
        toks = tokenize(text, g)
    except TokenizeError:
        return f'<span class="bad">{_e(text)}</span>'
    out, last = [], 0
    for t in toks:
        out.append(_e(text[last:t.col - 1]))
        if t.symbol is not None:
            out.append(f'<span class="sym" title="{_e(g.label(t.symbol, lang))}">{_e(t.symbol.glyph)}</span>')
        elif t.type == "NAME":
            label = g.label(g.names[t.value], lang) if t.value in g.names else t.value
            o, c = g.role("name_open").glyph, g.role("name_close").glyph
            out.append(f'<span class="name" title="{_e(t.value)}">{_e(o + label + c)}</span>')
        elif t.type == "EFFECT":
            label = g.label(g.effects[t.value], lang) if t.value in g.effects else t.value
            o, c = g.role("effect_open").glyph, g.role("effect_close").glyph
            out.append(f'<span class="effect" title="{_e(label)}">{_e(o + t.value + c)}</span>')
        elif t.type == "MANA":
            out.append(f'<span class="mana">{_e(t.text)}</span>')
        else:
            out.append(_e(t.text))
        last = t.end
    out.append(_e(text[last:]))
    return "".join(out)


def _safe_ascii(text: str, g: Glossary) -> str:
    try:
        return to_ascii(text, g)
    except TokenizeError:
        return text


def ascii_file(text: str, g: Glossary) -> str:
    lines = []
    for line in text.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        lines.append(line if (not stripped or stripped.startswith("#") or stripped == "//") else _safe_ascii(line, g))
    return "\n".join(lines)


def render_site(root: Path, out: Path, lang: str = "en") -> None:
    root, out = Path(root), Path(out)
    g = load_glossary(root / "glossary")
    parser = LineParser(g)
    snap = load_snapshot(root / "data")
    issues, _ = validate_all(root)
    by_file = defaultdict(list)
    for i in issues:
        if i.file:
            by_file[Path(i.file).resolve()].append(i)

    env = Environment(loader=PackageLoader("mtglang"), autoescape=select_autoescape(["html"]))
    sets = []
    (out / "ascii").mkdir(parents=True, exist_ok=True)
    for code in SETS:
        files = sorted((root / "cards" / code).glob("*.mtgl"))
        cards, ascii_parts = [], []
        for path in files:
            ascii_parts.append(ascii_file(path.read_text(encoding="utf-8"), g))
            doc, _ = parse_card_file(path, parser)
            card = snap.get((code, path.stem))
            entry = {"slug": path.stem, "faces": [], "issues": [str(i) for i in by_file.get(path.resolve(), [])]}
            if doc is not None:
                for fi, f in enumerate(doc.faces):
                    sf = card.faces[fi] if card and fi < len(card.faces) else None
                    olines = oracle_lines(sf) if sf else []
                    n = max(len(f.abilities), len(olines))
                    rows = []
                    for k in range(n):
                        a = f.abilities[k].text if k < len(f.abilities) else ""
                        rows.append({"notation": notation_html(a, g, lang), "ascii": _safe_ascii(a, g),
                                     "oracle": olines[k] if k < len(olines) else ""})
                    o, c = g.role("name_open").glyph, g.role("name_close").glyph
                    header = notation_html(f"{o}{f.name}{c} {f.mana}".strip(), g, lang)
                    entry["faces"].append({"header": header, "type_line": notation_html(f.type_line, g, lang),
                                           "stats": notation_html(f.stats, g, lang) if f.stats else None,
                                           "rows": rows})
            cards.append(entry)
        total = sum(1 for k in snap if k[0] == code)
        sets.append({"code": code, "translated": len(files), "total": total, "cards": cards})
        (out / "ascii" / f"{code}.txt").write_text("\n\n".join(ascii_parts), encoding="utf-8")

    ctx = {"sets": sets, "lang": lang}
    (out / "index.html").write_text(env.get_template("index.html").render(**ctx), encoding="utf-8")
    for s in sets:
        (out / f"{s['code']}.html").write_text(
            env.get_template("set.html").render(code=s["code"], cards=s["cards"], **ctx), encoding="utf-8")
    groups = defaultdict(list)
    for sym in g.symbols:
        groups[sym.cls].append({"glyph": sym.glyph, "ascii": sym.ascii, "label": g.label(sym, lang), "oracle": sym.oracle,
                                "definition": notation_html(sym.definition, g, lang) if sym.definition else ""})
    effects = [{"key": e.key, "card": e.card, "label": g.label(e, lang)} for e in g.effects.values()]
    (out / "legend.html").write_text(
        env.get_template("legend.html").render(groups=list(groups.items()), effects=effects, **ctx), encoding="utf-8")
