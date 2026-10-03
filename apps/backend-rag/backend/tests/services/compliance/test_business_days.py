"""Indonesian business days and the decreed holiday table behind them (pure, no I/O).

Calendar facts used below, all 2026: 15 Feb is a Sunday; 16 Feb (cuti bersama Imlek) and 17 Feb
(Imlek) are decreed; 18 Feb is a Wednesday. 20 Mar (cuti bersama Idulfitri) is a Friday, 21-22 Mar
are Idulfitri AND the weekend, 23-24 Mar are cuti bersama, 25 Mar is a Wednesday — the longest
closed run in the decree. 17 Aug (Proklamasi Kemerdekaan) is a Monday. 9 Sep is a Wednesday.

The 18 February 2026 case is the PAYMENT/deposit deadline of Pasal 94 (the 15th of the following
month), not a reporting deadline: Sun 15 Feb, then cuti bersama and Imlek, land it on Wed 18 Feb.
The same month's SPT Masa is a different deadline (Pasal 171, the 20th) and does not move at all.
The arithmetic below rests on the decreed dates, not on anyone's worked example.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.data.id_holidays import DECREED_YEARS, HOLIDAY_DATES, HOLIDAYS, HolidayKind
from backend.services.compliance.business_days import (
    holiday_years_loaded,
    is_business_day,
    next_business_day,
)
from backend.services.garuda_flow.operating_calendar import (
    COVERAGE_END,
    COVERAGE_START,
    OPERATING_CALENDAR,
)


class TestIsBusinessDay:
    def test_ordinary_weekday_is_a_business_day(self) -> None:
        assert is_business_day(date(2026, 9, 9)) is True

    @pytest.mark.parametrize("day", [date(2026, 9, 12), date(2026, 9, 13)])
    def test_weekend_is_not_a_business_day(self, day: date) -> None:
        assert is_business_day(day) is False

    def test_libur_nasional_is_not_a_business_day(self) -> None:
        assert is_business_day(date(2026, 8, 17)) is False  # Proklamasi Kemerdekaan, a Monday

    def test_cuti_bersama_is_not_a_business_day(self) -> None:
        # PMK 81/2024 Pasal 100 ayat (2) names cuti bersama in the hari-libur definition, so a
        # deadline moves off it exactly like a libur nasional.
        assert is_business_day(date(2026, 3, 20)) is False  # Friday, cuti bersama Idulfitri

    def test_every_decreed_date_is_closed(self) -> None:
        assert not [day for day in HOLIDAY_DATES if is_business_day(day)]


class TestNextBusinessDay:
    def test_a_business_day_does_not_move(self) -> None:
        assert next_business_day(date(2026, 9, 9)) == date(2026, 9, 9)

    def test_weekend_moves_to_monday(self) -> None:
        assert next_business_day(date(2026, 9, 12)) == date(2026, 9, 14)
        assert next_business_day(date(2026, 9, 13)) == date(2026, 9, 14)

    def test_sunday_before_two_decreed_days_lands_on_wednesday(self) -> None:
        # Sun 15 Feb -> Mon 16 (cuti bersama Imlek) -> Tue 17 (Imlek) -> Wed 18. The old
        # weekend-only roll stopped on the 16th, a day the tax system is closed.
        assert next_business_day(date(2026, 2, 15)) == date(2026, 2, 18)

    def test_friday_before_the_idulfitri_block_crosses_the_longest_closed_run(self) -> None:
        # Fri 20 Mar cuti bersama, Sat/Sun 21-22 Idulfitri, Mon/Tue 23-24 cuti bersama -> Wed 25.
        assert next_business_day(date(2026, 3, 20)) == date(2026, 3, 25)

    def test_monday_holiday_pushes_a_weekend_date_past_it(self) -> None:
        # Sat 15 Aug -> Sun 16 -> Mon 17 is Independence Day -> Tue 18.
        assert next_business_day(date(2026, 8, 15)) == date(2026, 8, 18)

    def test_never_moves_a_date_backwards_and_is_idempotent(self) -> None:
        day = date(2026, 1, 1)
        while day < date(2028, 1, 1):
            rolled = next_business_day(day)
            assert rolled >= day
            assert next_business_day(rolled) == rolled
            assert is_business_day(rolled)
            day += timedelta(days=1)


class TestUndecreedYears:
    def test_only_fully_decreed_years_are_reported_loaded(self) -> None:
        assert holiday_years_loaded() == frozenset({2026, 2027})
        assert 2028 not in holiday_years_loaded()

    def test_an_undecreed_year_rolls_weekends_only(self) -> None:
        # 1 January is a national holiday every year, but 2028's SKB does not exist, so this
        # module must not pretend to know. It under-rolls and `holiday_years_loaded` is how a
        # caller learns to say so — see the obligations register's needs_review_reason.
        assert is_business_day(date(2028, 1, 3)) is True  # Monday, the 2028 New Year is a Saturday
        assert is_business_day(date(2028, 8, 17)) is True  # Thursday, Proklamasi, not decreed yet
        assert next_business_day(date(2028, 8, 17)) == date(2028, 8, 17)
        assert next_business_day(date(2028, 1, 1)) == date(2028, 1, 3)  # Sat -> Mon


class TestDecree2027:
    def test_new_year_2027_is_closed_and_rolls_to_monday(self) -> None:
        assert is_business_day(date(2027, 1, 1)) is False
        assert next_business_day(date(2027, 1, 1)) == date(2027, 1, 4)

    def test_idulfitri_block_2027_crosses_cuti_bersama_and_the_weekend(self) -> None:
        # Mon 8 Nyepi, Tue 9 CB, Wed 10 / Thu 11 Idulfitri, Fri 12 CB, Sat/Sun, Mon 15 CB -> Tue 16.
        assert next_business_day(date(2027, 3, 8)) == date(2027, 3, 16)

    def test_named_2027_dates(self) -> None:
        by_date = {h.at: h for h in HOLIDAYS}
        assert by_date[date(2027, 8, 17)].kind is HolidayKind.LIBUR_NASIONAL
        assert by_date[date(2027, 12, 26)].name == "Isra Mikraj Nabi Muhammad saw."
        assert by_date[date(2027, 12, 24)].kind is HolidayKind.CUTI_BERSAMA
        assert by_date[date(2027, 3, 15)].kind is HolidayKind.CUTI_BERSAMA


class TestDecreedTableIntegrity:
    """The data, not the arithmetic: a hand-edit that invents or drops a day fails here."""

    @pytest.mark.parametrize(
        ("year", "libur_nasional", "cuti_bersama"), [(2026, 17, 8), (2027, 18, 8)]
    )
    def test_the_decree_counts_per_year(
        self, year: int, libur_nasional: int, cuti_bersama: int
    ) -> None:
        kinds = [h.kind for h in HOLIDAYS if h.at.year == year]
        assert kinds.count(HolidayKind.LIBUR_NASIONAL) == libur_nasional
        assert kinds.count(HolidayKind.CUTI_BERSAMA) == cuti_bersama
        assert len(kinds) == libur_nasional + cuti_bersama
        assert len(HOLIDAYS) == 25 + 26

    def test_no_date_outside_a_decreed_year_and_no_duplicate(self) -> None:
        assert {h.at.year for h in HOLIDAYS} <= DECREED_YEARS
        assert len(HOLIDAY_DATES) == len(HOLIDAYS)

    def test_table_is_sorted_so_a_pasted_date_is_visible_in_review(self) -> None:
        assert [h.at for h in HOLIDAYS] == sorted(h.at for h in HOLIDAYS)

    def test_only_decreed_days_can_close_a_deadline(self) -> None:
        # The enforceable half of "Bali Zero's own closures are not statutory": the set this
        # module consults IS the decree's set, so an office closure cannot move a due date
        # without first being added to a table whose counts are pinned above.
        assert HOLIDAY_DATES == frozenset(h.at for h in HOLIDAYS)


class TestGarudaReadsTheSameTable:
    """Both readers, one table — and the VOA gate's published dataset did not change when the
    dates moved out of it (family #9: a shared-data refactor that silently mutates a consumer)."""

    def test_operating_calendar_is_the_shared_table_clipped_to_its_coverage(self) -> None:
        assert OPERATING_CALENDAR == tuple(
            h for h in HOLIDAYS if COVERAGE_START <= h.at <= COVERAGE_END
        )

    def test_the_voa_gate_still_carries_exactly_its_four_days(self) -> None:
        assert [h.at for h in OPERATING_CALENDAR] == [
            date(2026, 8, 17),
            date(2026, 8, 25),
            date(2026, 12, 24),
            date(2026, 12, 25),
        ]

    def test_clipping_hides_the_earlier_decreed_dates_from_the_voa_gate_only(self) -> None:
        # They exist in the shared table (so a deadline moves off them) and are outside the VOA
        # gate's materialized window (so it still cannot certify an open day back there).
        assert date(2026, 3, 19) in HOLIDAY_DATES
        assert date(2026, 3, 19) not in {h.at for h in OPERATING_CALENDAR}
