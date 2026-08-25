"""Tests for the GARUDA VOA Bali Zero operating calendar (pure, no I/O).

Two pinned dates verified by hand this session (2026-07-27), cross-checked
against the primary decree (KEPBERSAMA 3 Menteri No. 1497/2/5 Tahun 2025)
and an independent press route with zero divergence:

  - departure Tue 2026-08-18: 17 Aug is Independence Day (a Monday) -> the
    last open day is Fri 14 Aug (15/16 Aug are the weekend).
  - departure Mon 2026-12-28: 24 Dec (Thu, cuti bersama) and 25 Dec (Fri,
    libur nasional) are closed, and 26-27 Dec is the weekend -> the last
    open day is Wed 23 Dec.

Full end-to-end wiring of these dates through `build_verdict` (accept/
decline/submit_by_date) lives in
`backend/tests/services/garuda_flow/test_intake.py::TestIssuanceSubmissionWindowGate` —
this file pins the calendar arithmetic in isolation.
"""

from __future__ import annotations

from datetime import date, timedelta

from backend.services.garuda_flow.operating_calendar import (
    COVERAGE_END,
    COVERAGE_START,
    OPERATING_CALENDAR,
    is_open,
    last_open_day_before,
)


class TestIsOpen:
    def test_ordinary_weekday_is_open(self) -> None:
        assert is_open(date(2026, 7, 29)) is True  # Wednesday, no holiday

    def test_date_before_materialized_coverage_is_not_certified_open(self) -> None:
        assert is_open(COVERAGE_START - timedelta(days=1)) is False

    def test_saturday_is_closed(self) -> None:
        assert is_open(date(2026, 8, 15)) is False

    def test_sunday_is_closed(self) -> None:
        assert is_open(date(2026, 8, 16)) is False

    def test_independence_day_libur_nasional_is_closed(self) -> None:
        assert is_open(date(2026, 8, 17)) is False  # Proklamasi Kemerdekaan (Mon)

    def test_maulid_nabi_libur_nasional_is_closed(self) -> None:
        assert is_open(date(2026, 8, 25)) is False

    def test_cuti_bersama_is_also_closed(self) -> None:
        # Conservative reading (module docstring): Bali Zero's own systems
        # close for cuti bersama too, not only civil-servant offices —
        # this can only ever push a computed cutoff earlier, never later.
        assert is_open(date(2026, 12, 24)) is False

    def test_christmas_libur_nasional_is_closed(self) -> None:
        assert is_open(date(2026, 12, 25)) is False


class TestLastOpenDayBeforePinned:
    """The two dates the owner computed and verified by hand this session."""

    def test_departure_tue_18_aug_cutoff_is_fri_14_aug(self) -> None:
        assert last_open_day_before(date(2026, 8, 18)) == date(2026, 8, 14)

    def test_departure_mon_28_dec_cutoff_is_wed_23_dec(self) -> None:
        assert last_open_day_before(date(2026, 12, 28)) == date(2026, 12, 23)


class TestLastOpenDayBeforeOrdinaryCases:
    def test_ordinary_midweek_departure_cutoff_is_the_previous_day(self) -> None:
        # Wed 29 Jul -> Tue 28 Jul: no weekend, no holiday in between.
        assert last_open_day_before(date(2026, 7, 29)) == date(2026, 7, 28)

    def test_monday_departure_with_no_holiday_cutoff_is_the_previous_friday(self) -> None:
        # Mon 3 Aug -> Sat 1/Sun 2 Aug are the weekend -> Fri 31 Jul.
        assert last_open_day_before(date(2026, 8, 3)) == date(2026, 7, 31)

    def test_result_is_always_strictly_before_the_day_given(self) -> None:
        # "day" itself is never a candidate, even when it is itself open.
        day = date(2026, 7, 29)
        result = last_open_day_before(day)
        assert result is not None
        assert result < day

    def test_departure_tomorrow_from_an_open_today(self) -> None:
        # today = Wed 29 Jul (open) -> departure Thu 30 Jul -> cutoff is
        # today itself, since nothing closes the day in between.
        assert last_open_day_before(date(2026, 7, 30)) == date(2026, 7, 29)


class TestCoverageBounds:
    def test_materialized_coverage_starts_when_the_stored_subset_begins(self) -> None:
        assert COVERAGE_START == date(2026, 7, 28)

    def test_day_before_coverage_start_returns_none(self) -> None:
        assert last_open_day_before(COVERAGE_START - timedelta(days=1)) is None

    def test_coverage_start_has_no_certified_prior_open_day(self) -> None:
        assert last_open_day_before(COVERAGE_START) is None

    def test_day_after_coverage_start_can_use_the_boundary_day(self) -> None:
        assert last_open_day_before(COVERAGE_START + timedelta(days=1)) == COVERAGE_START

    def test_january_2026_is_uncovered_not_guessed_open(self) -> None:
        assert last_open_day_before(date(2026, 1, 6)) is None

    def test_departure_past_coverage_end_returns_none(self) -> None:
        assert last_open_day_before(COVERAGE_END + timedelta(days=5)) is None

    def test_departure_far_past_coverage_end_returns_none(self) -> None:
        assert last_open_day_before(date(2027, 6, 1)) is None

    def test_departure_exactly_at_coverage_end_is_still_computable(self) -> None:
        # The boundary date itself IS in coverage -- only strictly-after
        # fails closed.
        assert last_open_day_before(COVERAGE_END) is not None

    def test_day_after_coverage_end_can_use_the_covered_boundary_day(self) -> None:
        # The old expectation of None asserted the off-by-one bug, not the
        # fail-closed property: this function searches strictly before its
        # input, so COVERAGE_END is the only candidate and remains covered.
        # The farther-past tests above still protect fail-closed behavior once
        # the search would have to begin outside the materialized calendar.
        assert last_open_day_before(COVERAGE_END + timedelta(days=1)) == COVERAGE_END


class TestCalendarDataNeverExceedsCoverageEnd:
    """Guard (task requirement): nobody can quietly paste an undecreed
    2027+ date into `OPERATING_CALENDAR` later without this failing."""

    def test_no_calendar_date_beyond_coverage_end(self) -> None:
        assert len(OPERATING_CALENDAR) > 0, "calendar must not be silently emptied either"
        for entry in OPERATING_CALENDAR:
            assert entry.at <= COVERAGE_END, (
                f"{entry.name} ({entry.at}) is beyond COVERAGE_END={COVERAGE_END} — "
                "the following year's SKB has not been decreed yet"
            )
