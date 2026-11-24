# Semantic AST Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse every MTG-Lang card line into a typed, language-neutral semantic AST (with resolved number and `☞` antecedents) that unparses back to the exact source.

**Architecture:** A hand-written precedence parser (`semparse.py`) over the existing glossary tokenizer builds ~20 grammatical node kinds (`ast.py`), each headed by a glossary symbol whose behaviour comes from a new `syntax:` field in `symbols.yaml`. `unparse.py` turns the AST back into canonical notation (round-trip proof); `resolve.py` adds implicit meaning. The validator, card-file reader and CLI consume it.

**Tech Stack:** Python ≥ 3.12, dataclasses, PyYAML, pytest, uv. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-24-semantic-ast-design.md` (read it first; §-numbers below refer to it). Language spec: `spec/language.md`.

## Global Constraints

- `.mtgl` files remain the source of truth; the AST is derived, never committed except as golden test files.
- Every child of a node sits in a **named slot** that states its grammatical role; no `(symbol, children-in-token-order)` nodes, no `Opaque`/`Raw` fallback node (§4).
- No new `⟨named-effect⟩` escapes to dodge hard lines (§6).
- New symbols that behave like existing ones must need only a glossary entry, no Python change (§2.3).
- `symbols.yaml` keeps exactly one `- {…}` flow-style line per symbol (the glossary editor depends on it); `syntax:` must fit on that line.
- The glossary editor (`mtglang serve` → `edit.apply_symbol_edits`) must keep working and preserve `syntax:`.
- The parser accepts glyph, ASCII and mixed forms (spec/language.md §10), exactly like the tokenizer.
- Notation changes: scripted, listed in `spec/language.md` §12 ("v0.2 changes": before / after / why) and in the commit message; may touch hundreds of lines without asking (§6, §8).
- After every task: `uv run pytest -q` green. From Task 6 on: `uv run mtglang validate` → 0 errors.
- Git: commit (and push to `origin`) after each task; local identity is already configured. End commit messages with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **ASCII / mixed-form lines** (`Lf |> Ld[Ct Yu]^ => @ Dg1 ~> Al Op`) must give the same AST as the glyph form — test in Task 3.
2. **Glossary edits after parsing:** renaming a glyph in the editor must not change any AST (refs are by index); a newly appended symbol with only `class:` (no `syntax:`) must parse via the class default — tests in Task 1 and Task 3.
3. **Multi-line constructs:** modal `⊻n` followed by `•` lines (on a triggered line too: `◈↥ ⇒ ⊻1`), and multi-face `//` cards, must group correctly at card level — test in Task 5.
4. **Minus signs:** loyalty costs use `−` (U+2212) and type lines use `—`; `-` / `−` / `—` must stay distinct in unparse where the source distinguishes them — test in Task 5.
5. **Error reporting:** a line that fails to parse must report a column pointing at the offending token (with the line's indentation added, like `C-SYNTAX` today), not crash validation of the remaining cards — test in Task 6.

---

### Task 1: `syntax:` field in the glossary

**Files:**
- Modify: `mtglang/glossary.py` (Symbol, load_glossary, check_glossary)
- Modify: `glossary/symbols.yaml` (only where a class default is wrong — most symbols get none)
- Modify: `tests/fixtures/glossary/symbols.yaml` (mirror needed overrides)
- Test: `tests/test_glossary.py`, `tests/test_edit.py`

**Interfaces:**
- Produces: `Symbol.syntax: dict` (frozen-safe; store as a tuple of items or `types.MappingProxyType`), always populated (explicit `syntax:` merged over `default_syntax(cls)`).
- Produces: `default_syntax(cls: str) -> dict` and `SYNTAX_KINDS: frozenset[str]`.
- Produces: issue code `G-SYNTAX` from `check_glossary`.

`syntax` keys (fixed vocabulary — later tasks rely on these):
- `kind` ∈ `verb, type, object, player, reference, zone, duration, time, keyword, ability_word, counter_kind, characteristic, comparison, infix, prefix, postfix, marker, structural, stat`
- `args`: list of slot names for verbs (e.g. `[object]`, `[amount, recipient]`, `[object, destination]`)
- `subject`: slot name of the left-hand phrase for verbs that take one (`subject`, `source`)
- `params`: for keywords, list from `cost, number, filter, name` (e.g. Ward `[cost]`, Cycling variants `[filter, cost]`)
- `prec`: int, for `infix`/`prefix`/`postfix`

Class defaults: `action → {kind: verb, args: [object]}`, `type → type`, `object → object`, `player → player`, `reference → reference`, `zone → zone`, `time → time`, `keyword → {kind: keyword, params: []}`, `ability_word → ability_word`, `counter_kind → counter_kind`, `characteristic → characteristic`, `comparison → {kind: infix}`, `logic → marker`, `structural → structural`, `stat → stat`. Exact overrides (precedences, verb frames) are settled in Tasks 3–4 and written back to the YAML then.

- [ ] **Step 1: Write the failing tests**

```python
def test_syntax_defaults_from_class(fx_glossary):
    destroy = fx_glossary.lookup["✖"]
    assert destroy.syntax["kind"] == "verb" and destroy.syntax["args"] == ["object"]
    assert fx_glossary.lookup["♞"].syntax["kind"] == "type"

def test_explicit_syntax_overrides_default(tmp_path):  # write a 1-symbol glossary with syntax: {kind: infix, prec: 30}
    ...
    assert g.symbols[0].syntax == {"kind": "infix", "prec": 30}

def test_unknown_syntax_kind_is_g_syntax(tmp_path):
    ...  # syntax: {kind: bogus}
    assert "G-SYNTAX" in {i.code for i in check_glossary(g)}
```

In `tests/test_edit.py`:

```python
def test_editor_save_preserves_syntax_field(fx_copy):
    # add `syntax: {kind: verb, args: [amount, recipient]}` to a fixture symbol line, apply a glyph edit to another symbol
    ...
    assert "syntax: {kind: verb, args: [amount, recipient]}" in (fx_copy / "glossary/symbols.yaml").read_text()
```

- [ ] **Step 2: Run tests, verify they fail** — `uv run pytest tests/test_glossary.py tests/test_edit.py -q` → FAIL (`Symbol` has no `syntax`).
- [ ] **Step 3: Implement** `default_syntax`, `SYNTAX_KINDS`, loading/merging in `load_glossary`, `G-SYNTAX` in `check_glossary` (unknown kind, `args`/`params` not a list of known names, `prec` not int). Check `edit._dump_entry` round-trips nested flow maps on one line; fix if not.
- [ ] **Step 4: Run** `uv run pytest -q` → all pass; `uv run mtglang validate` → 0 errors.
- [ ] **Step 5: Commit** `feat(glossary): syntax field with class defaults`.

---

### Task 2: AST node kinds, JSON, and unparse skeleton

**Files:**
- Create: `mtglang/ast.py`
- Create: `mtglang/unparse.py`
- Test: `tests/test_ast.py`

**Interfaces:**
- Produces (in `mtglang/ast.py`, all `@dataclass(frozen=True)`, each with a class-level `kind: ClassVar[str]`):
  - leaves: `SymRef(index: int, glyph: str)`, `NameRef(key: str)`, `EffectRef(key: str)`, `Mana(text: str)`, `Num(value: int)`, `Var(name: str)`
  - card: `Card(faces)`, `Face(name, cost, types, stats, abilities)`, `TypeLine(types, subtypes, dash: str)`, `Stats(kind: "pt"|"loyalty"|"defense", power, toughness, value)`
  - ability: `Keywords(items)`, `Keyword(sym, params)`, `Triggered(event, condition, while_, effect)`, `Activated(cost, effect, limits)`, `Static(body)`, `Replacement(event, effect)`, `Labelled(label, ability)`, `Chapter(numbers, ability)`, `Threshold(n, ability)`, `Modal(choose, modes)`, `Mode(ability)`
  - sentence: `Effects(sentences)`, `Action(verb, subject, args: tuple[tuple[str, Node], ...], modifiers, optional, negated, passive, duration)`, `Conditional(kind: "if"|"if_do"|"if_dont"|"unless", cond, then)`, `Coord(op, items)`, `Bind(var, value)`, `Becomes(subject, types)`, `ForEach(players, body)`, `Bounded(ability, until)`, `Delayed(trigger)`, `Reflexive(trigger)`, `Instead(effect)`, `NamedEffect(ref)`, `Limit(...)`
  - phrase: `NP(quantifier, count, head, filter, possessor, written: Written)`, `Filter(conds)`, `Token(...)`, `PTChange(power, toughness)`, `Count(np)`, `Arith(op, left, right)`, `Characteristic(sym, of)`, `Duration(...)`, `Zone(sym, owner, position, count, order)`, `Compare(op, left, right)`, `Or(items)`, `And(items)`, `Not(item)`
  - `Written`: source-form details needed for exact unparse (explicit `●` subject, `∀` written vs bare, spacing hints). Resolution fields (`number`, `quantity`, `antecedent`) are added to `NP` and `SymRef`-references in Task 7 as `None`-defaulted fields — declare them now as `None` so JSON shape is stable.
  - `Node` = union alias; `to_json(node) -> dict` (`{"kind": ..., <fields>}`; `SymRef` → `{"sym": glyph, "index": i}`); `walk(node) -> Iterator[tuple[path, Node]]`.
  - Exact field lists beyond these names are the implementer's call in Tasks 3–5; keep the class names.
- Produces (in `mtglang/unparse.py`): `unparse_ability(node, g: Glossary) -> str`, `unparse_card(card, g) -> str` (glyph form, canonical spacing). Initially supports leaves only; grows with each parser task.

- [ ] **Step 1: Write failing tests** — `test_to_json_symref`: `to_json(SymRef(5, "◈")) == {"kind": "sym", "sym": "◈", "index": 5}`; `test_nodes_are_frozen`; `test_walk_yields_paths` over a small hand-built `Action`.
- [ ] **Step 2: Run** `uv run pytest tests/test_ast.py -q` → FAIL (module missing).
- [ ] **Step 3: Implement** `ast.py` and the `unparse.py` skeleton.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(ast): node kinds, JSON, unparse skeleton`.

---

### Task 3: Parser — phrases (NPs, filters, values, tokens, zones, durations)

**Files:**
- Create: `mtglang/semparse.py`
- Modify: `mtglang/unparse.py`, `glossary/symbols.yaml` (precedence / kind overrides as found)
- Test: `tests/test_semparse_phrase.py`

**Interfaces:**
- Consumes: `tokenize`, `Tok` (tokenizer), `Symbol.syntax` (Task 1), node classes (Task 2).
- Produces: `class SemParser: __init__(self, g: Glossary)`; `parse_phrase(self, text: str) -> Node` (test entry point); `class SemSyntaxError(Exception)` with `.col` and `.message` (same shape as `LineSyntaxError`); internal `_Stream` cursor over `list[Tok]`.

Tests in Tasks 3–5 use the **real** glossary (`load_glossary(ROOT / "glossary")`); the fixture glossary uses different glyphs. Any `syntax:` override needed by fixture-based tests (Task 6) is mirrored into `tests/fixtures/glossary/symbols.yaml`.

Every test asserts both the structure **and** `unparse(parse(x)) == x`. Use a helper `rt(text)` in the test module.

- [ ] **Step 1: Write failing tests** (real-glossary fixture `g = load_glossary(ROOT/"glossary")`):

```python
def test_target_np_with_filter():   # ◎▣[⚑○]
    np = p.parse_phrase("◎▣[⚑○]")
    assert np.quantifier.glyph == "◎" and [h.glyph for h in np.head] == ["▣"]
    assert len(np.filter.conds) == 1

def test_up_to_n_targets():          # ≤1◎♞  → quantifier ◎, count Compare(≤, 1)
def test_or_head_with_filter():      # (♞ ∨ ⚝)[⚑● ≠◈]  → head Or(♞, ⚝); filter has control + another
def test_nested_filter_or():         # ♞[⚑○ (△ ≤ 1 ∨ ▽ ≤ 1)]
def test_token_spec():               # ◌[2/2 ♦{W} «Cat» «Soldier» ♞] «Ajani's Pridemate»  → Token(pt, colors, subtypes, types, name)
def test_predefined_token():         # ◌«Treasure»
def test_zone_top_n():               # ⌃4▤●   → Zone(▤, owner ●, position top, count 4)
def test_count_value():              # #≢ ⛰[⚑●]
def test_duration_each_of_your_turns():  # ∀◷●
def test_ascii_form_same_ast():      # parse_phrase("Tg Pm[Ct Op]") == parse_phrase("◎▣[⚑○]") (compare to_json)
def test_appended_symbol_uses_class_default(tmp_path):
    # copy real glossary, append a new `class: type` symbol with no syntax, parse "◎<new>" → NP head is it
def test_error_column():             # "◎▣[⚑○" → SemSyntaxError, col == 6
```

- [ ] **Step 2: Run** `uv run pytest tests/test_semparse_phrase.py -q` → FAIL.
- [ ] **Step 3: Implement** phrase parsing in `SemParser` (Pratt loop: prefix quantifiers → head → postfix filter/possessor/zone markers) and matching `unparse` cases. Record precedences/overrides in `symbols.yaml` via `syntax:`; no glyph literals in parser code except structural roles fetched with `g.role(...)` and the fixed punctuation.
- [ ] **Step 4: Run** → PASS; full suite green.
- [ ] **Step 5: Commit** `feat(semparse): noun phrases, filters, values`.

---

### Task 4: Parser — actions and sentences

**Files:**
- Modify: `mtglang/semparse.py`, `mtglang/unparse.py`, `glossary/symbols.yaml` (verb frames)
- Test: `tests/test_semparse_sentence.py`

**Interfaces:**
- Consumes: Task 3 phrase parser.
- Produces: `SemParser.parse_effects(self, text: str) -> Effects`.

Verb frames to write into `symbols.yaml` (others keep the default `[object]`): `✸ {subject: source, args: [amount, recipient]}`, `→ {kind: verb, args: [object, destination]}` (when following `✸`'s amount it's the recipient marker — implementer decides representation, but the AST must show `recipient` as a slot of the `✸` action), `♥ {args: [amount]}` with sign, `✚ {args: [object]}`, `⊞ / ⊟ {args: [counter, destination]}`, `∋ / ∌ {args: [ability]}`, `⊷ {args: [cost]}`, `⊕ {args: [mana]}`. The precedence table (`;` < `⊃`/`✓ ⊃`/`¬⊃` < `∧`/`∨` < action < phrase) is the starting point; adjust and document in Task 8.

- [ ] **Step 1: Write failing tests** (each also asserts round trip):

```python
def test_damage_slots():          # ◈ ✸3 → ◎   → Action(verb ✸, subject ◈, args {amount: 3, recipient: NP(◎ any target)})
def test_zone_move():             # ◎▭♞[⚰●] → ☚●   → Action(→, args {object, destination})
def test_optional_subject():      # ● ? ⤓1  → optional True, subject ●
def test_implicit_subject():      # ⤓1 → subject None, written.subject_explicit False
def test_pt_change_with_duration():   # ◎♞ +2/+0 ⧗
def test_coord_and_then():        # ◎♞ +2/+0 ∧ ∋↟ ⧗ ; ⊞+1/+1 → ☞   → Effects(2 sentences), first is Coord(∧)
def test_if_you_do():             # ● ? ⊷{2} ; ✓ ⊃ ⤓1
def test_unless():                # ◈ ↥↷ ¬⊃ ∃⚝[⚑●]
def test_bind_variable():         # ◎♞ +X/+0 ⧗ ; X ≔ #≢ ⛰[⚑●]
def test_becomes():               # ◈ ≔ «Ferengi» «Scout»   → Becomes, not Bind
def test_for_each_player():       # (∀○) ✖ ≤1◎♞[⚑☞]
def test_reflexive_trigger():     # ● ? ⌫1 ; (✓ ⇒ ◈ ✸2 → ◎)
def test_until_reveal():          # ◉ ⌃▤● ⊣ ◉▭(♞ ∨ ⚝)  — distinct node from duration ⊣▷◷●
def test_granted_activated():     # ∋ ({T}, ✝◈ : ⊕ 3◆)
def test_instead():               # … ; C ⊃ ⤳ effect  (pick a real corpus line)
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** sentence/action parsing and unparse. If a test line is genuinely ambiguous (e.g. `⊣` above), make a notation change per §8 using the Task 6 migration mechanism early, and update the test to the new form.
- [ ] **Step 4: Run** → PASS; full suite green.
- [ ] **Step 5: Commit** `feat(semparse): actions and sentences`.

---

### Task 5: Parser — ability shapes and card level

**Files:**
- Modify: `mtglang/semparse.py`, `mtglang/unparse.py`
- Test: `tests/test_semparse_ability.py`

**Interfaces:**
- Produces: `SemParser.parse_ability(self, text: str) -> Node` (one line, any shape incl. a bare `• …` mode line → `Mode`); `SemParser.parse_type_line(self, text: str) -> TypeLine`; `SemParser.parse_stats(self, text: str) -> Stats`; `build_card(doc: CardDoc, p: SemParser) -> Card` (in `semparse.py`; groups a `⊻n`-ending line with following `Mode` lines into `Modal`).

- [ ] **Step 1: Write failing tests:**

```python
def test_keywords_with_params():    # 🪽, ⊙, ♡, ⊠{2}
def test_cycling_variant():         # ♲[⊡⛰] {2}
def test_triggered_intervening_if():# ◈↥ ∧ #⛰[⚑●] ≥ 6 ⇒ ● ♥+1   → Triggered(condition set)
def test_trigger_while():           # (pick a corpus ∵ … ⇒ line) → while_ set
def test_activated_with_limit():    # {3}{R} : … ; ≡✎   → limits == [sorcery]
def test_loyalty_cost():            # −4 : ✚ ◌[…] …   → cost Num(-4); unparse keeps "−"
def test_labelled_landfall():       # ⛶ ▸ ⛰[⚑●]↥ ⇒ ◈ ✸1 → ∀○ ; ☞ ∈ «Mountain» ⊃ ⊕{R}
def test_flavor_label():            # «Open a Channel» ▸ …
def test_saga_chapter():            # §1,2 ▸ ● ♥+3
def test_station_threshold():       # 12+ | ⚙♞[⚑●] ∋ 🪽
def test_replacement():             # ◈↥ ⤳ ⊻ Y ; 0 ≤ Y ≤ 10
def test_type_line_dash():          # ⚜♞ — «Human» «Warrior»   (dash "—" preserved)
def test_modal_on_trigger_groups_modes():  # cards/fra/archive-arbiter.mtgl → Triggered(effect contains Modal with 2 Mode)
def test_modal_spell():             # cards/fra/charge-the-sanctum.mtgl
def test_multi_face_card():         # cards/fra/theorix-metamage-omit-variables.mtgl → 2 faces
def test_card_roundtrip():          # unparse_card(build_card(doc)) token-equal to the file for the cards above
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(semparse): ability shapes and card level`.

---

### Task 6: Corpus coverage to 100%, notation migrations, validator + CLI wiring

This is the long, open-ended task: drive every line of the 596 cards through the parser.

**Files:**
- Modify: `mtglang/cardfile.py` (`AbilityLine.ast`, `FaceDoc.type_ast`; `parse_card_file(path, parser, sem: SemParser | None = None)`), `mtglang/validate.py`, `mtglang/cli.py`, `mtglang/semparse.py`, `mtglang/unparse.py`, `glossary/symbols.yaml`, `spec/language.md` (§12), card files as migrated
- Create: `mtglang/migrate.py`, `scripts/migrations/NNN-<name>.py`
- Test: `tests/test_corpus.py`, `tests/test_validate.py`, `tests/test_migrate.py`

**Interfaces:**
- Produces: issue codes `S-PARSE` (with column incl. indentation) and `S-ROUNDTRIP` (token identity via `tokenizer._key`) emitted by `validate_all`; stats key `ast_lines`.
- Produces: `migrate.rewrite_lines(root: Path, fn: Callable[[str, Glossary], str]) -> int` — applies a token-aware line rewrite to every card file, returns lines changed; each `scripts/migrations/NNN-*.py` calls it and is idempotent.
- Produces: CLI `mtglang ast <set>/<slug> [--ascii]` → card AST JSON on stdout; `mtglang ast --coverage` → `parsed N/M lines, roundtrip N/M` plus the first 20 failures grouped by first-failing token; `mtglang render` also writes `build/ast/<set>.json` (list of `{slug, ast}`).
- `validate.english_type_line` switches to `TypeLine` (Lark type-line tree retired); keeping or removing Lark for ability outlines is the implementer's call — if removed, drop `grammar.lark`, `lineparser.py` and the `lark` dependency, and keep `C-SYNTAX` semantics via `SemSyntaxError`.

- [ ] **Step 1: Write failing tests:**

```python
# tests/test_corpus.py
@pytest.mark.skipif(not CARDS, reason="no corpus")
def test_every_card_parses_and_roundtrips():
    issues, _ = validate_all(ROOT)
    assert [i for i in issues if i.code in ("S-PARSE", "S-ROUNDTRIP")] == []

# tests/test_validate.py
def test_s_parse_reported_with_column(fx_copy):
    edit(fx_copy, ": ✋1", ": 1✋")       # fixture glossary glyphs; Lark's outline accepts it, semantics don't
    i = only(validate_all(fx_copy, only_existing=True), "S-PARSE")
    assert i.line == 7 and i.col in (11, 12)
def test_s_parse_does_not_stop_other_cards(fx_copy): ...   # second card still validated

# tests/test_migrate.py
def test_rewrite_lines_is_token_aware_and_counts(fx_copy): ...
```

- [ ] **Step 2: Run** → FAIL (and `mtglang ast --coverage` shows the starting coverage).
- [ ] **Step 3: Wire** `SemParser` into `cardfile`, `validate`, `cli`; implement `migrate.py`.
- [ ] **Step 4: Coverage loop** — repeat until `mtglang ast --coverage` reports 100% / 100%:
  1. Take the largest failure group.
  2. Fix with a grammar rule (preferred), a `syntax:` override, or — if genuinely ambiguous — a notation change: add `scripts/migrations/NNN-*.py`, run it, add the row to `spec/language.md` §12, add a unit test for the new form.
  3. Run `uv run pytest -q` and `uv run mtglang validate` (0 errors — Scryfall alignment and consistency must still hold after migrations).
  4. Commit each grammar batch / each migration separately; migration commit messages list the change and the number of lines touched.
- [ ] **Step 5: Run** `uv run pytest -q` → all pass; `uv run mtglang validate` → 0 errors; `uv run mtglang ast --coverage` → `parsed 100%, roundtrip 100%`.
- [ ] **Step 6: Commit** `feat: full-corpus semantic AST; S-PARSE/S-ROUNDTRIP; mtglang ast`.

---

### Task 7: Resolution pass — NP number and `☞` antecedents

**Files:**
- Create: `mtglang/resolve.py`
- Modify: `mtglang/ast.py` (fill the `None`-defaulted resolution fields), `mtglang/validate.py`, `mtglang/cli.py` (JSON includes resolved fields)
- Test: `tests/test_resolve.py`, `tests/test_corpus.py`

**Interfaces:**
- Consumes: `Card`, `walk` (Task 2), `build_card` (Task 5).
- Produces: `resolve_card(card: Card) -> tuple[Card, list[ResolveProblem]]` (returns a new tree — nodes are frozen — via `dataclasses.replace`); `ResolveProblem(path, message)`; NP fields `quantity: str | None` (`one, all, each, up_to, exactly, count, any`), `number: "sg"|"pl"|None`; reference nodes (`☞`, `☞⚑`) get `antecedent: str | None` (a `walk` path of the referenced NP/player); subject-less actions get `implicit_subject: "controller"`.
- Produces: validator code `S-RESOLVE` (one per unresolved NP / `☞`).

Rules (§7.5): explicit marks win (`◎` → one unless count; `≤n◎` → up_to; `∀` → each; numerals → exactly); bare NP as subject of a `Static` effect → all/pl; bare NP in a trigger event → one/sg; NP under `Count` → count/pl; bare object of an action → one/sg unless the verb's frame says otherwise. `☞`: most recent compatible NP (object for `☞`, player for `☞⚑`/player slots) searching backwards in the same ability (earlier sentences included); a trigger's event subject is a candidate; nested granted abilities resolve inside their own scope first, then outward. Ambiguous or unmatched → `ResolveProblem`, never a guess.

- [ ] **Step 1: Write failing tests:**

```python
def test_static_bare_np_is_all():        # ♞[⚑●] +1/+0 ⧗  (as a Static line) → quantity "all", number "pl"
def test_trigger_bare_np_is_one():       # ⛰[⚑●]↥ ⇒ …     → "one", "sg"
def test_target_is_one():                # ✖ ◎▣[⚑○]
def test_up_to():                        # ≤1◎♞ → "up_to"
def test_count_is_plural():              # #≢ ⛰[⚑●]
def test_that_refers_to_previous_target():   # ◎♞ +2/+0 ∧ ∋↟ ⧗ ; ⊞+1/+1 → ☞   → antecedent = path of ◎♞
def test_that_controller_is_player_ref():    # ☞⚑ → antecedent NP, kind player
def test_that_in_trigger_refers_to_event():  # ⛶ ▸ ⛰[⚑●]↥ ⇒ … ; ☞ ∈ «Mountain» ⊃ ⊕{R}  → ☞ = the land
def test_granted_ability_scope():        # ☞ inside ∋ (…) resolves within it first
def test_unresolvable_that_is_problem(): # ⤓1 ; ✖ ☞  → one ResolveProblem
def test_resolution_does_not_change_unparse():  # unparse(resolve(x)) == unparse(x) for the cases above
# tests/test_corpus.py
def test_every_card_resolves(): assert no S-RESOLVE in validate_all(ROOT)
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `resolve.py`; wire `S-RESOLVE` into `validate_all`.
- [ ] **Step 4: Coverage loop** as in Task 6 Step 4 until 0 `S-RESOLVE` (rule fixes preferred; notation change only if genuinely ambiguous, listed in §12).
- [ ] **Step 5: Run** `uv run pytest -q`; `uv run mtglang validate` → 0 errors.
- [ ] **Step 6: Commit** `feat(resolve): NP number and ☞ antecedents; S-RESOLVE`.

---

### Task 8: Golden files and spec documentation

**Files:**
- Create: `tests/golden/<set>-<slug>.json` (20 files), `tests/test_golden.py`
- Modify: `spec/language.md` (new §13 "Semantic AST": node kinds with one example each, the precedence table, the resolution rules; §12 complete), `README.md` (`ast` command row + section)

**Interfaces:**
- Consumes: `mtglang ast` JSON output (Task 6/7).

Golden cards (from `mtglang sample --k 20`): `fra/hexhaven-battalion fra/kwia-vigorbloom fra/theorix-metamage-omit-variables trk/borg-cube trk/amok-time trk/pah-wraith fra/ferocity-of-the-hunt fra/koth-the-geomancer fra/tetsuko-umezawa-pursuer fra/vraska-the-cutting-glare trk/elim-garak-simple-tailor trk/nyota-uhura-communications fra/ajani-resolute fra/arni-renowned-champion fra/bestial-incursion fra/charge-the-sanctum fra/countersculpt fra/fblthp-knows-the-way fra/forest fra/hunters-axe` (if a migration renamed nothing, slugs are unchanged — slugs come from Scryfall names).

- [ ] **Step 1: Generate** the 20 JSON files with `mtglang ast`; **hand-check each** against its Oracle text (slots named sensibly, quantifiers/filters on the right NP, durations on the right action, NP number and `☞` antecedents correct). Fix the parser/resolver for any wrong parse, regenerate.
- [ ] **Step 2: Write** `test_golden.py`: for each golden file, `to_json(resolve_card(build_card(...))[0]) == json.load(golden)`; add `--update-golden` handling via env var `MTGLANG_UPDATE_GOLDEN=1`.
- [ ] **Step 3: Run** `uv run pytest -q` → PASS.
- [ ] **Step 4: Write** spec §13 and README updates.
- [ ] **Step 5: Final check** — `uv run pytest -q`; `uv run mtglang validate` → 0 errors; `uv run mtglang ast --coverage` → 100% / 100%; `uv run mtglang render` builds without error.
- [ ] **Step 6: Commit and push** `docs: AST spec, golden files`.
