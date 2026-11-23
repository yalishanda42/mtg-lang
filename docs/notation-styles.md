# Notation style proposals (milestone 1)

Decision (2026-11-23): **Symbol-heavy**. Keywords get glyphs too; every glyph keeps a short ASCII alias for plain-text use. Glyphs below may be refined during sample review.

This doc shows the same 12 cards (from `docs/sample-cards.txt`) written in three styles. All three
share **one grammar**. They differ only in which marks the vocabulary uses. That's why the choice
is cheap to revise later: the vocabulary lives in `glossary/symbols.yaml`, not in code.

## Shared grammar (all styles)

| Shape | Form | Example (Mixed style) |
|---|---|---|
| keyword line | `K, K, K` | `F, V, LL, Wd{2}` |
| triggered | `event ⇒ effect` | `◈↥ ⇒ ● ♥+1` |
| intervening "if" | `event ∧ condition ⇒ effect` | `◈↥ ∧ #⛰[⚑●] ≥ 6 ⇒ …` |
| activated | `cost : effect` | `{T} : ⊕ {U} ∨ {R}` |
| static | statement | `⚙♞[⚑●] ∋ F` |
| ability word / mode name | `label ▸ ability` | `Lf ▸ ⛰[⚑●]↥ ⇒ …` |
| modal | `⊻1` line, then `• mode` lines | `• ◎♞ +2/+0 ⏳` |
| saga chapter | `§n ▸ effect` | `§2 ▸ ● ♥+3` |
| station threshold | `n+ \| ability` | `12+ \| ⚙♞[⚑●] ∋ F` |
| filter | `object[conditions]` (Scryfall-style conjunction) | `♞[⚑● ≠◈]` = "another creature you control" |
| sequence | `;` between sentences | `✖ ◎▣[⚑○] ; ☞⚑ ✚ «Treasure»` |
| granted ability | `∋ ( ability )` | `∋ ({T}, ✝◈ : ⊕ 3◆)` |
| variable | `X ≔ …` | `X ≔ #⊤ ♞[⚑● ¬«Borg»]` |
| proper name | `«…»` | `«Human»`, `«Porthos»` |
| one-off effect | `⟨…⟩` | (none needed in these 12) |
| card faces | a line `//` | prepare cards |

**Flavor words** (mode names like *Hail*, *Kill*, *Temba, His Arms Wide*) have no rules meaning but are printed on the card, so they are written as proper-name labels: `• «Hail» ▸ …`.
**Ability words** (*Landfall*, *Threshold*, *Federation*) also have no rules meaning, but they recur across many cards, so they get codes or glyphs.

## Core vocabulary: Mixed and Symbol-heavy share this

| Glyph | ASCII | Meaning | | Glyph | ASCII | Meaning |
|---|---|---|---|---|---|---|
| `◈` | `@` | this object | | `▤` | `Lb` | library |
| `☞` | `$` | that object (just mentioned) | | `✋` | `Hd` | hand |
| `●` | `Yu` | you | | `▦` | `Bf` | battlefield |
| `○` | `Op` | an opponent | | `⚰` | `Gy` | graveyard |
| `∀` | `Al` | each / all | | `⊘` | `Xl` | exile |
| `◎` | `Tg` | target | | `→` | `~>` | put into / deal to |
| `≤1◎` | `<=1Tg` | up to one target | | `↥` | `^` | enters |
| `?` | `?` | may | | `➹` | `At` | attacks |
| `≠◈` | `!=@` | another / other | | `↷` | `Tp` | tap / tapped |
| `⚑` | `Ct` | controller / you control | | `▶` | `Pl` | play (a land) |
| `⌂` | `Ow` | owner / you own | | `⤓` | `Dr` | draw |
| `⏳` | `Ue` | until end of turn | | `✖` | `Ds` | destroy |
| `◷` | `Tn` | turn (`◷` this turn, `◷●` your turn) | | `✝` | `Sc` | sacrifice |
| `≡✎` | `==So` | only as a sorcery | | `⊕` | `Ad` | add mana |
| `≤1◷` | `<=1Tn` | only once each turn | | `✸` | `Dm` | damage |
| `⊃` | `if` | if … then | | `♥` | `<3` | life (`♥+2` gain, `♥-2` lose) |
| `∵` | `wl` | as long as | | `✚` | `Mk` | create (token) |
| `✓` / `✗` | `ok` / `no` | if you do / if you can't | | `⊞` | `Co` | counter (`⊞+1/+1`, `⊞◇`) |
| `∧ ∨ ¬` | `& or ~` | and, or, non- | | `∋` | `Hs` | has / gains |
| `∈` | `in` | is a | | `#` | `#` | number of |
| `≔` | `:=` | where X is | | `⊻` | `Ch` | choose (`⊻1` choose one) |
| `⊤` | `Ty` | (creature) types among | | `✪` | `Em` | emblem |
| `♦` | `c.` | color (`♦G` green, `♦∅` colorless) | | `◆` | `Am` | mana of any one color |
| `◇` | `Lo` | loyalty | | `⛨` | `De` | defense |

