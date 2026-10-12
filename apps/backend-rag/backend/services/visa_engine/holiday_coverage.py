"""When does the loaded national-holiday coverage stop being enough for Visa Oracle?

`processing_times.estimate()` refuses to guess once a working-day walk reaches a year whose
holiday decree is not in `id_holidays`. This module finds the first anchor day on which ANY
product's longest window can no longer be estimated, by walking the real `estimate()` against the
real loaded years: no date here is typed, so loading the next decree moves the answer by itself.

`scripts/visa_holiday_coverage_probe.py` is the CLI over `assess`; the freshness sentinel runs it
under its own bare python3 (these modules are stdlib-only, so no venv is involved).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from backend.services.compliance.business_days import holiday_years_loaded
from backend.services.visa_engine import processing_times

__all__ = ["WARN_WITHIN_DAYS", "assess", "first_unestimable_anchor"]

WARN_WITHIN_DAYS = 60


def _blocked_by(anchor: date, longest: dict[str, int]) -> str | None:
    for code, high in sorted(longest.items(), key=lambda kv: -kv[1]):
        if processing_times.estimate(anchor, (high, high)) is None:
            return code
    return None


def first_unestimable_anchor(today: date) -> tuple[date, str] | None:
    """The first anchor day of the gap that ``today`` is in or ahead of, with the product code that
    fails first. Once ``today`` is already inside the gap the answer stays the day it began (walked
    back to the first loaded year; with no year loaded at all it reads as ``today``), so an alert that
    names the date never slides forward with the clock. None only when the products have no windows."""
    longest: dict[str, int] = {}
    for code, (_, high) in sorted(processing_times.product_windows().items()):
        if high not in longest.values():  # one probe per distinct maximum is enough
            longest[code] = high
    if not longest:
        return None
    loaded = holiday_years_loaded()
    # The walk fails for sure once the anchor year is undecreed, so the scan is bounded.
    last = date(max(loaded, default=today.year - 1) + 1, 1, 1)
    anchor = today
    while anchor <= max(last, today):
        code = _blocked_by(anchor, longest)
        if code is not None:
            return (_gap_start(anchor, code, longest) if anchor == today else (anchor, code))
        anchor += timedelta(days=1)
    return None


def _gap_start(today: date, code: str, longest: dict[str, int]) -> tuple[date, str]:
    """Walk back from a ``today`` already inside the gap to the day it began. The walk stops at the
    first loaded year's 1 January: with nothing estimable before that, the gap has no knowable
    start and ``today`` is the honest answer (no year loaded at all)."""
    loaded = holiday_years_loaded()
    floor = date(min(loaded), 1, 1) if loaded else today
    gap, first = today, code
    while gap > floor:
        before = gap - timedelta(days=1)
        blocked = _blocked_by(before, longest)
        if blocked is None:
            return gap, first
        gap, first = before, blocked
    return today, code


def assess(today: date) -> dict[str, Any]:
    found = first_unestimable_anchor(today)
    if found is None:
        return {"outcome": "UNKNOWN", "today": today.isoformat(), "reason": "no product windows"}
    gap, code = found
    days_left = (gap - today).days
    if days_left <= 0:
        outcome = "STALE"
    elif days_left <= WARN_WITHIN_DAYS:
        outcome = "WARN"
    else:
        outcome = "OK"
    year = today.year
    while year in holiday_years_loaded():
        year += 1
    return {
        "outcome": outcome,
        "today": today.isoformat(),
        "first_gap": gap.isoformat(),
        "days_left": days_left,
        "year_to_load": year,
        "product": code,
        "years_loaded": sorted(holiday_years_loaded()),
    }
