"""Olympus v2 — Alerts (nullable-safe).

alert_service may be None on API machines (light init).
Every method handles this gracefully — log only, no crash.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.services.monitoring.alert_service import AlertLevel, AlertService

logger = logging.getLogger("olympus.alerts")


class OlympusAlerts:
    """Sends alerts via Telegram. Safe when alert_service is None."""

    def __init__(self, alert_service: AlertService | None) -> None:
        self._service = alert_service

    async def send_alert(self, message: str, level: AlertLevel | None = None) -> None:
        if self._service is None:
            logger.info("[OLIMPO] (no alert_service) %s", message)
            return
        from backend.services.monitoring.alert_service import AlertLevel as AL
        await self._service.send_alert(
            title="Olympus DB Guardian",
            message=f"[OLIMPO] {message}",
            level=level or AL.WARNING,
        )

    async def send_pulse_summary(self, actions_count: int, failures: int) -> None:
        if failures > 0:
            msg = f"Pulse completato: {actions_count} azioni, {failures} fallimenti"
        else:
            msg = f"Pulse completato: {actions_count} azioni, tutto OK"
        await self.send_alert(msg)
