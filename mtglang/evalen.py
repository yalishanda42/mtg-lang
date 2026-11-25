"""AST → English evaluation against Scryfall Oracle text."""
from __future__ import annotations

import re

_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})


def normalize(s: str) -> str:
    """Collapse whitespace and unify typographic quotes; nothing else (articles, commas, order all count)."""
    return re.sub(r"\s+", " ", s.translate(_QUOTES)).strip()


import difflib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

GAP = re.compile(r"⟦([^⟧]*)⟧")


@dataclass
class LineResult:
    ref: str              # <set>/<slug>#<face>.<k> (ability k) or #<face>.name / .type / .stats
    field: str            # ability / name / type / stats
    notation: str
    rendered: str
    oracle: str
    match: bool
    cause: str | None     # None (match), renderer, gap:<kind>, ast, align, notation, accepted, style:<id>


def load_accepted(root: Path) -> dict[str, str]:
    """line ref → cause, from data/eval-en-accepted.yaml (categories → style:<id>, accepted, triage)."""
    p = Path(root) / "data" / "eval-en-accepted.yaml"
    if not p.exists():
        return {}
    d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    out: dict[str, str] = {}
    for c in d.get("categories") or []:
        for line in c.get("lines") or []:
            out[line] = f"style:{c['id']}"
    for a in d.get("accepted") or []:
        out[a["line"]] = "accepted"
    for t in d.get("triage") or []:
        out[t["line"]] = t["cause"]
    return out


def _cause(ref: str, rendered: str, oracle: str, accepted: dict[str, str]) -> tuple[bool, str | None]:
    if normalize(rendered) == normalize(oracle):
        return True, None
    if ref in accepted:
        return False, accepted[ref]
    m = GAP.search(rendered)
    if m:
        return False, "gap:" + m.group(1).split(".")[0].split(":")[0]
    return False, "renderer"


def evaluate(root: Path, sets: list[str] | None = None) -> list[LineResult]:
    from mtglang.astexport import corpus_asts
    from mtglang.glossary import load_glossary
    from mtglang.oracle import oracle_lines
    from mtglang.realize.en import render_card
    from mtglang.scryfall import load_snapshot
    from mtglang.cardfile import parse_card_file
    from mtglang.lineparser import LineParser

    root = Path(root)
    g = load_glossary(root / "glossary")
    lp = LineParser(g)
    snap = load_snapshot(root / "data")
    accepted = load_accepted(root)
    out: list[LineResult] = []
    for code, slug, card, _err in corpus_asts(root, sets):
        sc = snap.get((code, slug))
        if sc is None:
            continue
        base = f"{code}/{slug}#"
        doc, _ = parse_card_file(root / "cards" / code / f"{slug}.mtgl", lp)
        notes = [[a.text.strip() for a in f.abilities] for f in doc.faces] if doc else []
        if card is None:
            for fi, sf in enumerate(sc.faces):
                for k, o in enumerate(oracle_lines(sf)):
                    out.append(LineResult(f"{base}{fi}.{k}", "ability", "", "", o, False, "ast"))
            continue
        try:
            faces = render_card(card, g)
        except Exception as e:          # a renderer crash is a renderer mismatch, never a crashed eval
            faces = None
            err = f"⟦crash:{type(e).__name__}: {e}⟧"
        for fi, sf in enumerate(sc.faces):
            ft = faces[fi] if faces and fi < len(faces) else None
            nf = notes[fi] if fi < len(notes) else []
            want_stats = f"{sf.power}/{sf.toughness}" if sf.power is not None else (sf.loyalty or sf.defense)
            heads = [("name", ft.name if ft else "", sf.name), ("type", ft.type_line if ft else "", sf.type_line)]
            if want_stats is not None or (ft and ft.stats):
                heads.append(("stats", (ft.stats or "") if ft else "", want_stats or ""))
            for field, got, want in heads:
                ref = f"{base}{fi}.{field}"
                ok, cause = _cause(ref, got, want, accepted)
                out.append(LineResult(ref, field, "", got, want, ok, cause))
            olines = oracle_lines(sf)
            n_ab = len(nf)
            aligned = n_ab == len(olines)
            for k in range(max(n_ab, len(olines))):
                ref = f"{base}{fi}.{k}"
                notation = nf[k] if k < n_ab else ""
                rendered = (ft.lines[k] if ft and k < len(ft.lines) else "") if faces else err
                o = olines[k] if k < len(olines) else ""
                if not aligned:
                    out.append(LineResult(ref, "ability", notation, rendered, o, False, "align"))
                    continue
                ok, cause = _cause(ref, rendered, o, accepted)
                out.append(LineResult(ref, "ability", notation, rendered, o, ok, cause))
    return out


def summary(results) -> dict:
    by_set: dict[str, list[int]] = {}
    by_cause: dict[str, int] = {}
    for r in results:
        s = by_set.setdefault(r.ref.split("/")[0], [0, 0])
        s[1] += 1
        if r.match:
            s[0] += 1
        else:
            by_cause[r.cause or "renderer"] = by_cause.get(r.cause or "renderer", 0) + 1
    ab = [r for r in results if r.field == "ability"]
    return {"lines": len(results), "exact": sum(1 for r in results if r.match), "by_set": by_set,
            "abilities": [sum(1 for r in ab if r.match), len(ab)],
            "by_cause": dict(sorted(by_cause.items(), key=lambda kv: -kv[1]))}


def word_diff(a: str, b: str) -> list[tuple[str, str]]:
    """[(op, text)] with op in ' ', '-', '+' over whitespace tokens (rendered a → Oracle b)."""
    x, y = a.split(), b.split()
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=x, b=y, autojunk=False).get_opcodes():
        if tag == "equal":
            out.append((" ", " ".join(x[i1:i2])))
        else:
            if i2 > i1:
                out.append(("-", " ".join(x[i1:i2])))
            if j2 > j1:
                out.append(("+", " ".join(y[j1:j2])))
    return out


def _signature(r: LineResult) -> str:
    """Renderer mismatches grouped by their first differing token pair."""
    if r.cause != "renderer":
        return r.cause or ""
    d = word_diff(r.rendered, r.oracle)
    minus = next((t for op, t in d if op == "-"), "")
    plus = next((t for op, t in d if op == "+"), "")
    return f"{' '.join(minus.split()[:3])} → {' '.join(plus.split()[:3])}"


def write_report(results, out: Path) -> Path:
    from jinja2 import Environment, PackageLoader, select_autoescape
    out = Path(out) / "eval-en"
    out.mkdir(parents=True, exist_ok=True)
    s = summary(results)
    (out / "report.json").write_text(json.dumps({"summary": s, "lines": [asdict(r) for r in results]},
                                                ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    groups: dict[str, dict[str, list]] = {}
    for r in results:
        if r.match:
            continue
        groups.setdefault(r.cause or "renderer", {}).setdefault(_signature(r), []).append(
            {"r": r, "diff": word_diff(r.rendered, r.oracle)})
    ordered = sorted(((c, sorted(g.items(), key=lambda kv: -len(kv[1]))) for c, g in groups.items()),
                     key=lambda cg: -sum(len(v) for _, v in cg[1]))
    env = Environment(loader=PackageLoader("mtglang"), autoescape=select_autoescape(["html"]))
    page = out / "index.html"
    page.write_text(env.get_template("eval_en.html").render(summary=s, groups=ordered), encoding="utf-8")
    return page
