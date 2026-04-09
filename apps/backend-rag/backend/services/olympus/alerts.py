"""Olympus Alerts — Telegram integration for alerts and proposals."""

from __future__ import annotations

import logging

from backend.services.monitoring.alert_service import AlertLevel, AlertService

logger = logging.getLogger("olympus.alerts")


class OlympusAlerts:
    """Sends alerts and proposals to Zero via Telegram."""

    def __init__(self, alert_service: AlertService) -> None:
        self.alert_service = alert_service

    async def send_alert(self, message: str, level: AlertLevel = AlertLevel.WARNING) -> None:
        formatted = f"[OLIMPO] {message}"
        await self.alert_service.send_alert(
            title="Olympus DB Guardian", message=formatted, level=level,
        )

    async def send_proposal(self, title: str, detail: str) -> None:
        formatted = f"[OLIMPO PROPOSTA]\n\n{title}\n\n{detail}\n\nRispondi per approvare o rifiutare."
        await self.alert_service.send_alert(
            title="Olympus Proposal", message=formatted, level=AlertLevel.INFO,
        )

    async def send_pulse_summary(self, actions_count: int, failures: int) -> None:
        if failures > 0:
            msg = f"Pulse completato: {actions_count} azioni, {failures} fallimenti"
            await self.send_alert(msg, AlertLevel.WARNING)
        else:
            msg = f"Pulse completato: {actions_count} azioni, tutto OK"
            await self.send_alert(msg, AlertLevel.INFO)
