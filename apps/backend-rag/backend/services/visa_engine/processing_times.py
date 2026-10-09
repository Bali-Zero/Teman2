"""Bali Zero's typical processing time per product, as Indonesian working days.

The window comes from a committed snapshot of the production catalogue so the engine stays
deterministic. A completion estimate walks Indonesian working days after the anchor and refuses to
guess when the walk touches a year whose national holiday table is not decreed.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from backend.services.compliance.business_days import holiday_years_loaded, is_business_day

_SNAPSHOT = Path(__file__).resolve().parents[2] / "data" / "bali_zero_processing_times_2026.json"
# A real window is at most weeks; the cap only stops a corrupt snapshot from walking forever.
_MAX_WINDOW_DAYS = 120

__all__ = ["estimate", "typical_window"]


@lru_cache(maxsize=1)
def _windows() -> dict[str, tuple[int, int]]:
    raw = json.loads(_SNAPSHOT.read_text(encoding="utf-8"))
    windows: dict[str, tuple[int, int]] = {}
    for code, row in raw["products"].items():
        low, high = row["min"], row["max"]
        if not (0 <= low <= high <= _MAX_WINDOW_DAYS):
            raise ValueError(f"processing window for {code} is out of range: {low}-{high}")
        windows[code] = (low, high)
    return windows


def typical_window(product_code: str) -> tuple[int, int] | None:
    return _windows().get(product_code)


def _nth_working_day_after(anchor: date, count: int) -> date | None:
    loaded = holiday_years_loaded()
    if anchor.year not in loaded:
        return None
    day = anchor
    remaining = count
    while remaining > 0:
        day += timedelta(days=1)
        if day.year not in loaded:
            return None
        if is_business_day(day):
            remaining -= 1
    return day


def estimate(anchor: date, window: tuple[int, int]) -> tuple[date, date] | None:
    low = _nth_working_day_after(anchor, window[0])
    high = _nth_working_day_after(anchor, window[1])
    if low is None or high is None:
        return None
    return low, high
