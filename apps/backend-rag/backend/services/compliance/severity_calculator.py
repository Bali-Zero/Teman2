"""
Severity Calculator Service
Responsibility: Calculate alert severity
"""

import logging
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels"""

    INFO = "info"  # >60 days
    WARNING = "warning"  # 30-60 days
    URGENT = "urgent"  # 7-30 days
    CRITICAL = "critical"  # <7 days or overdue


class SeverityCalculatorService:
    """
    Service for calculating alert severity.

    Responsibility: Calculate alert severity based on days until deadline.
    """

    # Alert thresholds (days before deadline)
    ALERT_THRESHOLDS = {
        AlertSeverity.INFO: 60,
        AlertSeverity.WARNING: 30,
        AlertSeverity.URGENT: 7,
        AlertSeverity.CRITICAL: 0,  # Overdue
    }

    def calculate_severity(self, deadline: str) -> tuple[AlertSeverity, int]:
        """
        Calculate alert severity based on days until deadline.

        Args:
            deadline: Deadline date (ISO)

        Returns:
            Tuple of (severity, days_until_deadline)
        """
        deadline_date = datetime.fromisoformat(deadline.replace("Z", ""))
        now = datetime.now()
        days_until = (deadline_date - now).days

        if days_until < 0:
            return AlertSeverity.CRITICAL, days_until
        elif days_until <= self.ALERT_THRESHOLDS[AlertSeverity.URGENT]:
            return AlertSeverity.URGENT, days_until
        elif days_until <= self.ALERT_THRESHOLDS[AlertSeverity.WARNING]:
            return AlertSeverity.WARNING, days_until
        else:
            return AlertSeverity.INFO, days_until

    def get_days_until_deadline(self, deadline: str) -> int:
        """
        Get days until deadline.

        Args:
            deadline: Deadline date (ISO)

        Returns:
            Days until deadline (negative if overdue)
        """
        deadline_date = datetime.fromisoformat(deadline.replace("Z", ""))
        now = datetime.now()
        return (deadline_date - now).days
