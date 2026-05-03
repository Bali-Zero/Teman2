"""
AlertsEngine.generate_alerts orchestration.

Tests use real DB (db_tx) + mocked PricingTool/Dispatcher.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
import asyncpg

from backend.services.compliance.alerts_engine import AlertsEngine
from backend.services.compliance.predictive_engine import ComplianceForecast


pytestmark = pytest.mark.integration


def _make_forecast(client_id: int, **overrides) -> ComplianceForecast:
    today = date.today()
    base = dict(
        client_id=client_id,
        client_name="X",
        assigned_to=None,
        document_type="visa",
        current_visa_type="C1",
        expiry_date=today + timedelta(days=7),
        days_until_expiry=7,
        matched_rule_id="visa_c1",
        processing_days=14,
        lead_time_start=today,
        recommended_action_by=today,
        days_until_action=0,
        estimated_revenue_idr=None,
        renewal_pricing_key="visa.c1_renewal",
        priority_score=0.9,
        urgency_level="urgent",
        required_docs=[],
        has_active_renewal_practice=False,
        notes="",
    )
    base.update(overrides)
    return ComplianceForecast(**base)


@pytest.fixture
def mock_pricing() -> MagicMock:
    pricing = MagicMock()
    pricing.get_price = MagicMock(return_value=None)
    return pricing


@pytest.fixture
def mock_dispatcher() -> AsyncMock:
    dispatcher = AsyncMock()
    dispatcher.dispatch = AsyncMock(return_value=True)
    return dispatcher


@pytest.mark.asyncio
async def test_generate_empty_forecasts_returns_empty(
    db_tx: asyncpg.Connection, mock_pricing, mock_dispatcher,
) -> None:
    engine = AlertsEngine.with_connection(
        db_tx, pricing=mock_pricing, dispatcher=mock_dispatcher,
    )
    out = await engine.generate_alerts([])
    assert out == []
    mock_dispatcher.dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_creates_new_alert(
    db_tx: asyncpg.Connection, sample_client, mock_pricing, mock_dispatcher,
) -> None:
    engine = AlertsEngine.with_connection(
        db_tx, pricing=mock_pricing, dispatcher=mock_dispatcher,
    )
    forecast = _make_forecast(
        client_id=sample_client["id"], matched_rule_id="visa_c1_doc_99",
    )
    out = await engine.generate_alerts([forecast])
    assert len(out) == 1
    assert out[0].category == "visa_expiry"
    mock_dispatcher.dispatch.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_dedup_skip_same_severity(
    db_tx: asyncpg.Connection, sample_client, mock_pricing, mock_dispatcher,
) -> None:
    engine = AlertsEngine.with_connection(
        db_tx, pricing=mock_pricing, dispatcher=mock_dispatcher,
    )
    forecast = _make_forecast(client_id=sample_client["id"])
    await engine.generate_alerts([forecast])
    mock_dispatcher.reset_mock()

    # Same forecast again → no new alert, no dispatch
    out = await engine.generate_alerts([forecast])
    assert len(out) == 1  # returns the existing alert
    mock_dispatcher.dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_promotes_on_severity_upgrade(
    db_tx: asyncpg.Connection, sample_client, mock_pricing, mock_dispatcher,
) -> None:
    engine = AlertsEngine.with_connection(
        db_tx, pricing=mock_pricing, dispatcher=mock_dispatcher,
    )
    warn = _make_forecast(
        client_id=sample_client["id"], urgency_level="warning",
        days_until_expiry=30,
    )
    await engine.generate_alerts([warn])
    mock_dispatcher.reset_mock()

    urg = _make_forecast(
        client_id=sample_client["id"], urgency_level="urgent", days_until_expiry=7,
    )
    out = await engine.generate_alerts([urg])
    assert out[0].severity == "urgent"
    assert out[0].upgrade_count == 1
    mock_dispatcher.dispatch.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_uses_pricing_tool_never_hardcoded(
    db_tx: asyncpg.Connection, sample_client, mock_pricing, mock_dispatcher,
) -> None:
    mock_pricing.get_price = MagicMock(return_value=12_000_000)
    engine = AlertsEngine.with_connection(
        db_tx, pricing=mock_pricing, dispatcher=mock_dispatcher,
    )
    forecast = _make_forecast(client_id=sample_client["id"])
    out = await engine.generate_alerts([forecast])
    assert out[0].estimated_cost_idr == 12_000_000
    mock_pricing.get_price.assert_called_with("visa.c1_renewal")


@pytest.mark.asyncio
async def test_generate_sets_nb2_ref_from_rule_registry(
    db_tx: asyncpg.Connection, sample_client, mock_pricing, mock_dispatcher,
    monkeypatch,
) -> None:
    # Patch the renewal rules registry to include a rule with nb2_ref set
    from backend.services.compliance import renewal_rules as rr_module
    from backend.services.compliance.renewal_rules import RenewalRule

    stub_rule = RenewalRule(
        rule_id="visa_c1_renewal_rule",
        document_types=("visa",),
        visa_type_patterns=("c1",),
        processing_days=7,
        lead_time_days=14,
        recommended_start_days=21,
        renewal_pricing_key=None,
        required_docs=(),
        nb2_ref="NB-2-doc-X-p-42",
    )

    patched = dict(rr_module.RENEWAL_RULES)
    patched["visa_c1_renewal_rule"] = stub_rule
    monkeypatch.setattr(rr_module, "RENEWAL_RULES", patched)

    engine = AlertsEngine.with_connection(
        db_tx, pricing=mock_pricing, dispatcher=mock_dispatcher,
    )
    forecast = _make_forecast(
        client_id=sample_client["id"], matched_rule_id="visa_c1_renewal_rule",
    )
    out = await engine.generate_alerts([forecast])
    assert out[0].nb2_ref == "NB-2-doc-X-p-42"


@pytest.mark.asyncio
async def test_generate_renders_all_three_languages(
    db_tx: asyncpg.Connection, sample_client, mock_pricing, mock_dispatcher,
) -> None:
    engine = AlertsEngine.with_connection(
        db_tx, pricing=mock_pricing, dispatcher=mock_dispatcher,
    )
    forecast = _make_forecast(client_id=sample_client["id"])
    out = await engine.generate_alerts([forecast])
    assert out[0].message_it and len(out[0].message_it) > 0
    assert out[0].message_en and len(out[0].message_en) > 0
    assert out[0].message_id and len(out[0].message_id) > 0


@pytest.mark.asyncio
async def test_engine_with_real_dispatcher_end_to_end(
    db_tx: asyncpg.Connection, sample_client, mock_pricing,
) -> None:
    from backend.services.compliance.alert_dispatcher import AlertDispatcher

    dispatcher = AlertDispatcher.with_connection(
        db_tx,
        email_service=AsyncMock(),
        telegram_service=AsyncMock(),
        inapp_service=AsyncMock(),
        wa_service=AsyncMock(),
    )
    engine = AlertsEngine.with_connection(
        db_tx, pricing=mock_pricing, dispatcher=dispatcher,
    )
    forecast = _make_forecast(client_id=sample_client["id"])
    out = await engine.generate_alerts([forecast])
    assert len(out) == 1
