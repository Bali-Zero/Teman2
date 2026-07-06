import pytest

from backend.services.monitoring import alert_service as alert_module
from backend.services.monitoring.alert_service import AlertLevel, AlertService


def make_service() -> AlertService:
    service = AlertService()
    service.enable_telegram = False
    service.enable_slack = False
    service.enable_discord = False
    return service


def test_get_alert_service_reuses_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(alert_module, "_alert_service", None)

    first = alert_module.get_alert_service()
    second = alert_module.get_alert_service()

    assert first is second


@pytest.mark.asyncio
async def test_send_alert_logs_and_rate_limits_repeated_dedup_key() -> None:
    service = make_service()

    first = await service.send_alert(
        "Title",
        "Message",
        AlertLevel.ERROR,
        metadata={"path": "/health"},
        dedup_key="same",
    )
    second = await service.send_alert(
        "Title",
        "Message",
        AlertLevel.ERROR,
        metadata={"path": "/health"},
        dedup_key="same",
    )

    assert first == {"telegram": False, "slack": False, "discord": False, "logging": True}
    assert second == {"telegram": False, "slack": False, "discord": False, "logging": True}
    assert service._alert_repeat["same"] == 1


@pytest.mark.asyncio
async def test_send_http_error_alert_maps_status_to_level_and_metadata() -> None:
    service = make_service()
    captured: dict[str, object] = {}

    async def fake_send_alert(**kwargs: object) -> dict[str, bool]:
        captured.update(kwargs)
        return {"logging": True, "telegram": False, "slack": False, "discord": False}

    service.send_alert = fake_send_alert

    result = await service.send_http_error_alert(
        status_code=503,
        method="GET",
        path="/api/fail",
        error_detail="down",
        request_id="req-1",
        user_agent="agent" * 40,
    )

    assert result["logging"] is True
    assert captured["title"] == "HTTP 503 Error"
    assert captured["level"] == AlertLevel.CRITICAL
    assert captured["metadata"]["request_id"] == "req-1"
    assert len(captured["metadata"]["user_agent"]) == 100


@pytest.mark.asyncio
async def test_send_latency_alert_buffers_event_for_digest() -> None:
    service = make_service()

    result = await service.send_latency_alert(
        duration_ms=1250.4,
        method="POST",
        path="/api/slow",
        threshold_ms=1000,
        request_id="req-2",
        user_agent="browser",
    )

    assert result == {"telegram": False, "slack": False, "discord": False, "logging": True}
    assert service._latency_buffer[0]["duration_ms"] == 1250
    assert service._latency_buffer[0]["threshold_ms"] == 1000
    assert service._latency_buffer[0]["path"] == "/api/slow"


@pytest.mark.asyncio
async def test_send_resource_alert_uses_stable_dedup_key_and_warning_level() -> None:
    service = make_service()
    captured: dict[str, object] = {}

    async def fake_send_alert(**kwargs: object) -> dict[str, bool]:
        captured.update(kwargs)
        return {"logging": True, "telegram": False, "slack": False, "discord": False}

    service.send_alert = fake_send_alert

    await service.send_resource_alert("memory", current_value=86.0, threshold=85.0)

    assert captured["dedup_key"] == "resource:memory"
    assert captured["level"] == AlertLevel.WARNING
    assert captured["metadata"]["current_value"] == "86.0%"


@pytest.mark.asyncio
async def test_send_resource_alert_escalates_when_well_above_threshold() -> None:
    service = make_service()
    captured: dict[str, object] = {}

    async def fake_send_alert(**kwargs: object) -> dict[str, bool]:
        captured.update(kwargs)
        return {"logging": True, "telegram": False, "slack": False, "discord": False}

    service.send_alert = fake_send_alert

    await service.send_resource_alert("cpu", current_value=95.0, threshold=80.0)

    assert captured["level"] == AlertLevel.CRITICAL
