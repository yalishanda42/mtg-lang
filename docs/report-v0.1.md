# MTG-Lang v0.1 — readability report

Date: 2026-11-23 · Style: symbol-heavy · Spec: `spec/language.md` v0.1

## 1. Coverage

| Set | Cards | Ability lines | One-off effects | Validation |
|---|---|---|---|---|
| Reality Fracture (`fra`) | 285 / 285 | 599 | 2 (0.33%) | 0 errors |
| Star Trek (`trk`) | 311 / 311 | 643 | 3 (0.47%) | 0 errors |
| **Total** | **596 / 596** | **1,242** | **5 (0.40%)**, target < 5% | **0 errors, 0 warnings** |

The validator checks every card file against Scryfall (name, mana cost, type line, P/T or loyalty,
one notation line per Oracle line, face count). It also checks every proper name and one-off effect
against the glossary, rejects any English word outside `«…»`/`⟨…⟩`, and requires identical Oracle
lines to have identical notation across all 596 cards.

## 2. Vocabulary size

| Glossary | Size | Breakdown |
|---|---|---|
| Symbols (closed vocabulary) | 200 | 45 actions, 42 keywords, 21 logic, 13 comparison, 14 time, 12 structural, 10 characteristics, 9 card types, 9 zones, 6 counter kinds, 5 object kinds, 5 ability words, 5 players, 2 references, 2 stats |
| Proper names | 801 | 600 card/face names, 157 subtypes, 35 flavor words, 9 token names |
| One-off effects | 4 keys / 5 uses | `⟨no-legend-rule⟩`, `⟨any-number⟩`, `⟨extra-lifegain-trigger⟩`, `⟨no-max-hand⟩` (2 uses) |

Symbols grew from 139 (sample) to 200 (full corpus). Most additions were rules concepts the 30-card
sample didn't touch: turn structure, library positions, copies, replacement "instead", counter kinds.

## 3. Back-translation test

**Method:** `mtglang backtrans --n 40 --seed 7` picked 40 random cards. A fresh agent got **only** the
legend and the notation, with no Oracle text, spec, or other files, and wrote Oracle-style English.
The answers were then compared line by line with the real Oracle text, applying the strict standard
(spec §5.5a).

| Result | Cards | Which |
|---|---|---|
| Rules meaning preserved (wording may differ) | 37 | all others |
| Preserved, but the reader flagged a real notation ambiguity | 2 | #3 H.M.S. Bounty ("this game" written as `∀◷`), #4 Draconic Visitor (reader rewrote "created under your control" as "you would create") |
| **Rules difference** | **1** | #20 La'An Noonien-Singh: "Whenever you attack **while** …" read as an intervening "if" |

**Score: 39/40 (97.5%) rules meaning preserved**, or 38/40 (95%) if #4 also counts as a miss.
The spec's bar is ≥90%; whether that is met is your call.

### Fixes applied after the test
- **"while" vs. intervening "if" (#20):** 8 cards wrote a trigger-time "while" condition with `∧`, which the
  spec reserves for an intervening "if" that is re-checked on resolution. They now use `∵`:
  - Hologram Janeway, Kirk Commanding Officer, La'An, Tactical Officer, Una Chin-Riley and Worf Honor-Bound (`● ➹ ∵ Σ△ ♞[⚑●] ≥ 8 ⇒`);
  - Combadge;
  - Kira Nerys.

  Spec §8 is updated.
- **"this game" (#3):** new symbol `∞`. H.M.S. Bounty and First Contact now use it.

## 4. What the reader found hardest (open problems for v0.2)

1. **Keywords with no definition in the legend.** Set mechanics such as `⟁` Empower Jace, `⧉` Prepared,
   `⛭` Station, `⟡` Discover and `☀` Sunburst show only a name. **Proposal:** give every keyword a
   definition in notation. Where that isn't practical, put the reminder text in the per-language label.
2. **Scope of station blocks.** It isn't visible which lines belong to an `n+ |` threshold (H.M.S. Bounty).
   **Proposal:** indent the lines in a block, or repeat the `n+ |` prefix on each line.
3. **Filters carry too much.** Controller, zone, counters and "another" all share one bracket:
   `⊟ ≤3⊞[◎(♞ ∨ ⚝)[≠◈]]`, `♞[⚑● ⊞]`. **Proposal:** a separate "on" mark for counters (`⊞@◎…`) and
   a rule that a bare `⊞` in a filter means "with any counter".
4. **Token name vs. subtype.** In `◌[…] «Cadet»` the trailing name could be a third subtype.
   **Proposal:** a "named" mark, e.g. `◌[…]=«Cadet»`.
5. **Mixed conditionals.** `¬⊃` (unless), `✓ ⊃` (if you do), `⊃ ⤳` (…instead) work, but are tiring to read.
   **Proposal:** dedicated glyphs for "unless" and "instead", and make `✓`/`✗` stand alone.
6. **Smaller:**
   - `☞` refers to both single objects and groups.
   - The `(∀○)` "for each opponent" prefix isn't in the legend.
   - `∈` (adds a type) vs. `≔` (replaces types) is subtle.
   - The scope of `⧗` over several joined effects is unclear.

### Caveats on the test
- **Name hints:** card names are shown as proper names, so the reader gets English hints (e.g. "Unsummon"). A
  stricter test would replace card names with neutral IDs.
- **Expert reader:** the reader is an LLM that already knows Magic. It fills gaps a newcomer couldn't, but it
  is also a good stand-in for the target reader, an experienced player who learns the legend.

## 5. Decisions made while translating (all in the git history)

- **Passive `←`:** `¬⛉←` is "can't be blocked" and `¬⛉` is "can't block". Introduced on the first
  "can't block" card, then applied back to the 3 earlier cards that needed it and to the Menace definition.
- **Pay `⊷`:** "pay life" (`⊷♥2`) is distinct from "lose life" (`♥-2`), as the rules require.
- **Becomes `≔`:** "becomes a <type>" uses `≔`, which replaces subtypes (CR 205.1b). "In addition to its other types" uses `∈`.
- **Grouped abilities:** reflexive triggers ("When you do"), delayed triggers ("at the beginning of the
  next end step") and "until your next turn, whenever…" are written as abilities inside parentheses.
- **Data quirk:** the Scryfall text for *Those Old Scientists* has a reminder text whose parentheses span
  two lines. Oracle cleanup now handles that (test added).