Card types: `♞` creature (`Cr`), `⚙` artifact (`Ar`), `✧` enchantment (`Nc`), `⛰` land (`Ld`), `⚝` planeswalker (`Wk`), `ϟ` instant (`In`), `✎` sorcery (`So`), `⚜` legendary (`Lg`), `⊡` basic (`Bs`), `◌` token (`Tk`), `▭` card (`Cd`), `▣` permanent (`Pm`).

## Keyword marks per style

| Keyword | Mixed | Symbol-heavy | Letter-code |
|---|---|---|---|
| Flying | `F` | `✈` | `F` |
| Vigilance | `V` | `⊙` | `V` |
| Lifelink | `LL` | `♡` | `LL` |
| Ward | `Wd` | `⊠` | `Wd` |
| Reach | `Rh` | `⇞` | `Rh` |
| Deathtouch | `DT` | `☣` | `DT` |
| First strike | `FS` | `↟` | `FS` |
| Mill | `Mi` | `⤋` | `Mi` |
| Fight | `Fi` | `⚔` | `Fi` |
| Explore | `Xp` | `⌖` | `Xp` |
| Affinity | `Af` | `⊜` | `Af` |
| Assimilate | `As` | `⊛` | `As` |
| Station | `St` | `⚓` | `St` |
| Prepared | `Pr` | `⧉` | `Pr` |
| Threshold (ability word) | `Th` | `⚱` | `Th` |
| Landfall (ability word) | `Lf` | `⛶` | `Lf` |
| Federation (ability word) | `Fd` | `☍` | `Fd` |

**Letter-code style** also replaces the *core* glyphs with codes:

| Meaning | Code |
|---|---|
| this | `Sf` |
| that | `Rf` |
| you | `Yu` |
| opponent | `Op` |
| each | `Ea` |
| target | `Tg` |
| up to | `Up` |
| may | `My` |
| another | `An` |
| enters | `ET` |
| attacks | `At` |
| move to | `Mv` |
| is a | `Is` |
| has | `Hs` |
| life | `Lp` |
| until end of turn | `Ue` |
| this turn | `Tn` |
| sorcery-speed | `AS` |
| once per turn | `Ot` |
| if | `If` |
| as long as | `Wl` |
| number of | `Nb` |
| choose | `Ch` |

Structure marks (`=> : |> * % ; << >>`) and the type and zone codes from the core table stay the same.

## The 12 cards

Each card shows Oracle text first, then the **Mixed (M)**, **Symbol-heavy (S)** and **Letter-code (L)** versions. Then comes the ASCII form. S and M share it, since S keyword glyphs alias to the M codes. L is already ASCII.

### 1. Forest (basic land, no rules text)
```
Oracle: Basic Land — Forest
M/S:    «Forest»
        ⊡⛰ — «Forest»
L:      <<Forest>>
        Bs Ld — <<Forest>>
ASCII:  <<Forest>> / Bs Ld — <<Forest>>
```

