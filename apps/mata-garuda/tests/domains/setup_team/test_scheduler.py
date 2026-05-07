"""Bali calendar guard tests (T8).

Anchor: 2026-06-17 IS Galungan, 2026-06-27 IS Kuningan
(per foundations/bali_calendar.py module docstring).
"""
from __future__ import annotations

from datetime import date

from mata_garuda.domains.setup_team.scheduler import (
    should_skip_today,
    sla_deadline_extension_days,
)
from mata_garuda.foundations.bali_calendar import is_galungan, is_kuningan


GALUNGAN_2026 = date(2026, 6, 17)
KUNINGAN_2026 = date(2026, 6, 27)


def test_galungan_anchor_is_correctly_detected():
    """Sanity: foundation reference date is Galungan."""
    assert is_galungan(GALUNGAN_2026)
    assert is_kuningan(KUNINGAN_2026)


def test_should_skip_today_on_galungan_itself():
    skip, reason = should_skip_today(GALUNGAN_2026)
    assert skip is True
    assert "Galungan" in reason
    assert "today" in reason


def test_should_skip_today_on_galungan_minus_1():
    """Day before Galungan — owner availability ~0."""
    yesterday_of_galungan = GALUNGAN_2026.replace(day=16)
    skip, reason = should_skip_today(yesterday_of_galungan)
    assert skip is True
    assert "Galungan" in reason
    assert "tomorrow" in reason


def test_should_skip_today_on_galungan_plus_1():
    day_after = GALUNGAN_2026.replace(day=18)
    skip, reason = should_skip_today(day_after)
    assert skip is True
    assert "Galungan" in reason
    assert "yesterday" in reason


def test_should_skip_today_on_kuningan():
    skip, reason = should_skip_today(KUNINGAN_2026)
    assert skip is True
    assert "Kuningan" in reason


def test_should_skip_today_normal_day():
    """A wuku day far from any ceremony."""
    quiet = date(2026, 5, 10)
    # Sanity check
    assert not is_galungan(quiet) and not is_kuningan(quiet)
    skip, reason = should_skip_today(quiet)
    assert skip is False
    assert reason == ""


def test_should_skip_today_default_argument_uses_today():
    """Smoke test that default-argument path doesn't crash."""
    skip, reason = should_skip_today()
    assert isinstance(skip, bool)
    assert isinstance(reason, str)


def test_sla_extension_when_galungan_within_14_days():
    """On 2026-06-10, Galungan 2026-06-17 is 7 days away → +3 days."""
    target = date(2026, 6, 10)
    assert sla_deadline_extension_days(target) == 3


def test_sla_extension_when_kuningan_within_14_days():
    target = date(2026, 6, 14)
    # Kuningan 2026-06-27 is 13 days away → +3 days
    assert sla_deadline_extension_days(target) == 3


def test_sla_extension_zero_when_no_ceremony_in_window():
    """A date far from any Pawukon ceremony."""
    target = date(2026, 5, 1)
    # Galungan 2026-06-17 is 47 days away — outside 14-day window
    assert sla_deadline_extension_days(target) == 0
