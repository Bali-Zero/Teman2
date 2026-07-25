"""GARUDA VOA pilot — intake eligibility screen (pure, no I/O).

A faithful, auditable encoding of SOP-v0-GARUDA-B1 §1 segmentation:

    ACCEPT only if ALL true: eligible nationality/entry · simple tourism ·
    1 adult traveler · clean ordinary passport (>=6 months validity) · at
    least D-10 of runway (extension case) · self-pay · willing to give
    anonymous feedback.

    EXCLUDE (decline politely, log reason): urgent · families/groups ·
    special passports · work/business purpose · prior overstay/refusal/
    blacklist · airport fast-lane requests · extension below D-10.

The screen collects EVERY failing reason (never short-circuits) so the case
sheet can log a complete "why declined" — SOP §1 "decline politely, log reason".
The D-10 gate is the enforceable version of the Gate-1 SIM-2 criterion that was
"not testable" on 2026-07-20 because the threshold did not yet exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.services.garuda_flow.constants import PILOT_INTAKE_THRESHOLD_DAYS


class Decision(str, Enum):
    ACCEPT = "ACCEPT"
    DECLINE = "DECLINE"


@dataclass(frozen=True)
class EligibilityInput:
    """Structured intake for the pilot eligibility screen.

    ``is_extension`` distinguishes a fresh VOA issuance (the D-10 runway gate
    does not apply) from an extension case (it does). ``days_until_expiry`` is
    required for an extension case and ignored otherwise.
    """

    # ── Must ALL be true to ACCEPT (SOP §1 positive criteria) ──
    nationality_entry_eligible: bool
    simple_tourism: bool
    single_adult_traveler: bool
    clean_ordinary_passport: bool
    passport_valid_6mo_from_entry: bool
    self_pay: bool
    willing_anonymous_feedback: bool

    # ── Case shape ──
    is_extension: bool
    days_until_expiry: int | None = None  # required iff is_extension

    # ── Any true → EXCLUDE (SOP §1 exclusion signals) ──
    urgent_case: bool = False
    family_or_group: bool = False
    special_passport: bool = False
    work_or_business_purpose: bool = False
    prior_overstay_refusal_blacklist: bool = False
    wants_airport_fastlane: bool = False


@dataclass(frozen=True)
class EligibilityResult:
    decision: Decision
    decline_reasons: list[str] = field(default_factory=list)  # empty ⇔ ACCEPT

    @property
    def accepted(self) -> bool:
        return self.decision is Decision.ACCEPT


def screen(inp: EligibilityInput) -> EligibilityResult:
    """Apply the SOP §1 pilot intake screen; return decision + all reasons."""
    reasons: list[str] = []

    # ── Positive criteria (all must hold) ──
    if not inp.nationality_entry_eligible:
        reasons.append("nationality or entry point not eligible for VOA")
    if not inp.simple_tourism:
        reasons.append("not a simple-tourism case")
    if not inp.single_adult_traveler:
        reasons.append("not a single adult traveler")
    if not inp.clean_ordinary_passport:
        reasons.append("not a clean ordinary passport")
    if not inp.passport_valid_6mo_from_entry:
        reasons.append("passport not valid >= 6 months from entry")
    if not inp.self_pay:
        reasons.append("not self-pay")
    if not inp.willing_anonymous_feedback:
        reasons.append("not willing to give anonymous feedback")

    # ── Exclusion signals (any triggers a decline) ──
    if inp.urgent_case:
        reasons.append("urgent case (excluded from pilot)")
    if inp.family_or_group:
        reasons.append("family/group case (excluded from pilot)")
    if inp.special_passport:
        reasons.append("special passport (excluded from pilot)")
    if inp.work_or_business_purpose:
        reasons.append("work/business purpose (B1 does not permit work)")
    if inp.prior_overstay_refusal_blacklist:
        reasons.append("prior overstay/refusal/blacklist (excluded from pilot)")
    if inp.wants_airport_fastlane:
        reasons.append("airport fast-lane request (excluded from pilot)")

    # ── D-10 runway gate (extension cases only) ──
    if inp.is_extension:
        if inp.days_until_expiry is None:
            reasons.append("extension case missing days-until-expiry (cannot verify D-10 runway)")
        elif inp.days_until_expiry < PILOT_INTAKE_THRESHOLD_DAYS:
            reasons.append(
                f"below D-{PILOT_INTAKE_THRESHOLD_DAYS} pilot threshold "
                f"({inp.days_until_expiry} days to expiry) — hand off to the ordinary channel"
            )

    decision = Decision.ACCEPT if not reasons else Decision.DECLINE
    return EligibilityResult(decision=decision, decline_reasons=reasons)


__all__ = [
    "Decision",
    "EligibilityInput",
    "EligibilityResult",
    "screen",
]
