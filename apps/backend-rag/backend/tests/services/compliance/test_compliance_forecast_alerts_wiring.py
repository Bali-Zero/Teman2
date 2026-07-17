"""
POST /api/cron/notifiers/compliance-forecast — AlertsEngine wiring.

Covers the core defect this arming PR fixes: `run_compliance_forecast()`
computed forecasts and returned them over HTTP but never constructed an
AlertsEngine nor called `generate_alerts()` — forecasts were never persisted
as alerts nor dispatched. This proves:

  (a) when the kill switch is ON, forecasts flow into
      `build_alerts_engine(...).generate_alerts(forecasts)` and the count
      is reflected in the response as `alerts_generated`;
  (b) when the kill switch is OFF, the route returns early — the alerts
      wiring (`build_alerts_engine`) is never even invoked.

No real Postgres, no real network: `PredictiveComplianceEngine` and
`build_alerts_engine` are monkeypatched at the module attribute they're
looked up from (both are LOCAL imports inside the route function, so
patching the source module's attribute is picked up on every call). The
kill switch itself goes through the REAL `is_engine_enabled()` logic via a
minimal fake asyncpg-pool — only the two heavy dependencies are faked.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.routers import cron_notifiers
from backend.services.compliance.predictive_engine import ComplianceForecast


def _make_forecast(client_id: int = 1) -> ComplianceForecast:
    today = date.today()
    return ComplianceForecast(
        client_id=client_id,
        client_name="Wiring Test Client",
        assigned_to=None,
        document_type="visa",
        current_visa_type="C1",
        expiry_date=today + timedelta(days=7),
        days_until_expiry=7,
        matched_rule_id="visa_c1_renewal",
        processing_days=14,
        lead_time_start=today,
        recommended_action_by=today,
        days_until_action=0,
        estimated_revenue_idr=None,
        renewal_pricing_key="C1 Tourism Extension",
        priority_score=0.9,
        urgency_level="urgent",
        required_docs=[],
        has_active_renewal_practice=False,
        notes="wiring-test",
    )


class _FakeConn:
    def __init__(self, kill_switch_value: str | None) -> None:
        self._value = kill_switch_value

    async def fetchval(self, query: str, *args: Any) -> Any:
        return self._value


class _FakeAcquireCtx:
    def __init__(self, kill_switch_value: str | None) -> None:
        self._value = kill_switch_value

    async def __aenter__(self) -> _FakeConn:
        return _FakeConn(self._value)

    async def __aexit__(self, *exc: Any) -> None:
        return None


class _FakePool:
    """Fakes ONLY what `is_engine_enabled()` needs: `acquire().fetchval(...)`."""

    def __init__(self, kill_switch_value: str | None) -> None:
        self._value = kill_switch_value

    def acquire(self) -> _FakeAcquireCtx:
        return _FakeAcquireCtx(self._value)


class _FakeAppState:
    def __init__(self, db_pool: Any) -> None:
        self.db_pool = db_pool


class _FakeApp:
    def __init__(self, db_pool: Any) -> None:
        self.state = _FakeAppState(db_pool)


class _FakeRequest:
    def __init__(self, db_pool: Any, api_key: str, query_params: dict | None = None) -> None:
        self.headers = {"X-API-Key": api_key}
        self.app = _FakeApp(db_pool)
        self.query_params = query_params or {}


class _FakeScanResult:
    def __init__(self, forecasts: list[ComplianceForecast]) -> None:
        self.forecasts = forecasts
        self.summary = SimpleNamespace(
            total_forecasts=len(forecasts),
            by_urgency={},
            total_estimated_revenue_idr=0,
            clients_with_active_practice_skipped=0,
            top_revenue_forecasts=[],
        )
        self.scan_window_days = 365
        self.generated_at = "2026-07-17T00:00:00+00:00"


def _fake_engine_class(forecasts: list[ComplianceForecast]) -> type:
    class _FakeEngine:
        def __init__(self, db_pool: Any, all_prices: Any, scan_window_days: int) -> None:
            self.db_pool = db_pool
            self.all_prices = all_prices
            self.scan_window_days = scan_window_days

        async def scan(self) -> _FakeScanResult:
            return _FakeScanResult(forecasts)

    return _FakeEngine


@pytest.mark.asyncio
async def test_forecasts_flow_into_generate_alerts_when_switch_on(monkeypatch) -> None:
    monkeypatch.setattr(cron_notifiers, "_API_KEY", "test-key")

    forecasts = [_make_forecast(client_id=42)]
    monkeypatch.setattr(
        "backend.services.compliance.predictive_engine.PredictiveComplianceEngine",
        _fake_engine_class(forecasts),
    )

    fake_alerts_engine = MagicMock()
    fake_alerts_engine.generate_alerts = AsyncMock(return_value=[MagicMock(), MagicMock()])
    build_mock = MagicMock(return_value=fake_alerts_engine)
    monkeypatch.setattr(
        "backend.services.compliance.alert_wiring.build_alerts_engine",
        build_mock,
    )

    fake_pool = _FakePool(kill_switch_value="true")
    request = _FakeRequest(db_pool=fake_pool, api_key="test-key")

    response = await cron_notifiers.run_compliance_forecast(request)

    assert response["status"] == "ok"
    # generate_alerts must receive the EXACT forecasts list the scan produced.
    build_mock.assert_called_once()
    assert build_mock.call_args.args[0] is fake_pool
    fake_alerts_engine.generate_alerts.assert_awaited_once()
    awaited_forecasts = fake_alerts_engine.generate_alerts.await_args.args[0]
    assert awaited_forecasts is forecasts
    # 2 AlertRow-shaped objects returned by the (mocked) engine -> reflected verbatim.
    assert response["alerts_generated"] == 2
    assert "alerts_error" not in response


@pytest.mark.asyncio
async def test_nothing_generated_when_switch_off(monkeypatch) -> None:
    monkeypatch.setattr(cron_notifiers, "_API_KEY", "test-key")

    build_mock = MagicMock()
    monkeypatch.setattr(
        "backend.services.compliance.alert_wiring.build_alerts_engine",
        build_mock,
    )
    fake_engine_class = _fake_engine_class([_make_forecast()])
    monkeypatch.setattr(
        "backend.services.compliance.predictive_engine.PredictiveComplianceEngine",
        fake_engine_class,
    )

    fake_pool = _FakePool(kill_switch_value="false")
    request = _FakeRequest(db_pool=fake_pool, api_key="test-key")

    response = await cron_notifiers.run_compliance_forecast(request)

    assert response == {
        "service": "compliance_forecast",
        "status": "disabled",
        "reason": "Set compliance_forecast_enabled=true in system_settings to enable",
    }
    # The kill switch must gate the ENTIRE forecast+alerts path — the wiring
    # factory is never even called when disabled.
    build_mock.assert_not_called()


@pytest.mark.asyncio
async def test_alerts_wiring_failure_does_not_break_http_response(monkeypatch) -> None:
    """AlertsEngine construction/call failures must never surface as a 500 —
    the forecast HTTP response already succeeded and must still return it."""
    monkeypatch.setattr(cron_notifiers, "_API_KEY", "test-key")

    forecasts = [_make_forecast()]
    monkeypatch.setattr(
        "backend.services.compliance.predictive_engine.PredictiveComplianceEngine",
        _fake_engine_class(forecasts),
    )

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("TELEGRAM_OWNER_CHAT_ID not configured")

    monkeypatch.setattr(
        "backend.services.compliance.alert_wiring.build_alerts_engine",
        _boom,
    )

    fake_pool = _FakePool(kill_switch_value="true")
    request = _FakeRequest(db_pool=fake_pool, api_key="test-key")

    response = await cron_notifiers.run_compliance_forecast(request)

    assert response["status"] == "ok"  # forecast response still succeeds
    assert response["alerts_generated"] == 0
    assert "TELEGRAM_OWNER_CHAT_ID" in response["alerts_error"]
    assert len(response["forecasts"]) == 1  # forecast computation unaffected
