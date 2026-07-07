from unittest.mock import AsyncMock

import pytest

from backend.services.compliance.notifications import ComplianceNotificationService


@pytest.mark.asyncio
async def test_send_alert_uses_injected_notification_service() -> None:
    notification_service = AsyncMock()
    notification_service.send.return_value = True
    service = ComplianceNotificationService(notification_service=notification_service)

    result = await service.send_alert(
        alert_id="alert-1",
        client_id="client-1",
        message="LKPM due soon",
        via="email",
    )

    assert result is True
    notification_service.send.assert_awaited_once_with(
        client_id="client-1",
        message="LKPM due soon",
        via="email",
    )


@pytest.mark.asyncio
async def test_send_alert_returns_false_when_provider_raises() -> None:
    notification_service = AsyncMock()
    notification_service.send.side_effect = RuntimeError("provider down")
    service = ComplianceNotificationService(notification_service=notification_service)

    assert await service.send_alert("alert-1", "client-1", "message") is False


@pytest.mark.asyncio
async def test_send_alert_without_provider_is_log_only_success() -> None:
    service = ComplianceNotificationService()

    assert await service.send_alert("alert-1", "client-1", "message") is True
