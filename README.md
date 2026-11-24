# MTG-Lang

A language-independent notation for *Magic: The Gathering* card text. Each card's rules text is
written in a compact, symbol-heavy notation (`cards/<set>/<slug>.mtgl`) that a reader can learn once
and read in any language. Only proper names (`«…»`) and rare one-off effects (`⟨…⟩`) are words,
and the glossary translates those.

```
«Essence Burn» {1}{R}
ϟ

◈ ✸5 → ◎(♞ ∨ ⚝)[♦{B} ∨ ♦{G}] ; ☞☠ ◷ ⤳ ☞ → ⊘
```

v0.1 covers two sets, Reality Fracture (`fra`) and Star Trek (`trk`): 596 cards, 0 validation errors.

- **Language spec:** [`spec/language.md`](spec/language.md)
- **Vocabulary:** [`glossary/`](glossary): `symbols.yaml`, `names.yaml`, `named_effects.yaml`
- **Readability report:** [`docs/report-v0.1.md`](docs/report-v0.1.md)
- **Gallery:** deployed to GitHub Pages on every push to `main`

## Setup

Requires Python ≥ 3.12 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
```

Run every command below from the repo root as `uv run mtglang <command>`. All commands accept
`--root DIR` (default `.`) to point at a different checkout.

## Commands

| Command | What it does |
|---|---|
| `fetch` | Download the Scryfall snapshot into `data/` |
| `fetch-symbols` | Download mana/tap symbol SVGs into `data/symbols/` |
| `sync-names` | Add snapshot card names and subtypes to `glossary/names.yaml` |
| `sample` | Print a sample of cards that covers the notation's features |
| `validate` | Check every card file against Scryfall and the glossary |
| `render` | Build the single-page HTML gallery and the ASCII export |
| `serve` | Serve the gallery on localhost, with a glossary editor that can save |
| `backtrans` | Write a back-translation test bundle and its answer key |

### `fetch`

```sh
uv run mtglang fetch
```

Downloads every card in the configured sets (`fra`, `trk`) to `data/<set>.json`, plus Scryfall's
catalogs to `data/catalogs.json`. The snapshot is committed, so you only need this to refresh it.

### `fetch-symbols`

```sh
uv run mtglang fetch-symbols
```

Downloads Scryfall's symbol SVGs (`{G}`, `{T}`, `{2/W}`, …) into `data/symbols/` with an
`index.json`. The renderer embeds them in the gallery.

### `sync-names`

```sh
uv run mtglang sync-names
```

Adds any card names and subtypes in the snapshot that `glossary/names.yaml` is missing, and prints
how many it added. Existing entries and their translations are left alone.

### `sample`

```sh
uv run mtglang sample [--k 30]
```

Prints `<set>/<slug>` for `--k` cards (default 30), chosen to cover the notation's features.
This is useful when reviewing changes to the language.

### `validate`

```sh
uv run mtglang validate [--set fra] [--set trk] [--only-existing]
```

Checks each card file against Scryfall (name, mana cost, type line, P/T or loyalty, face count, one
notation line per Oracle line) and against the glossary (known symbols, names and effects, no
English words outside `«…»` or `⟨…⟩`, and identical notation for identical Oracle lines).

| Option | Meaning |
|---|---|
| `--set CODE` | Only check this set. Repeat it to check several. Default: all sets |
| `--only-existing` | Don't report cards that have no `.mtgl` file yet |

Exits with status 1 if there are any errors. Warnings alone exit 0.

### `render`

```sh
uv run mtglang render [--out build] [--lang en]
```

Writes `<out>/index.html`, a self-contained gallery with card views, notation painted over the card
scans, and a Legend tab. It also writes the plain-ASCII notation to `<out>/ascii/<set>.txt`.

| Option | Meaning |
|---|---|
| `--out DIR` | Output directory (default `build`) |
| `--lang CODE` | Language for names and symbol meanings (default `en`) |

### `serve`

```sh
uv run mtglang serve [--port 8765] [--out build] [--lang en]
```

Renders the gallery and serves it at `http://localhost:8765`. In this mode the Legend tab works as
an editor: changes to a symbol's glyph, ASCII alias or meaning preview live on every card. **Save**
rewrites `glossary/symbols.yaml` and every affected card file. The rewrite is token-aware and
refuses any edit that would make a line ambiguous.

### `backtrans`

```sh
uv run mtglang backtrans [--n 40] [--seed 7] [--out build/backtrans]
```

Writes a readability test. `bundle.md` holds `--n` cards in notation only, for a reader to
translate back to English, and `key.md` holds the Oracle text to grade against. `--seed` makes the
card selection reproducible.

## Development

```sh
uv run pytest -q          # run the test suite
uv run mtglang validate   # check the corpus
uv run mtglang render     # build the gallery into build/
```

CI ([`.github/workflows/pages.yml`](.github/workflows/pages.yml)) runs these same three steps on every
push to `main` and deploys the rendered gallery to GitHub Pages.

## Layout

```
cards/<set>/*.mtgl   one notation file per card
glossary/            symbols, proper names, one-off effects
data/                Scryfall snapshot and symbol SVGs
spec/language.md     the language specification
mtglang/             the toolchain (parser, validator, renderer, server)
tests/               pytest suite and fixtures
```
