"""Render the HTML gallery, the legend and the ASCII export."""
from __future__ import annotations

import base64
import html
import re
from collections import defaultdict
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from mtglang.cardfile import parse_card_file, read_card_text
from mtglang.glossary import Glossary, load_glossary
from mtglang.lineparser import LineParser
from mtglang.oracle import oracle_lines
from mtglang.scryfall import SETS, load_snapshot, load_symbols
from mtglang.tokenizer import TokenizeError, ascii_pieces, to_ascii, tokenize
from mtglang.validate import validate_all


def _e(s: str) -> str:
    return html.escape(s, quote=True)


_MANA_IN_TEXT = re.compile(r"\{[^{}\s]+\}")


def _icon_class(file: str) -> str:
    return "m-" + re.sub(r"[^A-Za-z0-9]", "_", Path(file).stem)


def mana_html(sym: str, symbols: dict | None) -> str:
    info = (symbols or {}).get(sym)
    if info:
        return (f'<span class="ms {_icon_class(info["file"])}" role="img" aria-label="{_e(sym)}" '
                f'title="{_e(info["english"])}"></span>')
    return f'<span class="mana">{_e(sym)}</span>'


def icon_css(symbols_dir: Path, symbols: dict | None) -> str:
    """One CSS rule per mana/tap icon with the SVG inlined, so the page needs no image files."""
    rules = {}
    for info in (symbols or {}).values():
        f = Path(symbols_dir) / info["file"]
        if f.exists():
            data = base64.b64encode(f.read_bytes()).decode("ascii")
            rules[_icon_class(info["file"])] = f'.{_icon_class(info["file"])}{{background-image:url("data:image/svg+xml;base64,{data}")}}'
    return "\n".join(rules[k] for k in sorted(rules))


def oracle_html(text: str, symbols: dict | None) -> str:
    out, last = [], 0
    for m in _MANA_IN_TEXT.finditer(text):
        info = (symbols or {}).get(m.group())
        if info:
            out.append(_e(text[last:m.start()]))
            out.append(mana_html(m.group(), symbols))
            last = m.end()
    out.append(_e(text[last:]))
    return "".join(out)


def _delimited(cls: str, title: str, g: Glossary, open_role: str, close_role: str, inner: str, attr: str,
               ascii: bool = False) -> str:
    """A «name» / ⟨effect⟩ span whose delimiters are tagged with their symbol index for live editing."""
    so, sc = g.role(open_role), g.role(close_role)
    o, c = (so.ascii, sc.ascii) if ascii else (so.glyph, sc.glyph)
    body = (f'<span {attr}="{g.index(so)}">{_e(o)}</span>{_e(inner)}'
            f'<span {attr}="{g.index(sc)}">{_e(c)}</span>')
    return f'<span class="{cls}" title="{_e(title)}">{body}</span>' if cls else body


def notation_html(text: str, g: Glossary, lang: str = "en", symbols: dict | None = None) -> str:
    """Notation as HTML; every glossary symbol carries ``data-s=<index>`` so the editor can restyle it in place."""
    try:
        toks = tokenize(text, g)
    except TokenizeError:
        return f'<span class="bad">{_e(text)}</span>'
    out, last = [], 0
    for t in toks:
        out.append(_e(text[last:t.col - 1]))
        if t.symbol is not None:
            out.append(f'<span class="sym" data-s="{g.index(t.symbol)}" title="{_e(g.label(t.symbol, lang))}">'
                       f'{_e(t.symbol.glyph)}</span>')
        elif t.type == "NAME":
            label = g.label(g.names[t.value], lang) if t.value in g.names else t.value
            out.append(_delimited("name", t.value, g, "name_open", "name_close", label, "data-s"))
        elif t.type == "EFFECT":
            label = g.label(g.effects[t.value], lang) if t.value in g.effects else t.value
            out.append(_delimited("effect", label, g, "effect_open", "effect_close", t.value, "data-s"))
        elif t.type == "MANA":
            out.append(mana_html(t.text, symbols))
        else:
            out.append(_e(t.text))
        last = t.end
    out.append(_e(text[last:]))
    return "".join(out)


