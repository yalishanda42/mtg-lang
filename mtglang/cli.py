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


def cmd_sync_names(args) -> int:
    from mtglang.glossary import sync_names
    print(f"added {sync_names(Path(args.root))} name(s)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mtglang")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download the Scryfall snapshot into data/")
    f.add_argument("--root", default=".")
    f.set_defaults(func=cmd_fetch)
    s = sub.add_parser("sample", help="print a feature-covering sample of cards")
    s.add_argument("--root", default=".")
    s.add_argument("--k", type=int, default=30)
    s.set_defaults(func=cmd_sample)
    v = sub.add_parser("validate", help="check all card files")
    v.add_argument("--root", default=".")
    v.add_argument("--set", action="append", choices=list(scryfall.SETS))
    v.add_argument("--only-existing", action="store_true", help="don't report cards without a file")
    v.set_defaults(func=cmd_validate)
    n = sub.add_parser("sync-names", help="add snapshot card names and subtypes to glossary/names.yaml")
    n.add_argument("--root", default=".")
    n.set_defaults(func=cmd_sync_names)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
