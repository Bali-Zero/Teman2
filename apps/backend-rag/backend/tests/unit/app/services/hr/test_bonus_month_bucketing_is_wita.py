"""Tripwire: every bonus month/year bucket must be cut on WITA, not UTC.

Bali Zero operates on WITA (UTC+8) and the Fly Postgres session is UTC, so a
bare ``EXTRACT(MONTH FROM awarded_at)`` cuts the month at 08:00 WITA: a bonus
awarded at 00:30 on the 1st is billed to the PREVIOUS month. Live prod data
already contains such rows.

Four call sites bucket bonuses by month — ``list_bonuses``, ``get_bonus_summary``,
``calculate_payroll`` and ``get_my_dashboard``. If any one of them drifts back to
UTC, payroll and the /hr/bonuses accounting view stop agreeing about which month
a bonus belongs to, and someone is paid the wrong amount. Curing one site is not
enough — this test is the class-audit made permanent.
"""

from __future__ import annotations

import re
from pathlib import Path

from backend.app.services.hr import hr_service as hr_service_module
from backend.app.services.hr.hr_service import BUSINESS_TZ, business_today

_RAW_SOURCE = Path(hr_service_module.__file__).read_text(encoding="utf-8")

# Adjacent Python string literals concatenate, so a single SQL clause can be
# split across lines mid-expression. Rejoin those seams (`"` newline `f"`) so
# the scan below sees the SQL the way Postgres will, not the way it is typed.
SOURCE = re.sub(r'"\s*f?"', " ", _RAW_SOURCE)

# `EXTRACT(<field> FROM ...awarded_at...)` — captures whatever sits between
# EXTRACT( and the matching close, so the timezone cast is visible or absent.
_EXTRACT_OVER_AWARDED_AT = re.compile(
    r"EXTRACT\(\s*(MONTH|YEAR)\s+FROM\s+([^)]*awarded_at[^)]*\)?)",
    re.IGNORECASE,
)


def test_business_tz_is_wita():
    assert BUSINESS_TZ == "Asia/Makassar"


def test_every_extract_over_awarded_at_converts_to_wita():
    matches = _EXTRACT_OVER_AWARDED_AT.findall(SOURCE)
    # Guard against the regex silently matching nothing (a blind-scan pass is
    # not the same as a clean one).
    assert len(matches) >= 4, (
        f"expected at least 4 month/year buckets over awarded_at, found {len(matches)} — "
        "did the queries move, or did the regex stop matching?"
    )
    offenders = [
        f"EXTRACT({field} FROM {expr}"
        for field, expr in matches
        if BUSINESS_TZ not in expr
    ]
    assert not offenders, (
        "bonus month/year buckets must convert to WITA before extracting — "
        f"UTC-bucketing found in: {offenders}"
    )


def test_no_bare_extract_month_from_awarded_at_remains():
    """The exact pre-fix shape must never come back."""
    assert not re.search(
        r"EXTRACT\(\s*(MONTH|YEAR)\s+FROM\s+(bl\.)?awarded_at\s*\)",
        SOURCE,
        re.IGNORECASE,
    )


def test_business_today_is_ahead_of_utc_date_at_the_boundary():
    """WITA is UTC+8, so the business date rolls over 8 hours before UTC's."""
    from datetime import date, datetime, timezone
    from unittest.mock import patch

    # 2026-02-28 16:30Z == 2026-03-01 00:30 WITA → the business day is March 1.
    frozen = datetime(2026, 2, 28, 16, 30, tzinfo=timezone.utc)

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen if tz else frozen.replace(tzinfo=None)

    with patch.object(hr_service_module, "datetime", _FrozenDatetime):
        assert business_today() == date(2026, 3, 1)
