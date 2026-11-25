# English renderer (AST → Oracle English) — design

Date: 2026-11-25. Status: draft for approval (builder-checked).

## 1. Intent

MTG-Lang exists so card text can be written once and read in any language. The semantic AST (spec §13) is
step 1; this project is step 2: generate natural-language text from the AST deterministically, no LLM per
card. The user's end goal is Bulgarian card text (modern and pre-1945 Ivanchev spelling) painted on a third
card in the gallery; English comes first because it is the only language with an answer key — Scryfall's
Oracle text for every one of the 596 cards.

So English serves two purposes:

1. **A renderer:** readable English for every card.
2. **An evaluation of MTG-Lang itself:** if AST → English reproduces Oracle exactly, the notation (and the
   AST and the resolution pass) demonstrably lose nothing. Every mismatch is a bug — in the renderer, in a
   card's notation, or in the AST/resolver.

The user chose **Oracle text as the target** (not "faithful paraphrase") and an **AST → English eval**.

## 2. Goals

1. `mtglang en <set>/<slug>` prints a card's rendered English; `mtglang render` uses it in the gallery.
2. `mtglang eval-en [set]` renders every ability line, compares it with its Oracle line, and reports:
   exact-match rate per set and overall, mismatches grouped by cause, and an HTML diff page
   (`build/eval-en/index.html`) plus JSON (`build/eval-en/report.json`).
3. Target: **every line matches Oracle** after normalisation (§7.3), or falls into an accepted *style
   category* (§7.2). Policy chosen by the user ("derive first, then accept"): Oracle style choices
   (sentence joins, duration placement, conjunct order …) are derived from the AST wherever a general rule
   exists; leftovers are accepted by category; the notation is changed **only** when the eval exposes a
   difference in *meaning*, never to carry English style.
4. **Two layers** (approach chosen by the user, §4): a language-neutral *planner* (AST → clause plans) and
   an *English realizer* (clause plans → strings). The planner is what the Bulgarian realizer will reuse.
5. **Glossary-driven words:** every English word that comes from a symbol or name lives in the glossary, so
   a new symbol that behaves like an existing one needs only glossary data, as with the AST.
6. Card headers too: name, mana cost, type line (`Artifact Creature — Gargoyle`), P/T / loyalty /
   defense — compared with Scryfall's `type_line` etc.

## 3. Non-goals

- The Bulgarian realizer (next project; this one only has to leave the planner ready for it).
- Reminder text and flavor text (Oracle comparison already strips reminders, `mtglang/oracle.py`).
- English → AST parsing.
- Rendering keyword `definition:` fields as prose.
- A rules engine.

## 4. Approaches considered

| | Approach | Trade-off | Verdict |
|---|---|---|---|
| 1 | Single English renderer: one function per AST kind + English phrase frames | fastest to a high Oracle match; Bulgarian must be written from scratch — nothing about agreement, plurality, pronouns, sentence splitting is shared | rejected |
| **2** | **Shared planner → per-language realizer** | a little slower to start; Bulgarian reuses all semantic decisions, and the English eval tests the planner Bulgarian will depend on | **chosen by the user** |
| 3 | Grammatical Framework (GF, has a Bulgarian resource grammar) | linguistically strongest, but a new toolchain and language; Oracle idioms fight a general grammar; breaks "add a symbol = glossary only" | rejected |

## 5. Anti-goals (failure even if the match rate is 100%)

- **Per-card strings.** No table mapping card/line → English, no `if card == …`. Every rule must be about a
  node kind, a symbol's lexicon data, or a construction that recurs (or could recur) on other cards.
- **English style in the notation.** No symbol or marker whose only job is to pick an English wording
  (e.g. a separate "`, then`" join). Style that can't be derived goes to an accepted category.
- **Smuggling English through named effects.** `⟨…⟩` effects stay the four existing one-offs; adding new
  ones to hit a match is cheating. If the AST can't express something, fix the notation.
- **English in the planner.** The clause plan must not contain English word order, articles, "a/an",
  English-specific idioms or literal strings. Test: could the Bulgarian realizer consume it unchanged?
