"""
DEPRECATED: use backend.services.compliance.alerts_engine.AlertsEngine instead.

This module is kept as a backward-compat shim. The in-memory alert dict was
removed as part of the 2026-04-18 compliance-intel-e2e PR. All code should
migrate to AlertsEngine + AlertRepository.
"""
from __future__ import annotations

import warnings

from backend.services.compliance.alert_repository import AlertRow as ComplianceAlert  # noqa: F401
from backend.services.compliance.alerts_engine import AlertsEngine  # noqa: F401
from backend.services.compliance.severity_calculator import AlertSeverity  # noqa: F401

warnings.warn(
    "alert_generator.AlertGeneratorService is deprecated; use "
    "backend.services.compliance.alerts_engine.AlertsEngine.",
    DeprecationWarning,
    stacklevel=2,
)


class AlertStatus:
    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    EXPIRED = "expired"


class AlertGeneratorService:  # pragma: no cover — shim
    """Deprecated. Every call emits a DeprecationWarning and raises NotImplementedError."""

    def __init__(self, *args, **kwargs) -> None:
        warnings.warn(
            "AlertGeneratorService is deprecated; use AlertsEngine.",
            DeprecationWarning, stacklevel=2,
        )

    def generate_alert(self, *args, **kwargs):
        raise NotImplementedError("Use AlertsEngine.generate_alerts instead")

    def find_existing_alert(self, *args, **kwargs):
        raise NotImplementedError("Use AlertRepository.find_active_by_dedup_key instead")

    def get_alerts_for_client(self, *args, **kwargs):
        raise NotImplementedError("Use AlertRepository.list_by_client instead")

    def acknowledge_alert(self, *args, **kwargs):
        raise NotImplementedError(
            "Use AlertRepository.update_status(alert_id, new_status='acknowledged')",
        )

    def mark_alert_sent(self, *args, **kwargs):
        raise NotImplementedError(
            "Use AlertRepository.update_status(alert_id, new_status='sent')",
        )

    def get_stats(self) -> dict:
        return {}


__all__ = ["AlertGeneratorService", "AlertStatus", "ComplianceAlert"]
