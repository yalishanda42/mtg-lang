# Bulgarian Renderer (sample round) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render a ~25-card sample into modern and Ivanchev Bulgarian from the clause plans, and paint it as a third card in the gallery.

**Architecture:** `mtglang/realize/bg.py` (second realizer on `mtglang/planner.py`) + `lex.bg` word data in the glossary + `to_ivanchev` over each finished line. Gallery adds a third overlay for cards listed in `data/bg-sample.txt`.

**Tech Stack:** Python ≥ 3.12, PyYAML, Jinja2, pytest, uv. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-26-bulgarian-renderer-design.md`

## Global Constraints

- No per-card Bulgarian strings or line overrides; no translating English output.
- Planner changes only if language-neutral; English ratchet (`tests/eval_en_baseline.json`) must hold.
- Register: the existing `bg` labels' words (Твар, нишан, подобие, белег, щета, заточение …), late-19th-c. literary.
- `symbols.yaml` / `names.yaml` keep one `- {…}` flow line per entry; `mtglang validate` 0 errors.
- Commit and push after each task; messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Feminine/neuter heads agree everywhere (adjective, numeral, demonstrative, pronoun, participle): *нишанна твар*, *две твари*, *тая земя … наклонена*, *на нея* — tests in Task 3.
2. Ivanchev pass leaves mana symbols, `+1/+1`, digits and `—` untouched — test in Task 2.
3. A sample card whose plan the Bulgarian realizer can't handle shows `⟦…⟧` in the CLI and no third card is hidden silently — test in Task 3.
4. Gallery: non-sample cards render exactly as before (two figures) — test in Task 4.
5. Glossary editor save keeps `lex.bg` — covered by the existing whole-entry copy; test in Task 2.

---

### Task 1: Sample list and `mtglang bg`

**Files:** Create `data/bg-sample.txt`, `mtglang/realize/bg.py` (skeleton), `tests/test_realize_bg.py`; Modify `mtglang/cli.py`.

**Interfaces — Produces:** `SAMPLE_FILE = "data/bg-sample.txt"`; `load_sample(root: Path) -> list[str]` (refs `set/slug`, `#` comments ignored); `render_card_bg(root: Path, ref: str) -> list[BgFace]`; `@dataclass BgFace(name: str, type_line: str, stats: str | None, lines: tuple[str, ...], old: "BgFace | None")` where `old` is the Ivanchev version; `render_card(card: A.Card, g) -> list[BgFace]`. CLI `mtglang bg <set>/<slug> [--modern]` prints the Ivanchev text (and modern with `--modern`).

Sample: 25 cards, both sets, every ability line already matching Oracle in `build/eval-en/report.json`, covering: keyword line, activated cost, triggered (once and repeated), intervening if, modal, token creation, counters, until end of turn, as long as, replacement (*As … enters*), Saga, planeswalker, two-face card, equipment/aura, search chain.

- [ ] Test `test_sample_list`: 20–30 refs, both sets, each exists in `cards/`.
- [ ] Test `test_cli_bg_prints_name_and_lines` (structure only: name line + one line per Oracle line).
- [ ] Run → FAIL; implement; run → PASS; commit `feat(bg): sample list and mtglang bg skeleton`.

### Task 2: `lex.bg` data and the Ivanchev pass

**Files:** Modify `mtglang/glossary.py` (`LEX_KEYS` += `gender`, `def`, `pl_def`, `pf`, `ipf`, `ipf_s`, `pf_s`, `imp`, `part`, `num`), `glossary/symbols.yaml`, `glossary/names.yaml`, `mtglang/realize/bg.py`, `spec/language.md` §15.2.

**Interfaces — Produces:** `Lexicon(g, "bg")` entries; `to_old(text: str, root: Path) -> str` (Ivanchev with `ortho_overrides.yaml` words).

Key meanings: `gender` m/f/n; `noun`/`pl`/`def`/`pl_def` (твар / твари / тварта / тварите); verbs: `imp` (imperative 2sg: изтегли), `ipf_s` (3sg imperfective: тегли), `pf_s` (3sg perfective: изтегли), `pl` (3pl), `part` (past participle m sg: изтеглил); `adj` with forms via a small inflection rule (m base, f +а, n +о, pl +и) unless overridden.

- [ ] Test `test_bg_lex_keys_valid` (G-LEX clean) and `test_to_old_keeps_symbols` (`"Сложи белег +1/+1 на {G} — тварта"` keeps `+1/+1`, `{G}`, `—`, gives *тварьта*-style spelling per converter).
- [ ] Test `test_edit_preserves_lex_bg`.
- [ ] Run → FAIL; add keys, data for the sample's words; run → PASS; commit `feat(bg): lex.bg word data, Ivanchev pass`.

### Task 3: Bulgarian realizer for the sample

**Files:** Modify `mtglang/realize/bg.py`; Test `tests/test_realize_bg.py`.

**Interfaces — Consumes:** plan IR (`planir.py`), `Lexicon(g, "bg")`. Mirrors `En` (`ability`, `sentences`, `clause`, `np`, `time`, `move`, `compare` …) with Bulgarian rules: temporal clause by `once` (*Когато … встъпи* / *Щом … напада*), `aspect`, `tense`, `self_as`, gender agreement, definite plural for quantity `all`, imperative for implicit-controller clauses, *можеш да* for optional.

- [ ] Test `test_sample_has_no_gaps` (every sample line, modern and old, contains no `⟦`).
- [ ] Tests for Review Focus 1: pick sample lines that exercise feminine adjective, numeral, demonstrative, pronoun, participle; assert the agreeing form appears.
- [ ] Run → FAIL; implement; run → PASS; English ratchet still passes; commit `feat(bg): Bulgarian realizer for the sample`.

### Task 4: Third card in the gallery

**Files:** Modify `mtglang/render.py` (`card_view` gets `bg_faces`), `mtglang/templates/page.html` (third `<figure>` when present), `mtglang/ui_strings.yaml` (`old_bulgarian` caption); Test `tests/test_render.py`.

- [ ] Test: a sample card's `.pair` has three figures and the third contains its Ivanchev name; a non-sample card has two.
- [ ] Run → FAIL; implement; run → PASS; commit `feat(gallery): old-Bulgarian third card for the sample`.

### Task 5: Docs

- [ ] README (`bg` command, sample), spec §15 note on the Bulgarian realizer; commit `docs: Bulgarian renderer`.