- **Breaking existing guarantees:** validator stays at 0 errors, every line still round-trips
  (`S-ROUNDTRIP`), the glossary editor (`mtglang serve`) keeps working and preserves the new glossary data.

## 6. Architecture

```
.mtgl ──semparse──► AST ──resolve──► resolved AST ──plan──► clause plans ──realize(en)──► English
                                                             (neutral)      lexicon: glossary `lex.en`
```

New modules (names are suggestions):

- `mtglang/plan.py` — planner. Input: resolved AST + card context. Output: plan objects (§6.1).
- `mtglang/realize/en.py` — English realizer: word order, articles, plural forms, Oracle idioms.
- `mtglang/lexicon.py` — loads per-language lexicon entries from the glossary.
- `mtglang/evalen.py` — eval: alignment, normalisation, comparison, cause grouping, report writing.

### 6.1 Clause plans (the language-neutral IR)

A small set of dataclasses, roughly:

- `AbilityPlan` — shape (static / triggered / activated / keyword line / modal / chapter / labelled …),
  its parts (trigger event, intervening condition, cost, effect sentences, limits).
- `SentencePlan` — an ordered list of clauses, with how they are joined (then, and, or, if, unless,
  instead, until, for each …).
- `ClausePlan` — a predicate (symbol ref: verb / characteristic change / comparison), subject, role-tagged
  arguments (`object`, `destination`, `amount`, `duration` …), and features: polarity, optional ("may"),
  passive, tense/aspect where the AST implies it (trigger event vs effect vs condition "this turn"),
  mood (imperative-to-controller vs third person).
- `PhrasePlan` — noun phrase: head(s) (symbol / name refs), modifiers in role slots (filters, relations,
  counts, zones), and features: `number` (sg/pl, from resolve), `quantity` (one / all / each / up_to /
  exactly / …), `definiteness`, `reference` (`self`, `anaphor` with antecedent, `new`), `person`
  (you vs others), whether it is the subject.

Decisions the planner makes (because every language needs them): when a reference becomes a pronoun vs a
repeated phrase; number and quantity; implicit subjects; which clauses share a subject; sentence splits.
Decisions the realizer makes: order, articles, inflection, punctuation, capitalisation, idioms.

**Planner decisions are defaults, never lossy.** The plan always keeps the full information behind each
discourse choice: a pronoun-ised phrase keeps its antecedent's full phrase plan; clause boundaries and
join kinds stay explicit even when the planner proposes merging; each choice carries its reason (e.g.
`pronoun: same-sentence antecedent`). A realizer may override any of them (Bulgarian may repeat a noun
where English says "it", or split differently) without changing the planner. Oracle-specific discourse
tuning that isn't plausibly universal belongs in the English realizer, not the planner.

### 6.2 Lexicon in the glossary

The current `labels.en` are descriptions for the Legend ("that object / player (just mentioned)") — not
words to render. Each symbol gets an optional `lex:` mapping per language, beside `labels`:

```yaml
- {glyph: ✖, …, lex: {en: {verb: destroy, s: destroys}}}
- {glyph: ♞, …, lex: {en: {noun: creature, pl: creatures}}}
```

The exact keys per syntax `kind` (verb forms and argument frames with prepositions, noun singular/plural,
adjective, preposition, keyword text …) are the builder's to design; they must be declarative data, not
templates containing logic. Irregular forms are data (`pl: Elves`). Names (`names.yaml`) are already
English keys; they get an optional `lex.en` only where needed (plural of a subtype, short name of a
legendary card if Oracle uses one). Keywords already have `oracle:` — reuse it.

`mtglang serve` / `mtglang/edit.py` must round-trip `lex` (as it does `syntax`). The validator warns when a
symbol used in the corpus has no `lex.en`.

### 6.3 Card context

The realizer receives the card: name, type line, legendary or not, face. Oracle (since late 2024) refers to
the card itself as **its name if legendary** (short name before the comma: "Arni"), otherwise **"this
<type>"** (this creature, this enchantment, this Saga …), and as "it" after the first mention in a
sentence. The planner marks `self`; the realizer picks the form from the card context.

## 7. Evaluation

### 7.1 Alignment

