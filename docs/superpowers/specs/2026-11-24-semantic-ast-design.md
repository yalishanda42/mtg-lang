# Semantic AST for MTG-Lang — design

Date: 2026-11-24. Status: draft for approval (builder-checked).

## 1. Intent

MTG-Lang (v0.1, 596 cards in `fra` + `trk`) is meant to be a card-text language independent of any natural
language. The next ambition is to translate cards *out of* it deterministically — into English, Bulgarian,
Bulgarian in pre-1945 orthography (Ѣ, Ѫ), possibly Old Church Slavonic or other invented notations — without an
LLM per card.

That needs a meaning-level tree (AST): who does what to whom, with which filters, for how long. Natural
languages differ in word order, agreement (gender/number/case), articles, and so on; a renderer can only
handle those if it knows which symbol is the head noun, which are its modifiers, and what grammatical role a
phrase plays. Today the parser knows only the *outline* of a line (label, `⇒`, `:`, brackets); everything inside
`expr` is a flat token list (`mtglang/grammar.lark`: `expr: (term | COMMA)+`).

This project builds that AST. It is step 1 of a sequence; the natural-language renderers (English first, then
Bulgarian, then the orthography layer, …) are separate later projects, done one at a time.

## 2. Goals

1. A typed AST covering **every ability line of all 596 cards**, plus card headers (name, mana cost, type line,
   stats) and multi-face cards.
2. **Lossless round trip:** `unparse(parse(line))` reproduces every line of every `.mtgl` file
   token-for-token (whitespace may be normalised to one canonical spacing — see §7.4). This proves the AST drops
   nothing before any language work starts.
3. **Glossary-driven:** each symbol's syntactic behaviour is declared in `glossary/symbols.yaml` (new `syntax:`
   field). Adding a symbol that behaves like an existing one (e.g. a new destroy-like verb, a new counter kind,
   a new keyword) needs only a glossary entry — no Python change.
4. **Fail loudly:** the validator reports any line that doesn't parse to a full AST as an error, so the corpus
   stays at 0 errors.
5. A JSON export of the AST per card, for inspection and for future renderers / tools.

## 3. Non-goals