def ascii_html(text: str, g: Glossary) -> str:
    """ASCII form as HTML; glossary aliases carry ``data-a=<index>`` for live editing."""
    try:
        pieces = ascii_pieces(text, g)
    except TokenizeError:
        return _e(text)
    out = []
    for gap, piece, t in pieces:
        out.append(_e(gap))
        if t is None:
            continue
        if t.symbol is not None:
            out.append(f'<span data-a="{g.index(t.symbol)}">{_e(piece)}</span>')
        elif t.type == "NAME":
            out.append(_delimited("", "", g, "name_open", "name_close", t.value, "data-a", ascii=True))
        elif t.type == "EFFECT":
            out.append(_delimited("", "", g, "effect_open", "effect_close", t.value, "data-a", ascii=True))
        else:
            out.append(_e(piece))
    return "".join(out)


# --- card view: notation painted over the real card scan --------------------

_BAR = {"W": "#f4f4ee", "U": "#b7d5e4", "B": "#b4aeae", "R": "#f3ccb8", "G": "#bccfc6"}
_BOX = {"W": "#f4f4ec", "U": "#dbe9f2", "B": "#e8e7e5", "R": "#f0dfd5", "G": "#d4e4db"}
_GOLD = ("#d0bc84", "#f2eed8")
_ARTIFACT = ("#d0d9dd", "#d0dce0")
_COLORLESS = ("#cec7c5", "#e8e3dc")
_PAIRS = ("WU", "UB", "BR", "RG", "GW", "WB", "UR", "BG", "RW", "GU")  # frame order of two-colour cards
VIEW_LAYOUTS = ("normal", "saga", "prepare")


def frame_palette(colors: list[str], type_line: str) -> tuple[str, str, str]:
    """(bar colour, text-box background, solid text-box colour) approximating the printed 2015 frame.

    Two-colour cards get a left-to-right gradient text box; the solid variant is for narrow panels (sagas)."""
    cs = [c for c in colors if c in _BAR]
    if not cs:
        pal = _ARTIFACT if "Artifact" in type_line else _COLORLESS
        return pal + (pal[1],)
    if len(cs) == 1:
        return _BAR[cs[0]], _BOX[cs[0]], _BOX[cs[0]]
    if len(cs) == 2:
        pair = next((p for p in _PAIRS if set(p) == set(cs)), "".join(cs))
        a, b = _BOX[pair[0]], _BOX[pair[1]]
        return _GOLD[0], f"linear-gradient(90deg, {a} 30%, {b} 70%)", f"color-mix(in srgb, {a}, {b})"
    return _GOLD + (_GOLD[1],)


def card_view(card, doc, g: Glossary, lang: str, symbols: dict | None) -> dict | None:
    """Overlay data for the card scan, or None if the layout/frame isn't supported."""
    if card is None or doc is None or not card.image or card.layout not in VIEW_LAYOUTS:
        return None
    if card.layout == "prepare" and len(doc.faces) < 2:
        return None
    if card.layout != "prepare" and len(doc.faces) != 1:
        return None
    if "Battle" in card.faces[0].type_line:
        return None
    kind = card.layout
    if "Planeswalker" in card.faces[0].type_line:
        if card.layout != "normal":
            return None
        # the printed planeswalker frame has a shorter art box when there are four ability rows
        kind = "pw pw4" if len(oracle_lines(card.faces[0])) >= 4 else "pw pw3"
    o, c = g.role("name_open").glyph, g.role("name_close").glyph
    faces = []
    for fi, f in enumerate(doc.faces[:2]):
        sf = card.faces[fi] if fi < len(card.faces) else None
        olines = oracle_lines(sf) if sf else []
        rows = [{"html": notation_html(a.text, g, lang, symbols), "oracle": olines[k] if k < len(olines) else ""}
                for k, a in enumerate(f.abilities)]
        faces.append({"name": notation_html(f"{o}{f.name}{c}", g, lang, symbols),
                      "mana": notation_html(f.mana, g, lang, symbols) if f.mana else "",
                      "type": notation_html(f.type_line, g, lang, symbols),
                      "oracle_name": sf.name if sf else "", "oracle_type": sf.type_line if sf else "",
                      "rows": rows})
    bar, box, solid = frame_palette(card.colors, card.faces[0].type_line)
    return {"kind": kind, "image": card.image, "bar": bar, "box": solid if card.layout == "saga" else box,
            "pt": bool(doc.faces[0].stats) or bool(card.faces[0].power), "faces": faces}


