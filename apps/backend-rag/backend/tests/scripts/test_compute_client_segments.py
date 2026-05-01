"""Test LTV computation + tier assignment logic.

Tests synthetic in-memory data only. Real-DB integration test happens via
deploy verification (Task 7-8).

Schema reality (verified 2026-05-01 against repo code):
- practices.total_invoiced_idr NUMERIC(16,2)  — IDR only, single currency
- practices.completed_at TIMESTAMPTZ          — set on status='completed' transition
- practices.status TEXT                       — 'completed' | 'on_process' | etc.
"""
import pytest

from scripts.compute_client_segments import assign_tier, compute_ltv_usd


class TestComputeLtvUsd:
    def test_completed_practice_idr_converts_to_usd(self):
        # 31,000,000 IDR @ 15500 IDR/USD = $2000
        practices = [{"total_invoiced_idr": 31_000_000, "status": "completed"}]
        assert compute_ltv_usd(practices) == pytest.approx(2000.0, rel=1e-3)

    def test_multiple_completed_practices_sum(self):
        # 31M + 15.5M = 46.5M IDR = $3000
        practices = [
            {"total_invoiced_idr": 31_000_000, "status": "completed"},
            {"total_invoiced_idr": 15_500_000, "status": "completed"},
        ]
        assert compute_ltv_usd(practices) == pytest.approx(3000.0, rel=1e-3)

    def test_only_completed_status_counts(self):
        practices = [
            {"total_invoiced_idr": 15_500_000, "status": "completed"},  # $1000
            {"total_invoiced_idr": 31_000_000, "status": "on_process"},  # not counted
            {"total_invoiced_idr": 46_500_000, "status": "cancelled"},  # not counted
            {"total_invoiced_idr": 15_500_000, "status": "sending_invoice"},  # not counted
        ]
        assert compute_ltv_usd(practices) == pytest.approx(1000.0, rel=1e-3)

    def test_no_practices_returns_zero(self):
        assert compute_ltv_usd([]) == 0.0

    def test_null_total_invoiced_idr_treated_as_zero(self):
        practices = [{"total_invoiced_idr": None, "status": "completed"}]
        assert compute_ltv_usd(practices) == 0.0

    def test_zero_total_invoiced_idr(self):
        practices = [{"total_invoiced_idr": 0, "status": "completed"}]
        assert compute_ltv_usd(practices) == 0.0


class TestAssignTier:
    def test_tier_1_at_5000(self):
        assert assign_tier(5000.0) == 1

    def test_tier_1_above_5000(self):
        assert assign_tier(7500.0) == 1

    def test_tier_2_at_2000(self):
        assert assign_tier(2000.0) == 2

    def test_tier_2_at_4999(self):
        assert assign_tier(4999.99) == 2

    def test_tier_3_below_2000(self):
        assert assign_tier(1999.99) == 3

    def test_tier_3_at_zero(self):
        assert assign_tier(0.0) == 3
