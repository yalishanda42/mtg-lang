# Bulgarian Labels and Ivanchev Spelling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An offline modern-Bulgarian → Ivanchev spelling converter (`mtglang ortho`) plus `bg` / `bg-ivanchev` labels for every glossary symbol, name and named effect, in a Vazov-era literary register.

**Architecture:** `mtglang/ortho/` ports the pravopis.osvedomitel.bg engine (Peshowe/converter-web-app, MIT) to dependency-free Python with vendored word lists; `glossary/ortho_overrides.yaml` holds reviewed corrections. Labels live in the existing `labels:` maps; `bg-ivanchev` is generated from `bg` and stored. The gallery reads labels and a small UI string table per `--lang`.

**Tech Stack:** Python ≥ 3.12, PyYAML, Jinja2, pytest, uv. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-25-bulgarian-ivanchev-design.md`

## Global Constraints

- No network at conversion time; upstream data vendored once from commit `d4db8e961d57b8880744b820388fbe1035ab2e1e`.
- Upstream MIT LICENSE kept next to vendored data; README credits pravopis.osvedomitel.bg / Petar Nedelev.
- `symbols.yaml` and `names.yaml` keep one `- {…}` flow-style line per entry.
- Labels: `bg` = modern spelling, citation form (nouns nominative singular unless the English label is plural; actions in card imperative: Изтегли, Унищожи); `bg-ivanchev` = generated, period-correct; corrections only via `ortho_overrides.yaml`.
- Register: Vazov-era literary Bulgarian — native / Church-Slavonic-flavoured words, Ottoman-era words where they fit; never manual-speak.
- `mtglang validate` stays at 0 errors throughout (missing Bulgarian labels are warnings `G-LABEL-BG`).
- Commit and push after each task; commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Mixed-case and capitalised words (`Тварь`, ALL CAPS, `«Аджаниев побратим»`) keep their case through conversion — test in Task 2.
2. Punctuation, dashes and guillemets around words (`—`, `«»`, commas, apostrophes in names) survive conversion unchanged — test in Task 2.
3. Text that is already in Ivanchev spelling (contains ѣ/ѫ/final ъ) is not double-converted (`пѫть` stays, no `ъъ`) — test in Task 2.
4. Latin letters, digits, mana symbols `{G}` in a label pass through untouched — test in Task 2.
5. Saving in the glossary editor (`mtglang serve`) with `--lang en` must keep `bg` / `bg-ivanchev` labels — test in Task 4.

---

### Task 1: Vendor upstream data

**Files:**
- Create: `mtglang/ortho/__init__.py`, `mtglang/ortho/data/*.txt`, `mtglang/ortho/data/LICENSE.md`, `mtglang/ortho/data/README.md`, `tests/fixtures/ortho/text*.txt`, `tests/fixtures/ortho/conv*.txt`
- Modify: `pyproject.toml` (ensure `mtglang/ortho/data` ships in the wheel — hatch includes package data by default; verify)

**Interfaces:**
- Produces: `mtglang.ortho.data_path(name: str) -> Path`.

Files to vendor from `converter/static/converter/word_lists/`: yatRoots, yatExclusions, usRoots, usExclusions, nonYatPrefixRoots, abbreviations, masculine_soft_ending, feminine_soft_ending, nouns_in_te, verbs-te, verbs_only_homonyms. From `test_files/`: every `text*.txt` with its `conv*.txt` pair. README records the commit, date, URLs, and which files were deliberately not vendored (most_freq.txt, BERT weights) and why.

- [ ] **Step 1:** write `tests/test_ortho_data.py::test_all_lists_present` — every listed file exists via `data_path`, is UTF-8, non-empty; LICENSE mentions "Petar Nedelev".
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** download with `curl -sfL` from `https://raw.githubusercontent.com/Peshowe/converter-web-app/d4db8e9…/…` into the data dir; strip BOMs; write README; implement `data_path`.
- [ ] **Step 4:** run → PASS.
- [ ] **Step 5:** commit `feat(ortho): vendor converter word lists (MIT, pinned)`.

---

### Task 2: Converter port

**Files:**
- Create: `mtglang/ortho/ivanchev.py`
- Test: `tests/test_ortho.py`

**Interfaces:**
- Produces: `to_ivanchev(text: str, words: dict[str, str] | None = None) -> str` (words = override pairs, lowercase modern → old, applied per word before rules, case preserved); `convert_word(word: str) -> str` (lowercase in/out); `word_accuracy(modern: str, original: str) -> float`.

Port every rule of upstream `Converter` (`_checkEnding`, `_checkUs`, `_checkYat`, `_checkFeminineThe`, `_checkExclusionWords`, `_wordVerified`, case keeping) and the constant sets in `process_vocabs.py` verbatim; `-те` homographs take the non-verb reading (upstream behaviour without BERT). Replace nltk with a regex word tokenizer over Cyrillic letters (`[А-Яа-яЀ-ӿ]+`), leaving every other character untouched. Words already containing ѣ, ѫ, or ending in ъ/ь after a consonant are returned unchanged.

- [ ] **Step 1: failing tests**

```python
def test_final_yer():            assert to_ivanchev("Почиват яростни вълни") == "Почиватъ яростни вълни"
def test_yat_and_yus():          assert to_ivanchev("за път обратен") == "за пѫть обратенъ"      # from upstream pair
def test_sa():                   assert to_ivanchev("те са") == "тѣ сѫ"
def test_soft_feminine():        assert to_ivanchev("крилатост") == "крилатость"
def test_case_kept():            assert to_ivanchev("ВЯТЪР Вятър") == "ВѢТЪРЪ Вѣтъръ"
def test_punctuation_kept():     assert to_ivanchev("«Аджани» — път, {G}") == "«Аджани» — пѫть, {G}"
def test_idempotent():           assert to_ivanchev(to_ivanchev("път вятър")) == to_ivanchev("път вятър")
def test_override_wins():        assert to_ivanchev("мана", {"мана": "манна"}) == "манна"
def test_latin_digits_untouched(): assert to_ivanchev("X 2 ABC") == "X 2 ABC"
def test_accuracy_on_upstream_pairs():
    acc = mean(word_accuracy(t, c) for t, c in pairs())
    assert acc >= THRESHOLD     # THRESHOLD = first measured value − 0.02, written into the test
```
(Exact expected strings for yat/yus cases are taken from the vendored `conv*.txt` lines; adjust a case only if the upstream pair says otherwise.)

- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** implement.
- [ ] **Step 4:** run → PASS; record the measured accuracy in the test docstring.
- [ ] **Step 5:** commit `feat(ortho): offline Ivanchev spelling converter`.

---

### Task 3: Overrides, CLI, glossary regeneration, review file

**Files:**
- Create: `glossary/ortho_overrides.yaml` (`words: {}`, `entries: {}`), `mtglang/ortho/glossary.py`
- Modify: `mtglang/cli.py`
- Test: `tests/test_ortho_cli.py`

**Interfaces:**
- Produces: `load_overrides(root) -> tuple[dict, dict]`; `regenerate(root) -> RegenResult(changed: int, conflicts: list[str])` — sets `bg-ivanchev` for every entry with `bg`: `entries[key]` if present else `to_ivanchev(bg, words)`; if an existing `bg-ivanchev` differs from what would be generated and the key is not in `entries`, nothing is written and the conflicts are returned. Keys: `symbols:<glyph>`, `names:<key>`, `effects:<key>`. Writes YAML preserving the one-line-per-entry format (reuse `edit._dump_entry` style).
- Produces: `review_markdown(root) -> str` — tables by kind (symbols grouped by class; names by class, cards by set); columns `en | bg | bg-ivanchev | note` (note: "override: word→word" / "entry override" / translator remark from an optional `note:` label key `bg-note`).
- CLI: `mtglang ortho [TEXT]` (stdin if absent), `mtglang ortho --glossary` (exit 1 and list conflicts), `mtglang ortho --review` (writes `docs/bg-review.md`).

- [ ] **Step 1: failing tests** — CLI converts argument and stdin; `--glossary` on a fixture glossary fills `bg-ivanchev`, is idempotent, refuses on a hand-edited label not in `entries`, honours `entries`; `--review` output contains a header per kind and one row per entry with `bg`.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** implement.
- [ ] **Step 4:** run → PASS.
- [ ] **Step 5:** commit `feat(ortho): mtglang ortho CLI, overrides, glossary regeneration, review file`.

---

### Task 4: Validation warning, editor safety, gallery UI strings

**Files:**
- Modify: `mtglang/glossary.py` (`check_glossary` → warning `G-LABEL-BG`), `mtglang/render.py`, `mtglang/templates/page.html`
- Create: `glossary/ui_strings.yaml`
- Test: `tests/test_glossary.py`, `tests/test_edit.py`, `tests/test_render.py`

**Interfaces:**
- `G-LABEL-BG` (severity warning) per entry missing `bg` or `bg-ivanchev`; summary counts them once per file kind to keep output short (one warning per glossary file with the count and first 5 keys).
- `ui_strings.yaml`: `- {id: legend, labels: {en: Legend, bg: Легенда, bg-ivanchev: Легенда}}` …; render passes `ui(id)` to the template with fallback to `en`; class headings via ids `class:<cls>`.

- [ ] **Step 1: failing tests** — warning appears with one missing `bg`; editor save with lang `en` keeps a `bg` label on the edited symbol (Review Focus 5); `render_site(..., lang="bg")` output contains the `bg` Legend heading and a symbol's `bg` tooltip; unknown lang falls back to English.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** implement (all hard-coded English strings in `page.html` go through `ui`).
- [ ] **Step 4:** run → PASS; `mtglang validate` still 0 errors.
- [ ] **Step 5:** commit `feat: Bulgarian label warnings, gallery UI strings per language`.

---

### Task 5: Translate symbols

**Files:** Modify `glossary/symbols.yaml`, `glossary/ortho_overrides.yaml`, `glossary/ui_strings.yaml`

- [ ] **Step 1:** add `bg` to all ≈200 symbols (keywords, actions, types, zones, time, logic, structural, counters, stats). Keyword terms are coined in the register; actions in card imperative; reminder of English meaning comes from the `en` label.
- [ ] **Step 2:** `mtglang ortho --glossary`; then check every generated `bg-ivanchev` by hand against Ivanchev rules; record fixes as `words`/`entries` overrides; rerun until no conflicts.
- [ ] **Step 3:** `uv run pytest -q`; `mtglang validate` (0 errors; `G-LABEL-BG` count for symbols = 0).
- [ ] **Step 4:** commit `glossary: Bulgarian + Ivanchev labels for all symbols`.

---

### Task 6: Translate subtypes, tokens, flavor words, named effects

**Files:** Modify `glossary/names.yaml`, `glossary/named_effects.yaml`, `glossary/ortho_overrides.yaml`

- [ ] **Step 1:** `bg` for 157 subtypes, 9 tokens, 35 flavor words, 4 named effects (full sentences for effects).
- [ ] **Step 2–4:** as Task 5 (regenerate, hand-check, overrides, validate).
- [ ] **Step 5:** commit `glossary: Bulgarian + Ivanchev labels for subtypes, tokens, flavor words, effects`.

---

### Task 7: Translate card names

**Files:** Modify `glossary/names.yaml`, `glossary/ortho_overrides.yaml`

600 card names, in batches by set (fra, trk), ~100 per batch. Rules: translate meaning and keep wordplay where possible; character names transliterated in the old manner with possessive adjectives (Аджаниев); established Star Trek Bulgarian names kept (Спок, Кърк, Пикар); a `bg-note` label key explains non-obvious choices.

- [ ] **Step 1:** translate a batch; `mtglang ortho --glossary`; hand-check; overrides. Repeat until done.
- [ ] **Step 2:** `uv run pytest -q`; `mtglang validate` (0 errors, 0 `G-LABEL-BG`).
- [ ] **Step 3:** commit per set: `glossary: Bulgarian + Ivanchev card names (<set>)`.

---

### Task 8: Review file, gallery check, docs

**Files:** Create `docs/bg-review.md`; Modify `README.md`, `spec/language.md` (§14 Languages: label keys, ortho pipeline, overrides)

- [ ] **Step 1:** `mtglang ortho --review`; `mtglang render --lang bg-ivanchev --out build/bg-ivanchev` builds; open the HTML and spot-check Legend + 10 cards (names, tooltips, UI strings).
- [ ] **Step 2:** README: `ortho` command section, attribution; spec §14.
- [ ] **Step 3:** final `uv run pytest -q`, `mtglang validate`.
- [ ] **Step 4:** commit + push `docs: Bulgarian review file, ortho docs`.
