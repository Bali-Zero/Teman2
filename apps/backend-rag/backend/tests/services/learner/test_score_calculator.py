"""Tests for ScoreCalculator — weights, percentile, clamp, completeness flag."""

from __future__ import annotations

import pytest

from backend.services.learner.score_calculator import (
    W_ENGAGEMENT,
    W_LEADS_PER_1K,
    W_REACH,
    W_SAVE_RATE,
    ScoreCalculator,
    ScoreInputs,
    _clamp_01,
    _percentile_rank,
)
from backend.services.war_room.models import Platform


def test_weights_sum_to_one():
    total = W_REACH + W_ENGAGEMENT + W_LEADS_PER_1K + W_SAVE_RATE
    assert abs(total - 1.0) < 1e-9


def test_clamp_01():
    assert _clamp_01(-0.5) == 0.0
    assert _clamp_01(0.5) == 0.5
    assert _clamp_01(1.5) == 1.0


def test_percentile_rank_small_distribution_returns_median():
    assert _percentile_rank(42, []) == 0.5
    assert _percentile_rank(42, [1, 2]) == 0.5


def test_percentile_rank_above_all_is_one():
    dist = [10, 20, 30, 40, 50]
    assert _percentile_rank(100, dist) == 1.0


def test_percentile_rank_below_all_is_zero():
    dist = [10, 20, 30, 40, 50]
    assert _percentile_rank(1, dist) == 0.0


def test_percentile_rank_middle():
    dist = [10, 20, 30, 40, 50]
    # 30 is the middle — 3 values <= 30, out of 5 → 0.6
    assert _percentile_rank(30, dist) == 0.6


# ── calculator ────────────────────────────────────────────────────


def _full_inputs(imp: float = 10000.0) -> ScoreInputs:
    return ScoreInputs(
        reach=5000.0,
        impressions=imp,
        likes=200.0,
        comments=30.0,
        shares=40.0,
        saves=90.0,
        leads_attributed=5.0,
    )


def test_complete_score_full_inputs():
    c = ScoreCalculator().calculate(
        inputs=_full_inputs(),
        reach_distribution_90d=[1000, 2000, 3000, 4000, 6000, 8000],
        platform=Platform.INSTAGRAM,
    )
    assert c.complete is True
    assert c.missing_terms == []
    assert 0.0 <= c.value <= 1.0
    assert c.platform == Platform.INSTAGRAM


def test_engagement_rate_formula():
    c = ScoreCalculator().calculate(
        inputs=ScoreInputs(
            reach=100.0,
            impressions=1000.0,
            likes=100.0,
            comments=10.0,
            shares=10.0,
            saves=0.0,
            leads_attributed=0.0,
        ),
        reach_distribution_90d=[100, 100, 100, 100],
    )
    # engagement = (100 + 10 + 10) / 1000 = 0.12
    assert c.engagement_rate == pytest.approx(0.12)


def test_leads_per_1k_clamped_to_one():
    c = ScoreCalculator().calculate(
        inputs=ScoreInputs(
            reach=100.0,
            impressions=100.0,
            likes=0.0,
            comments=0.0,
            shares=0.0,
            saves=0.0,
            leads_attributed=1000.0,  # ridiculous, but we clamp
        ),
        reach_distribution_90d=[100, 100, 100, 100],
    )
    assert c.leads_per_1k == 1.0


def test_save_rate_formula():
    c = ScoreCalculator().calculate(
        inputs=ScoreInputs(
            reach=100.0,
            impressions=1000.0,
            likes=0.0,
            comments=0.0,
            shares=0.0,
            saves=50.0,
            leads_attributed=0.0,
        ),
        reach_distribution_90d=[100, 100, 100, 100],
    )
    assert c.save_rate == pytest.approx(0.05)


def test_incomplete_when_reach_missing():
    inputs = _full_inputs()
    inputs.reach = None
    c = ScoreCalculator().calculate(
        inputs=inputs,
        reach_distribution_90d=[1000, 2000, 3000, 4000],
    )
    assert c.complete is False
    assert "reach" in c.missing_terms
    assert c.norm_reach == 0.0


def test_incomplete_when_impressions_missing():
    inputs = _full_inputs()
    inputs.impressions = None
    c = ScoreCalculator().calculate(
        inputs=inputs,
        reach_distribution_90d=[1000, 2000, 3000, 4000],
    )
    assert c.complete is False
    assert "impressions" in c.missing_terms
    assert c.engagement_rate == 0.0
    assert c.leads_per_1k == 0.0
    assert c.save_rate == 0.0


def test_zero_impressions_does_not_divide_by_zero():
    inputs = _full_inputs()
    inputs.impressions = 0.0
    c = ScoreCalculator().calculate(
        inputs=inputs,
        reach_distribution_90d=[1000, 2000, 3000, 4000],
    )
    assert c.engagement_rate == 0.0
    assert c.save_rate == 0.0


def test_composite_value_in_0_1():
    c = ScoreCalculator().calculate(
        inputs=_full_inputs(),
        reach_distribution_90d=[1000, 2000, 3000, 4000],
    )
    assert 0.0 <= c.value <= 1.0
