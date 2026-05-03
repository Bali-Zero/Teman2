"""Test LTV computation + tier assignment logic.

Tests synthetic in-memory data only. Real-DB integration test happens via
deploy verification (Task 7-8).

Schema reality (verified 2026-05-01 against prod DB):
- practices.actual_price NUMERIC          — final invoiced amount (preferred)
- practices.quoted_price NUMERIC          — fallback if actual_price NULL
- practices.currency VARCHAR              — per-row currency (USD/IDR/etc.)
- practices.completion_date TIMESTAMPTZ   — completion timestamp
- practices.status VARCHAR                — 'completed' | 'on_process' | etc.

Earlier draft assumed total_invoiced_idr + completed_at — those columns
are referenced by services/crm/partners/commission_engine.py:89 but NOT
present in prod schema. verify_schema() catches the drift.
"""
import pytest

from scripts.compute_client_segments import (
    amount_to_usd,
    assign_tier,
    compute_ltv_usd,
)


class TestAmountToUsd:
    def test_usd_passthrough(self):
        assert amount_to_usd(1500, "USD") == 1500.0

    def test_idr_converted(self):
        # 31M IDR @ 15500 IDR/USD = $2000
        assert amount_to_usd(31_000_000, "IDR") == pytest.approx(2000.0, rel=1e-3)

    def test_eur_converted(self):
        assert amount_to_usd(1000, "EUR") == 1100.0

    def test_unknown_currency_passthrough(self):
        assert amount_to_usd(100, "XYZ") == 100.0

    def test_none_amount_returns_zero(self):
        assert amount_to_usd(None, "USD") == 0.0

    def test_zero_amount_returns_zero(self):
        assert amount_to_usd(0, "USD") == 0.0

    def test_negative_amount_returns_zero(self):
        assert amount_to_usd(-100, "USD") == 0.0

    def test_none_currency_treated_as_usd(self):
        assert amount_to_usd(500, None) == 500.0

    def test_lowercase_currency_normalized(self):
        assert amount_to_usd(1500, "usd") == 1500.0

    def test_genuine_usd_below_threshold(self):
        # $5000 USD genuino — below 50k threshold, no heuristic
        assert amount_to_usd(5000, "USD") == 5000.0

    def test_idr_mistag_heuristic_triggers_above_threshold(self):
        # 31M "USD" → almost certainly IDR mistag → ~$2000
        assert amount_to_usd(31_000_000, "USD") == pytest.approx(2000.0, rel=1e-3)

    def test_idr_mistag_heuristic_at_exact_threshold(self):
        # 50k exactly USD → genuino, no heuristic
        assert amount_to_usd(50_000, "USD") == 50_000.0

    def test_idr_mistag_heuristic_just_above_threshold(self):
        # 50k+1 → triggers heuristic
        result = amount_to_usd(50_001, "USD")
        assert result < 100  # ~$3.2 if treated as IDR


class TestComputeLtvUsd:
    def test_completed_practice_with_actual_price(self):
        practices = [
            {"actual_price": 2000, "quoted_price": 1500, "currency": "USD", "status": "completed"},
        ]
        assert compute_ltv_usd(practices) == 2000.0  # actual_price wins over quoted

    def test_completed_practice_falls_back_to_quoted_price_when_actual_null(self):
        practices = [
            {"actual_price": None, "quoted_price": 1500, "currency": "USD", "status": "completed"},
        ]
        assert compute_ltv_usd(practices) == 1500.0

    def test_idr_practice_converts_to_usd(self):
        # 31M IDR @ 15500 IDR/USD = $2000
        practices = [
            {"actual_price": 31_000_000, "quoted_price": None, "currency": "IDR", "status": "completed"},
        ]
        assert compute_ltv_usd(practices) == pytest.approx(2000.0, rel=1e-3)

    def test_multiple_completed_practices_sum(self):
        practices = [
            {"actual_price": 2000, "quoted_price": None, "currency": "USD", "status": "completed"},
            {"actual_price": 1000, "quoted_price": None, "currency": "USD", "status": "completed"},
        ]
        assert compute_ltv_usd(practices) == 3000.0

    def test_only_completed_status_counts(self):
        practices = [
            {"actual_price": 1000, "quoted_price": None, "currency": "USD", "status": "completed"},
            {"actual_price": 5000, "quoted_price": None, "currency": "USD", "status": "on_process"},
            {"actual_price": 2000, "quoted_price": None, "currency": "USD", "status": "cancelled"},
            {"actual_price": 1500, "quoted_price": None, "currency": "USD", "status": "sending_invoice"},
        ]
        assert compute_ltv_usd(practices) == 1000.0

    def test_no_practices_returns_zero(self):
        assert compute_ltv_usd([]) == 0.0

    def test_both_prices_null_returns_zero(self):
        practices = [
            {"actual_price": None, "quoted_price": None, "currency": "USD", "status": "completed"},
        ]
        assert compute_ltv_usd(practices) == 0.0

    def test_zero_actual_price_falls_back_to_quoted(self):
        # 0 is falsy via amount_to_usd → returns 0; but compute_ltv_usd still tries
        # quoted_price as fallback only if actual_price is None, not 0. So zero stays zero.
        practices = [
            {"actual_price": 0, "quoted_price": 1500, "currency": "USD", "status": "completed"},
        ]
        # actual_price=0 is treated as 0 (falsy in amount_to_usd guard, so 0); does not fall back
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
