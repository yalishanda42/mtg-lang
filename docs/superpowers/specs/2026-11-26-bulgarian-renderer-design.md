# Bulgarian renderer (old spelling), sample round — short design

Date: 2026-11-26. Status: draft for approval.

**Intent.** A third card in the gallery, next to the original and the MTG-Lang card: the same scan painted with
the card in pre-1945 (Ivanchev) Bulgarian — name, type line and rules text rendered from MTG-Lang. This is the
second realizer on the shared planner (English renderer, spec §15). Start with a sample of ~25 cards; the user
reviews the Bulgarian in the chat and each round of feedback becomes rules or word data.

**Goals.** `mtglang/realize/bg.py` renders the sample's every line with no `⟦gap⟧`; `mtglang bg <card>` prints the
modern and Ivanchev text; the gallery shows the third card (Ivanchev) for sample cards.

**Non-goals (this round).** Full-corpus coverage; an automatic score (there is no Bulgarian answer key); a
review tool or in-gallery editing (feedback comes in the chat); modern-spelling cards in the gallery.

**Anti-goals.** Per-card Bulgarian strings or line overrides; translating the English output; English
words or order leaking into the Bulgarian; the English eval dropping (ratchet); planner changes that aren't
language-neutral.

**Approaches.** (A) separate Bulgarian realizer on the planner + `lex.bg` word data + `to_ivanchev` on its
output — **chosen by the user**; (B) reuse the English realizer with swapped words — rejected (English idioms
leak, no agreement, throwaway); (C) translate rendered English — rejected (defeats language independence).

**Design.**
- `lex.bg` in `glossary/symbols.yaml` / `names.yaml`, same `lex:` maps as English; new keys as needed for
  Bulgarian (gender, definite forms, verb aspect pairs, participles) added to `LEX_KEYS` and spec §15.2. Written
  in the existing register (late-19th-c. literary, Vazov; the `bg` labels' word choices), only for words the
  sample uses.
- `bg.py` mirrors `en.py`'s structure and reads the same plan decisions: `once` → perfective/imperfective
  temporal clause (*когато встъпи* / *щом напада*), `aspect` → *има* / *придобива*, `tense=past`, `self_as`,
  anaphors via the antecedent's gender, plural `all` → definite plural.
- Self-reference: the card's name for legendary cards and spells (`bg` label of the name), otherwise
  *тая/тоя/туй <type>* agreeing in gender.
- Old spelling: modern Bulgarian out of `bg.py`, then `to_ivanchev` (with `ortho_overrides.yaml`) per line.
- Sample list: `data/bg-sample.txt`, ~25 cards from both sets covering triggers, costs, modal, tokens,
  counters, conditions, durations, a Saga, a planeswalker, a two-face card — only cards whose English already
  matches Oracle.
- Gallery: a third figure for sample cards, same overlay geometry, captioned in Bulgarian.
- Tests: no gaps on the sample; a few pinned Bulgarian lines after the user approves them; English ratchet.

**Left to the builder.** Exact `lex.bg` keys and module layout; which 25 cards.
