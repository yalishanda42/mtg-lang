"""Modern Bulgarian → Ivanchev (pre-1945) spelling.

A dependency-free port of the converter behind https://pravopis.osvedomitel.bg/ — Peshowe/converter-web-app
(``converter/converter.py`` and ``process_vocabs.py``), © 2021 Petar Nedelev, MIT License; word lists vendored in
``mtglang/ortho/data`` (see its README). Differences from upstream:

- no nltk: a regex tokenizer over Cyrillic words (hyphenated words stay one token), everything else untouched;
- no BERT tagger: ``-те`` verb/noun homographs take the non-verb reading (upstream's behaviour without weights);
- no frequency cache (speed only);
- ``override`` pairs (lowercase modern → old) are applied per word before the rules;
- words already in old spelling (containing ѣ / ѫ, or ending in ъ / ь) are left as they are, so conversion is
  idempotent;
- the second-vowel ѫ roots (гълъб, жълъд) use an offset from the root, not an absolute index (upstream bug).
"""
from __future__ import annotations

import re
from functools import lru_cache

from mtglang.ortho import data_path

_WORD = re.compile(r"[А-Яа-яЀ-ӿ]+(?:-[А-Яа-яЀ-ӿ]+)*")

CONS = set("бвгджзклмнпрстфхцчшщ")
VOWELS = set("аъоуеиѣѫ")
NO_SUCCEEDING_YAT = VOWELS | set("чшжгкх")
EXPANDED_VS = {"във", "със"}
US_HOMOGRAPHS = {"кът", "път", "прът", "имамбаялдъ"}
US_SECOND_VOWEL = {"гълъб", "жълъд"}
YAT_FULL_EXCLUSIONS = {"сте", "вещ", "лев", "лева", "свет", "нея", "бей", "бея", "беят"}
YAT_FULL_WORDS = {"ляв", "лява", "лявата", "бях", "бяха", "бяхме", "вежда", "вежди", "веждата", "веждитѣ", "де", "бе",
                  "дето", "утре", "таме", "тем", "тям", "нема", "немат", "дека"}
YAT_DOUBLE_ROOTS = {"бележ", "белез", "белег", "белех", "белел", "беляз", "белял", "белях", "предмет", "донейде",
                    "колене"}
YAT_PREFIXES = {"пре", "две", "ня", "нався", "вер"}
FEMININE_THE_ENDINGS = {"тта", "щта"}
EXCLUSION_WORDS = (("въстава", "възстава"), ("въстан", "възстан"), ("нишк", "нищк"), ("нужни", "нуждни"),
                   ("овошк", "овощк"), ("празник", "праздник"), ("празнич", "празднич"), ("празници", "праздници"),
                   ("сърц", "сърдц"), ("сърчи", "сърдчи"), ("отсѫств", "отсѫтств"), ("карадайъ", "карадаѭ"),
                   ("йълдъз", "ѭлдъз"))
US_NOT_EXCL = {"откъсн"}
NO_YAT_VERBS = {"клех", "взех", "клях", "взях"}


def _read(name: str) -> list[str]:
    return [w.strip() for w in data_path(name).read_text(encoding="utf-8").splitlines() if w.strip()]


@lru_cache(maxsize=1)
def _vocab() -> dict:
    nouns_in_te = set(_read("nouns_in_te"))
    verbs_te = set(_read("verbs-te"))
    homonyms_te = {w for w in _read("verbs_only_homonyms") if w.endswith("те")}
    masc = set(_read("masculine_soft_ending"))
    fem = set(_read("feminine_soft_ending"))
    return {
        "verbs_te": verbs_te,
        "homonyms_te": homonyms_te,
        "yat_not_te": (nouns_in_te | verbs_te) - homonyms_te,
        "soft_masc": masc,
        "soft_fem": fem,
        "soft": masc | fem,
        # longest roots first so a containing root wins deterministically (upstream iterates a set)
        "yat_roots": sorted(set(_read("yatRoots")), key=lambda r: (-len(r), r)),
        "yat_excl": set(_read("yatExclusions")),
        "us_roots": sorted(set(_read("usRoots")), key=lambda r: (-len(r), r)),
        "us_excl": set(_read("usExclusions")),
        "abbreviations": set(_read("abbreviations")),
        "non_yat_prefix_roots": set(_read("nonYatPrefixRoots")),
    }


def _yat_vowel(word: str) -> str:
    """The vowel (е or я) that turns into ѣ: whichever comes first."""
    ie = word.find("е")
    iya = word.find("я")
    if iya == -1:
        return "е"
    if ie == -1:
        return "я"
    return "е" if iya > ie else "я"


def _place_yat(word: str, current: str) -> str:
    """Copy every ѣ position of ``current`` into ``word`` (they share a prefix)."""
    out = list(word)
    for k, ch in enumerate(current):
        if ch == "ѣ" and k < len(out):
            out[k] = "ѣ"
    return "".join(out)


def _ending(word: str, cur: str, v: dict) -> str:
    if cur[-1] not in CONS:
        return word
    if cur in v["abbreviations"]:
        return word
    if cur in EXPANDED_VS:
        return word[:1] + "ъ"
    if cur in v["soft"]:
        return word + "ь"
    if cur[-2:] == "ят" and cur[:-2] in v["soft_masc"]:
        return word[:-2] + "ьтъ"
    return word + "ъ"


