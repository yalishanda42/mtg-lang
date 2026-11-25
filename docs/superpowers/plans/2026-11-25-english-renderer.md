# English Renderer (AST → Oracle English) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render every card of the corpus from its resolved AST into English that matches Scryfall Oracle text, through a language-neutral planner, and measure the match with `mtglang eval-en`.

**Architecture:** resolved AST → `mtglang/planner.py` (language-neutral clause plans, `mtglang/planir.py`) → `mtglang/realize/en.py` (English word order, articles, inflection, Oracle idioms) using per-symbol `lex.en` data from the glossary (`mtglang/lexicon.py`). `mtglang/evalen.py` aligns rendered lines with Oracle lines, normalises, classifies mismatches and writes `build/eval-en/`. Unplanned constructs become `Gap` plan nodes so the eval runs from day one and coverage grows by mismatch frequency.

**Tech Stack:** Python ≥ 3.12, PyYAML, Jinja2, pytest, uv. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-25-english-renderer-design.md`

## Global Constraints

- No per-card strings: no table card/line → English, no `if card == …`; rules are about node kinds, lexicon data, or recurring constructions.
- No new named effects (`⟨…⟩` stays at the four existing ones); no notation symbol/marker whose only job is English style.
- The plan IR contains no English: no literal words, articles, English order, idioms. Planner choices are defaults that keep full information (antecedent phrase, clause boundaries, join kind, reason).
- Notation changes only when the eval exposes a difference in **meaning**; via `scripts/migrations/` when more than one card, spec §12 table updated.
- `mtglang validate` stays at 0 errors; every line keeps round-tripping (`S-ROUNDTRIP`); `uv run pytest` green after every task.
- `glossary/symbols.yaml` and `names.yaml` keep one `- {…}` flow-style line per entry; `mtglang serve` saves preserve `lex`.
- Normalisation before comparing: reminder text stripped (existing `oracle_lines`), whitespace collapsed, `’‘`→`'`, `“”`→`"`. Nothing else.
- Deterministic output.
- Commit and push after each task; messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Two-face `prepare` cards: each face's self-reference follows that face's type line ("this creature" on the creature face, "this spell" on the sorcery face) — test in Task 3.
2. A card whose file fails to parse or resolve: `eval-en` reports its lines with cause `ast` and continues; never crashes — test in Task 5.
3. Loyalty costs keep U+2212 (`−4:`), `+1:`, `0:`; X in costs and mana symbols render verbatim (`{X}{R}`) — test in Task 4.
4. Saving a label in the glossary editor keeps every entry's `lex` map unchanged — test in Task 1.
5. Self-reference of legendary cards: comma names use the part before the comma, planeswalkers their planeswalker subtype ("Ajani"), `names.yaml` `lex.en.short` overrides both ("Dr. Crusher") — test in Task 3.

---

### Task 1: Lexicon in the glossary

**Files:**
- Modify: `mtglang/glossary.py` (`Symbol.lex`, `Name.lex`, loader, `check_glossary` key check), `mtglang/validate.py` (corpus warning)
- Create: `mtglang/lexicon.py`
- Test: `tests/test_lexicon.py`, `tests/test_edit.py` (add one test)

**Interfaces:**
- Produces:
  - `Symbol.lex: dict[str, dict]` and `Name.lex: dict[str, dict]` (default `{}`), loaded from the entry's `lex:` key.
  - `LEX_KEYS: frozenset[str] = {"verb", "s", "ed", "ing", "noun", "pl", "adj", "prep", "frame", "word", "short", "poss"}`.
  - `class Lexicon` in `mtglang/lexicon.py`: `Lexicon(g: Glossary, lang: str)`; `.sym(index: int) -> dict` (the `lex[lang]` map, `{}` if absent); `.name(key: str) -> dict`; `.keyword(index: int) -> str` (`lex[lang].word`, else `Symbol.oracle`, else raises `KeyError`).
  - Issue codes: `G-LEX` (error: unknown key in a `lex` map, or `lex` not a map of maps); `G-LEX-EN` (warning, one summary line: symbols used in the corpus without `lex.en` and without `oracle`).

`frame` is a declarative slot string with literal prepositions only, e.g. `{object} onto {destination}`; placeholders must be slot names from `ARG_SLOTS` (checked under `G-LEX`). No conditionals in data.

