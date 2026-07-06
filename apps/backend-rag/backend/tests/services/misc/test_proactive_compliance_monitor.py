from __future__ import annotations

import warnings
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from backend.services.compliance import AlertSeverity, ComplianceType
    from backend.services.compliance.alert_generator import AlertStatus
    from backend.services.misc.proactive_compliance_monitor import ProactiveComplianceMonitor


def _future_deadline(days: int) -> str:
    return (datetime.now(tz=timezone.utc) + timedelta(days=days)).isoformat()


def test_add_visa_expiry_tracks_item_metadata_and_stats() -> None:
    monitor = ProactiveComplianceMonitor()

    item = monitor.add_visa_expiry(
        client_id="client-1",
        visa_type="KITAS",
        expiry_date=_future_deadline(45),
        passport_number="P123456",
    )

    assert item.item_id in monitor.compliance_items
    assert item.client_id == "client-1"
    assert item.compliance_type == ComplianceType.VISA_EXPIRY.value
    assert item.title == "KITAS Expiry"
    assert item.metadata == {"visa_type": "KITAS", "passport_number": "P123456"}

    stats = monitor.get_monitor_stats()
    assert stats["total_items_tracked"] == 1
    assert stats["active_items"] == 1
    assert stats["compliance_type_distribution"] == {"visa_expiry": 1}


def test_add_annual_tax_deadline_uses_template_and_rejects_unknown_type() -> None:
    monitor = ProactiveComplianceMonitor()

    item = monitor.add_annual_tax_deadline(
        client_id="client-1",
        deadline_type="spt_tahunan_individual",
        year=2027,
    )

    assert item.compliance_type == ComplianceType.TAX_FILING.value
    assert item.title == "SPT Tahunan (Individual Tax Return) - 2027"
    assert item.deadline.startswith("2027-03-31")
    assert item.metadata == {"deadline_type": "spt_tahunan_individual", "tax_year": 2027}

    with pytest.raises(ValueError, match="Unknown deadline type"):
        monitor.add_annual_tax_deadline("client-1", "missing_template", 2027)


def test_calculate_severity_and_generate_alert_dicts() -> None:
    monitor = ProactiveComplianceMonitor()
    item = monitor.add_compliance_item(
        client_id="client-1",
        compliance_type=ComplianceType.DOCUMENT_EXPIRY,
        title="Passport Renewal",
        deadline=_future_deadline(5),
        description="Renew passport before visa extension.",
    )

    severity, days_until = monitor.calculate_severity(item.deadline)
    alerts = monitor.generate_alerts()

    assert severity == AlertSeverity.URGENT
    assert 3 <= days_until <= 5
    assert alerts == [
        {
            "alert_id": f"alert_{item.item_id}",
            "client_id": "client-1",
            "compliance_type": ComplianceType.DOCUMENT_EXPIRY.value,
            "title": "Passport Renewal",
            "description": "Renew passport before visa extension.",
            "deadline": item.deadline,
            "days_until": days_until,
            "severity": AlertSeverity.URGENT.value,
            "status": "active",
            "created_at": alerts[0]["created_at"],
        },
    ]
    assert datetime.fromisoformat(alerts[0]["created_at"]).tzinfo is not None


@pytest.mark.asyncio
async def test_send_alert_delegates_to_notification_service_and_counts_success() -> None:
    class FakeNotificationService:
        def __init__(self) -> None:
            self.calls: list[dict[str, str]] = []

        async def send(self, *, client_id: str, message: str, via: str) -> bool:
            self.calls.append({"client_id": client_id, "message": message, "via": via})
            return True

    fake_notifications = FakeNotificationService()
    monitor = ProactiveComplianceMonitor(notification_service=fake_notifications)
    monitor.alerts["alert-1"] = SimpleNamespace(
        client_id="client-1",
        message="Renew KITAS this week",
        compliance_item_id="item-1",
        status=AlertStatus.PENDING,
    )

    assert await monitor.send_alert("alert-1", via="email") is True
    assert await monitor.send_alert("missing-alert", via="email") is False
    assert fake_notifications.calls == [
        {
            "client_id": "client-1",
            "message": "Renew KITAS this week",
            "via": "email",
        },
    ]
    assert monitor.monitor_stats["alerts_sent"] == 1


def test_resolve_compliance_item_removes_active_item_and_marks_related_alerts() -> None:
    monitor = ProactiveComplianceMonitor()
    item = monitor.add_compliance_item(
        client_id="client-1",
        compliance_type="visa_expiry",
        title="KITAS",
        deadline=_future_deadline(15),
    )
    monitor.alerts["alert-1"] = SimpleNamespace(
        compliance_item_id=item.item_id,
        status=AlertStatus.PENDING,
    )

    assert monitor.resolve_compliance_item(item.item_id) is True
    assert item.item_id not in monitor.compliance_items
    assert monitor.alerts["alert-1"].status == AlertStatus.RESOLVED
    assert monitor.monitor_stats["active_items"] == 0
    assert monitor.resolve_compliance_item("missing-item") is False


def test_upcoming_deadlines_filter_by_client_and_alert_shim_is_safe() -> None:
    monitor = ProactiveComplianceMonitor()
    first = monitor.add_compliance_item(
        client_id="client-1",
        compliance_type="visa_expiry",
        title="First",
        deadline=_future_deadline(10),
    )
    monitor.add_compliance_item(
        client_id="client-2",
        compliance_type="visa_expiry",
        title="Second",
        deadline=_future_deadline(10),
    )

    upcoming = monitor.get_upcoming_deadlines(client_id="client-1", days_ahead=30)

    assert upcoming == [first]
    assert monitor.get_alerts_for_client("client-1") == []
    assert monitor.acknowledge_alert("missing-alert") is False
