"""
Notification Models
===================
Data models for the notification system.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class AlertType(str, Enum):
    """Types of alerts the system can generate."""

    PASSPORT_WARNING = "passport_warning"  # 13 months
    PASSPORT_CRITICAL = "passport_critical"  # 9 months
    PASSPORT_EXPIRED = "passport_expired"
    VISA_WARNING = "visa_warning"  # 4 months
    VISA_CRITICAL = "visa_critical"  # 2 months
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
    team_leader_email: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    passport_expiry: Optional[datetime] = None
    passport_number: Optional[str] = None
    visa_expiry: Optional[datetime] = None
    visa_type: Optional[str] = None


class ClientAlert(BaseModel):
    """An alert generated for a client."""

    id: Optional[int] = None
    client_id: int
    alert_type: AlertType
    status: AlertStatus = AlertStatus.PENDING
    message: str
    email_subject: str
    email_body: str
    created_at: datetime
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None


class EmailTemplate(BaseModel):
    """Email template for a specific language and alert type."""

    language: str
    alert_type: AlertType
    subject: str
    body_html: str
    body_text: str
    from_name: str = "Bali Zero Team"
    from_email: str = "notifications@balizero.com"


class NotificationResult(BaseModel):
    """Result of a notification send attempt."""

    success: bool
    alert_id: Optional[int] = None
    error_message: Optional[str] = None
    retry_after: Optional[int] = None  # Seconds to wait before retry
