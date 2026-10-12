"""The first anchor day Visa Oracle can no longer estimate a processing window, and its alert tier."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.services.visa_engine import holiday_coverage, processing_times
from backend.services.visa_engine.holiday_coverage import assess, first_unestimable_anchor


def _load_only(monkeypatch: pytest.MonkeyPatch, years: set[int]) -> None:
    loaded = frozenset(years)
    monkeypatch.setattr(processing_times, "holiday_years_loaded", lambda: loaded)
    monkeypatch.setattr(holiday_coverage, "holiday_years_loaded", lambda: loaded)


def _gap_with_only_2026(monkeypatch: pytest.MonkeyPatch) -> date:
    _load_only(monkeypatch, {2026})
    found = first_unestimable_anchor(date(2026, 1, 1))
    assert found is not None
    return found[0]


def test_real_data_first_gap_is_in_the_last_loaded_year_and_is_ok():
    # Data-relative: loading the next decree moves every expectation below by itself.
    loaded = holiday_coverage.holiday_years_loaded()
    last = max(loaded)
    result = assess(date(2026, 10, 10))
    gap = date.fromisoformat(result["first_gap"])
    assert result["outcome"] == "OK"
    assert result["years_loaded"] == sorted(loaded)
    assert gap.year == last and gap > date(last, 1, 1)
    assert result["year_to_load"] == last + 1
    assert result["product"] in processing_times.product_windows()


def test_the_gap_day_is_exactly_the_first_day_some_product_cannot_be_estimated(monkeypatch):
    gap = _gap_with_only_2026(monkeypatch)
    highs = {high for _, high in processing_times.product_windows().values()}
    day_before = gap - timedelta(days=1)
    assert all(processing_times.estimate(day_before, (h, h)) is not None for h in highs)
    assert any(processing_times.estimate(gap, (h, h)) is None for h in highs)


def test_thirty_days_out_warns(monkeypatch):
    gap = _gap_with_only_2026(monkeypatch)
    result = assess(gap - timedelta(days=30))
    assert result["outcome"] == "WARN"
    assert result["days_left"] == 30
    assert result["year_to_load"] == 2027


def test_sixty_days_out_still_warns_and_sixty_one_is_ok(monkeypatch):
    gap = _gap_with_only_2026(monkeypatch)
    assert assess(gap - timedelta(days=60))["outcome"] == "WARN"
    assert assess(gap - timedelta(days=61))["outcome"] == "OK"


def test_hundred_days_out_is_ok(monkeypatch):
    gap = _gap_with_only_2026(monkeypatch)
    assert assess(gap - timedelta(days=100))["outcome"] == "OK"


def test_the_gap_day_itself_and_the_past_are_stale(monkeypatch):
    gap = _gap_with_only_2026(monkeypatch)
    assert assess(gap)["outcome"] == "STALE"
    assert assess(gap + timedelta(days=200))["outcome"] == "STALE"


def test_guilt_after_the_gap_day_the_alert_still_names_the_day_it_began(monkeypatch):
    gap = _gap_with_only_2026(monkeypatch)
    for later in (1, 30, 200, 400, 800):
        result = assess(gap + timedelta(days=later))
        assert result["first_gap"] == gap.isoformat()
        assert result["days_left"] == -later


def test_innocence_before_the_gap_the_answer_is_the_same_day(monkeypatch):
    gap = _gap_with_only_2026(monkeypatch)
    assert assess(gap - timedelta(days=1))["first_gap"] == gap.isoformat()


def test_an_undecreed_current_year_is_stale_today(monkeypatch):
    _load_only(monkeypatch, set())
    result = assess(date(2026, 10, 10))
    assert result["outcome"] == "STALE"
    assert result["first_gap"] == "2026-10-10"
    assert result["year_to_load"] == 2026


def test_loading_the_next_decree_moves_the_gap_a_year(monkeypatch):
    _load_only(monkeypatch, {2026, 2027, 2028})
    result = assess(date(2026, 10, 10))
    assert result["outcome"] == "OK"
    assert date.fromisoformat(result["first_gap"]).year == 2028
    assert result["year_to_load"] == 2029