def bulgarian_view(view: dict, faces, symbols: dict | None) -> dict:
    """The MTG-Lang card view with the old-spelling Bulgarian text in place of the notation."""
    out = []
    for vf, bf in zip(view["faces"], faces):
        rows = [{"html": oracle_html(old, symbols), "oracle": modern}
                for old, modern in zip(bf.old.lines, bf.lines)]
        out.append(dict(vf, name=_e(bf.old.name), type=_e(bf.old.type_line), oracle_name=bf.name,
                        oracle_type=bf.type_line, rows=rows))
    return dict(view, faces=out)


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


def ui_strings(lang: str) -> dict[str, str]:
    """The gallery's fixed words in ``lang`` (fallback: English; bg-ivanchev: Ivanchev spelling of bg)."""
    from importlib.resources import files

    import yaml
    out = {}
    for e in yaml.safe_load(files("mtglang").joinpath("ui_strings.yaml").read_text(encoding="utf-8")):
        labels = e["labels"]
        text = labels.get(lang)
        if text is None and lang == "bg-ivanchev" and labels.get("bg"):
            from mtglang.ortho.ivanchev import to_ivanchev
            text = to_ivanchev(labels["bg"])
        out[e["id"]] = text if text is not None else labels["en"]
    return out


def _bg_row(labels: dict) -> dict:
    return {"iv": labels.get("bg-ivanchev", ""), "bg": labels.get("bg", ""), "en": labels.get("en", ""),
            "note": labels.get("bg-note", "")}


def bulgarian_glossary(g: Glossary) -> dict:
    """Rows for the Legend's Bulgarian tab: symbols by class, named effects, names by class."""
    symbols = defaultdict(list)
    for i, sym in enumerate(g.symbols):
        symbols[sym.cls].append({"i": i, "glyph": sym.glyph, **_bg_row(sym.labels)})
    effects = [{"key": e.key, **_bg_row(e.labels)} for e in g.effects.values()]
    names = defaultdict(list)
    for n in sorted(g.names.values(), key=lambda n: n.key.casefold()):
        names[n.cls].append({"key": n.key, **_bg_row(n.labels)})
    order = ("subtype", "token", "flavor", "card")
    return {"symbols": list(symbols.items()), "effects": effects,
            "names": sorted(names.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else len(order))}


STALE_PAGES = ("legend.html",)   # per-page outputs of earlier versions, superseded by the single index.html


