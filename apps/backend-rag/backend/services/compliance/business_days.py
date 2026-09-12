"""Indonesian business days for statutory deadlines (pure, no I/O).

A tax deadline that falls on a hari libur does not stay there, and the regulation defines the
holiday set in the same breath as the roll. Verified 2026-09-12 against the text of
PMK-81/PMK.03/2024 (the jdih.kemenkeu.go.id page-stamped PDF, read on the BPK mirror
https://peraturan.bpk.go.id/Download/366884/2024pmkeuangan081.pdf):

    Pasal 100 — payment and deposit:
      (1) "Dalam hal tanggal jatuh tempo pembayaran atau penyetoran pajak sebagaimana dimaksud
          dalam Pasal 94 bertepatan dengan hari libur, pembayaran atau penyetoran pajak dapat
          dilakukan paling lambat pada hari kerja berikutnya."
      (2) "Hari libur sebagaimana dimaksud pada ayat (1) yaitu hari Sabtu, hari Minggu, hari
          libur nasional, hari yang diliburkan untuk penyelenggaraan pemilihan umum, atau hari
          yang ditetapkan sebagai cuti bersama secara nasional."

    Pasal 173 — SPT Masa reporting: a SEPARATE provision, keyed to Pasal 171/172 and not to Pasal
    94/100, carrying the identical hari-libur definition in its own ayat (2). Payment rules and
    monthly reporting rules therefore roll for the same reason under two different articles, and
    this module is the one implementation of both. Pasal 264 ayat (2)-(3) repeats the template for
    oil-and-gas reporting.

WHAT THIS MODULE DOES NOT DECIDE: which obligations are entitled to the roll. That is the `roll`
field of each catalog rule, and the articles above cover the monthly payment and SPT Masa rules —
NOT every deadline in the catalog. The annual corporate return is a known open case: it sits under
UU KUP art. 3, its catalog `legal_source` still ends in "(verify)", and Pasal 173 does not name it.
Rolling it is therefore an unverified catalog entitlement, not something this module asserts; the
catalog-source verification pass owns that question. An over-broad `roll` still only ever moves a
date onto an open day, so it cannot produce a deadline nobody can meet.

Two deliberate gaps, both of which under-roll (they can only leave a date earlier than the law
allows, never later, so they never invent a deadline that has already passed):

- Election days ("hari yang diliburkan untuk penyelenggaraan pemilihan umum") are NOT modelled.
  They are decreed per election, are not part of the SKB this data comes from, and 2026 has no
  national election day. A deadline falling on a future one will not move here.
- A year whose SKB is not decreed yet rolls off WEEKENDS ONLY. `holiday_years_loaded` exists so
  a caller can say that out loud instead of shipping a silently incomplete date; the obligations
  register turns it into a `needs_review_reason` on the proposal.

Bali Zero's own closures are not statutory and cannot reach this module: it reads nothing but the
decreed national set in `backend.data.id_holidays`, whose docstring forbids an undecreed date and
whose test pins the decree's own 17 + 8 counts. A day the office chooses to take off does not
move a DJP deadline, and the office being open on a decreed holiday does not unmove one.
`garuda_flow.operating_calendar` answers the different question "is our office open" from the
same table; neither module is the other's source.

PURE functions — no I/O, no ``date.today()``. The caller always injects the day.
"""

from __future__ import annotations

from datetime import date, timedelta

from backend.data.id_holidays import DECREED_YEARS, HOLIDAY_DATES

__all__ = ["holiday_years_loaded", "is_business_day", "next_business_day"]

# The longest real closed run in the 2026 decree is 2026-03-18..2026-03-24 (7 days: Nyepi plus
# the Idulfitri block plus a weekend). This bound only exists so a future data error fails loudly
# instead of looping forever; it is never reached with decreed data.
_MAX_ROLL_DAYS: int = 30


def holiday_years_loaded() -> frozenset[int]:
    """Calendar years whose national holiday table is materialized IN FULL from a decree.

    A year absent from this set is not holiday-free: it is unknown. `is_business_day` then judges
    that year on weekends alone, so a caller that must not publish an under-rolled date checks
    membership and flags the result for review.
    """
    return DECREED_YEARS


def is_business_day(day: date) -> bool:
    """True unless ``day`` is a Saturday, a Sunday, or a decreed libur nasional / cuti bersama.

    Both kinds of decreed day count: PMK 81/2024 Pasal 100 ayat (2) names cuti bersama
    explicitly. For a year outside `holiday_years_loaded` only the weekend test can fire.
    """
    if day.weekday() >= 5:  # Monday=0 ... Saturday=5, Sunday=6
        return False
    return day not in HOLIDAY_DATES


def next_business_day(day: date) -> date:
    """The first business day at or AFTER ``day`` — ``day`` itself when it already is one.

    This is the "hari kerja berikutnya" of Pasal 100 / Pasal 173 applied to a statutory date: a
    deadline already on a working day does not move, and one on a closed day moves forward until
    the office and the tax system are both open. Never moves a date backwards.
    """
    candidate = day
    for _ in range(_MAX_ROLL_DAYS + 1):
        if is_business_day(candidate):
            return candidate
        candidate += timedelta(days=1)
    raise ValueError(
        f"no business day within {_MAX_ROLL_DAYS} days of {day.isoformat()} — "
        "the holiday data is almost certainly wrong"
    )
