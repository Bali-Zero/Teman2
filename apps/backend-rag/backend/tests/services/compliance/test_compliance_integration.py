"""
End-to-end compliance scenario:
  1. Seed a client with expiring visa
  2. ComplianceForecast produced manually (simulates PredictiveEngine)
  3. AlertsEngine generates an alert (DB row)
  4. AlertDispatcher sends to Telegram + email (mocks)
  5. notification_log records delivery
  6. Simulate outcome = 'acted'
  7. alert_outcomes row exists
  8. compute_metrics reflects new outcome
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
import asyncpg

from backend.services.compliance.alerts_engine import AlertsEngine
from backend.services.compliance.alert_dispatcher import AlertDispatcher
from backend.services.compliance.alert_metrics import compute_metrics
from backend.services.compliance.predictive_engine import ComplianceForecast


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_full_flow_visa_expiry_to_metrics(db_tx, sample_client) -> None:
    today = date.today()
    forecast = ComplianceForecast(
        client_id=sample_client["id"],
        client_name=sample_client["full_name"],
        assigned_to=None,
        document_type="visa",
        current_visa_type="C1",
        expiry_date=today + timedelta(days=7),
        days_until_expiry=7,
        matched_rule_id="visa_c1_doc_e2e",
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
        notes="e2e",
    )

    dispatcher = AlertDispatcher.with_connection(
        db_tx,
        email_service=AsyncMock(send=AsyncMock(return_value={"ok": True})),
        telegram_service=AsyncMock(send_message=AsyncMock(return_value={"ok": True})),
        inapp_service=AsyncMock(emit=AsyncMock(return_value=None)),
        wa_service=AsyncMock(send=AsyncMock(return_value={"ok": True})),
    )
    pricing = MagicMock()
    pricing.get_price = MagicMock(return_value=None)

    engine = AlertsEngine.with_connection(db_tx, pricing=pricing, dispatcher=dispatcher)
    alerts = await engine.generate_alerts([forecast])
    assert len(alerts) == 1

    # 5. notification_log has at least one row
    n = await db_tx.fetchval(
        "SELECT COUNT(*) FROM notification_log WHERE ref LIKE $1",
        f"compliance_alert:{alerts[0].alert_id}:%",
    )
    assert n >= 1

    # 6. Simulate outcome
    await db_tx.execute(
        "INSERT INTO alert_outcomes (alert_id, outcome, actioned_by) VALUES ($1, 'acted', 'e2e@x')",
        alerts[0].alert_id,
    )

    # 7. verify outcome row
    count = await db_tx.fetchval(
        "SELECT COUNT(*) FROM alert_outcomes WHERE alert_id = $1", alerts[0].alert_id,
    )
    assert count == 1

    # 8. metrics reflect the outcome
    m = await compute_metrics(db_tx, window_days=30, category="visa_expiry")
    assert m.acted >= 1
