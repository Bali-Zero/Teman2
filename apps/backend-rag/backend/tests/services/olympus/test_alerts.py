"""Tests for Olympus v2 OlympusAlerts — nullable alert_service."""

import logging
from unittest.mock import AsyncMock

import pytest

from backend.services.olympus.alerts import OlympusAlerts


@pytest.fixture
def mock_alert_service():
    svc = AsyncMock()
    svc.send_alert = AsyncMock()
    return svc


class TestOlympusAlerts:
    @pytest.mark.asyncio
    async def test_send_alert_with_service(self, mock_alert_service):
        alerts = OlympusAlerts(mock_alert_service)
        await alerts.send_alert("test message")
        mock_alert_service.send_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_alert_without_service_no_crash(self, caplog):
        """BUG-2 fix: alert_service=None must not crash."""
        alerts = OlympusAlerts(None)

        caplog.set_level(logging.INFO, logger="olympus.alerts")
        result = await alerts.send_alert("test message")

        assert result is None
        assert "[OLIMPO] (no alert_service) test message" in caplog.text

    @pytest.mark.asyncio
    async def test_send_pulse_summary_with_failures(self, mock_alert_service):
        alerts = OlympusAlerts(mock_alert_service)
        await alerts.send_pulse_summary(10, 3)
        mock_alert_service.send_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_pulse_summary_no_failures(self, mock_alert_service):
        alerts = OlympusAlerts(mock_alert_service)
        await alerts.send_pulse_summary(10, 0)
        mock_alert_service.send_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_pulse_summary_without_service(self, caplog):
        alerts = OlympusAlerts(None)

        caplog.set_level(logging.INFO, logger="olympus.alerts")
        result = await alerts.send_pulse_summary(5, 2)  # No crash

        assert result is None
        assert "[OLIMPO] (no alert_service) Pulse completato: 5 azioni, 2 fallimenti" in (
            caplog.text
        )
