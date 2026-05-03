"""
Notifications Module
====================
Automated email notification system for:
- Passport expiry alerts (13 months warning, 9 months critical)
- Visa expiry alerts (2 months critical)
- Birthday greetings

Following @ai_onboarding philosophy:
- Clean separation of concerns
- Type hints throughout
- Comprehensive logging
- Configurable via environment variables
- Rate limiting and retry logic
"""

from .checker import ExpiryChecker
from .models import AlertStatus, AlertType, ClientAlert
from .service import NotificationService

__all__ = [
    "NotificationService",
    "ExpiryChecker",
    "AlertType",
    "AlertStatus",
    "ClientAlert",
]
