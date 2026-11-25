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
- **Languages:** every glossary entry has `en`, `bg` and `bg-ivanchev` (pre-1945 spelling) labels;
  `mtglang render --lang bg-ivanchev` shows the gallery in old Bulgarian. Review table: [`docs/bg-review.md`](docs/bg-review.md)
- **Semantic AST:** [`spec/language.md` §13](spec/language.md#13-semantic-ast)
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
| `render` | Build the single-page HTML gallery, the ASCII export and the AST export |
| `serve` | Serve the gallery on localhost, with a glossary editor that can save |
| `backtrans` | Write a back-translation test bundle and its answer key |
| `ast` | Print a card's semantic AST as JSON, or `--coverage` of the corpus |
| `ortho` | Convert modern Bulgarian to the pre-1945 (Ivanchev) spelling, offline; maintain `bg-ivanchev` labels |
| `en` | Print a card rendered into English from its AST |
| `eval-en` | Compare AST → English with Oracle text for every line; write a report |

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
scans, and a Legend tab. It also writes the plain-ASCII notation to `<out>/ascii/<set>.txt`. The
line-by-line tables have an "English (rendered)" column (the AST rendered into English; cells that differ
from Oracle are tinted), and the eval report is written to `<out>/eval-en/`.

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

### `ast`

```sh
uv run mtglang ast fra/ajani-resolute
uv run mtglang ast --coverage
```

Prints the card's semantic AST as JSON: every ability as a typed tree (actions, phrases, filters, times …),
with each phrase's quantity and number and what every `☞` refers to (spec §13). `--coverage` counts the
ability lines that parse and round-trip back to identical notation, and lists the first failures.
`mtglang render` also writes the ASTs of all cards to `build/ast/<set>.json`.

### `ortho`

```sh
uv run mtglang ortho "Почиват яростни вълни"     # → Почиватъ яростни вълни
echo "за път обратен" | uv run mtglang ortho      # reads stdin
uv run mtglang ortho --glossary                   # regenerate every bg-ivanchev label from bg
uv run mtglang ortho --review                     # write docs/bg-review.md
```

Converts modern Bulgarian to the Ivanchev orthography used until 1945 (final ъ / ь, ѣ, ѫ, сѫ, -тѣ),
entirely offline. Corrections live in `glossary/ortho_overrides.yaml`: `words` (a word everywhere) and
`entries` (one glossary label). `--glossary` refuses to overwrite a label that differs from the converter's
output unless you pass `--overwrite`, which lists every label it replaces.

The converter is a port of the engine behind [pravopis.osvedomitel.bg](https://pravopis.osvedomitel.bg/)
([Peshowe/converter-web-app](https://github.com/Peshowe/converter-web-app), © 2021 Petar Nedelev, MIT
License); its word lists are vendored in `mtglang/ortho/data/` with the license and provenance.

### `en` and `eval-en`

```sh
uv run mtglang en fra/academic-ascent
uv run mtglang eval-en [--set fra] [--out build]
```

`en` renders a card into English from its AST: name, type line, stats and one line per Oracle line. The
pipeline is AST → language-neutral clause plan (`mtglang/planner.py`) → English realizer
(`mtglang/realize/en.py`), with the English words in the glossary's `lex.en` data (spec §15).

`eval-en` renders every line of the corpus, compares it with Oracle (reminder text stripped, whitespace and
typographic quotes normalised, nothing else) and prints the exact-match rate per set and the mismatches by
cause. `<out>/eval-en/index.html` lists every mismatch with a word diff; `report.json` has the same data.
Deliberate differences are listed in `data/eval-en-accepted.yaml`. A test keeps the exact-match count from
dropping (`tests/eval_en_baseline.json`).

