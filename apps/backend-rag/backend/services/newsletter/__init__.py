"""Newsletter — weekly roundup delivery (Sprint 20, design §20, §16.1 #7).

Weekly Monday 06:00 WITA:
    1. WeeklyRoundupBuilder: select 5 public-safe top dossiers + latest brief
    2. Render HTML via existing layout template (Sprint 5: NEWSLETTER)
    3. NewsletterPublisher: POST /api/notifications/send-email with X-API-Key
       (sender locked to zantara@balizero.com — see memory §email_sender)

Subscribers are injected: production wires a CRM query; tests pass mocks.
"""

from backend.services.newsletter.builder import (
    RoundupContent,
    WeeklyRoundupBuilder,
)
from backend.services.newsletter.publisher import (
    NewsletterPublisher,
    NewsletterSendResult,
)

__all__ = [
    "NewsletterPublisher",
    "NewsletterSendResult",
    "RoundupContent",
    "WeeklyRoundupBuilder",
]
