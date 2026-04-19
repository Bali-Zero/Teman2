"""Rule-based visa recommender for the Visa Match wizard.

Input: nationality (ISO-3), purpose, duration_months, budget_band.
Output: recommended_visa + reason + 0-2 alternatives + pre-arrival steps.

The tree is intentionally visible and deterministic (no ML). Each rule
prints its own reason so users see *why* a visa was picked. Every
branch terminates with a valid VisaType or a catch-all referral.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.services.visa_check.catalogue import VisaType


class Purpose(str, Enum):
    WORK_REMOTE = "work_remote"
    INVESTOR = "investor"
    WORK_EMPLOYEE = "work_employee"
    FAMILY = "family"
    LONG_TOURISM = "long_tourism"
    RETIREMENT = "retirement"
    STUDENT = "student"
    OTHER = "other"


class BudgetBand(str, Enum):
    UNDER_50M = "under_50m"       # < IDR 50M
    MID_50_500M = "50m_500m"      # IDR 50M–500M
    OVER_500M = "over_500m"       # > IDR 500M


@dataclass(frozen=True)
class MatchResult:
    recommended_visa: VisaType | None       # None → referral (catch-all)
    reason: str                              # 1-3 sentences, X_BRAND_VOICE
    alternatives: list[VisaType]             # 0-2 additional picks
    pre_arrival_steps: list[str]             # 4-6 short action items
    referral_mode: bool                      # True → show WA CTA, skip result


# ------------------------------------------------------------------
# Pre-arrival step libraries — reused across multiple leaf rules.
# ------------------------------------------------------------------

_STEPS_TOURISM: list[str] = [
    "Passport valid ≥ 6 months from entry date",
    "Confirmed accommodation for first 7 nights",
    "Return or onward flight ticket",
    "Travel insurance covering Indonesia",
]

_STEPS_DIGITAL_NOMAD: list[str] = [
    "Proof of remote employment with a foreign company",
    "Bank statement showing ≥ USD 60,000 balance (12 months)",
    "Passport valid ≥ 18 months",
    "Health insurance with Indonesia coverage",
    "CV + LinkedIn URL for immigration review",
]

_STEPS_INVESTOR: list[str] = [
    "PT PMA incorporated (or plan ready to incorporate on arrival)",
    "Investment plan document (IDR equivalent ≥ 10bn for E28A)",
    "Share capital confirmation",
    "Proposed business address in Indonesia",
    "Passport valid ≥ 24 months",
]

_STEPS_EMPLOYEE: list[str] = [
    "RPTKA from sponsoring Indonesian employer",
    "Signed employment contract",
    "Education certificate (notarised + translated)",
    "Curriculum vitae",
    "Passport valid ≥ 18 months",
]

_STEPS_RETIREMENT: list[str] = [
    "Proof of pension or passive income ≥ USD 1,500/month",
    "Passport valid ≥ 18 months",
    "Proof of accommodation (rental or property in Indonesia)",
    "Domestic helper hire letter (optional but recommended)",
    "Health insurance valid in Indonesia",
]

_STEPS_FAMILY: list[str] = [
    "Sponsor's KITAS/KITAP + passport copies",
    "Marriage or birth certificate (notarised + translated)",
    "Passport valid ≥ 18 months",
    "Proof of joint household (photos + rental/ownership docs)",
]

_STEPS_STUDENT: list[str] = [
    "Acceptance letter from an accredited Indonesian university",
    "Sponsor letter (university or direct bursary)",
    "Passport valid ≥ the full study programme",
    "Health insurance valid in Indonesia",
]


# ------------------------------------------------------------------
# Main rule dispatcher.
# ------------------------------------------------------------------


def recommend_visa(
    *,
    nationality: str,
    purpose: Purpose,
    duration_months: int,
    budget_band: BudgetBand,
) -> MatchResult:
    """Return the recommended visa for a planning user.

    The order of rules matters: earlier matches win. Catch-all at the
    bottom defers to the team via WhatsApp instead of guessing.

    `nationality` is accepted but not yet consulted — it shapes API
    stability for a future visa-waiver / reciprocal-agreement rule pass
    (e.g. ASEAN nationals need no tourist visa for short stays).
    """
    del nationality  # reserved for future rules, see docstring above
    # Normalise for safety (pydantic should have already done this).
    duration = max(1, min(60, int(duration_months)))

    # ── OTHER / not sure: do not invent — hand off directly. ──
    if purpose == Purpose.OTHER:
        return MatchResult(
            recommended_visa=None,
            reason=(
                "Your case has specifics we don't capture in a 4-step form. "
                "A 15-minute WhatsApp review with our visa team is faster than "
                "any guess we could make here."
            ),
            alternatives=[],
            pre_arrival_steps=[],
            referral_mode=True,
        )

    # ── LONG_TOURISM ──
    if purpose == Purpose.LONG_TOURISM:
        if duration <= 2:
            return MatchResult(
                recommended_visa=VisaType.C1,
                reason=(
                    f"For a {duration}-month visit, C1 Tourism (60 days, "
                    "extendable twice × 60 days) covers you up to 180 days total."
                ),
                alternatives=[VisaType.B211A],
                pre_arrival_steps=_STEPS_TOURISM,
                referral_mode=False,
            )
        if duration <= 6:
            return MatchResult(
                recommended_visa=VisaType.B211A,
                reason=(
                    f"For {duration} months of tourism, B211A (up to 180 days "
                    "with one extension) is the standard pick."
                ),
                alternatives=[VisaType.C1],
                pre_arrival_steps=_STEPS_TOURISM,
                referral_mode=False,
            )
        # > 6 months of "tourism" → the law doesn't support it.
        return MatchResult(
            recommended_visa=None,
            reason=(
                f"Indonesia's tourism visas max out at ~180 days. For a "
                f"{duration}-month stay, we need to pick a non-tourism route "
                "(investor, digital nomad, retirement) that matches what you "
                "actually plan to do here."
            ),
            alternatives=[],
            pre_arrival_steps=[],
            referral_mode=True,
        )

    # ── WORK_REMOTE ──
    if purpose == Purpose.WORK_REMOTE:
        if budget_band == BudgetBand.UNDER_50M:
            return MatchResult(
                recommended_visa=VisaType.B211A,
                reason=(
                    "E33G Digital Nomad KITAS requires proof of ≥ USD 60k in "
                    "savings. With your current budget, B211A is the realistic "
                    "short-term option; you can upgrade to E33G once the savings "
                    "threshold is met."
                ),
                alternatives=[VisaType.E33G],
                pre_arrival_steps=_STEPS_TOURISM,
                referral_mode=False,
            )
        return MatchResult(
            recommended_visa=VisaType.E33G,
            reason=(
                "E33G (Digital Nomad / Remote Worker KITAS) is the correct route "
                "for paid work performed for a foreign employer from Indonesia. "
                "Valid one year, renewable once."
            ),
            alternatives=[VisaType.B211A],
            pre_arrival_steps=_STEPS_DIGITAL_NOMAD,
            referral_mode=False,
        )

    # ── INVESTOR ──
    if purpose == Purpose.INVESTOR:
        if budget_band == BudgetBand.OVER_500M:
            return MatchResult(
                recommended_visa=VisaType.E28A,
                reason=(
                    "E28A Investor KITAS (2 years) fits a ≥ IDR 500M investor "
                    "profile. Requires a PT PMA and a formal investment plan."
                ),
                alternatives=[VisaType.E33G],
                pre_arrival_steps=_STEPS_INVESTOR,
                referral_mode=False,
            )
        if budget_band == BudgetBand.MID_50_500M:
            return MatchResult(
                recommended_visa=VisaType.E33G,
                reason=(
                    "With IDR 50M–500M, E28A investor KITAS is usually "
                    "out of reach (min-investment rules). E33G gives you legal "
                    "residency to build the PT PMA before escalating to E28A."
                ),
                alternatives=[VisaType.E28A, VisaType.B211A],
                pre_arrival_steps=_STEPS_DIGITAL_NOMAD,
                referral_mode=False,
            )
        # UNDER_50M investor: realistic routing is advisory.
        return MatchResult(
            recommended_visa=None,
            reason=(
                "Investor routes (E28A/E33G) have minimum-capital and savings "
                "requirements that a sub-IDR 50M budget does not meet. Let's "
                "talk through what kind of business you want to open — there "
                "may be a B211A → KITAS staged approach."
            ),
            alternatives=[],
            pre_arrival_steps=[],
            referral_mode=True,
        )

    # ── WORK_EMPLOYEE ──
    if purpose == Purpose.WORK_EMPLOYEE:
        return MatchResult(
            recommended_visa=VisaType.E23,
            reason=(
                "E23 Work KITAS is the employer-sponsored route. Your future "
                "Indonesian employer must file an RPTKA (workforce utilisation "
                "plan) before the visa application."
            ),
            alternatives=[],
            pre_arrival_steps=_STEPS_EMPLOYEE,
            referral_mode=False,
        )

    # ── FAMILY ──
    if purpose == Purpose.FAMILY:
        return MatchResult(
            recommended_visa=VisaType.E31,
            reason=(
                "E31 Family / Dependent KITAS covers spouses and dependents of "
                "existing KITAS/KITAP holders. Your sponsor's current status "
                "drives the paperwork."
            ),
            alternatives=[],
            pre_arrival_steps=_STEPS_FAMILY,
            referral_mode=False,
        )

    # ── RETIREMENT ──
    if purpose == Purpose.RETIREMENT:
        return MatchResult(
            recommended_visa=VisaType.E33F,
            reason=(
                "E33F Retirement KITAS is available from age 55 with proof of "
                "≥ USD 1,500/month passive income. Renewable yearly."
            ),
            alternatives=[],
            pre_arrival_steps=_STEPS_RETIREMENT,
            referral_mode=False,
        )

    # ── STUDENT ──
    if purpose == Purpose.STUDENT:
        return MatchResult(
            recommended_visa=VisaType.E30A,
            reason=(
                "E30A Student KITAS is sponsored by the Indonesian university "
                "where you've been accepted. Valid for the duration of the "
                "study programme."
            ),
            alternatives=[],
            pre_arrival_steps=_STEPS_STUDENT,
            referral_mode=False,
        )

    # Unreachable with the current enum, but keeps mypy honest.
    return MatchResult(
        recommended_visa=None,
        reason="Could not classify. Let's review on WhatsApp.",
        alternatives=[],
        pre_arrival_steps=[],
        referral_mode=True,
    )
