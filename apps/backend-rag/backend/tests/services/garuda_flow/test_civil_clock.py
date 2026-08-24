"""Tests for the GARUDA VOA civil-day clock anchor.

The engine has no timezone anchor unless this module supplies one; a
UTC-container "today" and the Bali civil "today" disagree for the first
eight hours of every Bali day. These tests freeze the instant so the
assertion is against a deterministic Asia/Makassar (WITA, UTC+8) civil date,
never the real wall clock.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from backend.services.garuda_flow import civil_clock


class _FrozenDatetime(datetime):
    """datetime subclass whose ``now()`` returns a fixed UTC instant."""

    _frozen_utc: datetime

    @classmethod
    def now(cls, tz=None):  # noqa: D102 - trivial override
        instant = cls._frozen_utc
        if tz is not None:
            return instant.astimezone(tz)
        return instant


def _freeze(monkeypatch: pytest.MonkeyPatch, utc_instant: datetime) -> None:
    frozen = type("_Frozen", (_FrozenDatetime,), {"_frozen_utc": utc_instant})
    monkeypatch.setattr(civil_clock, "datetime", frozen)


def test_garuda_today_returns_wita_date_when_ahead_of_utc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """16:00-23:59 UTC is already the NEXT civil day in WITA (UTC+8).

    This is the failure mode a bare ``date.today()``/UTC-date reading gets
    wrong for the first eight hours of every Bali day: this test must FAIL
    against that semantics, not just pass regardless of the fix.
    """
    utc_instant = datetime(2026, 8, 24, 18, 0, tzinfo=timezone.utc)
    _freeze(monkeypatch, utc_instant)

    result = civil_clock.garuda_today()

    assert result == date(2026, 8, 25)
    assert result != utc_instant.date()


def test_garuda_today_matches_utc_date_when_hours_align(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Symmetric case: an instant where UTC and WITA agree on the civil day.

    Guards against a fix that always adds a day regardless of the hour.
    """
    utc_instant = datetime(2026, 8, 24, 3, 0, tzinfo=timezone.utc)
    _freeze(monkeypatch, utc_instant)

    result = civil_clock.garuda_today()

    assert result == date(2026, 8, 24)
    assert result == utc_instant.date()


def test_civil_timezone_is_pinned_to_asia_makassar_not_jakarta() -> None:
    """Pin the identifier itself so a future WIB/WITA mixup fails loudly.

    Asia/Jakarta is WIB (UTC+7) — the wrong zone for a Bali/Ngurah Rai
    deadline; only Asia/Makassar (WITA, UTC+8) is correct here.
    """
    assert civil_clock.GARUDA_CIVIL_TIMEZONE.key == "Asia/Makassar"
    assert civil_clock.GARUDA_CIVIL_TIMEZONE.key != "Asia/Jakarta"