### 2. Andoria (enters tapped, trigger, mana ability)
```
Oracle: This land enters tapped.
        When this land enters, you gain 1 life.
        {T}: Add {U} or {R}.
M/S:    ◈ ↥↷
        ◈↥ ⇒ ● ♥+1
        {T} : ⊕ {U} ∨ {R}
L:      Sf ET Tp
        Sf ET => Yu Lp+1
        {T} : Ad {U} or {R}
ASCII:  @ ^Tp  |  @^ => Yu <3+1  |  {T} : Ad {U} or {R}
```

### 3. Koth, the Geomancer (ability word, self-reference, conditional)
```
Oracle: Reach
        Landfall — Whenever a land you control enters, Koth deals 1 damage to each opponent. If that land is a Mountain, add {R}.
M:      Rh
        Lf ▸ ⛰[⚑●]↥ ⇒ ◈ ✸1 → ∀○ ; ☞ ∈ «Mountain» ⊃ ⊕{R}
S:      ⇞
        ⛶ ▸ ⛰[⚑●]↥ ⇒ ◈ ✸1 → ∀○ ; ☞ ∈ «Mountain» ⊃ ⊕{R}
L:      Rh
        Lf |> Ld[Ct Yu] ET => Sf Dm1 Mv Ea Op ; Rf Is <<Mountain>> If Ad{R}
ASCII:  Lf |> Ld[Ct Yu]^ => @ Dm1 ~> Al Op ; $ in <<Mountain>> if Ad{R}
```

### 4. Vraska, the Cutting Glare (intervening if, target, "they")
```
Oracle: Deathtouch
        When Vraska enters, if you control six or more lands, destroy target permanent an opponent controls. They create a Treasure token.
M:      DT
        ◈↥ ∧ #⛰[⚑●] ≥ 6 ⇒ ✖ ◎▣[⚑○] ; ☞⚑ ✚ «Treasure»
S:      ☣
        (same second line as M)
L:      DT
        Sf ET & Nb Ld[Ct Yu] >= 6 => Ds Tg Pm[Ct Op] ; Rf Ct Mk <<Treasure>>
ASCII:  @^ & #Ld[Ct Yu] >= 6 => Ds TgPm[Ct Op] ; $Ct Mk <<Treasure>>
```

### 5. Kwia Vigorbloom (keyword list, named token with granted ability, once per turn)
```
Oracle: Flying, vigilance, lifelink, ward {2}
        Whenever you gain life, create a colorless artifact token named Lotus with "{T}, Sacrifice this token: Add three mana of any one color." This ability triggers only once each turn.
M:      F, V, LL, Wd{2}
        ● ♥+ ⇒ ✚ ◌[♦∅ ⚙] «Lotus» ∋ ({T}, ✝◈ : ⊕ 3◆) ; ≤1◷
S:      ✈, ⊙, ♡, ⊠{2}
        (same second line as M)
L:      F, V, LL, Wd{2}
        Yu Lp+ => Mk Tk[Cl Ar] <<Lotus>> Hs ({T}, Sc Sf : Ad 3Am) ; Ot
ASCII:  Yu <3+ => Mk Tk[c.Nl Ar] <<Lotus>> Hs ({T}, Sc@ : Ad 3Am) ; <=1Tn
```

### 6. Captain Kathryn Janeway ("may", "another")
```
Oracle: You may play an additional land on each of your turns.
        Whenever Captain Janeway or another creature you control enters, that creature explores.
M:      ● ? ▶⛰ +1 ∀◷●
        (◈ ∨ ♞[⚑● ≠◈])↥ ⇒ ☞ Xp
S:      ● ? ▶⛰ +1 ∀◷●
        (◈ ∨ ♞[⚑● ≠◈])↥ ⇒ ☞ ⌖
L:      Yu My Pl Ld +1 Ea Tn Yu
        (Sf or Cr[Ct Yu An]) ET => Rf Xp
ASCII:  Yu ? PlLd +1 AlTnYu  |  (@ or Cr[Ct Yu !=@])^ => $ Xp
```

