"""Ivanchev spelling converter (port of pravopis.osvedomitel.bg's engine)."""
from pathlib import Path
from statistics import mean

from mtglang.ortho.ivanchev import to_ivanchev, word_accuracy

FX = Path(__file__).parent / "fixtures" / "ortho"


def test_final_yer():
    assert to_ivanchev("Почиват яростни вълни") == "Почиватъ яростни вълни"


def test_yat_and_yus():
    assert to_ivanchev("И някога за път обратен") == "И нѣкога за пѫть обратенъ"


def test_sa_and_plural_article():
    assert to_ivanchev("те са") == "тѣ сѫ"


def test_soft_feminine():
    assert to_ivanchev("радост и твар") == "радость и тварь"


def test_case_kept():
    assert to_ivanchev("ПЪТ Път път") == "ПѪТЬ Пѫть пѫть"


def test_punctuation_and_symbols_kept():
    assert to_ivanchev("«Аджани» — път, {G}!") == "«Аджани» — пѫть, {G}!"


def test_idempotent():
    once = to_ivanchev("за път обратен, вятър")
    assert to_ivanchev(once) == once


def test_override_wins():
    assert to_ivanchev("Крилатост", {"крилатост": "крилатость"}) == "Крилатость"


def test_latin_digits_untouched():
    assert to_ivanchev("X 2 ABC") == "X 2 ABC"


def test_hyphenated_word_is_one_token():
    assert to_ivanchev("От заник-слънце озарени") == "Отъ заник-слънце озарени"


def _pairs():
    for n in (1, 2, 3):
        mod = (FX / f"owords{n}.txt").read_text(encoding="utf-8").split()
        old = (FX / f"cwords{n}.txt").read_text(encoding="utf-8").split()
        yield " ".join(mod), " ".join(old)


def test_accuracy_on_upstream_word_lists():
    """Measured 2026-11-25: see ACCURACY. Fails if a change makes it worse by more than 2 points."""
    acc = mean(word_accuracy(m, o) for m, o in _pairs())
    assert acc >= ACCURACY - 0.02, acc


ACCURACY = 0.986  # 2026-11-25: owords1 100%, owords2 99.9%, owords3 95.9% (already-old inputs) — mean 0.986
