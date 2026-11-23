# MTG-Lang: a language-independent notation for Magic card text — Design

Date: 2026-11-23
Status: draft v2 (identifier classes + strict fidelity decided), awaiting approval

## 1. Intent

Magic: The Gathering card text is written in English (and translated per language).
The goal is an alternative card-text language that is **not tied to any natural
language**: a reader who knows the notation's legend can understand a card without
knowing English. It takes inspiration from formal-logic predicates and syntax, gives
keyword mechanics short "nicknames" (letters or symbols, e.g. `F` = Flying), and borrows
filter syntax from Scryfall search (https://scryfall.com/docs/syntax).

**Readers:** humans first. The notation must be readable at a glance by a person who
knows the legend. Machine readability is second: we accept losing some of it (no
executable rules semantics), but every card must still parse against a grammar so the
notation stays consistent and checkable.

## 2. Scope (first iteration)

Main-set cards only, from the two most recent sets (Scryfall data, unique by card):

| Set | Code | Unique cards | Notable features |
|---|---|---|---|
| Star Trek | `trk` | 311 | Station / Spacecraft / Planet (27), Sagas (10), Strange new worlds, Beam me up, Face a dilemma, Federation, Assimilate, Surveil (22) |
| Reality Fracture | `fra` | 285 | Prepare layout (21), Planeswalkers (8), Empower Jace (35), Prepared (24), Surveil (43), Flashback, Threshold |

Total ≈ 596 cards, ≈ 1,270 rules-text lines. About 56% have triggered abilities, about 28%
have activated abilities, about 5% are modal ("Choose one"), and about 22% create tokens.

Excluded: Commander decks (`trc`, `frc`), token sets, Alchemy, art series, promos.
Tokens are described only where a card creates them.

## 3. Goals, non-goals, anti-goals

**Goals**
- A written **language spec** covering: card header, ability shapes, filters, effects,
  costs, keywords, numbers/variables, choices/modes, durations, and multi-face layouts.
- A **glossary** (symbol legend) that defines every symbol, keyword nickname, type,
  subtype and named effect, with display labels per natural language (English at
  minimum) and, for keywords, a definition written in the notation itself.
- **All ≈596 cards translated**, drafted by Claude and reviewed by the user.
- A **validator** that parses every card and checks it against the glossary and Scryfall data.
- A **renderer** that produces a browsable HTML gallery (notation next to Oracle text) and a
  plain-ASCII fallback form.

**Non-goals**
- A rules engine, or semantics precise enough to run a game.
- Automatic English→notation translation (possible later, once the language settles).
- Sets beyond `trk` + `fra`; flavor text, artist, card-frame design.

**Anti-goals** (failure even if technically complete)
- **English creeping back in.** Words used as words, e.g. `when creature dies`. Every token
  must be a symbol, number, mana symbol, or glossary identifier.
- **Programming-language look.** If a typical card line reads like code rather than like a
  compact formula, the notation has failed its primary reader.
- **Glossary bloat.** If most cards need their own special named effect, the language
  isn't really expressing anything. The escape hatch (§5.6) must stay rare.
- **Ambiguity that changes meaning.** Two different Oracle texts must never translate to
  the same notation unless they really mean the same thing.

## 4. Approaches considered

| | Approach | Trade-off | Verdict |
|---|---|---|---|
| A | **Custom text notation with a formal grammar** | Reads like a language and like logic; grammar file doubles as spec; needs careful up-front design | **Chosen**, in its human-readable form (below) |
| B | Structured data (YAML/JSON + schema) | Easiest tooling, free validation; 3–4× longer, unpleasant to write, a data format rather than a notation | Rejected: fails the human reader |
| C | Cards as typed code (TS/Python builders) | Type checker validates; but ties the "language-independent" language to a programming language | Rejected: works against the intent |

Decided in conversation: **A, adjusted toward humans**. The human-readable form is the
*only* authored form (no separate verbose machine core). The grammar checks structure,
not full rules semantics. One-off rules use a named-effect escape hatch.

## 5. The language (decided principles; vocabulary to be designed)

### 5.1 Token rule (the core of language independence)
Every token in card text is exactly one of:
1. a **symbol** from the legend (e.g. `⇒`, `↑`, `✝`),
2. a **number or variable** (`3`, `X`, `≥`, `+1/+1`),
3. a **mana/game symbol** already used by Magic (`{R}`, `{T}`, `{3}`),
4. a **glossary identifier**, split into two classes (decided: "mixed"):
   - **Closed vocabulary → symbols or neutral codes, never words.** Everything that is
     grammar or appears across many cards: card types, supertypes, zones, players
     (you/opponent/each), actions/verbs, comparisons, durations, timing, keywords,
     counters, mana. These must not look like English (validator-enforced: a lexical
     rule restricts these glossary classes to symbols/short codes).
   - **Open-ended proper names → localizable keys.** Creature/artifact/land subtypes,
     card names, token names (e.g. "Porthos"), and named effects. These may be
     word-like keys in source, are marked syntactically (e.g. a sigil or quoting — exact
     form decided in milestone 1), and are shown through the glossary's per-language
     labels when rendered — like place names on a map, not grammar.

   The validator enforces that word-like tokens appear **only** in the proper-name
   class; any word-like token elsewhere is an error.

### 5.2 Card layout
- **Header:** name (identifier), mana cost (existing mana symbols), type line (type
  symbols + subtype identifiers), P/T or loyalty or defense.
- **Body:** one ability per line, as in Oracle text.
- **Reminder text is dropped.** It lives once in the glossary as the keyword's definition.
- Multi-face cards (prepare layout, adventures if any) and Sagas/stations use a face or
  chapter separator. Station thresholds (`9+ |`) and Saga chapters (`I —`) get dedicated syntax.

### 5.3 Ability shapes (logic-inspired)
- **Keyword:** a nickname alone on a line, e.g. `F` (Flying), possibly with a parameter (`Ward {2}`).
- **Triggered:** `event ⇒ effect` (implication). Optional condition: `event ∧ cond ⇒ effect`.
- **Activated:** `cost : effect` (mirrors Magic's own colon convention).
- **Static:** a statement with a filter, e.g. "creatures you control get +1/+1".
- **Ability words** (Landfall, Federation, Threshold…) are optional labels prefixed to a line.

### 5.4 Filters (borrowed from Scryfall syntax)
Object descriptions use bracketed key:value filters modeled on Scryfall search:
"creature card with mana value 4 or less in your graveyard" — structurally
`[‹creature› ‹mv›≤4 ‹graveyard›:‹you›]`, where each ‹…› becomes a symbol/code per §5.1
(the English placeholders here are for this doc only). The structure (bracketed conjunction of attribute tests, comparison operators `≤ ≥ =`,
`∨` for alternatives, `¬` for negation) is decided. The exact keys/symbols are part of
vocabulary design (§7, milestone 1), and must obey the token rule.

### 5.5 Effects and quantities
Effects are predicates/verbs written as symbols or glossary identifiers with arguments:
draw, damage, destroy, exile, create token, counters, add mana, life gain/loss, surveil,
mill, etc. Variables are defined inline ("where X is…") with a `X≔…` binding. Durations
("until end of turn") get symbols. Choices ("choose one") get a mode-list syntax with `•`.

### 5.5a Fidelity: strict (decided)
Translations must preserve **every rules-relevant distinction** — a judge must be able to
rule from the notation alone. At minimum the notation encodes distinctly:
target vs. non-target vs. "each"; "up to N" vs. "N"; "may" vs. mandatory; "you control"
vs. "you own"; "this turn" vs. "until end of turn"; timing restrictions ("activate only as
a sorcery", "only once each turn"); replacement effects ("if … would … instead") vs.
triggers; "enters tapped", "enters with counters"; intervening-if conditions; "another"
/ "other" exclusions; owner vs. controller on zone changes. Each such distinction should
cost as little as a single mark where possible (e.g. one symbol for "target", one for
"may") to protect readability.

Consistency rule: identical Oracle phrasing (after normalizing card self-references)
must produce identical notation across cards. The validator reports violations.

### 5.6 Escape hatch: named effects
Rules that appear on only one card may be written as a named effect `⟨id⟩`, defined once
in the glossary (prose definition per language). The validator reports usage. Target:
**under 5% of ability lines** use a named effect.

### 5.7 Two display forms
- **Symbol form** (primary): Unicode symbols, rendered in HTML.
- **ASCII form**: auto-generated letter equivalents (`F`, `=>`, …) for plain-text contexts.
  Every symbol has an ASCII alias in the glossary, and the parser accepts both.

Illustrative only (vocabulary not yet designed). Dal R'El, Augment Orphan:
```
Landfall: ⛰↑ ⇒ +{R|G}
{3}, ✝⛰ : ✋+1
```

## 6. Deliverables and repository layout (proposed)

```
mtg-lang/
  docs/superpowers/specs/      design docs (this file)
  spec/
    language.md                human-readable spec with examples
    grammar.lark               formal grammar (Lark, Python)
  glossary/
    symbols.yaml               symbol → meaning, ASCII alias, labels per language
    keywords.yaml              nickname → definition in notation, reminder labels
    types.yaml                 card types, subtypes, counters, tokens
    named_effects.yaml         escape-hatch definitions
  cards/
    trk/<card-slug>.mtgl       one file per card (easy review and diffs)
    fra/<card-slug>.mtgl
  data/                        cached Scryfall JSON snapshot (fetched by script)
  tools/ (Python package + CLI)
    fetch                      download/update the Scryfall snapshot (respects rate limits)
    validate                   parse every card; report errors and coverage
    render                     HTML gallery + ASCII export
```

**Validator checks:** every card parses; every identifier exists in the glossary; header
matches Scryfall (name, mana cost, types, P/T/loyalty); every Scryfall card in scope has a
translation; named-effect usage and glossary-size statistics; symbols have ASCII aliases;
word-like tokens only in the proper-name class (§5.1); identical normalized Oracle lines
map to identical notation (§5.5a).

**Renderer** also takes a display-language option (English labels at minimum) for
proper-name keys.

**Renderer:** static HTML gallery. Each card shows the notation (symbol form), the ASCII
form, and the Oracle text side by side, plus a legend page generated from the glossary.

## 7. Milestones

1. **Vocabulary & grammar draft.** Pick ~30 representative cards covering every ability shape,
   both sets' mechanics, stations, sagas, prepare cards, planeswalkers, and modal spells.
   Propose 2–3 notation styles (symbol-heavy, letter-heavy, mixed) on the same cards and
   **review with the user**, who decides the look. Then freeze v0.1 of the spec + grammar.
2. **Tooling:** fetch, validator, renderer working on the 30 sample cards.
3. **Translate `fra`**, then **`trk`**, in batches of ~50. The user reviews each batch in the
   HTML gallery, and grammar/glossary are revised as patterns emerge (the validator re-checks
   all cards after each change).
4. **Readability check & report.** Back-translation test: a fresh LLM given *only* the
   glossary and the notation writes English for a random sample, and we compare it with
   Oracle text. Report coverage, escape-hatch rate, and open problems.

## 8. Success criteria
- 100% of in-scope cards translated, parsing, and reviewed by the user.
- Named effects on under 5% of ability lines.
- No natural-language words outside glossary identifiers (validator-enforced).
- Back-translation sample: rules meaning preserved (strict, judge-level — §5.5a) on ≥90%
  of sampled cards (user judges); every miss leads to a notation or glossary fix.
- The user finds the symbol form readable at a glance once they know the legend.

## 9. Constraints
- Scryfall API: identify via a User-Agent header, about 10 requests/second max. Cache the
  snapshot locally and don't refetch per run.
- Symbols must render in common fonts (macOS/Windows/Linux defaults). Avoid obscure glyphs.
- Python 3 with Lark for the grammar (Claude's call; user handed over the how).

## 10. Left to the builder
- Exact grammar productions, error messages, CLI ergonomics.
- HTML styling (clean and legible, no card-frame imitation needed).
- Card-file header format details, slug naming.
- Test structure (grammar tests per ability shape; snapshot tests for renderer).
