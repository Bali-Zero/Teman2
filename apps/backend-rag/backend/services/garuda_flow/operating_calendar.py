"""GARUDA VOA — Bali Zero operating calendar (pure, no I/O).

Owner ruling (2026-07-27, Zero): a VOA is issued in a few hours, so the
online issuance funnel may accept a request up to the day BEFORE departure —
counting that Bali Zero's systems are closed on Saturday, Sunday, AND
Indonesian national holidays / cuti bersama (follow-up ruling, same
session). This module is the enforceable calendar behind that ruling: it
tells the intake layer which calendar days Bali Zero's systems are open, and
therefore how many real business days of runway a given arrival date still
has. It does NOT touch the extension path — extensions require an in-person
photo/interview (since 29 May 2025) and carry their own published D-7
Ngurah Rai filing deadline (`safe_clock.py`), untouched by this ruling.

Provenance — NO date is typed in this module. The decreed dates live in
`backend.data.id_holidays` (SKB 3 Menteri No. 1497/2025, 2/2025, 5/2025 —
see that module for the decree text, URLs and the 2026-07-27 corroboration
route), because a second organ now needs the same dates: the compliance
obligations register rolls a statutory tax deadline off a hari libur
(`services.compliance.business_days`, PMK 81/2024). Two readers, one table,
no hand-copied date.

    This module still publishes only the closure set from 2026-07-28
    onward: `OPERATING_CALENDAR` is the shared table CLIPPED to
    [COVERAGE_START, COVERAGE_END], which is byte-for-byte the four days it
    carried before the table moved out (17 Aug, 25 Aug, 24 Dec, 25 Dec
    2026). Clipping is not data loss — `is_open` already fails closed
    outside coverage — it keeps this gate's promise that it cannot certify
    an open day before its materialization boundary. Widening the VOA
    pilot's coverage is a separate decision with its own evidence; it is
    not a side effect of giving the dates a home.

⚠️ COVERAGE_END = 2026-12-31. The 2027 SKB does not exist yet — this decree
class is issued around September of the PRECEDING year (this one was
19 September 2025 for 2026), so the 2027 decree is expected ~September
2026. Any "2027 Indonesian holiday calendar" circulating online ahead of
that is a third-party estimate, NOT a decreed fact — this module carries
ZERO 2027 (or later) dates and never will until a real decree is sourced
and this docstring updated to cite it. `test_no_calendar_date_beyond_coverage_end`
in the test suite pins this so nobody can quietly paste one in later.

PURE functions only — no I/O, no ``date.today()`` anywhere in this module.
The caller always injects ``today`` (or the day being tested); that is what
makes the whole engine deterministic and unit-testable.
"""

from __future__ import annotations

from datetime import date, timedelta

from backend.data.id_holidays import HOLIDAYS, Holiday, HolidayKind

__all__ = [
    "COVERAGE_END",
    "COVERAGE_START",
    "OPERATING_CALENDAR",
    "HolidayKind",
    "OperatingCalendarDate",
    "is_open",
    "last_open_day_before",
]


# This gate's historical name for one decreed closed day. The type moved to
# `backend.data.id_holidays` with the dates it describes; the alias keeps the
# name this module (and `garuda_flow/__init__`) has always exported, with the
# same frozen `at` / `kind` / `name` fields. `HolidayKind` is re-exported from
# the same place for the same reason: both kinds close this gate (the
# conservative reading — see `is_open`), and the tag stays on the data so that
# reading can be revisited without re-sourcing a single date.
OperatingCalendarDate = Holiday

# The source decree spans 2026, but the closure subset this gate publishes
# begins at the pilot's materialization boundary. Coverage describes what THIS
# dataset can actually certify, not what exists in the clipped part.
COVERAGE_START: date = date(2026, 7, 28)
COVERAGE_END: date = date(2026, 12, 31)

# Derived, never typed: a new non-working day is added to the shared decree
# table, and shows up here only if it falls inside the coverage window.
OPERATING_CALENDAR: tuple[OperatingCalendarDate, ...] = tuple(
    holiday for holiday in HOLIDAYS if COVERAGE_START <= holiday.at <= COVERAGE_END
)

_CLOSED_DATES: frozenset[date] = frozenset(d.at for d in OPERATING_CALENDAR)

# Generous bound on how far back `last_open_day_before` will walk before
# concluding "no open day exists". The longest real closed run in
# OPERATING_CALENDAR is 4 consecutive days (Thu 24 Dec - Sun 27 Dec 2026);
# this bound only exists so a future data error (e.g. an entire month
# marked closed) fails loudly instead of looping forever.
_MAX_LOOKBACK_DAYS: int = 60


def is_open(day: date) -> bool:
    """True unless ``day`` is a Saturday, a Sunday, or any decreed calendar
    date — BOTH kinds (`libur_nasional` and `cuti_bersama`): Bali Zero's own
    systems close for cuti bersama too, and treating it as closed is the
    conservative direction here (it can only ever push a computed cutoff
    EARLIER, never later, so it never tells a visitor they have more
    runway than they actually do). The two kinds stay tagged in
    `OPERATING_CALENDAR` precisely so this call can be revisited later
    without re-sourcing a single date.
    """
    if day < COVERAGE_START or day > COVERAGE_END:
        return False
    if day.weekday() >= 5:  # Monday=0 ... Saturday=5, Sunday=6
        return False
    return day not in _CLOSED_DATES


def last_open_day_before(day: date) -> date | None:
    """The latest open day strictly before ``day``.

    Returns ``None`` in two uncovered cases — this function must NEVER
    silently guess a date:

    - ``day`` is at/before `COVERAGE_START` or more than one day after
      `COVERAGE_END`: the first candidate would be outside materialized-data
      coverage, so this returns ``None`` rather than certify an omitted date.
      `COVERAGE_END + 1 day` remains computable because the search is strictly
      before ``day`` and therefore begins on the covered boundary itself.
    - no open day was found within `_MAX_LOOKBACK_DAYS` (defensive only —
      not reachable with the current `OPERATING_CALENDAR` data, whose
      longest closed run is 4 days).

    Pure function of ``day`` alone — no wall-clock read.
    """
    if day <= COVERAGE_START or day > COVERAGE_END + timedelta(days=1):
        return None

    candidate = day - timedelta(days=1)
    earliest = max(COVERAGE_START, day - timedelta(days=_MAX_LOOKBACK_DAYS))
    while candidate >= earliest:
        if is_open(candidate):
            return candidate
        candidate -= timedelta(days=1)
    return None