def render_site(root: Path, out: Path, lang: str = "en") -> Path:
    """Write the single-page gallery (index, legend/editor, every set) and the ASCII export; returns the page."""
    root, out = Path(root), Path(out)
    g = load_glossary(root / "glossary")
    parser = LineParser(g)
    snap = load_snapshot(root / "data")
    symbols = load_symbols(root / "data" / "symbols")
    issues, _ = validate_all(root)
    by_file = defaultdict(list)
    for i in issues:
        if i.file:
            by_file[Path(i.file).resolve()].append(i)

    env = Environment(loader=PackageLoader("mtglang"), autoescape=select_autoescape(["html"]))
    from mtglang.evalen import evaluate, normalize, write_report
    from mtglang.realize.en import render_card
    from mtglang.resolve import resolve_card
    from mtglang.semparse import SemParser, SemSyntaxError, build_card
    sem = SemParser(g)
    from mtglang.realize import bg as BG
    sample = set(BG.load_sample(root))
    sets = []
    (out / "ascii").mkdir(parents=True, exist_ok=True)
    o, c = g.role("name_open").glyph, g.role("name_close").glyph
    for code in SETS:
        files = sorted((root / "cards" / code).glob("*.mtgl"))
        cards, ascii_parts = [], []
        for path in files:
            text = read_card_text(path)
            if text is not None:
                ascii_parts.append(ascii_file(text, g))
            doc, _ = parse_card_file(path, parser)
            card = snap.get((code, path.stem))
            english, resolved = None, None
            if doc is not None:
                try:
                    resolved = resolve_card(build_card(doc, sem), g)[0]
                    english = render_card(resolved, g)
                except (SemSyntaxError, Exception):     # a card the AST or renderer can't handle shows no English
                    english = None
            view = card_view(card, doc, g, lang, symbols)
            entry = {"slug": path.stem, "faces": [], "issues": [str(i) for i in by_file.get(path.resolve(), [])],
                     "view": view, "view_bg": None}
            if view is not None and resolved is not None and f"{code}/{path.stem}" in sample:
                entry["view_bg"] = bulgarian_view(view, BG.render_card(resolved, g, root), symbols)
            if doc is not None:
                for fi, f in enumerate(doc.faces):
                    sf = card.faces[fi] if card and fi < len(card.faces) else None
                    olines = oracle_lines(sf) if sf else []
                    n = max(len(f.abilities), len(olines))
                    rows = []
                    elines = english[fi].lines if english and fi < len(english) else ()
                    for k in range(n):
                        a = f.abilities[k].text if k < len(f.abilities) else ""
                        en = elines[k] if k < len(elines) else ""
                        ol = olines[k] if k < len(olines) else ""
                        rows.append({"notation": notation_html(a, g, lang, symbols), "ascii": ascii_html(a, g),
                                     "oracle": oracle_html(ol, symbols) if ol else "", "english": en,
                                     "english_ok": normalize(en) == normalize(ol)})
                    header = notation_html(f"{o}{f.name}{c} {f.mana}".strip(), g, lang, symbols)
                    entry["faces"].append({"header": header, "type_line": notation_html(f.type_line, g, lang),
                                           "stats": notation_html(f.stats, g, lang) if f.stats else None,
                                           "rows": rows})
            cards.append(entry)
        total = sum(1 for k in snap if k[0] == code)
        sets.append({"code": code, "translated": len(files), "total": total, "cards": cards})
        (out / "ascii" / f"{code}.txt").write_text("\n\n".join(ascii_parts), encoding="utf-8")

    groups = defaultdict(list)
    for i, sym in enumerate(g.symbols):
        groups[sym.cls].append({"i": i, "glyph": sym.glyph, "ascii": sym.ascii, "label": g.label(sym, lang),
                                "role": sym.role or "", "oracle": sym.oracle,
                                "definition": notation_html(sym.definition, g, lang) if sym.definition else ""})
    effects = [{"key": e.key, "card": e.card, "label": g.label(e, lang)} for e in g.effects.values()]
    bg = bulgarian_glossary(g)
    page = out / "index.html"
    ui = ui_strings(lang)
    page.write_text(env.get_template("page.html").render(
        sets=sets, lang=lang, groups=list(groups.items()), effects=effects, bg=bg, ui=ui,
        cls_label=lambda c: ui.get(f"class:{c}", c),
        icon_css=icon_css(root / "data" / "symbols", symbols)), encoding="utf-8")
    for stale in STALE_PAGES + tuple(f"{code}.html" for code in SETS):
        (out / stale).unlink(missing_ok=True)
    write_report(evaluate(root), out)
    return page
