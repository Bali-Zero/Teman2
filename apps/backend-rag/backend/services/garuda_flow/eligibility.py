"""GARUDA VOA pilot — intake eligibility screen (pure, no I/O).

A faithful, auditable encoding of SOP-v0-GARUDA-B1 §1 segmentation:

    ACCEPT only if ALL true: eligible nationality/entry · simple tourism ·
    1 adult traveler · clean ordinary passport (>=6 months validity) ·
    still filable under the published Ngurah Rai filing deadline
    (extension case) · self-pay · willing to give anonymous feedback.

    EXCLUDE (decline politely, log reason): urgent · families/groups ·
    special passports · work/business purpose · prior overstay/refusal/
    blacklist · airport fast-lane requests · extension past the published
    filing deadline.

The screen collects EVERY failing reason (never short-circuits) so the case
sheet can log a complete "why declined" — SOP §1 "decline politely, log reason".

Owner ruling (2026-07-27): the extension runway gate accepts a case
whenever it can still be filed under the PUBLISHED Ngurah Rai deadline —
``PUBLISHED_FILING_DEADLINE_DAYS`` (constants.py), "paling lambat 7 hari
sebelum masa izin tinggal berakhir". This retires the earlier D-10
pilot-conservatism gate (``PILOT_INTAKE_THRESHOLD_DAYS``), which was
declining cases (e.g. 8 days of runway) that are still legally filable —
our threshold and the office's published deadline are now the SAME line,
with no added margin. ``PILOT_INTAKE_THRESHOLD_DAYS`` survives ONLY as the
SOP §6 internal staff-escalation checkpoint inside
``safe_clock.compute_stay`` — it is no longer an ACCEPT/DECLINE gate
anywhere in this module, and this module never hardcodes the day-count
literal: it is always read from ``PUBLISHED_FILING_DEADLINE_DAYS``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.services.garuda_flow.constants import PUBLISHED_FILING_DEADLINE_DAYS


class Decision(str, Enum):
    ACCEPT = "ACCEPT"
    DECLINE = "DECLINE"


class DeclineCode(str, Enum):
    """Stable machine code for each decline reason `screen()` can emit —
    one code per ``reasons.append(...)`` call site below (plus
    ``EXTENSION_ALREADY_USED``, appended by ``intake.build_verdict`` for a
    VOA/B1-shape rule layered on top of this generic screen).

    This is the ONLY form of a decline reason that may ever cross the wire
    to a visitor (`app/routers/garuda_voa.py::VoaResponse.reason_codes`) —
    the human strings in ``decline_reasons`` are engine-internal audit
    prose (English, and occasionally naming an internal checkpoint like
    "D-10" — see constants.py) and must stay server-side only. Every code
    here is neutral vocabulary a visitor could see without harm: no
    threshold number, no "pilot"/"D-N" wording, ever.
    """

    NATIONALITY_NOT_ELIGIBLE = "NATIONALITY_NOT_ELIGIBLE"
    PURPOSE_NOT_ELIGIBLE = "PURPOSE_NOT_ELIGIBLE"
    GROUP_CASE = "GROUP_CASE"
    PASSPORT_TYPE = "PASSPORT_TYPE"
    PASSPORT_VALIDITY = "PASSPORT_VALIDITY"
    NOT_SELF_PAY = "NOT_SELF_PAY"
    FEEDBACK_REQUIRED = "FEEDBACK_REQUIRED"
    URGENT_CASE = "URGENT_CASE"
    SPECIAL_PASSPORT = "SPECIAL_PASSPORT"
    PRIOR_ISSUE = "PRIOR_ISSUE"
    FASTLANE_REQUEST = "FASTLANE_REQUEST"
    EXPIRY_UNKNOWN = "EXPIRY_UNKNOWN"
    EXPIRES_TOO_SOON = "EXPIRES_TOO_SOON"
    # Not emitted by `screen()` itself — layered on by
    # `intake.build_verdict` for the VOA/B1 "only one extension" rule.
    # Declared here so every decline code the funnel can ever emit has one
    # SSOT enum, and the guard test (test_no_internal_prose_on_wire.py)
    # can enumerate the whole set from this one place.
    EXTENSION_ALREADY_USED = "EXTENSION_ALREADY_USED"
    # Not emitted by `screen()` either — layered on by
    # `intake.build_verdict` for the issuance-only submission-window gate
    # (owner ruling 2026-07-27; `operating_calendar.py`). Two distinct
    # codes so the visitor-facing routing can distinguish "come back to the
    # ordinary channel, you're just past our online cutoff" from "we
    # genuinely cannot compute this yet — a human will confirm":
    ARRIVAL_TOO_SOON = "ARRIVAL_TOO_SOON"
    ARRIVAL_DATE_UNCONFIRMED = "ARRIVAL_DATE_UNCONFIRMED"
    # Not emitted by `screen()` either — layered on by
    # `intake.build_verdict` for the issuance-only eVOA usability-window
    # gate (GARUDA B1 truth-sheet, line 41, verified 14 Jul 2026):
    # an eVOA is usable for EVOA_USABILITY_WINDOW_DAYS from issuance.
    # With no issuance_date input, `today` is the earliest possible issuance
    # date, so an arrival strictly later than today + that window cannot be
    # covered. This is the other end of the same axis as ARRIVAL_TOO_SOON.
    ARRIVAL_TOO_FAR = "ARRIVAL_TOO_FAR"
    # Not emitted by `screen()` either — layered on by `intake.build_verdict`
    # for the B1 max-total-stay boundary (`constants.b1_max_total_stay_exceeded`,
    # 2026-08-23): a printed extension expiry whose day-DIFFERENCE from entry
    # is >= the legal max (60 for B1) is already one day past it, because the
    # arrival day counts as day 1. Promoted from the owner-local
    # `internal_preview_cli` guard (its sole caller, PR #4685) into the
    # shared engine so a future public-funnel restore built on
    # `build_verdict()` cannot silently reintroduce that ACCEPT-on-the-
    # boundary bug on the client-facing surface — here it is a DECLINE with
    # this neutral code, never a bare error.
    EXTENSION_EXCEEDS_MAX_STAY = "EXTENSION_EXCEEDS_MAX_STAY"


@dataclass(frozen=True)
class EligibilityInput:
    """Structured intake for the pilot eligibility screen.

    ``is_extension`` distinguishes a fresh VOA issuance (the runway gate
    does not apply) from an extension case (it does — see ``screen()`` for
    the published-deadline boundary). ``days_until_expiry`` is required for
    an extension case and ignored otherwise.
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
    # Parallel to ``decline_reasons`` — same length, same order, index-for-
    # index the machine-code twin of the human string at that index. Purely
    # additive (BUILD-SPEC decline-code-fix-2026-07-27): `decline_reasons`
    # keeps carrying the exact same audit prose it always has, for the
    # existing callers/tests that read it.
    decline_codes: list[str] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.decision is Decision.ACCEPT


