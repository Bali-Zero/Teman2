"""Visa Check app (homepage) — Clock + Match branches.

Exports
-------
    VisaCheckRepository         persistence
    VisaClockResult             shape returned by /api/visa/clock
    VisaMatchResult             shape returned by /api/visa/match
    clock_timeline              deterministic 5-checkpoint builder
    recommend_visa              match decision tree
    estimate_match_cost         PricingTool bridge (read-only)
"""

from backend.services.visa_check.clock import clock_timeline
from backend.services.visa_check.match_tree import recommend_visa
from backend.services.visa_check.pricing_bridge import estimate_match_cost
from backend.services.visa_check.repository import (
    VisaCheckRepository,
    VisaClockResult,
    VisaMatchResult,
)

__all__ = [
    "VisaCheckRepository",
    "VisaClockResult",
    "VisaMatchResult",
    "clock_timeline",
    "recommend_visa",
    "estimate_match_cost",
]