def _us(word: str, cur: str, v: dict) -> str:
    if cur == "са":
        return "сѫ"
    if "ъ" not in cur:
        return word
    if any(x in cur for x in v["us_excl"]) and not any(x in cur for x in US_NOT_EXCL):
        return word
    if cur in US_HOMOGRAPHS:
        return word.replace("ъ", "ѫ", 1)
    for root in v["us_roots"]:
        if root in word:
            idx = cur.index(root) if root in cur else word.index(root)
            if root in US_SECOND_VOWEL:
                idx += 2
            if root in US_HOMOGRAPHS and cur.endswith(root):
                return word
            word = word[:idx] + word[idx:].replace("ъ", "ѫ", 1)
    return word


def _yat(word: str, cur: str, v: dict) -> str:
    if "е" not in cur and "я" not in cur:
        return word
    if cur in YAT_FULL_EXCLUSIONS:
        return word
    if cur[-2:] == "те" and cur not in v["yat_not_te"]:
        cur = cur[:-1] + "ѣ"
    if cur in YAT_FULL_WORDS:
        cur = cur.replace(_yat_vowel(cur), "ѣ", 1)
        return _place_yat(word, cur)
    # past tense endings
    if cur[-4:] in {"яхме", "ехме", "яхте", "ехте"} and len(cur) >= 5 and cur[-5] not in NO_SUCCEEDING_YAT:
        if len(cur) == 5 or cur[-6:-2] not in NO_YAT_VERBS:
            cur = cur[:-4] + "ѣ" + cur[-3:]
    elif cur[-3:] in {"яха", "еха", "еше"} and len(cur) >= 4 and cur[-4] not in NO_SUCCEEDING_YAT:
        if len(cur) == 4 or cur[-5:-1] not in NO_YAT_VERBS:
            cur = cur[:-3] + "ѣ" + cur[-2:]
    elif cur[-2:] in {"ех", "ях"} and len(cur) >= 3 and cur[-3] not in NO_SUCCEEDING_YAT:
        if len(cur) == 3 or cur[-4:] not in NO_YAT_VERBS:
            cur = cur[:-2] + "ѣ" + cur[-1]
    # prefixes with ѣ
    if not any(x in cur for x in v["non_yat_prefix_roots"]):
        for prefix in sorted(YAT_PREFIXES, key=len, reverse=True):
            if cur.startswith(prefix):
                cur = cur.replace(_yat_vowel(prefix), "ѣ", 1)
                break
    # roots with two ѣ
    for root in sorted(YAT_DOUBLE_ROOTS):
        if root in cur:
            idx = cur.index(root)
            first = _yat_vowel(root)
            second = _yat_vowel(root.replace(first, "X", 1))
            cur = cur[:idx] + cur[idx:].replace(first, "ѣ", 1).replace(second, "ѣ", 1)
            return _place_yat(word, cur)
    if any(x in cur for x in v["yat_excl"]):
        return _place_yat(word, cur)
    for root in v["yat_roots"]:
        if root in cur:
            if root == "дете" and cur in v["verbs_te"]:
                continue
            if root == "лев" and "делев" in cur:
                continue
            idx = cur.index(root)
            cur = cur[:idx] + cur[idx:].replace(_yat_vowel(root), "ѣ", 1)
            return _place_yat(word, cur)
    return _place_yat(word, cur)


def _feminine_the(word: str, cur: str, v: dict) -> str:
    if any(cur.endswith(x) for x in FEMININE_THE_ENDINGS):
        return word[:-2] + "ь" + word[-2:]
    if cur.endswith("та") and cur[:-2] in v["soft_fem"]:
        return word[:-2] + "ьта"
    return word


def _exclusions(word: str) -> str:
    for old, new in EXCLUSION_WORDS:
        if old in word:
            return word.replace(old, new, 1)
    return word


def _already_old(cur: str) -> bool:
    return "ѣ" in cur or "ѫ" in cur or (len(cur) > 1 and cur[-1] in "ъь" and cur[-2] in CONS)


def convert_word(word: str) -> str:
    """Convert one lowercase word (hyphenated parts are one word, as upstream)."""
    v = _vocab()
    cur = word
    if _already_old(cur):
        return word
    if len(cur) == 1 and cur not in {"с", "в"}:
        return word
    word = _ending(word, cur, v)
    word = _us(word, cur, v)
    word = _yat(word, cur, v)
    word = _feminine_the(word, cur, v)
    return _exclusions(word)


def _keep_case(orig: str, new: str) -> str:
    if orig.islower():
        return new
    if orig.isupper() and len(orig) > 1:
        return new.upper()
    if orig[:1].isupper() and orig[1:].islower():
        return new[:1].upper() + new[1:]
    if orig.isupper():
        return new[:1].upper() + new[1:]
    return new


def to_ivanchev(text: str, override: dict[str, str] | None = None) -> str:
    """Convert modern-spelling Bulgarian text; non-Cyrillic text passes through unchanged."""
    override = override or {}

    def sub(m: re.Match) -> str:
        w = m.group()
        low = w.lower()
        if w.isupper() and len(w) > 1 and not any(c in VOWELS | {"я", "ю", "и", "е"} for c in low):
            return w                      # an abbreviation in capitals
        new = override.get(low)
        if new is None:
            new = convert_word(low)
        return _keep_case(w, new)

    return _WORD.sub(sub, text)


def word_accuracy(modern: str, original: str) -> float:
    """Share of words where ``to_ivanchev(modern)`` matches ``original`` (same word count expected)."""
    got = _WORD.findall(to_ivanchev(modern))
    want = _WORD.findall(original)
    if not want:
        return 1.0
    return sum(1 for a, b in zip(got, want) if a.lower() == b.lower()) / max(len(got), len(want))