- [ ] **Step 1:** write tests: `test_lex_loaded` (temp glossary entry `lex: {en: {verb: destroy, s: destroys}}` → `Lexicon(g,"en").sym(i) == {"verb": "destroy", "s": "destroys"}`); `test_lex_unknown_key_is_error` (`lex: {en: {colour: x}}` → `G-LEX`); `test_lex_frame_bad_slot_is_error` (`frame: "{foo} onto"` → `G-LEX`); `test_keyword_falls_back_to_oracle` (🪽 → `"Flying"`); in `tests/test_edit.py` `test_edit_preserves_lex` (fixture copy, add `lex` to a symbol line, `apply_symbol_edits` a label change on that symbol → the written line still has the identical `lex` map).
- [ ] **Step 2:** `uv run pytest tests/test_lexicon.py tests/test_edit.py -q` → new tests FAIL.
- [ ] **Step 3:** implement fields, loader, `_lex_problems`, `Lexicon`, `G-LEX-EN` in `validate_all` (symbols referenced by any card AST).
- [ ] **Step 4:** tests PASS; `uv run mtglang validate` → 0 errors (a `G-LEX-EN` warning is expected now).
- [ ] **Step 5:** commit `feat(lexicon): per-language lex data on glossary entries`, push.

---

### Task 2: Plan IR and planner skeleton

**Files:**
- Create: `mtglang/planir.py`, `mtglang/planner.py`
- Test: `tests/test_planner.py`

**Interfaces:**
- Consumes: resolved `A.Card` (`mtglang.astexport.card_ast`), `A.walk` paths.
- Produces (frozen dataclasses in `planir.py`; every node has `path: str` = the AST `walk` path it came from):
  - `CardContext(name: str, short: str, legendary: bool, type_syms: tuple[int, ...], subtype_keys: tuple[str, ...], face: int, is_spell: bool)`
  - `CardPlan(faces: tuple[FacePlan, ...])`; `FacePlan(ctx: CardContext, name: str, cost: str, types: A.TypeLine, stats: A.Stats | None, abilities: tuple[AbilityPlan, ...])`
  - `AbilityPlan(shape: str, parts: dict[str, Any], label: tuple = ())` — `shape` ∈ `keywords, static, triggered, activated, modal, mode, chapter, threshold, labelled`; `parts` keys per shape: `items` / `body` / `event, conds, while_, effect` / `cost, effect, limits` / `choose, modes` …
  - `SentencePlan(clauses: tuple, joins: tuple[Join, ...])` with `len(joins) == len(clauses) - 1`; `Join(kind: str, reason: str)`; `kind` ∈ `sentence, then, and, or, if, unless, if_do, if_dont, instead, while, as_though, until, for_each, where`.
  - `ClausePlan(pred: Any, subject: PhrasePlan | None, args: tuple[tuple[str, Any], ...], optional: bool, negated: bool, passive: bool, mood: str, tense: str, subject_shared: bool)` — `pred` is an `A.SymRef` / `A.EffectRef` / `A.Delta` / `A.PT`; `mood` ∈ `imperative, indicative`; `tense` ∈ `present, past, perfect`.
  - `PhrasePlan(heads: tuple, mods: tuple[tuple[str, Any], ...], number: str, quantity: str, definite: bool, ref: str, antecedent: "PhrasePlan | None", person: int, reason: str)` — `ref` ∈ `new, self, anaphor, you`; for `anaphor` the full `antecedent` plan is always set.
  - `Gap(kind: str, path: str)` — an AST node the planner doesn't handle yet.
  - `plan_card(card: A.Card, ctxs: list[CardContext], g: Glossary) -> CardPlan` in `planner.py`; `context_for(card: A.Card, face: int, g: Glossary) -> CardContext`.

- [ ] **Step 1:** write tests on real cards (`card_ast(ROOT, ref)`): `test_plan_keywords` (`fra/aerid-konstrari` ability 0 → shape `keywords`, one item 🪽); `test_plan_triggered_parts` (`fra/afterthought-sentry` ability 1 → shape `triggered`, `parts["event"]` is a `ClausePlan` whose subject `ref == "self"`); `test_anaphor_keeps_antecedent` (any corpus line with `☞` → its `PhrasePlan.ref == "anaphor"` and `antecedent` is not None); `test_unknown_kind_is_gap` (monkeypatch the dispatch table to drop `Modify` → a `Gap("modify", path)` appears, no exception); `test_no_english_in_plan` (plan every card; walk all dataclass fields; no `str` field outside `{path, kind, reason, shape, mood, tense, number, quantity, ref, name, short, cost}` and join/parts keys).
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** implement dataclasses; planner dispatch by AST class for abilities, `Effects`, `Coord`, `Action`, `Modify`, `NP`; everything else → `Gap`. Joins from `;` default to `Join("sentence", "default")`.
- [ ] **Step 4:** run → PASS.
- [ ] **Step 5:** commit `feat(planner): language-neutral plan IR and planner skeleton`, push.

