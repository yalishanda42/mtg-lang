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


def test_each_part_of_a_compound_gets_its_ending():
    assert to_ivanchev("Плащ-невидимка") == "Плащъ-невидимка"
    assert to_ivanchev("сам-самичък един-два") == "самъ-самичъкъ единъ-два"


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


def test_inner_capitals_kept():
    assert to_ivanchev("Ел-Ауриец") == "Елъ-Ауриецъ"


def test_soft_agent_and_abstract_nouns():
    assert to_ivanchev("учител присадителят лютост лютостта") == "учитель присадительтъ лютость лютостьта"
    assert to_ivanchev("хвост мост прост") == "хвостъ мостъ простъ"     # short words keep the hard ending


def test_inner_capitals_kept_when_a_letter_is_inserted():
    assert to_ivanchev("Сърце-Камък") == "Сърдце-Камъкъ"
    assert to_ivanchev("Отсъствие-Ад") == "Отсѫтствие-Адъ"


def test_accuracy_on_upstream_paired_texts():
    """Spec §5: modern text vs the original pre-reform text. Measured 2026-11-25 with per-part compound endings."""
    for n in (1, 2):
        acc = word_accuracy((FX / f"text{n}.txt").read_text(encoding="utf-8"),
                            (FX / f"conv{n}.txt").read_text(encoding="utf-8"))
        assert acc >= 0.96, (n, acc)