- Any natural-language renderer (English, Bulgarian, …). Next project.
- English → AST parsing (for new sets). Later; probably LLM-assisted.
- Changes to the gallery UI.
- Rules-engine semantics (the AST describes the *text*, it doesn't execute it).
- Parsing the `definition:` fields of keywords in `symbols.yaml` — nice to have, not required. (Builder may
  include them if cheap; they are good extra test cases.)

## 4. Anti-goals (would be a failure even if tests pass)

- **A generic tree in disguise.** If nodes are just `(symbol, children-in-token-order)`, renderers can't do
  agreement or reordering. Every child must be in a *named slot* that says its grammatical role.
- **An escape hatch that swallows hard lines.** No `Opaque`/`Raw` node that holds an unparsed token run.
  Hard lines are solved by grammar rules or by notation changes (§8), not hidden.
- **Breaking the glossary editor.** `mtglang serve` rewrites `symbols.yaml` and migrates card files; it must
  keep working and must preserve the new `syntax:` field.
- **Renderer-specific shortcuts in the AST** (e.g. storing English word order). The AST is language-neutral.

## 5. Approaches considered

| | Approach | Trade-off | Verdict |
|---|---|---|---|
| A | One node class per construct (`Create`, `Destroy`, `Damage`, … ~150 classes) | Nice field names; but every new verb symbol needs new code, so the glossary editor's "add a symbol" stops being enough | rejected |
| B | Generic tree: every node is `(symbol, children)` | Small, glossary-driven; but no grammatical roles, so renderers can't do agreement or case | rejected |
| **C** | **~20 grammatical node kinds, each headed by a glossary symbol; symbol argument frames declared in `symbols.yaml`** | Renderers write rules per *kind* + a word per *symbol* — the classic NLG split; new symbols are glossary-only | **chosen by the user** |

Parser technique (my call, accepted with C): a **hand-written precedence (Pratt-style) parser** over the existing
tokenizer, reading `syntax:` metadata. Lark stays only for the card-file outline if useful, or is retired from
line parsing entirely (builder's call). Reason: Lark's grammar would need editing per symbol, and its ambiguity
resolution would silently hide the clashes we want to surface and fix.

## 6. Decisions already made

- **Approach C** (above).
- **Notation may change** where it's genuinely ambiguous: small, explicit changes to spec + glossary + affected
  card files are allowed, rather than context-sensitive parser hacks. Each change is listed (see §8).
- `.mtgl` files remain the **source of truth**; the AST is derived. (Not stored in the repo except as a build
  artifact.)
- **The AST resolves implicit meaning** (user chose this over "record only what's written" and over "mark it in
  the notation"): a post-parse pass fills in the *number* of bare noun phrases and links every `☞` to its
  antecedent (§7.5). Every inflected target language needs this, so it is done once here, not per renderer.
- **No new `⟨named-effect⟩` escapes** to dodge hard lines (my call, follows §4). `⟨…⟩` stays for genuine one-off
  rules as in v0.1.
- **Notation migrations may be large** (my call, matching the user's batch-and-review-at-end preference): a
  scripted change touching hundreds of lines is fine without stopping to ask, as long as it is listed (§8).

## 7. Design

### 7.1 Node kinds (proposal — builder may merge/split, but must keep named slots)

All nodes are frozen dataclasses with a `kind` and named fields. Leaf references to glossary entries are
`SymRef` (glossary index, so stable across glyph/ASCII edits), `NameRef` (`«…»` key), `EffectRef` (`⟨…⟩` key).

**Card level**
- `Card(faces: list[Face])`
- `Face(name: NameRef, cost: ManaCost|None, types: TypeLine, stats: Stats|None, abilities: list[Ability])`
- `TypeLine(supertypes+types: list[SymRef], subtypes: list[NameRef])`
- `Stats` — P/T (`Num|Var|*` pair), loyalty, or defense.

**Ability level** (one per card line)
- `Keywords(items: list[Keyword])`; `Keyword(sym, params: list[Value|ManaCost|Filter])` — e.g. `⊠{2}`, `♲[⊡⛰] {2}`
- `Triggered(event: Clause, condition: Cond|None, effect: Effects)` — `∧` before `⇒` is the intervening-if;
  `∵` before `⇒` is trigger-time "while"
- `Activated(cost: list[CostItem], effect: Effects, limits: list[Limit])` — `; ≡✎`, `; ≡ ≤1◷`, `; ≡(cond)`
- `Static(body: Effects)`
- `Replacement(event: Clause, effect: Effects)` — `⤳`
- Wrappers: `Labelled(label: SymRef|NameRef, ability)`, `Chapter(numbers, ability)`, `Threshold(n, ability)`,
  `Modal(choose: Value)` + `Mode(ability)` lines

**Sentence level**
- `Effects(sentences: list[Sentence])` — split on `;`
- `Sentence` is one of: `Action`, `Conditional(cond, then, otherwise?)` (`⊃`, `✓ ⊃`, `✗ ⊃`, `¬⊃` unless),
  `Coord(op: ∧|∨, items)`, `Bind(var, value)` (`X ≔ …`), `Becomes(subject, types)` (`≔` replacing types),
  `ForEach(players, body)` (`(∀○) …`), `Bounded(ability, until)` (`(…) ⊣▷◷●`), `Delayed(trigger)`,
  `Reflexive(trigger)` (`(✓ ⇒ …)`), `Instead(effect)` (`⤳` inside an effect), `NamedEffect(EffectRef)`
- `Action(verb: SymRef, subject: NP|None, args: dict[slot → NP|Value|Zone|…], modifiers: list[Mod],
  optional: bool (?), negated: bool (¬), passive: bool (←), duration: Duration|None)`
  — the argument slots come from the verb's `syntax.args` frame (§7.2), e.g. `✸`: `source, amount, recipient`;
  `→`: `object, destination` (zone move) **or** `recipient` (damage) — whichever the notation makes unambiguous
  after §8 fixes.

**Phrase level**
- `NP` (object / player phrase): `quantifier` (◎ target, `≤n◎`, `n◎`, ∀ each, ∃, none = bare),
  `count`, `head` (types/object symbols, `Or` of types, player symbol, `◈` self, `☞` that, token, copy …),
  `filter: Filter|None`, `possessor` (`☞⚑`, `▤●`)
- `Filter(conds: list[Cond])` — conjunction (Scryfall-style); conds include control/own (`⚑●`), zone (`⚰●`),
  comparisons (`⌀ ≤ 3`), negation (`¬♞`), "another" (`≠◈`), colour, name, attachment (`⚭◈`)
- `Token(pt, colors, subtypes, types, name, copy_of)`; `PT change` (`+2/+0`)
- `Value`: `Num`, `Var`, `Count(#…)`, `Arith(×, ÷, +)`, `Characteristic(△ of NP)`
- `Duration` / time: `⧗`, `◷`, `◷●`, `∀◷●`, `⊢☼◷●`, `⊣▷◷●`, …
- `Zone(sym, owner, position: top n / bottom, order: ⚂|⇅)`
- `Cond` / comparison (`=`, `≠`, `≤`, `≥`, `<`, `>`), `Or`, `And`, `Not`

**Symbol identity** (my call): `SymRef` holds the glossary index in memory (stable across glyph/ASCII edits, as
`edit.py` already assumes); the JSON export writes the glyph alongside it. The export is consistent per build and
not a long-lived key — future renderers get their words from `labels: {<lang>: …}` in the glossary itself, so no
permanent symbol ID is needed now. If that changes, add an `id:` field then.

**Source details for round trip:** nodes keep what's needed to unparse exactly — e.g. explicit vs implicit `●`
subject, `∀` written vs bare — as fields separate from the resolved meaning (§7.5), so resolution never changes
the unparsed text.

### 7.2 Glossary: `syntax:` field

Each symbol in `symbols.yaml` gains an optional `syntax:` map, read by the parser. Sketch:

```yaml
- {glyph: ✖, ascii: Ds, class: action, syntax: {kind: verb, args: [object]}, labels: {en: destroy}}
- {glyph: ✸, ascii: Dg, class: action, syntax: {kind: verb, args: [amount, recipient], subject: source}, ...}
- {glyph: ♞, ascii: Cr, class: type, syntax: {kind: type}, ...}
- {glyph: ⧗, ascii: Ue, class: time, syntax: {kind: duration}, ...}
- {glyph: ⊠, ascii: Wd, class: keyword, syntax: {kind: keyword, params: [cost]}, ...}
- {glyph: ∧, ascii: '&', class: logic, syntax: {kind: infix, prec: 30}, ...}
```

Exact vocabulary of `kind`s, slot names and precedence numbers is the builder's to settle while writing the
parser; constraints:
- most symbols' `syntax` should be derivable from `class` as a default, so the YAML only overrides where needed
  (keeps the file readable);
- `check_glossary` validates the field;
- `edit.apply_symbol_edits` (glossary editor save) must round-trip it unchanged — add a test.

### 7.3 Modules

- `mtglang/ast.py` — node dataclasses + `to_json()`.
- `mtglang/semparse.py` — tokens → AST (precedence parser), with errors carrying the column like
  `LineSyntaxError`.
- `mtglang/unparse.py` — AST → canonical `.mtgl` line (glyph form; ASCII form via existing `to_ascii`).
- `cardfile.py` gets an `ast` per ability line / face (alongside or replacing the Lark tree — builder's call;
  `validate.english_type_line` currently consumes the Lark type-line tree).
- CLI: `mtglang ast <set>/<slug>` prints a card's AST as JSON; `mtglang render` (or a new `mtglang export`)
  writes `build/ast/<set>.json`.

### 7.4 Round trip and canonical spacing

`unparse` emits one canonical spacing. Comparison for the round-trip test is on **token identity**
(`tokenizer._key`), so spacing differences don't fail it. Whether to then *reformat* card files to canonical
spacing is the builder's call (a one-time mechanical commit is fine; don't mix it with notation changes).

### 7.5 Resolution pass (implicit meaning)

After parsing, `mtglang/resolve.py` annotates the AST (it adds fields; it never changes the written form):

1. **Number / quantity of every NP:** `quantity ∈ {one, all, each, up_to(n), exactly(n), count, …}` and grammatical
   `number ∈ {sg, pl}`. Explicit marks (`◎`, `≤n◎`, `∀`, `∃`, numerals) win. Bare NPs are resolved by context, with
   the rules documented in the spec, e.g.: bare NP as subject of a static effect → *all* (pl); bare NP in a trigger
   event → *one* ("a land you control enters"); after `#` → counted set; as an action's object without a mark →
   per the verb's frame (default *one*). Every rule has unit tests; any NP the rules can't classify is an
   `S-RESOLVE` validator error, not a guess.
2. **Antecedent of every `☞`:** link (by node path/id) to the NP or player it refers to, so renderers can read its
   gender/number. Default rule: the most recent compatible NP (object vs player, per `☞` vs `☞⚑`) in the same
   ability, searching backward through earlier sentences; triggers may refer to the event's subject; granted /
   nested abilities resolve inside their own scope first. Cases that the rules can't resolve uniquely are
   `S-RESOLVE` errors; fix by rule, or by a listed notation change (§8).
3. Also record, where cheap: the implicit subject of subject-less actions (the ability's controller, i.e. "you").

The JSON export includes the resolved fields. The §9.4 golden files check them.

### 7.6 Validation

- New validator error code `S-PARSE` (line doesn't parse to an AST, with column) and `S-ROUNDTRIP`
  (unparse differs from source by token identity), `S-RESOLVE` (NP number or `☞` antecedent unresolved).
- `mtglang validate` must end at **0 errors** on the full corpus.
- The existing consistency rule (identical Oracle lines → identical notation) can optionally be strengthened to
  compare ASTs instead of token strings (builder's call).

## 8. Notation changes

Allowed when the notation is genuinely ambiguous (the user approved small explicit changes over parser hacks).
Rules:
- Prefer the smallest change: a disambiguating symbol or bracket, not a redesign.
- Each change: update `spec/language.md` (new §12 "v0.2 changes" table: before / after / why), the glossary, and
  migrate all affected card files (scripted, not by hand).
- List every change in the commit message and the final summary.
- `mtglang validate` (Scryfall alignment, consistency) must still pass after each change.

Known suspects found while reading the spec (builder confirms or dismisses each):
- `∧` = intervening-if before `⇒`, but plain "and" elsewhere (probably fine positionally — before `⇒` is
  unambiguous).
- `≔` = variable binding (`X ≔ …`) and "becomes" (`◈ ≔ «Ferengi» «Scout»`) — distinguishable by left side
  (variable vs object) — probably fine.
- `→` = zone move and damage recipient — distinguishable via the preceding verb (`✸`) — probably fine.
- `⊣` = "until" for durations (`⊣▷◷●`) and "until you reveal" (`◉ ⌃▤● ⊣ ◉▭(…)`).
- Implicit subject "you" (`◓ ⌃5▤●` vs `● ◓ …`) — AST should normalise to an explicit subject slot (None =
  implicit controller) without notation changes.
- Scope of `∧` vs `;` vs `⊃` in long lines (e.g. `{3} : ◈ ∈ «Scout» ⊃ ◈ ≔ … ∧ ∋ (…) ∧ ∋ (…)`) — needs a precise
  precedence table, documented in the spec.

## 9. Success criteria

1. Every ability line and header in `cards/` (2,847 non-blank lines, counting headers, type lines, stats and `//`)
   parses to an AST with no fallback node, and every NP and `☞` is resolved (0 `S-RESOLVE`).
2. Round trip passes for every line (token identity).
3. `mtglang validate` → 0 errors; full test suite green; new unit tests per node kind and per notation change.
4. Spot check: for ~20 cards from `mtglang sample`, the JSON AST reads as an obviously correct parse to a human
   (slots named sensibly, quantifiers/filters on the right NP, durations attached to the right action, NP number and `☞` antecedents correct). These 20
   are committed as golden-file tests.
5. Spec gains: a section describing the AST kinds and the precedence table, and §12 listing notation changes.

## 10. Left to the builder

- Exact node fields, `kind` vocabulary, slot names, precedence numbers.
- Whether Lark is kept for the outline or replaced.
- Whether to reformat card files to canonical spacing.
- JSON layout of the export.
- Order of work (suggested: phrases/NPs → actions → sentences → ability shapes → card level, driven by a
  corpus-coverage counter that shows how many lines parse).