---

### Task 3: Card context and self-reference

**Files:**
- Modify: `mtglang/planner.py` (`context_for`), `glossary/names.yaml` (`lex.en.short` where needed)
- Create: `mtglang/realize/__init__.py`, `mtglang/realize/en.py` (`self_phrase` only, for now)
- Test: `tests/test_realize_en.py`

**Interfaces:**
- Produces: `self_phrase(ctx: CardContext, lex: Lexicon, first: bool, in_token: bool) -> str` — legendary → `ctx.short`; otherwise `"this " + word`, word from the first subtype in `SELF_SUBTYPES = ("Saga", "Aura", "Equipment", "Vehicle", "Spacecraft", "Planet", "Class", "Case", "Room")` present, else the first of creature, land, artifact, enchantment, battle in the type line (lexicon noun), else `"spell"` for instants/sorceries; `in_token` (self inside an ability granted to a token) → `"this token"`. `first=False` is used by the realizer to decide "it" (Task 6); `self_phrase` itself always returns the full form.
- `context_for`: `short` = `names.yaml` `lex.en.short` if set; else planeswalker → its planeswalker subtype key; else name before the first comma; else full name.

- [ ] **Step 1:** tests: `fra/afterthought-sentry` → `"this creature"`; `fra/aerid-konstrari` → `"Aerid Konstrari"`; `fra/ajani-resolute` → `"Ajani"`; a comma legend (`fra/arni-humble-scribe`) → `"Arni"`; the `prepare` card `fra/vigorbloom-vanguard-seed-suture` face 0 → `"this creature"`, face 1 → `"this spell"`; a card using `short` (`trk/dr-beverly-crusher` → `"Dr. Crusher"`); a Saga (`trk/amok-time`) → `"this Saga"`.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** implement; add `lex: {en: {short: …}}` to the names the builder check listed ("Dr. Crusher", "Commander Musiker", "U.S.S. Cerritos" — confirm exact forms in Oracle).
- [ ] **Step 4:** PASS; `uv run mtglang validate` 0 errors.
- [ ] **Step 5:** commit `feat(en): card context and self-reference`, push.

---

### Task 4: English realizer core and headers

**Files:**
- Modify: `mtglang/realize/en.py`, `glossary/symbols.yaml` (`lex.en` for the symbols these lines use)
- Test: `tests/test_realize_en.py`

**Interfaces:**
- Consumes: `CardPlan` (Task 2), `Lexicon` (Task 1), `self_phrase` (Task 3).
- Produces:
  - `@dataclass FaceText(name: str, type_line: str, stats: str | None, lines: tuple[str, ...])`
  - `realize_card(plan: CardPlan, lex: Lexicon) -> list[FaceText]`
  - `render_card_en(root: Path, ref: str) -> list[FaceText]` (load, resolve, plan, realize).
  - A `Gap` renders as `⟦<kind>⟧` inside the line.
- Type line: reuse `validate.english_type_line` logic via the lexicon (keep `V-TYPE` passing). Stats: `2/2`, loyalty/defense value as Scryfall prints it.

Lines that must match exactly after this task (add to `MUST_MATCH` in `tests/test_en_lines.py`, a parametrized test comparing `render_card_en` with `oracle_lines` after normalisation):
- `fra/aerid-konstrari#0.0` "Flying"
- `fra/academic-ascent#0.0` "Target creature gets +2/+2 and gains flying until end of turn."
- `trk/dal-rel-augment-orphan#0.1` "{3}, Sacrifice a land: Draw a card."
- `fra/ajani-resolute#0.1` "0: You gain 1 life."
- one `−N:` loyalty line and one `{X}` cost line from the corpus (builder picks; Review Focus 3).

- [ ] **Step 1:** write `tests/test_en_lines.py` with `MUST_MATCH` above plus header tests (name, type line, stats equal Scryfall for 5 cards incl. a planeswalker).
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** implement NP realisation (quantity → "target"/"up to N target"/"each"/bare plural/"a"/"an"; filters "you control", relations), actions with `frame`, `Modify` (gets/gains), keyword lines (comma-joined, first capitalised, rest lowercase via lexicon), costs (`{3}, Sacrifice a land`), loyalty costs; add needed `lex.en` entries.
- [ ] **Step 4:** PASS.
- [ ] **Step 5:** commit `feat(en): realizer core, headers, keyword and cost lines`, push.

