"""Decreed Indonesian non-working days — the ONE place such a date may live.

Two unrelated organs need the same fact and must never disagree about it:

- ``services.garuda_flow.operating_calendar`` — is Bali Zero's office open that day?
- ``services.compliance.business_days`` — does a statutory tax deadline move off that day?

They answer different questions with different boundaries — the VOA gate publishes only the part
of the year its pilot materialized, a tax deadline cares about the whole year — so they keep
their own logic. What they share is the DATA, and a date is typed here once or not at all.

DECREED ONLY. Bali Zero's own non-working days are not decreed days and may never be added here:
a day the office chooses to close does not move a statutory deadline, and putting one in this
table would move it. 24-25 December 2026 are in the table because the decree puts them there,
not because anyone is on holiday.

Provenance — every date below comes from one decree, whose number this module does not invent:

    KEPUTUSAN BERSAMA MENTERI AGAMA / MENTERI KETENAGAKERJAAN / MENTERI PANRB RI —
    NOMOR 1497 TAHUN 2025, NOMOR 2 TAHUN 2025, NOMOR 5 TAHUN 2025, tentang Hari Libur
    Nasional dan Cuti Bersama Tahun 2026. Ditetapkan di Jakarta, 19 September 2025.
    Full year 2026 = 17 hari libur nasional + 8 cuti bersama (``test_id_holidays`` pins
    both counts, so a hand-edit that drops or invents a day fails loudly).

    Retrieved 2026-09-12 from Sekretariat Negara RI, which publishes the decree's own tables:
    https://setneg.go.id/baca/index/inilah_skb_3_menteri_libur_nasional_dan_cuti_bersama_2026
    Decree PDF: https://www.kemenkopmk.go.id/sites/default/files/pengumuman/2025-09/
    SKB%20Libur%20Nasional%20dan%20Cuti%20Bersama%20Tahun%202026.pdf
    The four dates from 2026-07-28 onward were independently sourced in the 2026-07-27
    GARUDA session (decree + press route, zero divergence) and agree with this table.

``DECREED_YEARS`` is the honest coverage statement and the reason this module is not just a
tuple: a year is listed ONLY when the whole calendar year is materialized from a real decree.
This decree class is issued around September of the PRECEDING year, so the 2027 SKB does not
exist yet (expected ~September 2026). Any "2027 Indonesian holiday calendar" circulating before
that is a third-party estimate, not a decreed fact. Callers that cannot silently under-answer
for an undecreed year read ``DECREED_YEARS`` and say so — see
``business_days.holiday_years_loaded`` and the ``needs_review_reason`` the obligations register
attaches. NOTHING here may carry a date outside ``DECREED_YEARS``.

PURE data — no I/O, no ``date.today()``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

__all__ = ["DECREED_YEARS", "HOLIDAYS", "HOLIDAY_DATES", "Holiday", "HolidayKind"]


class HolidayKind(str, Enum):
    """The decree names two distinct kinds of non-working day.

    Both are "hari libur" for a tax deadline (PMK 81/2024 Pasal 100 ayat (2) names cuti bersama
    explicitly) and both close Bali Zero's own systems, but the tag stays on the data so either
    reading can be revisited later without re-sourcing a single date.
    """

    LIBUR_NASIONAL = "libur_nasional"
    CUTI_BERSAMA = "cuti_bersama"


@dataclass(frozen=True)
class Holiday:
    """One decreed non-working day."""

    at: date
    kind: HolidayKind
    name: str


_LN = HolidayKind.LIBUR_NASIONAL
_CB = HolidayKind.CUTI_BERSAMA

# SKB 3 Menteri 2026 — in decree order within each kind, merged chronologically.
HOLIDAYS: tuple[Holiday, ...] = (
    Holiday(date(2026, 1, 1), _LN, "Tahun Baru 2026 Masehi"),
    Holiday(date(2026, 1, 16), _LN, "Isra Mikraj Nabi Muhammad S.A.W."),
    Holiday(date(2026, 2, 16), _CB, "Cuti Bersama Tahun Baru Imlek 2577 Kongzili"),
    Holiday(date(2026, 2, 17), _LN, "Tahun Baru Imlek 2577 Kongzili"),
    Holiday(date(2026, 3, 18), _CB, "Cuti Bersama Hari Suci Nyepi"),
    Holiday(date(2026, 3, 19), _LN, "Hari Suci Nyepi (Tahun Baru Saka 1948)"),
    Holiday(date(2026, 3, 20), _CB, "Cuti Bersama Idulfitri 1447 Hijriah"),
    Holiday(date(2026, 3, 21), _LN, "Idulfitri 1447 Hijriah"),
    Holiday(date(2026, 3, 22), _LN, "Idulfitri 1447 Hijriah"),
    Holiday(date(2026, 3, 23), _CB, "Cuti Bersama Idulfitri 1447 Hijriah"),
    Holiday(date(2026, 3, 24), _CB, "Cuti Bersama Idulfitri 1447 Hijriah"),
    Holiday(date(2026, 4, 3), _LN, "Wafat Yesus Kristus"),
    Holiday(date(2026, 4, 5), _LN, "Kebangkitan Yesus Kristus (Paskah)"),
    Holiday(date(2026, 5, 1), _LN, "Hari Buruh Internasional"),
    Holiday(date(2026, 5, 14), _LN, "Kenaikan Yesus Kristus"),
    Holiday(date(2026, 5, 15), _CB, "Cuti Bersama Kenaikan Yesus Kristus"),
    Holiday(date(2026, 5, 27), _LN, "Iduladha 1447 Hijriah"),
    Holiday(date(2026, 5, 28), _CB, "Cuti Bersama Iduladha 1447 Hijriah"),
    Holiday(date(2026, 5, 31), _LN, "Hari Raya Waisak 2570 BE"),
    Holiday(date(2026, 6, 1), _LN, "Hari Lahir Pancasila"),
    Holiday(date(2026, 6, 16), _LN, "1 Muharam Tahun Baru Islam 1448 Hijriah"),
    Holiday(date(2026, 8, 17), _LN, "Proklamasi Kemerdekaan"),
    Holiday(date(2026, 8, 25), _LN, "Maulid Nabi Muhammad S.A.W."),
    Holiday(date(2026, 12, 24), _CB, "Cuti Bersama Kelahiran Yesus Kristus"),
    Holiday(date(2026, 12, 25), _LN, "Kelahiran Yesus Kristus (Hari Raya Natal)"),
)

# Years materialized IN FULL from a decree. Not "years that appear in HOLIDAYS" — a partially
# typed year must never be advertised as covered, which is why this is written, not derived.
DECREED_YEARS: frozenset[int] = frozenset({2026})

HOLIDAY_DATES: frozenset[date] = frozenset(h.at for h in HOLIDAYS)
