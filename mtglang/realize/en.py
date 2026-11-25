"""English realizer: clause plans → Oracle-style English."""
from __future__ import annotations

from mtglang.lexicon import Lexicon
from mtglang.planir import CardContext

# subtypes a card names itself by ("this Saga"); otherwise the card type decides ("this creature")
SELF_SUBTYPES = ("Saga", "Aura", "Equipment", "Spacecraft", "Vehicle")
SELF_TYPES = ("Creature", "Land", "Artifact", "Enchantment", "Planeswalker", "Battle")


def _type_noun(lex: Lexicon, index: int) -> str:
    return lex.sym(index).get("noun") or lex.g.symbols[index].labels["en"].lower()


def self_phrase(ctx: CardContext, lex: Lexicon, as_: str = "permanent", in_token: bool = False) -> str:
    """How the card names itself: its (short) name if legendary, else "this <type>"; "this card" / "this
    spell" when it is a card in a zone or a spell; "this token" inside an ability granted to a token."""
    if in_token:
        return "this token"
    if as_ == "card":
        return "this card"
    if as_ == "spell" or ctx.is_spell:
        return "this spell"
    if ctx.legendary:
        return ctx.short
    for sub in SELF_SUBTYPES:
        if sub in ctx.subtype_keys:
            return f"this {sub}"
    labels = {lex.g.symbols[i].labels["en"]: i for i in ctx.type_syms}
    for t in SELF_TYPES:
        if t in labels:
            return f"this {_type_noun(lex, labels[t])}"
    return "this permanent"
