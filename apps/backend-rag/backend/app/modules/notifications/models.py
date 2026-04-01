"""
Notification Models
===================
Data models for the notification system.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class AlertType(str, Enum):
    """Types of alerts the system can generate."""

    PASSPORT_WARNING = "passport_warning"  # 13 months
    PASSPORT_CRITICAL = "passport_critical"  # 9 months
    PASSPORT_EXPIRED = "passport_expired"
    VISA_WARNING = "visa_warning"  # 4 months
    VISA_CRITICAL = "visa_critical"  # 2 months
    VISA_EMERGENCY = "visa_emergency"  # 7 days — multi-channel blast
    VISA_EXPIRED = "visa_expired"
    BIRTHDAY = "birthday"


class AlertStatus(str, Enum):
    """Status of an alert in the system."""

    PENDING = "pending"  # Generated but not sent
    SENT = "sent"  # Email sent successfully
    FAILED = "failed"  # Email failed to send
    SUPPRESSED = "suppressed"  # Rate limited or opted out


class ClientInfo(BaseModel):
    """Client information needed for notifications."""

    id: int
    email: str
    full_name: str
    preferred_language: str = "en"  # ISO 639-1 code
    team_leader_email: str | None = None
    date_of_birth: datetime | None = None
    passport_expiry: datetime | None = None
    passport_number: str | None = None
    visa_expiry: datetime | None = None
    visa_type: str | None = None


class ClientAlert(BaseModel):
    """An alert generated for a client."""

    id: int | None = None
    client_id: int
    alert_type: AlertType
    status: AlertStatus = AlertStatus.PENDING
    message: str
    email_subject: str
    email_body: str
    created_at: datetime
    sent_at: datetime | None = None
    error_message: str | None = None
    retry_count: int = 0


class NotificationResult(BaseModel):
    """Result of a notification send attempt."""

    success: bool
    alert_id: int | None = None
    error_message: str | None = None
    retry_after: int | None = None  # Seconds to wait before retry
