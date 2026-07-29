"""GARUDA VOA pilot — the guarded flow engine.

The enforceable core of the "VOA as a product" funnel: the deterministic date +
eligibility logic that the Gate-1 role-play validated by hand. Pure functions,
no I/O, no PII, no payment — safe to build and test ahead of the funnel around it.

Entry points:
    from backend.services.garuda_flow import (
        compute_stay, days_until_expiry, is_overstay,
        screen, EligibilityInput, EligibilityResult, Decision,
        build_verdict, CaseType, Purpose, VoaIntakeRequest, VoaVerdict,
        is_open, last_open_day_before,
    )
"""

from backend.services.garuda_flow.eligibility import (
    Decision,
    EligibilityInput,
    EligibilityResult,
    screen,
)
from backend.services.garuda_flow.intake import (
    CaseType,
    Purpose,
    VoaIntakeRequest,
    VoaVerdict,
    build_verdict,
)
from backend.services.garuda_flow.operating_calendar import (
    COVERAGE_END,
    OPERATING_CALENDAR,
    HolidayKind,
    OperatingCalendarDate,
    is_open,
    last_open_day_before,
)
from backend.services.garuda_flow.safe_clock import (
    SafeCheckpoint,
    StayWindow,
    compute_stay,
    days_until_expiry,
    is_overstay,
)

__all__ = [
    "COVERAGE_END",
    "OPERATING_CALENDAR",
    "CaseType",
    "Decision",
    "EligibilityInput",
    "EligibilityResult",
    "HolidayKind",
    "OperatingCalendarDate",
    "Purpose",
    "SafeCheckpoint",
    "StayWindow",
    "VoaIntakeRequest",
    "VoaVerdict",
    "build_verdict",
    "compute_stay",
    "days_until_expiry",
    "is_open",
    "is_overstay",
    "last_open_day_before",
    "screen",
]
