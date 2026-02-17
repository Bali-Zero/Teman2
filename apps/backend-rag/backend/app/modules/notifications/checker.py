"""
Expiry Checker
==============
Logic for checking passport, visa, and birthday alerts.

Scheduling:
- Runs daily at 9:00 AM Bali time (UTC+8)
- Can be triggered manually via API
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from .models import (
    AlertType,
    ClientInfo,
    ClientAlert,
    AlertStatus,
)
from .templates import get_template, format_template, INDONESIAN_BLESSINGS
import random

logger = logging.getLogger(__name__)


class ExpiryChecker:
    """Checks client data for expiring documents and birthdays."""

    # Alert thresholds
    PASSPORT_WARNING_MONTHS = 13
    PASSPORT_CRITICAL_MONTHS = 9
    VISA_WARNING_DAYS = 120  # ~4 months
    VISA_CRITICAL_DAYS = 60  # ~2 months

    def __init__(self):
        self.today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    def check_all_clients(self, clients: List[ClientInfo]) -> List[ClientAlert]:
        """Check all clients and return list of alerts to send."""
        alerts = []

        for client in clients:
            client_alerts = self.check_client(client)
            alerts.extend(client_alerts)

        logger.info(
            "Expiry check completed",
            extra={
                "total_clients": len(clients),
                "total_alerts": len(alerts),
            },
        )

        return alerts

    def check_client(self, client: ClientInfo) -> List[ClientAlert]:
        """Check a single client for all alert conditions."""
        alerts = []

        # Check passport
        passport_alert = self._check_passport(client)
        if passport_alert:
            alerts.append(passport_alert)

        # Check visa
        visa_alert = self._check_visa(client)
        if visa_alert:
            alerts.append(visa_alert)

        # Check birthday
        birthday_alert = self._check_birthday(client)
        if birthday_alert:
            alerts.append(birthday_alert)

        return alerts

    def _check_passport(self, client: ClientInfo) -> Optional[ClientAlert]:
        """Check passport expiry and generate alert if needed."""
        if not client.passport_expiry:
            return None

        expiry = client.passport_expiry.replace(tzinfo=None)
        months_until = self._months_between(self.today, expiry)

        # Determine alert type
        if expiry < self.today:
            alert_type = AlertType.PASSPORT_EXPIRED
        elif months_until <= self.PASSPORT_CRITICAL_MONTHS:
            alert_type = AlertType.PASSPORT_CRITICAL
        elif months_until <= self.PASSPORT_WARNING_MONTHS:
            alert_type = AlertType.PASSPORT_WARNING
        else:
            return None

        return self._create_alert(
            client=client,
            alert_type=alert_type,
            months_remaining=max(0, int(months_until)),
            expiry_date=expiry.strftime("%d %B %Y"),
        )

    def _check_visa(self, client: ClientInfo) -> Optional[ClientAlert]:
        """Check visa expiry and generate alert if needed."""
        if not client.visa_expiry:
            return None

        expiry = client.visa_expiry.replace(tzinfo=None)
        days_until = (expiry - self.today).days

        # Determine alert type
        if expiry < self.today:
            alert_type = AlertType.VISA_EXPIRED
        elif days_until <= self.VISA_CRITICAL_DAYS:
            alert_type = AlertType.VISA_CRITICAL
        elif days_until <= self.VISA_WARNING_DAYS:
            alert_type = AlertType.VISA_WARNING
        else:
            return None

        return self._create_alert(
            client=client,
            alert_type=alert_type,
            days_remaining=max(0, days_until),
            expiry_date=expiry.strftime("%d %B %Y"),
            visa_type=client.visa_type or "Current",
        )

    def _check_birthday(self, client: ClientInfo) -> Optional[ClientAlert]:
        """Check if today is client's birthday."""
        if not client.date_of_birth:
            return None

        dob = client.date_of_birth.replace(tzinfo=None)

        # Check if today matches birthday (month and day)
        if self.today.month == dob.month and self.today.day == dob.day:
            return self._create_alert(
                client=client,
                alert_type=AlertType.BIRTHDAY,
                indonesian_blessing=random.choice(INDONESIAN_BLESSINGS),
            )

        return None

    def _create_alert(
        self,
        client: ClientInfo,
        alert_type: AlertType,
        **kwargs,
    ) -> ClientAlert:
        """Create a ClientAlert with appropriate email content."""
        template = get_template(client.preferred_language, alert_type)

        # Prepare template variables
        template_vars = {
            "full_name": client.full_name,
            **kwargs,
        }

        subject = format_template(template["subject"], **template_vars)
        body = format_template(template["body"], **template_vars)

        return ClientAlert(
            client_id=client.id,
            alert_type=alert_type,
            status=AlertStatus.PENDING,
            message=f"{alert_type.value} alert for {client.full_name}",
            email_subject=subject,
            email_body=body,
            created_at=datetime.now(),
        )

    @staticmethod
    def _months_between(start: datetime, end: datetime) -> float:
        """Calculate months between two dates."""
        months = (end.year - start.year) * 12 + (end.month - start.month)
        # Adjust for day of month
        if end.day < start.day:
            months -= 1
        return max(0, months)


class AlertDeduplicator:
    """Prevents duplicate alerts from being sent."""

    def __init__(self, db_pool):
        self.db_pool = db_pool

    async def should_send_alert(
        self,
        client_id: int,
        alert_type: AlertType,
        min_days_between: int = 7,
    ) -> bool:
        """
        Check if alert should be sent based on last sent time.
        Returns True if enough time has passed since last alert.
        """
        async with self.db_pool.acquire() as conn:
            last_alert = await conn.fetchval(
                """
                SELECT MAX(sent_at) 
                FROM notification_alerts 
                WHERE client_id = $1 
                AND alert_type = $2 
                AND status = 'sent'
                """,
                client_id,
                alert_type.value,
            )

            if not last_alert:
                return True

            days_since = (datetime.now() - last_alert).days
            return days_since >= min_days_between

    async def mark_alert_sent(self, alert_id: int):
        """Mark an alert as sent in the database."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE notification_alerts 
                SET status = 'sent', sent_at = NOW() 
                WHERE id = $1
                """,
                alert_id,
            )