def screen(inp: EligibilityInput) -> EligibilityResult:
    """Apply the SOP §1 pilot intake screen; return decision + all reasons."""
    reasons: list[str] = []
    codes: list[str] = []

    def _decline(code: DeclineCode, message: str) -> None:
        codes.append(code.value)
        reasons.append(message)

    # ── Positive criteria (all must hold) ──
    if not inp.nationality_entry_eligible:
        _decline(
            DeclineCode.NATIONALITY_NOT_ELIGIBLE,
            "nationality or entry point not eligible for VOA",
        )
    if not inp.simple_tourism:
        _decline(DeclineCode.PURPOSE_NOT_ELIGIBLE, "not a simple-tourism case")
    if not inp.single_adult_traveler:
        _decline(DeclineCode.GROUP_CASE, "not a single adult traveler")
    if not inp.clean_ordinary_passport:
        _decline(DeclineCode.PASSPORT_TYPE, "not a clean ordinary passport")
    if not inp.passport_valid_6mo_from_entry:
        _decline(DeclineCode.PASSPORT_VALIDITY, "passport not valid >= 6 months from entry")
    if not inp.self_pay:
        _decline(DeclineCode.NOT_SELF_PAY, "not self-pay")
    if not inp.willing_anonymous_feedback:
        _decline(DeclineCode.FEEDBACK_REQUIRED, "not willing to give anonymous feedback")

    # ── Exclusion signals (any triggers a decline) ──
    if inp.urgent_case:
        _decline(DeclineCode.URGENT_CASE, "urgent case (excluded from pilot)")
    if inp.family_or_group:
        _decline(DeclineCode.GROUP_CASE, "family/group case (excluded from pilot)")
    if inp.special_passport:
        _decline(DeclineCode.SPECIAL_PASSPORT, "special passport (excluded from pilot)")
    if inp.work_or_business_purpose:
        _decline(
            DeclineCode.PURPOSE_NOT_ELIGIBLE,
            "work/business purpose (B1 does not permit work)",
        )
    if inp.prior_overstay_refusal_blacklist:
        _decline(
            DeclineCode.PRIOR_ISSUE,
            "prior overstay/refusal/blacklist (excluded from pilot)",
        )
    if inp.wants_airport_fastlane:
        _decline(DeclineCode.FASTLANE_REQUEST, "airport fast-lane request (excluded from pilot)")

    # ── Runway gate (extension cases only) — owner ruling 2026-07-27: the
    # ONLY source of truth for "too late" is the published filing deadline
    # (``PUBLISHED_FILING_DEADLINE_DAYS``). A case with EXACTLY that many
    # days of runway left is still ACCEPTED (the deadline day itself is
    # filable — "paling lambat N hari sebelum ... berakhir" reads as "at
    # the latest"); one day tighter DECLINES. Never a hardcoded literal.
    if inp.is_extension:
        if inp.days_until_expiry is None:
            _decline(
                DeclineCode.EXPIRY_UNKNOWN,
                "extension case missing days-until-expiry (cannot verify filing-deadline runway)",
            )
        elif inp.days_until_expiry < PUBLISHED_FILING_DEADLINE_DAYS:
            _decline(
                DeclineCode.EXPIRES_TOO_SOON,
                f"past the published D-{PUBLISHED_FILING_DEADLINE_DAYS} filing deadline "
                f"({inp.days_until_expiry} days to expiry) — hand off to the ordinary channel",
            )

    decision = Decision.ACCEPT if not reasons else Decision.DECLINE
    return EligibilityResult(decision=decision, decline_reasons=reasons, decline_codes=codes)


__all__ = [
    "Decision",
    "DeclineCode",
    "EligibilityInput",
    "EligibilityResult",
    "screen",
]
