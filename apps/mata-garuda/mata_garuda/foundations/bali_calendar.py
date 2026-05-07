"""Balinese Pawukon + Saka calendar.

Discovered in R6 SOTA 2026-05-08. Source: babadbali.com + peradnya/balinese-date-js-lib (port).

Pawukon cycle = 210 days. 30 wuku of 7 days each. Galungan = Buda (Wed) Kliwon Dungulan
(day 1 of wuku Dunggulan, position 11/30). Kuningan = Saniscara (Sat) Kliwon Kuningan
(day 5 of wuku Kuningan, position 12/30, 10 days after Galungan).

Anchor: 2026-06-17 (Wed) IS Galungan — verified against
https://kalenderbali.org/?bulan=6&tanggal=17&tahun=2026 (R6).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

PAWUKON_CYCLE_DAYS = 210

WUKU_NAMES = [
    "Sinta", "Landep", "Ukir", "Kulantir", "Tolu", "Gumbreg", "Wariga",
    "Warigadean", "Julungwangi", "Sungsang", "Dunggulan", "Kuningan",
    "Langkir", "Medangsia", "Pujut", "Pahang", "Krulut", "Merakih",
    "Tambir", "Medangkungan", "Matal", "Uye", "Menail", "Prangbakat",
    "Bala", "Ugu", "Wayang", "Kelawu", "Dukut", "Watugunung",
]
assert len(WUKU_NAMES) == 30

# Anchor: 2026-06-17 = Galungan = day 1 of Dunggulan (wuku 11, 0-indexed 10).
# Wuku Dunggulan starts on 2026-06-17 in this anchor convention.
# Therefore Pawukon day 1 of cycle (Sinta day 1) = 2026-06-17 - (10 * 7) days = 2026-04-08.
ANCHOR_PAWUKON_DAY_1 = date(2026, 4, 8)
GALUNGAN_PAWUKON_DAY_INDEX = 10 * 7  # 0-indexed: day 70 of cycle (1-indexed: 71)
# Kuningan = Galungan + 10 days (Sat 2026-06-27 verified via R6 source).
KUNINGAN_PAWUKON_DAY_INDEX = GALUNGAN_PAWUKON_DAY_INDEX + 10  # 0-indexed: 80


@dataclass(frozen=True)
class BalineseDate:
    gregorian: date
    pawukon_day: int  # 1..210
    wuku: str
    wuku_day: int  # 1..7 within current wuku
    is_galungan: bool
    is_kuningan: bool


def _pawukon_day_index(target: date) -> int:
    """Return 0-indexed position in 210-day Pawukon cycle."""
    delta_days = (target - ANCHOR_PAWUKON_DAY_1).days
    return delta_days % PAWUKON_CYCLE_DAYS


def get_balinese_date(target: date) -> BalineseDate:
    idx = _pawukon_day_index(target)
    wuku_position = idx // 7  # 0..29
    wuku_day = (idx % 7) + 1  # 1..7
    return BalineseDate(
        gregorian=target,
        pawukon_day=idx + 1,
        wuku=WUKU_NAMES[wuku_position],
        wuku_day=wuku_day,
        is_galungan=(idx == GALUNGAN_PAWUKON_DAY_INDEX),
        is_kuningan=(idx == KUNINGAN_PAWUKON_DAY_INDEX),
    )


def is_galungan(target: date) -> bool:
    return _pawukon_day_index(target) == GALUNGAN_PAWUKON_DAY_INDEX


def is_kuningan(target: date) -> bool:
    return _pawukon_day_index(target) == KUNINGAN_PAWUKON_DAY_INDEX


def days_until_next_galungan(target: date) -> int:
    idx = _pawukon_day_index(target)
    days_until = (GALUNGAN_PAWUKON_DAY_INDEX - idx) % PAWUKON_CYCLE_DAYS
    if days_until == 0:
        return PAWUKON_CYCLE_DAYS
    return days_until
