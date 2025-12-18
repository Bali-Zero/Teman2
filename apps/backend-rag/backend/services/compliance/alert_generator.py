"""
Alert Generator Service
Responsibility: Generate compliance alerts
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from services.compliance.compliance_tracker import ComplianceItem
from services.compliance.severity_calculator import AlertSeverity

logger = logging.getLogger(__name__)


class AlertStatus(str, Enum):
    """Alert status"""

    PENDING = "pending"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    EXPIRED = "expired"


@dataclass
class ComplianceAlert:
    """Alert for upcoming compliance deadline"""

    alert_id: str
    compliance_item_id: str
    client_id: str
    severity: AlertSeverity
    title: str
    message: str
    deadline: str
    days_until_deadline: int
    action_required: str
    estimated_cost: float | None = None
    status: AlertStatus = AlertStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    sent_at: str | None = None
    acknowledged_at: str | None = None


class AlertGeneratorService:
    """
    Service for generating compliance alerts.

    Responsibility: Generate alerts from compliance items.
    """

    def __init__(self):
        """Initialize alert generator service."""
        self.alerts: dict[str, ComplianceAlert] = {}
        self.generator_stats = {
            "alerts_generated": 0,
            "alerts_sent": 0,
        }

    def generate_alert(
        self, item: ComplianceItem, severity: AlertSeverity, days_until: int
    ) -> ComplianceAlert:
        """
        Generate alert from compliance item.

        Args:
            item: ComplianceItem instance
            severity: Alert severity level
            days_until: Days until deadline

        Returns:
            ComplianceAlert instance
        """
        alert_id = f"alert_{item.item_id}_{severity.value}_{int(datetime.now().timestamp())}"

        # Generate message based on severity
        if severity == AlertSeverity.CRITICAL:
            message = f"⚠️ OVERDUE: {item.title} was due on {item.deadline}"
            action = "URGENT ACTION REQUIRED - Contact Bali Zero immediately"
        elif severity == AlertSeverity.URGENT:
            message = f"🚨 URGENT: {item.title} is due in {days_until} days"
            action = "Start renewal process immediately"
        elif severity == AlertSeverity.WARNING:
            message = f"⚠️ REMINDER: {item.title} is due in {days_until} days"
            action = "Prepare required documents and schedule appointment"
        else:
            message = f"ℹ️ UPCOMING: {item.title} is due in {days_until} days"
            action = "Review requirements and plan ahead"

        # Add cost info if available
        if item.estimated_cost:
            message += f"\nEstimated cost: Rp {item.estimated_cost:,.0f}"

        # Add document requirements
        if item.required_documents:
            message += "\nRequired documents:\n"
            for doc in item.required_documents[:5]:  # Top 5
                message += f"  • {doc}\n"

        alert = ComplianceAlert(
            alert_id=alert_id,
            compliance_item_id=item.item_id,
            client_id=item.client_id,
            severity=severity,
            title=f"{severity.value.upper()}: {item.title}",
            message=message,
            deadline=item.deadline,
            days_until_deadline=days_until,
            action_required=action,
            estimated_cost=item.estimated_cost,
        )

        self.alerts[alert_id] = alert
        self.generator_stats["alerts_generated"] += 1

        return alert

    def find_existing_alert(
        self, compliance_item_id: str, severity: AlertSeverity
    ) -> ComplianceAlert | None:
        """
        Find existing alert for item at severity level.

        Args:
            compliance_item_id: Compliance item identifier
            severity: Severity level

        Returns:
            ComplianceAlert instance or None
        """
        for alert in self.alerts.values():
            if (
                alert.compliance_item_id == compliance_item_id
                and alert.severity == severity
                and alert.status != AlertStatus.EXPIRED
            ):
                return alert
        return None

    def get_alerts_for_client(
        self, client_id: str, status_filter: AlertStatus | None = None
    ) -> list[ComplianceAlert]:
        """
        Get alerts for a specific client.

        Args:
            client_id: Client identifier
            status_filter: Optional status filter

        Returns:
            List of alerts
        """
        alerts = [alert for alert in self.alerts.values() if alert.client_id == client_id]

        if status_filter:
            alerts = [a for a in alerts if a.status == status_filter]

        # Sort by severity (critical first)
        severity_order = [
            AlertSeverity.CRITICAL,
            AlertSeverity.URGENT,
            AlertSeverity.WARNING,
            AlertSeverity.INFO,
        ]
        alerts.sort(key=lambda x: severity_order.index(x.severity))

        return alerts

    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Mark alert as acknowledged.

        Args:
            alert_id: Alert identifier

        Returns:
            True if acknowledged
        """
        alert = self.alerts.get(alert_id)
        if not alert:
            return False

        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.now().isoformat()

        logger.info(f"✅ Alert acknowledged: {alert_id}")
        return True

    def mark_alert_sent(self, alert_id: str) -> bool:
        """
        Mark alert as sent.

        Args:
            alert_id: Alert identifier

        Returns:
            True if marked
        """
        alert = self.alerts.get(alert_id)
        if not alert:
            return False

        alert.status = AlertStatus.SENT
        alert.sent_at = datetime.now().isoformat()
        self.generator_stats["alerts_sent"] += 1

        return True

    def get_stats(self) -> dict:
        """Get generator statistics."""
        return self.generator_stats
