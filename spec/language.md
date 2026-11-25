# MTG-Lang — language specification

Version 0.1 (symbol-heavy style), frozen 2026-11-23 after sample review. The vocabulary lives in `glossary/`, and the Legend tab of
the single-page gallery (`mtglang render` → `build/index.html`) lists every symbol with its meaning. `mtglang serve`
serves the same page on localhost and makes the Legend an editor: glyph, ASCII and meaning edits preview live on every
card, and Save rewrites `glossary/symbols.yaml` plus every card file (token-aware, refusing any edit that would make a
line ambiguous). This document covers the *structure*.

## 1. Token rule

Every token on a card is exactly one of:

| Kind | Examples | Notes |
|---|---|---|
| glossary symbol | `◈ ⇒ ♞ 🪽 ⧗` | closed vocabulary, `glossary/symbols.yaml`; each has an ASCII alias |
| number / variable | `3`, `X`, `Y`, `Z` | |
| mana / game symbol | `{G}`, `{2}`, `{T}`, `{U/B}` | Magic's own symbols, unchanged |
| fixed punctuation | `[ ] ( ) , / + - − —` | `−` is the minus sign in loyalty costs |
| proper name | `«Human»`, `«Porthos»` | open-ended names (subtypes, cards, tokens, flavor words). Shown in the reader's language via `glossary/names.yaml` |
| one-off effect | `⟨key⟩` | escape hatch for a rule found on a single card (`glossary/named_effects.yaml`) |

Natural-language words (`[A-Za-z]{3,}`) may appear **only** inside `«…»` or `⟨…⟩`. Two-letter ASCII
aliases (`Cr`, `Tg`) are allowed, and adjacent aliases may touch (`SaLd`).

## 2. Card files

One file per card, `cards/<set>/<slug>.mtgl`:

```
«Koth, the Geomancer» {2}{R}        ← name + mana cost
⚜♞ — «Human» «Warrior»              ← type line: type symbols — subtypes
3/2                                 ← power/toughness, ◇n (loyalty) or ⛨n (defense); omitted otherwise

⇞                                   ← one notation line per Oracle line, same order
⛶ ▸ ⛰[⚑●]↥ ⇒ ◈ ✸1 → ∀○ ; ☞ ∈ «Mountain» ⊃ ⊕{R}
```

