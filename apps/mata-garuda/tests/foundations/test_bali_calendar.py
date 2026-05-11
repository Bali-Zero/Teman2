from datetime import date
from mata_garuda.foundations.bali_calendar import (
    get_balinese_date,
    is_galungan,
    is_kuningan,
    days_until_next_galungan,
)


def test_galungan_2026_06_17():
    """R6 source-of-truth: Galungan = Wed 2026-06-17."""
    assert is_galungan(date(2026, 6, 17)) is True


def test_kuningan_2026_06_27():
    """R6 source-of-truth: Kuningan = Sat 2026-06-27."""
    assert is_kuningan(date(2026, 6, 27)) is True


def test_non_ceremony_day_returns_false():
    assert is_galungan(date(2026, 5, 8)) is False
    assert is_kuningan(date(2026, 5, 8)) is False


def test_get_balinese_date_returns_wuku_and_pawukon_day():
    result = get_balinese_date(date(2026, 6, 17))
    assert result.wuku == "Dunggulan"
    assert result.is_galungan is True
    assert result.is_kuningan is False


def test_days_until_next_galungan_from_2026_05_08():
    """40 days from 2026-05-08 to 2026-06-17."""
    delta = days_until_next_galungan(date(2026, 5, 8))
    assert delta == 40


def test_days_until_next_galungan_after_event_returns_next_cycle():
    """From 2026-06-18 (day after), next Galungan = 2027-01-13 (210 days later)."""
    delta = days_until_next_galungan(date(2026, 6, 18))
    assert delta == 210 - 1  # 209 days
