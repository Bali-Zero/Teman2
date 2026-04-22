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
    """Deprecated. Methods are no-ops returning safe defaults.

    New code: use backend.services.compliance.alerts_engine.AlertsEngine.
    """

    def __init__(self, *args, **kwargs) -> None:
        warnings.warn(
            "AlertGeneratorService is deprecated; use AlertsEngine. "
            "Calls are now no-ops returning safe defaults.",
            DeprecationWarning, stacklevel=2,
        )
        # Backward-compat attribute accessed by ProactiveComplianceMonitor
        self.alerts: dict = {}

    def generate_alert(self, *args, **kwargs) -> None:
        warnings.warn(
            "AlertGeneratorService.generate_alert is a deprecated no-op; "
            "use AlertsEngine.generate_alerts(forecasts).",
            DeprecationWarning, stacklevel=2,
        )
        return None

    def find_existing_alert(self, *args, **kwargs) -> None:
        warnings.warn(
            "AlertGeneratorService.find_existing_alert is a deprecated no-op; "
            "use AlertRepository.find_active_by_dedup_key.",
            DeprecationWarning, stacklevel=2,
        )
        return None

    def get_alerts_for_client(self, *args, **kwargs) -> list:
        warnings.warn(
            "AlertGeneratorService.get_alerts_for_client is a deprecated no-op; "
            "use AlertRepository.list_by_client.",
            DeprecationWarning, stacklevel=2,
        )
        return []

    def acknowledge_alert(self, *args, **kwargs) -> bool:
        warnings.warn(
            "AlertGeneratorService.acknowledge_alert is a deprecated no-op; "
            "use AlertRepository.update_status(alert_id, new_status='acknowledged').",
            DeprecationWarning, stacklevel=2,
        )
        return False

    def mark_alert_sent(self, *args, **kwargs) -> bool:
        warnings.warn(
            "AlertGeneratorService.mark_alert_sent is a deprecated no-op; "
            "use AlertRepository.update_status(alert_id, new_status='sent').",
            DeprecationWarning, stacklevel=2,
        )
        return False

    def get_stats(self) -> dict:
        return {}


__all__ = ["AlertGeneratorService", "AlertStatus", "ComplianceAlert"]