---

### Task 5: Eval, report, CLI, ratchet

**Files:**
- Create: `mtglang/evalen.py`, `mtglang/templates/eval_en.html`, `data/eval-en-accepted.yaml`, `tests/eval_en_baseline.json`
- Modify: `mtglang/cli.py` (`en`, `eval-en`)
- Test: `tests/test_evalen.py`

**Interfaces:**
- Consumes: `render_card_en` (Task 4), `oracle_lines`, `load_snapshot`.
- Produces:
  - `normalize(s: str) -> str` (Global Constraints rules).
  - `@dataclass LineResult(ref: str, field: str, notation: str, rendered: str, oracle: str, match: bool, cause: str | None)`; `ref` = `"<set>/<slug>#<face>.<k>"` for ability *k*, `#<face>.name|type|stats` for headers; `cause` ∈ `None` (match), `renderer`, `gap:<kind>`, `ast`, `align`, `notation`, `accepted`, `style:<id>`.
  - `evaluate(root: Path, sets: list[str] | None = None) -> list[LineResult]`.
  - `summary(results) -> dict` with `{"lines", "exact", "by_set": {code: [exact, lines]}, "by_cause": {cause: n}}`.
  - `write_report(results, out: Path) -> Path` → `out/eval-en/index.html` and `out/eval-en/report.json`.
  - `data/eval-en-accepted.yaml` schema:
    ```yaml
    categories:   # style the AST can't predict
      - {id: join, description: "…", tried: "rules attempted and why they fail", lines: ["fra/x#0.2", …]}
    accepted:     # one-offs
      - {line: "fra/x#0.1", reason: "…"}
    triage:       # known non-renderer causes, still mismatches
      - {line: "fra/x#0.3", cause: notation, note: "…"}
    ```
  - CLI: `mtglang en <set>/<slug>` prints name, type line, stats, lines; `mtglang eval-en [--set S] [--out build]` prints the summary and writes the report; exit 0.
  - `tests/eval_en_baseline.json`: `{"exact": N}`; `test_eval_en_ratchet` fails if `summary(evaluate(ROOT))["exact"] < N`.

Word diff in the report: `difflib.SequenceMatcher` over whitespace tokens; mismatches grouped by cause, renderer mismatches sub-grouped by first differing token pair.

- [ ] **Step 1:** tests: `test_normalize` (`"it’s  “x”"` → `"it's \"x\""`); `test_match_line` (academic-ascent → `match=True, cause=None`); `test_gap_cause` (a line with a Gap → `cause == "gap:<kind>"`); `test_parse_failure_is_ast` (fixture copy with a broken card line → results contain that card with `cause == "ast"`, other cards evaluated — Review Focus 2); `test_align` (fixture with one notation line dropped → `cause == "align"`); `test_accepted_category` (category entry → `cause == "style:join"`); `test_report_written` (files exist, JSON has `summary`); `test_eval_en_ratchet`.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** implement; set baseline to the current exact count.
- [ ] **Step 4:** PASS; run `uv run mtglang eval-en` and record the first numbers in the commit message.
- [ ] **Step 5:** commit `feat(eval-en): Oracle comparison, report, ratchet`, push.

---

### Tasks 6–10: Coverage

Each coverage task follows the same cycle, so the steps are stated once:

- [ ] **a.** Pick the mismatch groups of this task's area from `build/eval-en/index.html`; add 10–30 representative corpus lines (refs) to `MUST_MATCH`.
- [ ] **b.** `uv run pytest tests/test_en_lines.py -q` → those FAIL.
- [ ] **c.** Implement in planner (if the decision is language-neutral) or realizer (if English); add `lex.en` data. If a mismatch is a meaning loss, fix the card/AST (migration + spec §12) and record it; if it is non-derivable style, add a category with `tried`.
- [ ] **d.** Tests PASS; `uv run pytest -q` green; `uv run mtglang validate` 0 errors; raise `tests/eval_en_baseline.json` to the new exact count.
- [ ] **e.** Commit `feat(en): <area>` with before → after exact counts; push.

