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

Provenance — every date below is traceable to ONE decree, cross-checked by
a second, independent sourcing route in the same session with zero
divergence on any date:

    KEPUTUSAN BERSAMA MENTERI AGAMA / MENTERI KETENAGAKERJAAN / MENTERI
    PANRB RI — NOMOR 1497 TAHUN 2025, NOMOR 2 TAHUN 2025, NOMOR 5 TAHUN
    2025, tentang Hari Libur Nasional dan Cuti Bersama Tahun 2026.
    Ditetapkan di Jakarta, 19 September 2025.
    Primary source (PDF): https://www.kemenkopmk.go.id/sites/default/files/
    pengumuman/2025-09/SKB%20Libur%20Nasional%20dan%20Cuti%20Bersama%20
    Tahun%202026.pdf
    Corroborated (2026-07-27 session) by an independent route through
    Indonesian press — both agreed on every date, zero divergence.

    Full year 2026 per the decree = 17 hari libur nasional + 8 cuti
    bersama. This module materializes ONLY the closure set needed from
    2026-07-28 onward. Earlier dates were deliberately omitted when the
    pilot began, so this dataset cannot certify an open day before that
    materialization boundary even though the source decree spans the year.

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

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

__all__ = [
    "COVERAGE_END",
    "COVERAGE_START",
    "OPERATING_CALENDAR",
    "HolidayKind",
    "OperatingCalendarDate",
    "is_open",
    "last_open_day_before",
]


class HolidayKind(str, Enum):
    """The decree names two distinct kinds of non-working day. Both close
    Bali Zero's systems for the purpose of this gate (the conservative
    reading — see `is_open`'s docstring for why), but the tag is kept on
    the data so a future retune can revisit that reading without having to
    re-source a single date."""

    LIBUR_NASIONAL = "libur_nasional"
    CUTI_BERSAMA = "cuti_bersama"


@dataclass(frozen=True)
class OperatingCalendarDate:
    """One decreed non-working day."""

    at: date
    kind: HolidayKind
    name: str


# The one and only place a 2026 non-working day may be added — see the
# module docstring for provenance and the COVERAGE_END boundary.
OPERATING_CALENDAR: tuple[OperatingCalendarDate, ...] = (
    OperatingCalendarDate(date(2026, 8, 17), HolidayKind.LIBUR_NASIONAL, "Proklamasi Kemerdekaan"),
    OperatingCalendarDate(
        date(2026, 8, 25), HolidayKind.LIBUR_NASIONAL, "Maulid Nabi Muhammad S.A.W."
    ),
    OperatingCalendarDate(
        date(2026, 12, 24),
        HolidayKind.CUTI_BERSAMA,
        "Cuti Bersama Kelahiran Yesus Kristus",
    ),
    OperatingCalendarDate(
        date(2026, 12, 25),
        HolidayKind.LIBUR_NASIONAL,
        "Kelahiran Yesus Kristus (Hari Raya Natal)",
    ),
)

# The source decree spans 2026, but the checked-in closure subset begins at
# the pilot's materialization boundary. Coverage describes what THIS dataset
# can actually certify, not what exists in the omitted part of the decree.
COVERAGE_START: date = date(2026, 7, 28)
COVERAGE_END: date = date(2026, 12, 31)

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