### 7. Captain Jonathan Archer (named token, variable X, sorcery-speed)
```
Oracle: When Captain Archer enters, create Porthos, a legendary 1/1 green Dog creature token.
        Federation — {G}, {T}: Target creature you control gets +X/+X until end of turn, where X is the number of creature types among non-Borg creatures you control. Activate only as a sorcery.
M:      ◈↥ ⇒ ✚ ◌[⚜ 1/1 ♦G ♞ «Dog»] «Porthos»
        Fd ▸ {G}, {T} : ◎♞[⚑●] +X/+X ⏳ ; X ≔ #⊤ ♞[⚑● ¬«Borg»] ; ≡✎
S:      (line 1 same) / ☍ ▸ … (rest same as M)
L:      Sf ET => Mk Tk[Lg 1/1 c.G Cr <<Dog>>] <<Porthos>>
        Fd |> {G}, {T} : Tg Cr[Ct Yu] +X/+X Ue ; X := Nb Ty Cr[Ct Yu ~<<Borg>>] ; AS
ASCII:  Fd |> {G}, {T} : TgCr[Ct Yu] +X/+X Ue ; X := #Ty Cr[Ct Yu ~<<Borg>>] ; ==So
```

### 8. Amok Time (saga, "up to one target", fight)
```
Oracle: I — Target creature you control fights up to one target creature an opponent controls.
        II — You gain 3 life.
        III — Return target creature card from your graveyard to your hand.
M:      §1 ▸ ◎♞[⚑●] Fi ≤1◎♞[⚑○]
        §2 ▸ ● ♥+3
        §3 ▸ ◎▭♞[⚰●] → ✋●
S:      §1 ▸ ◎♞[⚑●] ⚔ ≤1◎♞[⚑○]   (rest same)
L:      %1 |> Tg Cr[Ct Yu] Fi Up1 Tg Cr[Ct Op]
        %2 |> Yu Lp+3
        %3 |> Tg Cd Cr[Gy Yu] Mv Hd Yu
```

### 9. Theorix Metamage // Omit Variables (prepare card, threshold, two faces)
```
Oracle: This creature enters prepared.
        Threshold — This creature gets +1/+0 and has flying as long as there are seven or more cards in your graveyard.
        // Omit Variables: Mill three cards.
M:      ◈ ↥Pr
        Th ▸ ◈ +1/+0 ∧ ∋F ∵ #▭[⚰●] ≥ 7
        //
        «Omit Variables» {U/B}
        ✎

        Mi3
S:      ◈ ↥⧉  /  ⚱ ▸ ◈ +1/+0 ∧ ∋✈ ∵ #▭[⚰●] ≥ 7  /  … ⤋3
L:      Sf ET Pr  /  Th |> Sf +1/+0 & Hs F Wl Nb Cd[Gy Yu] >= 7  /  … Mi3
```

### 10. Ajani Resolute (planeswalker, loyalty costs, emblem)
```
Oracle: Whenever you gain life, put a loyalty counter on Ajani.
        0: You gain 1 life.
        −4: Create a 2/2 white Cat Soldier creature token named Ajani's Pridemate with "Whenever you gain life, put a +1/+1 counter on this token."
        −10: You get an emblem with "Creatures you control get +2/+2."
M/S:    «Ajani Resolute» {1}{W}
        ⚜⚝ — «Ajani»
        ◇2

        ● ♥+ ⇒ ⊞◇ → ◈
        0 : ● ♥+1
        −4 : ✚ ◌[2/2 ♦W ♞ «Cat» «Soldier»] «Ajani's Pridemate» ∋ (● ♥+ ⇒ ⊞+1/+1 → ◈)
        −10 : ● ✪ ∋ (♞[⚑●] +2/+2)
L:      Yu Lp+ => Co Lo Mv Sf  /  0 : Yu Lp+1  /  −4 : Mk Tk[2/2 c.W Cr <<Cat>> <<Soldier>>] <<Ajani's Pridemate>> Hs (Yu Lp+ => Co+1/+1 Mv Sf)  /  −10 : Yu Em Hs (Cr[Ct Yu] +2/+2)
```

### 11. Charge the Sanctum (modal spell)
```
Oracle: Choose one —
        • Creatures you control get +2/+0 until end of turn.
        • Target creature gets +2/+0 and gains first strike until end of turn. Put a +1/+1 counter on it.
M:      ⊻1
        • ♞[⚑●] +2/+0 ⏳
        • ◎♞ +2/+0 ∧ ∋FS ⏳ ; ⊞+1/+1 → ☞
S:      (same, with ∋↟)
L:      Ch1  /  * Cr[Ct Yu] +2/+0 Ue  /  * Tg Cr +2/+0 & Hs FS Ue ; Co+1/+1 Mv Rf
```