Rows are aligned exactly as the gallery does today: ability *k* of face *f* ↔ Oracle line *k* of face *f*
(`oracle_lines`). Header fields compare with Scryfall `name`, `type_line`, `power/toughness`, `loyalty`,
`defense`. A card whose ability count differs from its Oracle line count is reported as an alignment
problem (cause `align`), not silently matched.

### 7.2 Causes

Every mismatch gets one cause, assigned by the eval where it can and by a reviewed list otherwise:

- `renderer` — default for any mismatch (realizer or planner bug).
- `style:<category>` — Oracle wording the AST can't predict and no general rule derives (e.g.
  `style:join` for `;` rendered as ". " vs ", then" vs ". Then"; `style:duration-order`). Accepted by
  category in `data/eval-en-accepted.yaml` (category, description, matching rule or list of lines);
  the report shows each category's size. A category is only for genuinely non-derivable style — the
  builder must first try a rule (e.g. ", then" when both clauses are short imperatives to the same
  player) and record in the category description what was tried.
- `notation` — the card file loses information; fixed by changing the card (migration script in
  `scripts/migrations/` if it affects several cards, spec §12 updated).
- `ast` — the AST/resolver can't represent or resolves wrongly; fixed in semparse/resolve.
- `accepted` — a one-off deliberate difference listed in the same file (`set/slug`, line, reason), e.g. an
  Oracle inconsistency between two cards with identical notation.

### 7.3 Normalisation

Before comparing: strip reminder text (existing), collapse whitespace, unify typographic quotes/dashes
(`’`→`'`, `—` kept as is in type lines), compare case-sensitively otherwise. Mana symbols compared as text
(`{1}{W}`). Nothing else is normalised — articles, commas, word order all count.

### 7.4 Report

`build/eval-en/index.html`: summary (lines, exact, per set, per cause), then each mismatch: card, line,
notation, rendered, Oracle, a word-level diff. `report.json` holds the same data for tests and scripts.
The gallery's line-by-line table gets an "English (rendered)" column; mismatching cells are marked.

### 7.5 Ratchet

`tests/` keeps the current exact-match count in a small file; a test fails if it drops. It is raised as
work progresses, ending at "all lines match or are accepted".

### 7.6 Facts established by the builder check

- All 1242 lines parse and round-trip; validator at 0 errors. Line alignment (`V-ALIGN`) and header checks
  (`V-CARDNAME`, `V-MANA`, `V-TYPE`, `V-STATS`) already exist; `english_type_line` exists and can be reused.
- The Oracle snapshot uses post-2024 self-reference wording.
- Identical notation → different Oracle text: 10 of 898 cases, all self-reference forms, covered by §6.3
  and short names in `names.yaml` ("Dr. Crusher", "Commander Musiker", "U.S.S. Cerritos").
- `;` maps to three Oracle joins (new sentence ≈249 lines, ", then" ≈46, ". Then" / ", where X is" ≈26) —
  the first expected style category or derivation rule.

### 7.7 Neutrality check (Bulgarian probe)

No Bulgarian realizer in this project, but a deliverable: ~15 representative lines (pronouns, plurals,
"each/target/up to", triggers, conditions, durations, a modal) rendered into Bulgarian **by hand from the
clause plans alone**, recorded in `docs/bg-probe.md` with the plan for each. Any Bulgarian need the plan
doesn't carry (gender of an antecedent, definiteness, aspect …) is a planner bug to fix now.

## 8. Working order (for the plan, not binding)

1. Planner + realizer skeleton, lexicon loading, card context, headers, keyword lines, eval + report —
   to get a first number quickly.
2. Grow node-kind coverage by frequency of mismatch causes in the report.
3. Fix notation/AST where the eval shows lost information.
4. Gallery column; docs (README, spec new §15 "Rendering").

## 9. Constraints

- Python, existing stack (uv, lark, jinja2, pytest). No new heavy dependencies.
- Card files remain the source of truth; any notation change goes through migrations and keeps 0 validator
  errors and the round-trip.
- Determinism: same input → same output.

## 10. Left to the builder

- Exact dataclass fields of the plan objects, module layout.
- `lex` key schema per syntax kind.
- How causes other than `renderer` are recorded (inline in the accepted file vs separate triage notes).
- Diff algorithm for the report.
