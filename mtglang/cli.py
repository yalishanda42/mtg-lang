"""Command-line interface: `mtglang <command>`."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from mtglang import scryfall


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cmd_fetch(args) -> int:
    root = Path(args.root)
    for code in scryfall.SETS:
        cards = scryfall.fetch_set(code)
        _write_json(root / "data" / f"{code}.json", cards)
        print(f"{code}: {len(cards)} cards")
    _write_json(root / "data" / "catalogs.json", scryfall.fetch_catalogs())
    return 0


def cmd_fetch_symbols(args) -> int:
    n = scryfall.fetch_symbols(Path(args.root) / "data" / "symbols")
    print(f"{n} symbol(s) saved to data/symbols/")
    return 0


def cmd_sample(args) -> int:
    from mtglang.sample import pick_sample
    snap = scryfall.load_snapshot(Path(args.root) / "data")
    for c in pick_sample(snap.values(), k=args.k):
        print(f"{c.set_code}/{c.slug}")
    return 0


def cmd_validate(args) -> int:
    from mtglang.validate import validate_all
    issues, stats = validate_all(Path(args.root), sets=args.set or None, only_existing=args.only_existing)
    for i in issues:
        print(i)
    n_err = sum(1 for i in issues if i.severity == "error")
    n_warn = len(issues) - n_err
    print(f"{stats['cards']} card(s), {stats['ability_lines']} ability line(s), "
          f"named effects {stats['named_effect_rate']:.1%} — {n_err} error(s), {n_warn} warning(s)")
    return 1 if n_err else 0


def cmd_ast(args) -> int:
    from mtglang.astexport import card_ast, coverage
    from mtglang.ast import to_json
    from mtglang.semparse import SemSyntaxError
    if args.coverage:
        c = coverage(Path(args.root))
        print(f"parsed {c['parsed']}/{c['total']}, roundtrip {c['roundtrip']}/{c['total']}")
        for k, (msg, where) in enumerate(sorted(c["failures"].items(), key=lambda kv: -len(kv[1]))):
            if k == 20:
                break
            print(f"  {len(where):4}  {msg}  e.g. {where[0]}")
        return 0 if c["roundtrip"] == c["total"] else 1
    if not args.card:
        print("give <set>/<slug> or --coverage")
        return 2
    try:
        card = card_ast(Path(args.root), args.card)
    except SemSyntaxError as e:
        print(f"{args.card}:{getattr(e, 'line', '?')}: {e}")
        return 1
    if card is None:
        print(f"no card file for {args.card}")
        return 1
    print(json.dumps(to_json(card), ensure_ascii=False, indent=1))
    return 0


def cmd_ortho(args) -> int:
    try:
        return _ortho(args)
    except ValueError as e:
        print(f"error: {e}")
        return 1


def _ortho(args) -> int:
    import sys
    from mtglang.ortho.glossary import load_overrides, regenerate, review_markdown
    from mtglang.ortho.ivanchev import to_ivanchev
    root = Path(args.root)
    if args.glossary:
        ow = args.overwrite if args.overwrite is None else (True if args.overwrite == [] else args.overwrite)
        r = regenerate(root, overwrite=ow if ow is not None else False)
        for key, old, new in r.overwritten:
            print(f"overwrote {key}: {old} → {new}")
        if r.conflicts:
            print("not written: these bg-ivanchev labels differ from what bg + the overrides give now — a hand edit, "
                  "or a label left from an earlier bg / converter. Keep a hand edit by moving it into "
                  "glossary/ortho_overrides.yaml → entries; replace stale ones with --overwrite KEY … "
                  "(or --overwrite alone for all):")
            for k in r.conflicts:
                print(f"  {k}")
            return 1
        print(f"updated {r.changed} bg-ivanchev label(s)")
        return 0
    if args.review:
        out = root / "docs" / "bg-review.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(review_markdown(root) + "\n", encoding="utf-8")
        print(f"wrote {out}")
        return 0
    text = args.text if args.text is not None else sys.stdin.read()
    words = load_overrides(root)[0] if (root / "glossary").exists() else {}
    print(to_ivanchev(text, words).rstrip("\n"))
    return 0


def cmd_sync_names(args) -> int:
    from mtglang.glossary import sync_names
    print(f"added {sync_names(Path(args.root))} name(s)")
    return 0


def cmd_render(args) -> int:
    from mtglang.astexport import export_ast
    from mtglang.render import render_site
    print(f"wrote {render_site(Path(args.root), Path(args.out), lang=args.lang)}")
    for p in export_ast(Path(args.root), Path(args.out)):
        print(f"wrote {p}")
    return 0


def cmd_serve(args) -> int:
    from mtglang.serve import serve
    serve(Path(args.root), Path(args.out), lang=args.lang, port=args.port)
    return 0


def cmd_backtrans(args) -> int:
    from mtglang.backtrans import backtrans_bundle
    bundle, key = backtrans_bundle(Path(args.root), args.n, args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "bundle.md").write_text(bundle, encoding="utf-8")
    (out / "key.md").write_text(key, encoding="utf-8")
    print(f"wrote {out / 'bundle.md'} and {out / 'key.md'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mtglang")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download the Scryfall snapshot into data/")
    f.add_argument("--root", default=".")
    f.set_defaults(func=cmd_fetch)
    fs = sub.add_parser("fetch-symbols", help="download Scryfall mana/tap symbol SVGs into data/symbols/")
    fs.add_argument("--root", default=".")
    fs.set_defaults(func=cmd_fetch_symbols)
    s = sub.add_parser("sample", help="print a feature-covering sample of cards")
    s.add_argument("--root", default=".")
    s.add_argument("--k", type=int, default=30)
    s.set_defaults(func=cmd_sample)
    v = sub.add_parser("validate", help="check all card files")
    v.add_argument("--root", default=".")
    v.add_argument("--set", action="append", choices=list(scryfall.SETS))
    v.add_argument("--only-existing", action="store_true", help="don't report cards without a file")
    v.set_defaults(func=cmd_validate)
    a = sub.add_parser("ast", help="print a card's semantic AST as JSON, or --coverage of the whole corpus")
    a.add_argument("card", nargs="?", help="<set>/<slug>, e.g. fra/ajani-resolute")
    a.add_argument("--root", default=".")
    a.add_argument("--coverage", action="store_true", help="count lines that parse and round-trip")
    a.set_defaults(func=cmd_ast)
    o = sub.add_parser("ortho", help="convert modern Bulgarian to Ivanchev (pre-1945) spelling, offline")
    o.add_argument("text", nargs="?", help="text to convert (default: read stdin)")
    o.add_argument("--root", default=".")
    o.add_argument("--glossary", action="store_true", help="regenerate every bg-ivanchev label from bg")
    o.add_argument("--overwrite", nargs="*", metavar="KEY",
                   help="with --glossary: replace differing labels — only the KEYs given, or all if none")
    o.add_argument("--review", action="store_true", help="write docs/bg-review.md")
    o.set_defaults(func=cmd_ortho)
    n = sub.add_parser("sync-names", help="add snapshot card names and subtypes to glossary/names.yaml")
    n.add_argument("--root", default=".")
    n.set_defaults(func=cmd_sync_names)
    r = sub.add_parser("render", help="write the single-page HTML gallery (index.html) and the ASCII export")
    r.add_argument("--root", default=".")
    r.add_argument("--out", default="build")
    r.add_argument("--lang", default="en")
    r.set_defaults(func=cmd_render)
    sv = sub.add_parser("serve", help="serve the gallery on localhost; glossary edits made in the page can be saved")
    sv.add_argument("--root", default=".")
    sv.add_argument("--out", default="build")
    sv.add_argument("--lang", default="en")
    sv.add_argument("--port", type=int, default=8765)
    sv.set_defaults(func=cmd_serve)
    b = sub.add_parser("backtrans", help="write a back-translation bundle and answer key")
    b.add_argument("--root", default=".")
    b.add_argument("--n", type=int, default=40)
    b.add_argument("--seed", type=int, default=7)
    b.add_argument("--out", default="build/backtrans")
    b.set_defaults(func=cmd_backtrans)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