**Task 6 — events, triggers, references.** "When/Whenever" (derive: self one-time events — enters, dies, leaves, is put into a graveyard — take "When"; check against corpus), trigger subjects ("a land you control enters"), "this creature" vs "it" (`first` flag: full form at first mention in the ability, "it" after, unless the planner reason forbids), `☞` anaphors incl. "that player"/"its controller", event tense, intervening "if", activated limits ("Activate only once each turn.").

**Task 7 — noun phrases.** Quantities ("up to one", "each", "another", "all"), counts and `#` ("the number of …"), filters/relations ("with flying", "other than", "you don't control", "attacking"), zones ("from a graveyard", "your library", "top N cards"), characteristics ("its power", "mana value 3 or less"), tokens (`✚ ◌[2/2 ♦{W} «Cat» «Soldier» ♞] «Name» ∋ (…)` → "a 2/2 white Cat Soldier creature token named … with "…"", "this token" inside), colours, counters ("a +1/+1 counter").

**Task 8 — sentences.** Coordination, `;` joins (try rules: ", then" for two short imperatives of the same subject; ". Then" when the second clause changes subject after a `✚`/result; ", where X is" for `Bind`; leftovers → category `join`), conditions (if / unless / "If you do" / "If you don't"), replacements ("instead"), while/as long as, as though, until, timed durations and their placement (category `duration-order` for leftovers), for each, scoped subjects ("Each player discards…"), nested abilities in quotes, reflexive "When you do,", delayed triggers ("At the beginning of the next end step").

**Task 9 — ability shapes.** Modal ("Choose one —", "• " modes, "Choose one or more —"), Saga chapters ("I —", "II, III —"), station thresholds, labelled ability words ("Landfall — "), keywords with parameters ("Ward {2}", cycling variants), named effects (their `en` label verbatim), emblems ("You get an emblem with "…"").

**Task 10 — long tail.** Drive every remaining non-accepted mismatch to zero: each is fixed in renderer/planner, fixed in notation/AST (meaning loss), or added to a category/accepted entry with a reason. Done when `summary` shows `exact + accepted + style:* == lines` and no `renderer`/`gap:*`/`ast`/`align`/`notation` causes remain. Review `data/eval-en-accepted.yaml` as a whole: every category has a `tried` text; one-offs are rare.

---

### Task 11: Bulgarian probe

**Files:**
- Create: `docs/bg-probe.md`, `scripts/plan_dump.py` (prints a line's plan as indented text)
- Modify: `mtglang/planner.py` / `planir.py` only if the probe finds a missing feature

**Interfaces:**
- Consumes: `plan_card`.

- [ ] **Step 1:** pick 15 lines covering: pronoun/anaphor, plural subject, "each", "target", "up to one", trigger, intervening if, condition, duration, replacement, modal, token creation, counter, characteristic, "you" vs opponent.
- [ ] **Step 2:** for each, write in `docs/bg-probe.md`: notation, plan dump, Bulgarian rendering made **only** from the plan dump + glossary `bg` labels, and a note of every fact the Bulgarian needed (gender, definiteness, aspect, number …) and whether the plan carried it.
- [ ] **Step 3:** any fact the plan lacked → add it to the plan IR (with a test in `tests/test_planner.py`), English output unchanged (`test_en_lines.py` and ratchet still pass).
- [ ] **Step 4:** commit `docs: Bulgarian probe of the plan IR`, push.

---

### Task 12: Gallery column and docs

**Files:**
- Modify: `mtglang/render.py`, `mtglang/templates/page.html`, `mtglang/ui_strings.yaml` (`rendered_en` label, en + bg), `mtglang/cli.py` (`render` also writes the eval report), `README.md`, `spec/` (new §15 "Rendering"), `tests/test_render.py`

**Interfaces:**
- Consumes: `render_card_en`, `evaluate`, `normalize`.

- [ ] **Step 1:** test in `tests/test_render.py`: rendered page contains, for `fra/academic-ascent`, a cell with the rendered English and no mismatch class; for a known mismatching line (fixture copy with an edited card) the cell has class `mismatch`.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** add the "English (rendered)" column to the line-by-line table (class `mismatch` when `normalize(rendered) != normalize(oracle)`); `mtglang render` also writes `build/eval-en/`; README section on `en` / `eval-en`; spec §15: pipeline, plan IR, lexicon keys, self-reference rule, eval causes and categories.
- [ ] **Step 4:** PASS; `uv run mtglang render` works; `uv run mtglang validate` 0 errors.
- [ ] **Step 5:** commit `feat(gallery): rendered English column; docs`, push.
