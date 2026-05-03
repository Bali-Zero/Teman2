"""HGT — Horizontal Gene Transfer for Nuzantara cells.

Enables skill sharing between sibling cells via Redis Streams.
Three components:
- Publisher: broadcasts high-confidence Project skills to cell:skills
- Consumer: subscribes to relevant domains, integrates with decay
- Feedback: child→parent improvement proposals via cell:feedback

All components degrade gracefully if Redis is unavailable.
"""
from cell_core.hgt.domains import CANONICAL_DOMAINS, validate_domain
from cell_core.hgt.publisher import HGTPublisher
from cell_core.hgt.consumer import HGTConsumer
from cell_core.hgt.feedback import VerticalFeedback

__all__ = [
    "CANONICAL_DOMAINS",
    "validate_domain",
    "HGTPublisher",
    "HGTConsumer",
    "VerticalFeedback",
]
