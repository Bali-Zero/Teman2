"""GARUDA VOA pilot — the guarded flow engine.

The enforceable core of the "VOA as a product" funnel: the deterministic date +
eligibility logic that the Gate-1 role-play validated by hand. Pure functions,
no I/O, no PII, no payment — safe to build and test ahead of the funnel around it.

Entry points:
    from backend.services.garuda_flow import (
        compute_stay, days_until_expiry, is_overstay,
        screen, EligibilityInput, EligibilityResult, Decision,
    )
"""

from backend.services.garuda_flow.eligibility import (
    Decision,
    EligibilityInput,
    EligibilityResult,
    screen,
)
from backend.services.garuda_flow.safe_clock import (
    SafeCheckpoint,
    StayWindow,
    compute_stay,
    days_until_expiry,
    is_overstay,
)

__all__ = [
    "Decision",
    "EligibilityInput",
    "EligibilityResult",
    "SafeCheckpoint",
    "StayWindow",
    "compute_stay",
    "days_until_expiry",
    "is_overstay",
    "screen",
]
