"""Edit glossary symbols and migrate every card file (and symbol definition) to the new spelling."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import yaml

from mtglang.cardfile import read_card_text
from mtglang.glossary import Glossary, check_glossary, load_glossary
from mtglang.tokenizer import ASCII_PUNCT, Tok, TokenizeError, tokenize

_DELIMS = {"NAME": ("name_open", "name_close"), "EFFECT": ("effect_open", "effect_close")}


class EditError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _identity(toks: list[Tok], g: Glossary) -> list[tuple]:
    """Token sequence independent of glyph/ASCII spelling: symbols by index, everything else by value."""
    out = []
    for t in toks:
        if t.symbol is not None:
            out.append(("SYM", g.index(t.symbol)))
        else:
            typ = "MINUS" if t.type == "DASH" else t.type
            out.append((typ, t.value if typ in _DELIMS else ASCII_PUNCT.get(t.value, t.value)))
    return out


def _respell(t: Tok, old: Glossary, new: Glossary) -> str:
    """Token text in the new glossary, keeping the glyph-vs-ASCII choice of the source."""
    if t.symbol is not None:
        ns = new.symbols[old.index(t.symbol)]
        return ns.glyph if t.text == t.symbol.glyph else ns.ascii
    if t.type in _DELIMS:
        o_role, c_role = _DELIMS[t.type]
        oo, oc = old.role(o_role), old.role(c_role)
        no, nc = new.role(o_role), new.role(c_role)
        if t.text.startswith(oo.glyph) and t.text.endswith(oc.glyph):
            return no.glyph + t.value + nc.glyph
        return no.ascii + t.value + nc.ascii
    return t.text


def migrate_line(text: str, old: Glossary, new: Glossary) -> str:
    """Rewrite one notation line from the old glossary spelling to the new one.

    Raises ValueError if the rewritten line would no longer mean the same token sequence."""
    try:
        toks = tokenize(text, old)
    except TokenizeError:
        return text            # already invalid; leave it for the validator to report
    want = _identity(toks, old)
    out, last = [], 0
    for k, t in enumerate(toks):
        gap = text[last:t.col - 1]
        piece = _respell(t, old, new)
        if not gap and k:
            # a new spelling may glue onto its neighbour (e.g. '-' + '>' → '->'): separate them
            try:
                glued = _identity(tokenize(out[-1] + piece, new), new) == want[k - 1:k + 1]
            except TokenizeError:
                glued = False
            if not glued:
                gap = " "
        out.append(gap)
        out.append(piece)
        last = t.end
    out.append(text[last:])
    result = "".join(out)
    try:
        got = _identity(tokenize(result, new), new)
    except TokenizeError as e:
        raise ValueError(e.message) from None
    if got != want:
        raise ValueError("the new spelling is ambiguous here")
    return result


def _migrate_card(text: str, old: Glossary, new: Glossary) -> tuple[str, int]:
    lines, changed = [], 0
    for raw in text.splitlines(keepends=True):
        body = raw.rstrip("\r\n")
        end = raw[len(body):]
        stripped = body.strip()
        if stripped and not stripped.startswith("#") and stripped != "//":
            new_body = migrate_line(body, old, new)
            if new_body != body:
                changed += 1
                body = new_body
        lines.append(body + end)
    return "".join(lines), changed


def _dump_entry(entry: dict) -> str:
    return "- " + yaml.safe_dump(entry, allow_unicode=True, sort_keys=False, default_flow_style=True,
                                 width=10_000).strip()


def _ivanchev(root: Path, glyph: str, bg: str) -> str:
    from mtglang.ortho.glossary import generated, load_overrides
    words, entries = load_overrides(root)
    return generated(bg, f"symbols:{glyph}", words, entries)


def apply_symbol_edits(root: Path, edits: list[dict], lang: str = "en") -> dict:
    """Apply ``[{index, orig, glyph, ascii, label}]`` to glossary/symbols.yaml and migrate all card files.

    Nothing is written unless every file migrates cleanly. Returns ``{"files": n, "lines": m}``."""
    root = Path(root)
    gpath = root / "glossary" / "symbols.yaml"
    text = gpath.read_text(encoding="utf-8")
    lines = text.split("\n")
    entry_lines = [k for k, l in enumerate(lines) if l.startswith("- ")]
    entries = [(yaml.safe_load(lines[k]) or [None])[0] for k in entry_lines]
    old = load_glossary(root / "glossary")
    if len(entries) != len(old.symbols) or any(not isinstance(e, dict) for e in entries):
        raise EditError(["glossary/symbols.yaml must have exactly one '- {…}' line per symbol to be edited here"])

    errors: list[str] = []
    symbols = list(old.symbols)
    touched: set[int] = set()
    for ed in edits:
        i = ed.get("index")
        if not isinstance(i, int) or not 0 <= i < len(symbols):
            errors.append(f"no symbol #{i}")
            continue
        if ed.get("orig") != old.symbols[i].glyph:
            errors.append(f"symbol #{i} changed on disk (now {old.symbols[i].glyph!r}); reload the page")
            continue
        glyph, ascii_ = str(ed.get("glyph", "")).strip(), str(ed.get("ascii", "")).strip()
        label = str(ed.get("label", "")).strip()
        labels = dict(old.symbols[i].labels)
        if label:
            labels[lang] = label
            if lang == "bg":           # keep the generated old spelling in step with the edited modern label
                labels["bg-ivanchev"] = _ivanchev(root, glyph, label)
        symbols[i] = replace(old.symbols[i], glyph=glyph, ascii=ascii_, labels=labels)
        entry = dict(entries[i])
        entry["glyph"], entry["ascii"] = glyph, ascii_
        entry["labels"] = dict(entry.get("labels") or {}, **({lang: label} if label else {}))
        if label and lang == "bg":
            entry["labels"]["bg-ivanchev"] = labels["bg-ivanchev"]
        entries[i] = entry
        touched.add(i)
    if errors:
        raise EditError(errors)

    new = Glossary(symbols, old.names, old.effects)
    errors = [i.message for i in check_glossary(new) if i.severity == "error"]
    if errors:
        raise EditError(errors)

    # symbol definitions are notation too
    for i, s in enumerate(new.symbols):
        if s.definition:
            try:
                d = migrate_line(s.definition, old, new)
            except ValueError as e:
                errors.append(f"definition of {s.glyph!r}: {e}")
                continue
            if d != s.definition:
                entries[i] = dict(entries[i], definition=d)
                touched.add(i)

    writes: list[tuple[Path, str]] = []
    n_lines = 0
    for path in sorted((root / "cards").glob("*/*.mtgl")):
        src = read_card_text(path)
        if src is None:
            continue
        try:
            out, changed = _migrate_card(src, old, new)
        except ValueError as e:
            errors.append(f"{path.relative_to(root)}: {e}")
            continue
        if changed:
            writes.append((path, out))
            n_lines += changed
    if errors:
        raise EditError(errors[:20] + ([f"… and {len(errors) - 20} more"] if len(errors) > 20 else []))

    for i in touched:
        lines[entry_lines[i]] = _dump_entry(entries[i])
    gpath.write_text("\n".join(lines), encoding="utf-8")
    for path, out in writes:
        path.write_text(out, encoding="utf-8")
    return {"files": len(writes), "lines": n_lines}