### 12. Borg Cube (spacecraft, station threshold, "if you can't")
```
Oracle: Affinity for artifact creatures
        Whenever this Spacecraft enters or attacks, assimilate a creature card exiled with it. If you can't, exile up to one target creature.
        Station
        12+ | Artifact creatures you control have flying.
M:      Af[⚙♞]
        (◈↥ ∨ ◈➹) ⇒ As ▭♞[⊘◈] ; ✗ ⊃ ≤1◎♞ → ⊘
        St
        12+ | ⚙♞[⚑●] ∋ F
S:      ⊜[⚙♞]  /  … ⊛ …  /  ⚓  /  12+ | ⚙♞[⚑●] ∋ ✈
L:      Af[Ar Cr]  /  (Sf ET or Sf At) => As Cd Cr[Xl Sf] ; No If Up1 Tg Cr Mv Xl  /  St  /  12+ | Ar Cr[Ct Yu] Hs F
```

## How each strict-fidelity distinction is marked (spec §5.5a)

| Distinction | Mixed / Symbol-heavy | Letter-code |
|---|---|---|
| target vs. non-target vs. each | `◎♞` vs `♞` vs `∀♞` | `Tg` / bare / `Ea` |
| up to N vs. N | `≤N◎` vs `N◎` | `UpN` |
| may vs. mandatory | `?` before the action | `My` |
| you control vs. you own | `[⚑●]` vs `[⌂●]` | `Ct Yu` / `Ow Yu` |
| until end of turn vs. this turn | `⏳` vs `◷` | `Ue` / `Tn` |
| activate only as a sorcery | `≡✎` | `AS` |
| only once each turn | `≤1◷` | `Ot` |
| replacement ("if … would … instead") vs. trigger | `⤳` (replace) vs `⇒` (trigger) — not needed in these 12 | `Rp` vs `=>` |
| enters tapped / with counters | `↥↷`, `↥⊞…` | `ET Tp` |
| intervening "if" vs. effect "if" | `∧` before `⇒` vs. `⊃` inside the effect | `&` vs `If` |
| another / other | `≠◈` | `An` |
| owner vs. controller on zone change | `→▦ ⚑⌂` ("under its owner's control") | `Mv Bf Ct Ow` |
| if you do / if you can't | `✓ ⊃` / `✗ ⊃` | `Ok If` / `No If` |

## Comparison

| | Mixed | Symbol-heavy | Letter-code |
|---|---|---|---|
| Language-free | high: only keyword codes are letters | highest | low: almost every code is an English abbreviation (`Yu`, `Tg`, `Mv`) |
| Learn effort | medium: about 60 glyphs plus keyword codes | high: every keyword is another glyph with no mnemonic | low for English speakers, high for others |
| Glance-readability | good: structure is visual, keywords are short | dense: hard to tell keywords apart | reads like a cipher of English |
| Typing | ASCII form available | ASCII form available | native ASCII |
| Grows with new sets | keyword codes scale easily | needs an ever-larger glyph supply | scales easily |

## Recommendation

**Mixed.** Structure, players, zones and actions are what every card is built from, so those get
glyphs. That's where "language-free" and "readable at a glance" matter most, and Magic players
learn them quickly because they repeat on every card. Keywords number in the hundreds and grow
with every set, so they get short codes (your own `F` for Flying idea). The codes are easier to learn
and type than an endless supply of pictograms, and the legend shows each code's meaning in the
reader's language. Letter-code leaks English everywhere, and Symbol-heavy turns keywords into a
memory test.

Open questions for you, if you want to fine-tune Mixed:
1. Should keyword codes stay English initials (`F`, `FS`, `DT`), or should we use glyphs for the
   ~10 evergreen keywords only (`✈` Flying, `☣` Deathtouch…) and codes for the rest?
2. Any glyph you dislike? For example `♞` for creature, `✎` for sorcery, `ϟ` for instant.
