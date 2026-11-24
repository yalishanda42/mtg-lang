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
