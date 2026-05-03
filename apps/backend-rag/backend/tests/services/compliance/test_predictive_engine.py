"""Tests for predictive_engine.py — engine logic without DB (unit layer)."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.compliance.predictive_engine import (
    ComplianceForecast,
    PredictiveComplianceEngine,
    is_engine_enabled,
)
from backend.services.compliance.renewal_rules import RENEWAL_RULES

# ── Pricing fixture ────────────────────────────────────────────────────────────

SAMPLE_PRICES: dict = {
    "services": {
        "kitas_permits": {
            "Investor KITAS 2 Years (Extend)": {"price": "18.000.000 IDR"},
            "Spouse 1 Year (Extend)": {"price": "9.000.000 IDR"},
            "E33G Remote Worker (Extend)": {"price": "10.000.000 IDR"},
            "Retirement (Extend)": {"price": "10.000.000 IDR"},
            "Dependent 1 Year (Extend)": {"price": "9.000.000 IDR"},
            "Working KITAS (Extend)": {"price": "31.500.000 IDR"},
        },
        "kitap_permits": {
            "Investor KITAP + MERP": {"price": "55.000.000 IDR"},
        },
        "visa_extensions": {
            "C1 Tourism Extension": {"price": "1.700.000 IDR"},
        },
    }
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_mock_pool(
    client_rows: list[dict],
    practice_rows: list[dict],
    has_active_renewal: bool = False,
    kill_switch_value: str | None = "true",
) -> AsyncMock:
    """Build a mock asyncpg pool that returns given rows."""
    conn = AsyncMock()
    # fetch calls: first = client_docs, second = practices
    conn.fetch = AsyncMock(side_effect=[
        [_dict_to_record(r) for r in client_rows],
        [_dict_to_record(r) for r in practice_rows],
    ])
    conn.fetchval = AsyncMock(return_value=1 if has_active_renewal else None)

    pool = AsyncMock()
    pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=conn),
        __aexit__=AsyncMock(return_value=None),
    ))
    return pool


def _dict_to_record(d: dict):
    """Minimal asyncpg record-like object."""
    class FakeRecord(dict):
        def __getitem__(self, key):
            return super().__getitem__(key)
        def get(self, key, default=None):
            return super().get(key, default)
    return FakeRecord(d)


def _client_row(
    *,
    client_id: int = 1,
    full_name: str = "Test Client",
    assigned_to: str = "surya@balizero.com",
    current_visa_type: str = "KITAS Investor",
    passport_expiry: date | None = None,
    document_type: str = "kitas",
    expiry_date: date | None = None,
) -> dict:
    if expiry_date is None:
        expiry_date = date.today() + timedelta(days=120)
    return {
        "client_id": client_id,
        "full_name": full_name,
        "assigned_to": assigned_to,
        "current_visa_type": current_visa_type,
        "passport_expiry": passport_expiry,
        "document_type": document_type,
        "expiry_date": expiry_date,
        "practice_type_code": None,
    }


# ── Tests ──────────────────────────────────────────────────────────────────────


class TestPredictiveEngineBasic:
    @pytest.mark.asyncio
    async def test_scan_returns_forecast_for_investor_kitas(self) -> None:
        expiry = date.today() + timedelta(days=120)
        pool = _make_mock_pool(
            client_rows=[_client_row(document_type="kitas", expiry_date=expiry)],
            practice_rows=[],
        )

        engine = PredictiveComplianceEngine(pool, SAMPLE_PRICES, scan_window_days=365)
        result = await engine.scan()

        assert result.summary.total_forecasts == 1
        forecast = result.forecasts[0]
        assert forecast.matched_rule_id == "kitas_investor_extend"
        assert forecast.expiry_date == expiry
        assert forecast.days_until_expiry == 120

    @pytest.mark.asyncio
    async def test_scan_skips_when_active_renewal_exists(self) -> None:
        pool = _make_mock_pool(
            client_rows=[_client_row()],
            practice_rows=[],
            has_active_renewal=True,
        )

        engine = PredictiveComplianceEngine(pool, SAMPLE_PRICES)
        result = await engine.scan()

        assert result.summary.total_forecasts == 0
        assert result.summary.clients_with_active_practice_skipped == 1

    @pytest.mark.asyncio
    async def test_revenue_estimated_from_pricing_service(self) -> None:
        expiry = date.today() + timedelta(days=120)
        pool = _make_mock_pool(
            client_rows=[_client_row(document_type="kitas", expiry_date=expiry)],
            practice_rows=[],
        )

        engine = PredictiveComplianceEngine(pool, SAMPLE_PRICES)
        result = await engine.scan()

        forecast = result.forecasts[0]
        assert forecast.estimated_revenue_idr == 18_000_000

    @pytest.mark.asyncio
    async def test_timeline_calculations_correct(self) -> None:
        today = date.today()
        expiry = today + timedelta(days=100)
        pool = _make_mock_pool(
            client_rows=[_client_row(document_type="kitas", expiry_date=expiry)],
            practice_rows=[],
        )

        engine = PredictiveComplianceEngine(pool, SAMPLE_PRICES)
        result = await engine.scan()
        forecast = result.forecasts[0]

        rule = RENEWAL_RULES["kitas_investor_extend"]
        expected_action_by = expiry - timedelta(days=rule.recommended_start_days)
        expected_lead_start = expiry - timedelta(days=rule.lead_time_days)

        assert forecast.recommended_action_by == expected_action_by
        assert forecast.lead_time_start == expected_lead_start
        assert forecast.days_until_action == (expected_action_by - today).days

    @pytest.mark.asyncio
    async def test_passport_expiry_before_visa_detected(self) -> None:
        today = date.today()
        expiry = today + timedelta(days=365)
        passport_expiry = today + timedelta(days=200)  # passport expires before visa

        pool = _make_mock_pool(
            client_rows=[_client_row(
                document_type="kitas",
                expiry_date=expiry,
                passport_expiry=passport_expiry,
            )],
            practice_rows=[],
        )

        engine = PredictiveComplianceEngine(pool, SAMPLE_PRICES)
        result = await engine.scan()

        forecast = result.forecasts[0]
        assert forecast.passport_expires_before_visa is True

    @pytest.mark.asyncio
    async def test_passport_not_expiring_before_visa(self) -> None:
        today = date.today()
        expiry = today + timedelta(days=200)
        passport_expiry = today + timedelta(days=365)  # passport valid longer

        pool = _make_mock_pool(
            client_rows=[_client_row(
                document_type="kitas",
                expiry_date=expiry,
                passport_expiry=passport_expiry,
            )],
            practice_rows=[],
        )

        engine = PredictiveComplianceEngine(pool, SAMPLE_PRICES)
        result = await engine.scan()

        forecast = result.forecasts[0]
        assert forecast.passport_expires_before_visa is False

    @pytest.mark.asyncio
    async def test_forecasts_sorted_by_priority_score_descending(self) -> None:
        today = date.today()
        # Two clients: one urgent (30d), one planning (300d)
        rows = [
            _client_row(client_id=1, expiry_date=today + timedelta(days=30)),
            _client_row(client_id=2, expiry_date=today + timedelta(days=300)),
        ]
        pool = _make_mock_pool(client_rows=rows, practice_rows=[])

        engine = PredictiveComplianceEngine(pool, SAMPLE_PRICES)
        result = await engine.scan()

        scores = [f.priority_score for f in result.forecasts]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_summary_totals_revenue(self) -> None:
        today = date.today()
        rows = [
            _client_row(client_id=1, expiry_date=today + timedelta(days=100)),
            _client_row(client_id=2, expiry_date=today + timedelta(days=200)),
        ]
        pool = _make_mock_pool(client_rows=rows, practice_rows=[])

        engine = PredictiveComplianceEngine(pool, SAMPLE_PRICES)
        result = await engine.scan()

        assert result.summary.total_estimated_revenue_idr == 18_000_000 * 2

    @pytest.mark.asyncio
    async def test_empty_result_when_no_rows(self) -> None:
        pool = _make_mock_pool(client_rows=[], practice_rows=[])

        engine = PredictiveComplianceEngine(pool, SAMPLE_PRICES)
        result = await engine.scan()

        assert result.summary.total_forecasts == 0
        assert result.summary.total_estimated_revenue_idr == 0

    @pytest.mark.asyncio
    async def test_assigned_to_preserved(self) -> None:
        pool = _make_mock_pool(
            client_rows=[_client_row(assigned_to="ari.firda@balizero.com")],
            practice_rows=[],
        )

        engine = PredictiveComplianceEngine(pool, SAMPLE_PRICES)
        result = await engine.scan()

        assert result.forecasts[0].assigned_to == "ari.firda@balizero.com"

    @pytest.mark.asyncio
    async def test_required_docs_populated(self) -> None:
        pool = _make_mock_pool(
            client_rows=[_client_row(document_type="kitas", current_visa_type="KITAS Investor")],
            practice_rows=[],
        )

        engine = PredictiveComplianceEngine(pool, SAMPLE_PRICES)
        result = await engine.scan()

        forecast = result.forecasts[0]
        assert len(forecast.required_docs) > 0
        assert "valid_passport" in forecast.required_docs

    @pytest.mark.asyncio
    async def test_scan_result_has_generated_at(self) -> None:
        pool = _make_mock_pool(client_rows=[], practice_rows=[])
        engine = PredictiveComplianceEngine(pool, SAMPLE_PRICES)
        result = await engine.scan()
        assert result.generated_at is not None
        assert "T" in result.generated_at  # ISO format


class TestIsEngineEnabled:
    @pytest.mark.asyncio
    async def test_returns_true_when_enabled(self) -> None:
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value="true")
        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        ))
        assert await is_engine_enabled(pool) is True

    @pytest.mark.asyncio
    async def test_returns_false_when_disabled(self) -> None:
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value="false")
        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        ))
        assert await is_engine_enabled(pool) is False

    @pytest.mark.asyncio
    async def test_returns_false_when_key_missing(self) -> None:
        conn = AsyncMock()
        conn.fetchval = AsyncMock(return_value=None)
        pool = AsyncMock()
        pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=conn),
            __aexit__=AsyncMock(return_value=None),
        ))
        assert await is_engine_enabled(pool) is False