- Lines starting with `#` are comments.
- Multi-face cards separate faces with a line containing only `//` (see *Theorix Metamage // Omit Variables*).
- Reminder text is never written. It lives in the glossary as the keyword's definition.

## 3. Ability shapes

| Shape | Form | Example | Reads |
|---|---|---|---|
| keyword(s) | `K, K` | `🪽, ⊙, ♡, ⊠{2}` | Flying, vigilance, lifelink, ward {2} |
| triggered | `event ⇒ effect` | `◈↥ ⇒ ● ♥+1` | When this enters, you gain 1 life. |
| intervening if | `event ∧ cond ⇒ effect` | `◈↥ ∧ #⛰[⚑●] ≥ 6 ⇒ …` | When this enters, if you control six or more lands, … |
| activated | `cost : effect` | `{T} : ⊕ {U} ∨ {R}` | {T}: Add {U} or {R}. |
| static | statement | `♞[⚭◈] +1/+0 ∧ ∋☣` | Enchanted creature gets +1/+0 and has deathtouch. |
| replacement | `event ⤳ effect` | `◈↥ ⤳ ⊻ Y ; 0 ≤ Y ≤ 10` | As this enters, choose a number between 0 and 10. |
| labelled | `label ▸ ability` | `⛶ ▸ …`, `«Open a Channel» ▸ …` | ability word / flavor word |
| modal | `⊻n` line, then `• …` lines | `⊻1` / `• ♞[⚑●] +2/+0 ⧗` | Choose one — • … |
| saga chapter | `§n ▸ effect` (`§1,2 ▸` for several) | `§2 ▸ ● ♥+3` | II — You gain 3 life. |
| station threshold | `n+ \| ability` | `12+ \| ⚙♞[⚑●] ∋ 🪽` | 12+ \| Artifact creatures you control have flying. |

Formal structure (`mtglang/grammar.lark`):

```
ability : prefix? label? body
prefix  : § NUMBER (, NUMBER)* ▸  |  NUMBER + |  |  •
label   : term+ ▸
body    : expr  |  expr ⇒ expr  |  expr : expr
expr    : (term | ,)+
term    : symbol | mana | number | var | «name» | ⟨effect⟩ | + | - | /
        | [ (term | ,)* ]                       (filter)
        | ( expr ((⇒ | :) expr)? )              (group / granted ability)
```

## 4. Objects and filters

An object is a type symbol followed by an optional **filter** in brackets. The brackets work like a
Scryfall search: a conjunction of conditions.

| Notation | Meaning |
|---|---|
| `♞[⚑●]` | creature you control |
| `♞[⚑● ≠◈]` | another creature you control |
| `▭♞[⚰●]` | creature card in your graveyard |
| `▣[⚑○]` | permanent an opponent controls |
| `♞[⚭◈]` / `♞[⚒◈]` | enchanted / equipped creature (attached to this) |
| `▭♞[⊘◈]` | creature card exiled with this |
| `✦[¬♞]` | noncreature spell |
| `✦[⌀ = Y]` | spell with mana value Y |
| `♞[⚑○ (△ ≤ 1 ∨ ▽ ≤ 1)]` | creature an opponent controls with power or toughness 1 or less |
| `(♞ ∨ ⚝)[⚑● ≠◈]` | another creature or planeswalker you control |

Adjacent type symbols combine: `⚙♞` is artifact creature, `⊡⛰` is basic land.

## 5. Quantifiers and references

| Mark | Meaning | Example |
|---|---|---|
| `◎` | target | `✖ ◎▣[⚑○]` destroy target permanent an opponent controls |
| `≤n◎` | up to n targets | `≤1◎♞` |
| `∀` | each | `◈ ✸1 → ∀○` this deals 1 damage to each opponent |
| `◈` | this object | |
| `☞` | that object/player (the one just mentioned) | `☞⚑` that permanent's controller |
| `?` | may / can | `● ? ▶⛰ +1 ∀◷●` |
| `●` / `○` / `◐` | you / an opponent / a player | |
| `⚑` / `⌂` | controller / owner | `→ ▦↷ ⚑⌂` onto the battlefield tapped under its owner's control |

## 6. Effects, quantities, variables

- Actions are verbs written as symbols, followed by their objects: `✖` destroy, `✝` sacrifice, `⤓` draw, `✚` create, `⊗` counter a spell, `⌖` search, `◉` reveal, `⟲` shuffle.
- Zone moves use `→`: `◎▭♞[⚰●] → ☚●` returns target creature card from your graveyard to your hand.
- Damage: `source ✸n → recipient`. Life: `♥+n` gain, `♥-n` lose. `♥+` alone is the *event* "gains life".
- Counters: `⊞+1/+1 → ☞`, `⊞◇ → ◈`, removal with `⊟`.
- P/T changes follow the object: `◎♞ +2/+0 ⧗`.
- Variables are bound with `≔` after the effect: `… +X/+0 ⧗ ; X ≔ #≢ ⛰[⚑●]`.
- `#` counts objects. `#⊤ ♞[…]` counts creature types among them. `#≢` counts objects with different names.
- Sentences are separated by `;`. `✓ ⊃ …` means "if you do, …" and `✗ ⊃ …` means "if you can't, …".
- Tokens: `◌[2/2 ♦∅ «Wizard» «Soldier» ♞] «Cadet»` is a 2/2 colorless Wizard Soldier creature token named Cadet. Predefined tokens are written `◌«Treasure»`.
- Granted abilities go in parentheses after `∋`: `∋ ({T}, ✝◈ : ⊕ 3◆)`.

## 7. Durations and timing

| Mark | Meaning |
|---|---|
| `⧗` | until end of turn |
| `◷` | this turn. `◷●` is your turn, `∀◷●` is each of your turns |
| `≡✎` | activate only as a sorcery |
| `≤1◷` | only once each turn |

## 8. Strict fidelity

Every rules-relevant distinction in the Oracle text must survive (spec §5.5a):

| Distinction | Marked as |
|---|---|
| target / non-target / each | `◎♞` / `♞` / `∀♞` |
| up to n / exactly n | `≤n◎` / `n◎` |
| may / must | `?` / nothing |
| you control / you own | `[⚑●]` / `[⌂●]` |
| until end of turn / this turn | `⧗` / `◷` |
| sorcery speed, once per turn | `≡✎`, `≤1◷` |
| replacement / trigger | `⤳` / `⇒` |
| intervening if / effect if / trigger-time "while" | `∧` before `⇒` / `⊃` inside the effect / `∵` before `⇒` ("Whenever you attack while …") |
| another | `≠◈` |
| if you do / if you can't | `✓ ⊃` / `✗ ⊃` |

The validator enforces one consistency rule: identical Oracle lines (after replacing the card's own
name with `~`) must be written identically on every card.

## 9. Keywords and cycling variants

Each keyword is one glyph, and its parameters follow it: `⊠{2}` ward {2}, `↺{5}{G}` flashback,
`⚒{2}` equip, `⇯{3}{G}` beam me up, `⟁2` empower Jace 2. Cycling variants are built from `♲` plus a
filter: `♲[⊡⛰] {2}` is basic landcycling {2}.

## 10. ASCII form

Every glyph has an ASCII alias, so `mtglang render` also writes `build/ascii/<set>.txt`. Example:
`⛶ ▸ ⛰[⚑●]↥ ⇒ ◈ ✸1 → ∀○` becomes `Lf |> Ld[Ct Yu]^ => @ Dg1 ~> Al Op`. The parser accepts both
forms, even mixed.

## 11. Constructs added during full translation (v0.1, all 596 cards)

| Construct | Example | Meaning |
|---|---|---|
| passive `←` | `◈ ¬⛉←` vs `◈ ¬⛉` | can't **be** blocked vs can't block |
| pay `⊷` | `● ? ⊷{2} ; ✓ ⊃ …`, `⊷♥2` | you may pay {2} / pay 2 life (≠ lose life `♥-2`) |
| unless `¬⊃` | `◈ ↥↷ ¬⊃ ∃⚝[⚑●]` | enters tapped unless you control a planeswalker |
| exists `∃` | `∃♞[➹ → ●] ⊃ ◈ ⊖{2}` | if a creature is attacking you, this costs {2} less |
| becomes `≔` | `◈ ≔ «Ferengi» «Scout»` | becomes (replacing subtypes); `∈` = is also |
| reflexive trigger | `● ? ⌫1 ; (✓ ⇒ ◈ ✸2 → ◎)` | "When you do, …" — a triggered ability in a group |
| delayed trigger | `(⊢▷☾ ⇒ ✝☞)` | "Sacrifice it at the beginning of the next end step" |
| bounded ability | `(♞➹ → ○ ⇒ …) ⊣▷◷●` | "Until your next turn, whenever …" |
| per player | `(∀○) ✖ ≤1◎♞[⚑☞]` | "For each opponent, destroy up to one target creature that player controls" |
| activation limit | `; ≡✎`, `; ≡ ≤1◷`, `; ≡(cond)`, `; ≡◷●` | only as a sorcery / once each turn / only if … / only during your turn |
| cost change | `◈ ⊖{X}`, `✦[¬♞ ✷○] ⨁{1}`, `⊳ ⊖{X}` | spell costs less / more; ability costs less |
| any target | `◈ ✸3 → ◎` | a bare `◎` is "any target" |
| turn structure | `⊢☼◷●`, `⊢⨯◷●`, `⊢☾`, `⊢☉1◷●` | beginning of your upkeep / combat on your turn / each end step / your first main phase |
| library positions | `⌃4▤●`, `→ ⌄▤● ⚂` | top four cards of your library; bottom in a random order (`⇅` any order) |
| copies | `✚ ◌[❐☞] ∋↯` | create a token that's a copy of it, with haste |
| counters | `2⊞+1/+1 → ◈`, `⊞✲`, `⊞◇`, `⊞✹`, `⊞✠`, `⊞⚐` | +1/+1, stun, loyalty, charge, finality, quest |
| replacement inside an effect | `… ; C ⊃ ⤳ effect` | "…instead" |

## 12. Notation changes in v0.2 (semantic AST)

Each change removes a construct the semantic parser could not read unambiguously. All are scripted in
`scripts/migrations/` (idempotent; run with `uv run python scripts/migrations/<file>.py`).

| # | Before | After | Why |
|---|---|---|---|
| 1 | `● ✪ ∋ (…)` | `● ✚ ✪ ∋ (…)` | "You get an emblem with …" had two subjects and no verb; `✚` (create) makes the emblem the object |
| 2 | `◈ ⊖{1} ∵ ◈ ◎ ♞[➹]` | `◈ ⊖{1} ∵ ♞[➹] ∈ ◎ ◈` | "If it targets an attacking creature": same form as `◈ ∈ ◎ ○`; the old clause had no verb |
| 3 | `⊢☾ ∧ ▣[▦ → ☚●] ◷ ⇒` | `⊢☾ ∧ ∃▣[▦ → ☚● ◷] ⇒` | "If a permanent was returned … this turn": a condition needs ∃, and the time belongs inside the filter (as in `∃♞☠◷`) |
| 4 | `(○ ✷ ✦ ∨ ○ ⊳ ▣)[ⁿ = ☞]` | `○ ✷ ✦[ⁿ = ☞] ∨ ○ ⊳ ▣[ⁿ = ☞]` | A filter narrows a phrase, not a pair of clauses |
| 5 | `● ? ◈ ❐ (⚙ ∨ ♞)[▦] ∧ ¬⚜` | `● ? (◈ ❐ (⚙ ∨ ♞)[▦] ∧ ¬⚜)` | "You may have this enter as a copy …": a parenthesised body gives the second subject its own clause (as in `◎○ ? (● ⤓1)`) |
| 6 | `∀▭[⊘ ☞] : ☞⚑ ? ▶☞ …` | `(∀▭[⊘ ☞]) ☞⚑ ? ▶☞ …` | `:` is the cost separator; "for each" is `(∀…)` everywhere else |
| 7 | `◌[«Planet» ⛰]↷ «New Planet»` | `◌[«Planet» ⛰] «New Planet»↷` | The token's name belongs to the token phrase; after `↷` it read as the thing being tapped |

## 13. Semantic AST

`mtglang ast <set>/<slug>` prints a card as a typed, language-neutral tree (JSON); `mtglang render` also
writes `build/ast/<set>.json`. The tree is derived from the `.mtgl` files (they stay the source of truth) by
`mtglang/semparse.py`, and `mtglang/unparse.py` turns it back into notation: every line of the corpus
round-trips token-for-token (validator code `S-ROUNDTRIP`).

### 13.1 Symbol behaviour comes from the glossary

Each symbol in `glossary/symbols.yaml` has a `syntax` (explicit, or defaulted from its `class`):

| Key | Meaning | Example |
|---|---|---|
| `kind` | grammatical kind: verb, type, object, player, reference, relation, quantifier, zone, time, characteristic, stat, keyword, ability_word, counter_kind, comparison, infix, prefix, marker, structural | `♞` type |
| `op` | the operator a parser rule needs (then, bind, and, or, not, if, while, replace, until, target, each, exists, may, count, …) | `⊃` if |
| `args` | a verb's argument slots, in order | `⊕` → `[amount, mana]` |
| `yields` | the verb's result can be referred to with `☞` | `⌕` surveil |
| `state` | the verb may follow another verb's arguments as a state or nominal object (`◈ ↥↷` enters tapped, `✚ ❐◈` create a copy of this); any other second verb is an error (missing `;` or `∧`) | `↷` |

A new symbol that behaves like an existing one needs only a glossary entry.

### 13.2 Node kinds

Every child sits in a named field or a named `(slot, node)` argument; the specific word is a glossary
reference (`sym`), a name (`name`) or a one-off effect (`effect`).

| Kind | Example | Fields |
|---|---|---|
| `card`, `face`, `typeline`, `stats` | the card file | faces; name, cost, types, stats, abilities |
| `keywords`, `keyword` | `🪽, ⊠{2}` | items; sym, params |
| `triggered` | `◈↥ ∧ #⛰[⚑●] ≥ 6 ⇒ …` | event, conds (intervening if), while_, effect |
| `activated` | `{2}, {T} : … ; ≡✎` | cost, effect, limits |
| `static` | `♞[⚑●] +1/+0` | body |
| `labelled`, `chapter`, `threshold`, `mode`, `modal` | `⛶ ▸`, `§2 ▸`, `12+ \|`, `•`, `⊻1` + `•` lines | label / numbers / n, ability; choose, modes |
| `effects` | `… ; …` | sentences |
| `action` | `◈ ✸3 → ◎` | verb, subject, args (`object`, `destination`, `amount`, `by`, `time`, `times`, `state`, `with`, `rel`, `filter`, `restrict`, …), optional, negated, passive |
| `modify` | `◎♞ +2/+0 ⧗`, `● ♥+1` | subject, change (`pt` or `delta`), args |
| `coord` | `X ∧ Y` | op, items |
| `cond` | `C ⊃ X`, `X ¬⊃ C`, `✓ ⊃ X`, `✗ ⊃ X` | mode (if / unless / if_do / if_dont), cond, then |
| `replace` | `E ⤳ X`, `⤳ X` (instead) | event, effect |
| `while`, `until`, `timed` | `X ∵ C`, `X ⊣ E`, `(…) ⧗` | body, cond / until / time |
| `bind`, `foreach`, `scoped`, `nested` | `X ≔ …`, `(∀○) …`, `∀◐ ? (…)`, `(✓ ⇒ …)` | var, value; over, body; subject, body; ability |
| `np` | `≤1◎♞[⚑○]`, `◌[2/2 ♦∅ «Cat» ♞] «Cadet»` | quant, each, count, heads, filters, name, post, neg, pre |
| `filter`, `rel`, `of` | `[⚑● ≠◈]`, `⚑●`, `☞⚑` | conds; rel, other; rel, of |
| `zone`, `time` | `⌃4▤●`, `∀◷●` | zone, pos, count, owner; items |
| `char`, `count`, `arith`, `compare`, `bound`, `pt`, `delta` | `◈△`, `#≢ ⛰[⚑●]`, `X ÷ 5`, `0 ≤ Y ≤ 10`, `≤1`, `+2/+0`, `♥+1` | … |

An `action` with no verb is "deals damage" written without a recipient (`◈ ✸⨯`, `∀♞[…] ✸⨯ = ☞▽`); its
`object` is the damage phrase. Signs are semantic (`+` / `-`; the loyalty `−` is spelling only), and a type
line's dash is stored as `—`.

`→` is the one transfer verb ("put into / onto / deal to"): `◈ ✸3 → ◎` is
`action(→, subject ◈, object ✸3, destination ◎)`. Written after another verb it is a particle and its target
sits in the `arrow:destination` slot.

### 13.3 Precedence

Loosest first, within one ability:

| Level | Symbols |
|---|---|
| ability prefix | `•`, `§n ▸`, `n+ \|`, `label ▸` |
| ability shape | first top-level `⇒` (triggered) or `:` (activated) |
| sentences | `;` |
| condition | `⊃`, `¬⊃`, `✓ ⊃`, `✗ ⊃` (split at the first) |
| replacement | `⤳` |
| while / as though | `∵`, then `≈` |
| until | `⊣` (an event, or a time like `▷◷●`) |
| coordination | `∨`, then `∧` — a side that has no verb (`∀♞ ∧ ∀◐`, `{R} ∨ {G}`) belongs to the neighbouring argument |
| clause | `[subject] [?] [¬] verb args`, or a verbless `subject change` / comparison |

Inside a clause, phrases bind tightest: quantifier, count, heads, filters, name; a glued characteristic or
relation after a reference (`◈△`, `☞⚑`).

### 13.4 Resolution

`mtglang/resolve.py` fills in what the notation leaves implicit (validator code `S-RESOLVE` when it can't):

- **quantity / number** of every phrase: explicit marks win (`◎` one, `≤n◎` up to, `∀` each, `n` exactly,
  `∃` exists); otherwise a bare phrase is *all* (plural) as a subject in an effect, *one* in a trigger
  event or as an object, *count* under `#`, *kind* inside a filter or keyword; a phrase attached to this
  object (`♞[⚭◈]`) is one; a passive agent (`¬⛉← ♞[△ ≤ 2]`) is all; a predicate type (`☞ ∈ «Mountain»`,
  `¬⚜`) is kind. A phrase no rule covers is an `S-RESOLVE` error. "You" is the player symbol with `op: you`.
- **`☞` antecedent**: the most recent compatible phrase before it in written order (players for `[⚑☞]`,
  `◷☞`, life changes; objects for `☞⚑`, `☞△`, P/T changes, `∋`, verb objects; values for `ⁿ = ☞`). The first
  `☞` in a trigger's effect prefers the event's subject; results of `yields` verbs (`⌕1`, `⤋4`) and `⊻`
  choices (also from other abilities) can be antecedents; a phrase is never "it" in its own clause's
  subject role. Antecedents are `walk` paths.
- **implicit subject** of subject-less actions: `controller`, or `shared` for a later conjunct (`◎♞ +2/+0 ∧
  ∋↟`).

## 14. Languages

Every glossary entry (symbols, names, named effects) carries labels per language:

| Key | Content |
|---|---|
| `en` | English (required) |
| `bg` | Bulgarian, modern spelling, citation form: nouns in the nominative singular, actions in the card imperative (Изтегли, Погуби), events in the third person (встъпва, загива) |
| `bg-ivanchev` | the same in the pre-1945 Ivanchev orthography — generated from `bg` by `mtglang ortho --glossary`, never edited by hand |
| `bg-note` | optional translator's remark (shown in `docs/bg-review.md`) |

The Bulgarian register is late-19th / early-20th-century literary (Вазов): native and folk words over
loanwords (нишан "target", Самодива "dryad", Ламя "hydra", Витяз "knight"), coined terms where Magic needs
them (Мироходец "planeswalker", трайник "permanent", подобие "token"). Star Trek proper names keep their
established Bulgarian forms.

`bg-ivanchev` comes from the offline converter in `mtglang/ortho/` plus the reviewed corrections in
`glossary/ortho_overrides.yaml` (`words`: a word everywhere; `entries`: one label). The gallery's own words
are in `mtglang/ui_strings.yaml`. `check_glossary` warns (`G-LABEL-BG`) once any Bulgarian label exists and
an entry still lacks one.


## 15. Rendering

`mtglang en` and `mtglang eval-en` turn the semantic AST into natural language in two layers:

```
resolved AST ──plan──► clause plans (language-neutral) ──realize(en)──► English
```

### 15.1 Clause plans

`mtglang/planner.py` replaces the sentence- and phrase-level AST nodes with plan nodes
(`mtglang/planir.py`) that hold the decisions every language needs; other phrase-level nodes (filters, zones,
characteristics, P/T …) stay AST nodes with their child phrases converted. A plan holds no word of any
language, and every choice keeps the information behind it, so a realizer may override it.

| Node | Holds |
|---|---|
| `AbilityPlan` | shape (keywords, static, triggered, activated, modal, mode, chapter, threshold, labelled) and its parts; triggered: `once` — the event happens to an object once (enters, dies, is cast: English *When*, Bulgarian perfective *когато встъпи*) |
| `SentencePlan` | clauses and the joins between them (sentence, and, or, if, unless, instead, while, as_though, until, during, for_each, where), or a lead (if_do, if_dont, instead) |
| `ClausePlan` | predicate, subject, role-tagged arguments, optional, negated, passive, mood (imperative to the ability's controller / indicative), tense (`past` for a completed event in a condition: *if you've cast a spell this turn*), aspect of *has* (state in a permanent's static ability / change in an effect), `subject_shared` (same subject as the previous clause) |
| `PhrasePlan` | heads, modifiers (quant, count, filters, name …), number, quantity, definite, ref (new / self / anaphor / you), the full antecedent of an anaphor, person, `pronoun` + `reason`, `self_as` (permanent / card in a hand, graveyard or library / spell) |

### 15.2 Words

English words come from the glossary: each symbol or name may have `lex: {<lang>: {…}}` with keys from
`verb, s, ed, pp, ing, noun, pl, adj, prep, frame, word, short, poss` (`G-LEX` checks them; `frame` may name
argument slots only). Keywords fall back to `oracle`. `G-LEX-EN` warns about corpus symbols with no English
words. Names get `lex.en.short` where Oracle shortens a legendary name in a way no rule derives (*Dr. Crusher*).

### 15.3 Self-reference

A permanent names itself *this <type>* (*this creature*, *this Saga*; subtypes Saga, Aura, Equipment,
Spacecraft, Vehicle win over the card type), a legendary permanent by its short name (before the comma;
planeswalkers by their planeswalker type; or `lex.en.short`), an instant or sorcery by its full name, any
card *this card* in a hand, graveyard or library and *this spell* when cast or when its cost changes, and
*this token* / *this emblem* inside a quoted ability granted to a token or emblem.

### 15.4 Eval

`mtglang eval-en` aligns ability *k* of each face with Oracle line *k* (a modal ability spans its *Choose …*
line and one line per mode) and compares after stripping reminder text, collapsing whitespace and unifying
typographic quotes. Each mismatch has a cause: `renderer`, `gap:<kind>` (a construct the renderer writes as
`⟦kind⟧`), `ast` (the card doesn't parse), `align`, or one from `data/eval-en-accepted.yaml`: `style:<id>`
(a category of Oracle wording no rule derives, with what was tried), `accepted` (a one-off) or a triage
cause (`notation`, `ast`). The notation changes only for differences in meaning, never for English style.
