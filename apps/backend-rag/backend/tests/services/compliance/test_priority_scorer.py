"""Tests for priority_scorer.py — composite priority calculation."""

import pytest

from backend.services.compliance.priority_scorer import (
    PriorityResult,
    calculate_priority,
    sort_forecasts,
)


class TestCalculatePriority:
    def test_overdue_has_highest_weight(self) -> None:
        result = calculate_priority(days_until_action=-1, estimated_revenue_idr=None, complexity=1.0)
        assert result.urgency_level == "overdue"
        assert result.urgency_weight == 10.0

    def test_critical_within_7_days(self) -> None:
        result = calculate_priority(days_until_action=5, estimated_revenue_idr=None, complexity=1.0)
        assert result.urgency_level == "critical"
        assert result.urgency_weight == 8.0

    def test_urgent_within_30_days(self) -> None:
        result = calculate_priority(days_until_action=20, estimated_revenue_idr=None, complexity=1.0)
        assert result.urgency_level == "urgent"
        assert result.urgency_weight == 5.0

    def test_warning_within_60_days(self) -> None:
        result = calculate_priority(days_until_action=45, estimated_revenue_idr=None, complexity=1.0)
        assert result.urgency_level == "warning"
        assert result.urgency_weight == 3.0

    def test_planning_within_90_days(self) -> None:
        result = calculate_priority(days_until_action=75, estimated_revenue_idr=None, complexity=1.0)
        assert result.urgency_level == "planning"
        assert result.urgency_weight == 2.0

    def test_informational_beyond_90_days(self) -> None:
        result = calculate_priority(days_until_action=200, estimated_revenue_idr=None, complexity=1.0)
        assert result.urgency_level == "informational"
        assert result.urgency_weight == 1.0

    def test_no_revenue_gives_0_5_value_weight(self) -> None:
        result = calculate_priority(days_until_action=30, estimated_revenue_idr=None, complexity=1.0)
        assert result.value_weight == 0.5

    def test_zero_revenue_gives_0_5_value_weight(self) -> None:
        result = calculate_priority(days_until_action=30, estimated_revenue_idr=0, complexity=1.0)
        assert result.value_weight == 0.5

    def test_max_revenue_gives_1_5_value_weight(self) -> None:
        # 55M IDR = max (Investor KITAP)
        result = calculate_priority(days_until_action=30, estimated_revenue_idr=55_000_000, complexity=1.0)
        assert result.value_weight == 1.5

    def test_half_max_revenue_gives_1_0_value_weight(self) -> None:
        # 27.5M IDR = 50% of max → 0.5 + 0.5 = 1.0
        result = calculate_priority(days_until_action=30, estimated_revenue_idr=27_500_000, complexity=1.0)
        assert abs(result.value_weight - 1.0) < 0.01

    def test_score_is_product(self) -> None:
        result = calculate_priority(
            days_until_action=5,        # critical → weight=8.0
            estimated_revenue_idr=55_000_000,   # max → value=1.5
            complexity=2.0,
        )
        expected = 8.0 * 1.5 * 2.0
        assert abs(result.score - expected) < 0.01

    def test_high_revenue_critical_item_scores_above_30(self) -> None:
        result = calculate_priority(
            days_until_action=-1,           # overdue → 10.0
            estimated_revenue_idr=55_000_000,
            complexity=3.0,
        )
        assert result.score > 30.0  # 10 × 1.5 × 3 = 45

    def test_simple_extend_scores_lower_than_kitap(self) -> None:
        simple = calculate_priority(
            days_until_action=20,
            estimated_revenue_idr=9_000_000,
            complexity=1.0,
        )
        kitap = calculate_priority(
            days_until_action=20,
            estimated_revenue_idr=55_000_000,
            complexity=3.0,
        )
        assert kitap.score > simple.score

    def test_score_is_rounded_to_2_decimals(self) -> None:
        result = calculate_priority(days_until_action=20, estimated_revenue_idr=18_000_000, complexity=1.5)
        # Ensure it's a clean float with at most 2 decimals
        assert result.score == round(result.score, 2)


class TestSortForecasts:
    def test_sorts_descending_by_priority_score(self) -> None:
        forecasts = [
            {"priority_score": 5.0, "name": "low"},
            {"priority_score": 20.0, "name": "high"},
            {"priority_score": 10.0, "name": "mid"},
        ]
        sorted_list = sort_forecasts(forecasts)
        scores = [f["priority_score"] for f in sorted_list]
        assert scores == sorted(scores, reverse=True)

    def test_empty_list_returns_empty(self) -> None:
        assert sort_forecasts([]) == []

    def test_single_item_unchanged(self) -> None:
        item = {"priority_score": 7.5}
        assert sort_forecasts([item]) == [item]
