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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mtglang")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download the Scryfall snapshot into data/")
    f.add_argument("--root", default=".")
    f.set_defaults(func=cmd_fetch)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
