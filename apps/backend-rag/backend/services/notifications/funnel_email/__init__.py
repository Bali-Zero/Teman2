"""Funnel-app drip emails (Visa Clock reminders, Match pre-arrival, etc).

Entry points:
    from backend.services.notifications.funnel_email.scheduler import (
        subscribe_visa_clock,
        subscribe_visa_match_prearrival,
        fire_due,
    )
    from backend.services.notifications.funnel_email.repository import (
        EmailSubscription,
        EmailSubscriptionRepository,
    )
"""

from backend.services.notifications.funnel_email.repository import (
    EmailSubscription,
    EmailSubscriptionRepository,
)
from backend.services.notifications.funnel_email.scheduler import (
    fire_due,
    subscribe_visa_clock,
    subscribe_visa_match_prearrival,
)

__all__ = [
    "EmailSubscription",
    "EmailSubscriptionRepository",
    "fire_due",
    "subscribe_visa_clock",
    "subscribe_visa_match_prearrival",
]
