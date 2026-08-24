"""Regression guard for the D-10 pilot-threshold leak (cross-family review,
2026-07-27): a decline reason composed as English audit prose at runtime
("below D-10 pilot threshold (...) — hand off to the ordinary channel")
was persisted, returned in `VoaResponse.reasons`, and rendered VERBATIM on
the public decline page — D-10 is an INTERNAL Bali Zero checkpoint that
constants.py and safe_clock.py both say must never be quoted to a client.

Fixed by moving decline reasons onto stable machine codes
(`VoaResponse.reason_codes`); the raw prose stays server-side only
(`VoaVerdict.decline_reasons` / `garuda_voa_checks.decline_reasons`, audit).

Follow-up ruling, SAME DAY (2026-07-27): the runway gate this leak was
originally about (`eligibility.screen()`'s extension boundary) no longer
uses `PILOT_INTAKE_THRESHOLD_DAYS`/D-10 at all — it now derives from the
published `PUBLISHED_FILING_DEADLINE_DAYS`/D-7 deadline (see
`eligibility.py`, `constants.py`). `PILOT_INTAKE_THRESHOLD_DAYS` survives
ONLY as the SOP §6 internal staff-escalation checkpoint inside
`safe_clock.compute_stay` — so `D-10` can no longer appear in a decline
reason's raw prose at all, and the "not vacuous" proof below had to move
off the (now-impossible) D-10-boundary scenario onto a still-live one (a
generic "excluded from pilot" branch, e.g. `urgent_case=True`) that still
carries the forbidden word "pilot". The forbidden-token LIST itself is
untouched — `D-{PILOT_INTAKE_THRESHOLD_DAYS}` stays on it defensively
(the SOP §6 checkpoint is still an internal-only marker), it just no
longer has a decline-reason producer to catch mid-leak.

This test is deliberately NOT a literal grep for "D-10" — that string never
existed literally in the codebase; it was composed at runtime from
`PILOT_INTAKE_THRESHOLD_DAYS`, and a literal grep is exactly the check that
missed the original leak. Instead it:

  1. Derives the forbidden tokens FROM THE CONSTANTS, so it keeps working
     if a threshold number is ever retuned (`D-{PILOT_INTAKE_THRESHOLD_DAYS}`,
     `D-{INTERNAL_ESCALATION_DAYS}`, `D-{FINAL_CHECK_DAYS}`,
     `D-{EXTENSION_WINDOW_OPENS_DAYS}`), plus the words "pilot" and
     "threshold".
  2. Constructs a real DECLINE `VoaResponse` for every decline branch the
     engine can produce (every `EligibilityInput` boolean flip, both
     runway-gate sub-branches, the extension-already-used rule, and a
     multi-reason decline), and serializes it to JSON exactly as FastAPI
     would put it on the wire.
  3. Asserts none of the forbidden tokens appear anywhere in that payload.

Both halves, so the guard cannot be vacuous: `TestGuardIsNotVacuous` proves
the RAW engine prose really does contain a forbidden token pre-fix (it
would fail without the fix); the `*IsCleanOnTheWire` classes prove the
actual wire payload never does (post-fix).
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from backend.app.routers.garuda_voa import VoaResponse
from backend.services.garuda_flow.constants import (
    EXTENSION_WINDOW_OPENS_DAYS,
    FINAL_CHECK_DAYS,
    INTERNAL_ESCALATION_DAYS,
    PILOT_INTAKE_THRESHOLD_DAYS,
    PUBLISHED_FILING_DEADLINE_DAYS,
)
from backend.services.garuda_flow.eligibility import EligibilityInput, screen
from backend.services.garuda_flow.intake import (
    CaseType,
    Purpose,
    VoaIntakeRequest,
    build_verdict,
)

# Forbidden tokens derived FROM THE CONSTANTS, not hardcoded — see module
# docstring: a literal "D-10" grep is exactly what missed the original leak.
_FORBIDDEN_TOKENS = (
    f"D-{PILOT_INTAKE_THRESHOLD_DAYS}",
    f"D-{INTERNAL_ESCALATION_DAYS}",
    f"D-{FINAL_CHECK_DAYS}",
    f"D-{EXTENSION_WINDOW_OPENS_DAYS}",
    "pilot",
    "threshold",
)


def _assert_payload_clean(payload: str) -> None:
    lowered = payload.lower()
    for token in _FORBIDDEN_TOKENS:
        assert token.lower() not in lowered, (
            f"internal-checkpoint marker {token!r} leaked onto the wire: {payload!r}"
        )


def _clean_extension(**overrides: object) -> EligibilityInput:
    """A fully-eligible extension case; override single fields per case —
    mirrors `test_eligibility.py::_clean_extension`."""
    base: dict[str, object] = {
        "nationality_entry_eligible": True,
        "simple_tourism": True,
        "single_adult_traveler": True,
        "clean_ordinary_passport": True,
        "passport_valid_6mo_from_entry": True,
        "self_pay": True,
        "willing_anonymous_feedback": True,
        "is_extension": True,
        "days_until_expiry": 18,
    }
    base.update(overrides)
    return EligibilityInput(**base)  # type: ignore[arg-type]


def _decline_response(codes: list[str], *, submit_by_date: date | None = None) -> VoaResponse:
    """A real `VoaResponse` shaped exactly like `_build_response` would
    build it from a persisted decline row — the actual shape put on the
    wire, not a hand-rolled stand-in."""
    return VoaResponse(
        hash="voa1234567890ab",
        decision="DECLINE",
        reason_codes=codes,
        case_type=CaseType.EXTENSION,
        nationality="USA",
        entry_date=date(2026, 7, 1),
        expiry_date=date(2026, 8, 1),
        last_legal_day=date(2026, 8, 1),
        expiry_is_estimated=False,
        published_filing_deadline=date(2026, 7, 25),
        submit_by_date=submit_by_date,
        price_idr=850_000,
        price_source="B1 Visa on Arrival Extension",
    )


class TestGuardIsNotVacuous:
    """Proves this guard would actually have caught the original leak.

    Follow-up ruling (2026-07-27, same day): the runway gate no longer
    uses `PILOT_INTAKE_THRESHOLD_DAYS`/D-10 at all (see module docstring),
    so `D-10` can no longer appear in ANY decline reason's raw prose —
    the original D-10-boundary scenario this proof used is gone. The
    not-vacuous demonstration moves to a still-live branch that reliably
    emits the forbidden word "pilot" (every SOP §1 exclusion signal is
    worded "excluded from pilot"). If this class failed, the
    `IsCleanOnTheWire` passes below would be meaningless."""

    def test_raw_prose_for_an_excluded_case_contains_a_forbidden_token(self) -> None:
        result = screen(_clean_extension(urgent_case=True))
        assert result.decline_reasons, "expected a decline reason for the excluded case"
        raw = json.dumps(result.decline_reasons).lower()
        assert any(tok.lower() in raw for tok in _FORBIDDEN_TOKENS), (
            "guard is vacuous: the RAW engine prose contains none of the forbidden "
            "tokens — this test would pass even without the fix"
        )

    def test_raw_prose_names_pilot_verbatim(self) -> None:
        result = screen(_clean_extension(urgent_case=True))
        raw = " ".join(result.decline_reasons).lower()
        assert "pilot" in raw
        # "threshold" is NOT asserted here anymore: post-2026-07-27 no
        # decline reason ever uses that word (the runway gate's message
        # talks about the published filing deadline, not a "threshold").
        # It stays on `_FORBIDDEN_TOKENS` defensively in case that wording
        # is ever reintroduced — this test just can't prove it live today.


class TestEveryEligibilityBranchDeclineIsCleanOnTheWire:
    """One parametrized case per `eligibility.screen()` decline branch —
    every boolean flip (and both runway-gate sub-branches) that can
    produce a decline reason. Each is serialized through the real
    `VoaResponse` and checked against the forbidden-token list."""

    @pytest.mark.parametrize(
        "overrides",
        [
            {"nationality_entry_eligible": False},
            {"simple_tourism": False},
            {"single_adult_traveler": False},
            {"clean_ordinary_passport": False},
            {"passport_valid_6mo_from_entry": False},
            {"self_pay": False},
            {"willing_anonymous_feedback": False},
            {"urgent_case": True},
            {"family_or_group": True},
            {"special_passport": True},
            {"work_or_business_purpose": True},
            {"prior_overstay_refusal_blacklist": True},
            {"wants_airport_fastlane": True},
            {"days_until_expiry": None},
            # One day past the published deadline (owner ruling
            # 2026-07-27) — the current runway-gate boundary decline.
            {"days_until_expiry": PUBLISHED_FILING_DEADLINE_DAYS - 1},
            {"days_until_expiry": -2},
        ],
        ids=lambda o: ",".join(f"{k}={v}" for k, v in o.items()),
    )
    def test_decline_response_never_leaks_internal_prose(self, overrides: dict) -> None:
        result = screen(_clean_extension(**overrides))
        assert result.decision.value == "DECLINE"
        response = _decline_response(result.decline_codes)
        _assert_payload_clean(response.model_dump_json())


class TestExtensionAlreadyUsedDeclineIsCleanOnTheWire:
    """The "only one extension" rule is layered on by `intake.build_verdict`
    (a VOA/B1-shape rule, not a `screen()` branch) — separate construction
    path, same guard."""

    def test_second_extension_decline_is_clean_on_the_wire(self) -> None:
        today = date(2026, 7, 27)
        req = VoaIntakeRequest(
            case_type=CaseType.EXTENSION,
            nationality="USA",
            entry_date=today - timedelta(days=20),
            passport_expiry_date=today + timedelta(days=400),
            purpose=Purpose.TOURISM,
            travellers=1,
            self_pay=True,
            voa_expiry_date=today + timedelta(days=25),  # plenty of runway
            extension_already_used=True,
        )
        verdict = build_verdict(req, today=today)
        assert verdict.decision.value == "DECLINE"
        response = _decline_response(verdict.decline_codes)
        _assert_payload_clean(response.model_dump_json())


class TestMaxTotalStayDeclineIsCleanOnTheWire:
    """The B1 max-total-stay boundary (`DeclineCode.EXTENSION_EXCEEDS_MAX_STAY`,
    layered on by `intake.build_verdict` — same construction path as
    ``EXTENSION_ALREADY_USED`` above, promoted 2026-08-23 from the
    owner-local `internal_preview_cli` guard) must never leak the derived
    day-count or any internal-checkpoint wording onto the wire."""

    def test_max_total_stay_decline_is_clean_on_the_wire(self) -> None:
        today = date(2026, 7, 27)
        req = VoaIntakeRequest(
            case_type=CaseType.EXTENSION,
            nationality="USA",
            entry_date=date(2026, 7, 1),
            passport_expiry_date=today + timedelta(days=400),
            purpose=Purpose.TOURISM,
            travellers=1,
            self_pay=True,
            voa_expiry_date=date(2026, 8, 30),  # exactly at the 60-day max
            extension_already_used=False,
        )
        verdict = build_verdict(req, today=today)
        assert verdict.decision.value == "DECLINE"
        assert "EXTENSION_EXCEEDS_MAX_STAY" in verdict.decline_codes
        response = _decline_response(verdict.decline_codes)
        _assert_payload_clean(response.model_dump_json())


class TestIssuanceSubmissionGateDeclineIsCleanOnTheWire:
    """The issuance-only submission-window gate (owner ruling 2026-07-27,
    `services.garuda_flow.operating_calendar`) is layered on by
    `intake.build_verdict` exactly like the extension-limit rule above —
    separate construction path, same guard. Neither `ARRIVAL_TOO_SOON` nor
    `ARRIVAL_DATE_UNCONFIRMED` may ever carry an internal-checkpoint marker
    onto the wire, and `submit_by_date` (the one date this gate may ever
    show a visitor) must never be a guessed value."""

    def test_arrival_too_soon_decline_is_clean_on_the_wire(self) -> None:
        # 17 Aug 2026 is Independence Day (a Monday); one day past the
        # Fri 14 Aug cutoff for a Tue 18 Aug arrival.
        today = date(2026, 8, 15)
        req = VoaIntakeRequest(
            case_type=CaseType.ISSUANCE,
            nationality="USA",
            entry_date=date(2026, 8, 18),
            passport_expiry_date=date(2026, 8, 18) + timedelta(days=400),
            purpose=Purpose.TOURISM,
            travellers=1,
            self_pay=True,
        )
        verdict = build_verdict(req, today=today)
        assert verdict.decision.value == "DECLINE"
        assert "ARRIVAL_TOO_SOON" in verdict.decline_codes
        response = _decline_response(verdict.decline_codes, submit_by_date=verdict.submit_by_date)
        _assert_payload_clean(response.model_dump_json())

    def test_arrival_date_unconfirmed_decline_is_clean_on_the_wire(self) -> None:
        from backend.services.garuda_flow.operating_calendar import COVERAGE_END

        today = date(2026, 12, 1)
        entry = COVERAGE_END + timedelta(days=5)  # past the decreed 2026 calendar
        req = VoaIntakeRequest(
            case_type=CaseType.ISSUANCE,
            nationality="USA",
            entry_date=entry,
            passport_expiry_date=entry + timedelta(days=400),
            purpose=Purpose.TOURISM,
            travellers=1,
            self_pay=True,
        )
        verdict = build_verdict(req, today=today)
        assert verdict.decision.value == "DECLINE"
        assert "ARRIVAL_DATE_UNCONFIRMED" in verdict.decline_codes
        assert "ARRIVAL_TOO_FAR" not in verdict.decline_codes
        assert verdict.submit_by_date is None  # never a guessed date
        response = _decline_response(verdict.decline_codes, submit_by_date=verdict.submit_by_date)
        _assert_payload_clean(response.model_dump_json())

    def test_arrival_too_far_decline_is_clean_on_the_wire(self) -> None:
        # 91 days out is the first day outside the eVOA usability window.
        today = date(2026, 8, 24)
        entry = today + timedelta(days=91)
        req = VoaIntakeRequest(
            case_type=CaseType.ISSUANCE,
            nationality="USA",
            entry_date=entry,
            passport_expiry_date=entry + timedelta(days=400),
            purpose=Purpose.TOURISM,
            travellers=1,
            self_pay=True,
        )
        verdict = build_verdict(req, today=today)
        assert verdict.decision.value == "DECLINE"
        assert "ARRIVAL_TOO_FAR" in verdict.decline_codes
        assert verdict.submit_by_date is not None
        response = _decline_response(verdict.decline_codes, submit_by_date=verdict.submit_by_date)
        _assert_payload_clean(response.model_dump_json())


class TestMultiReasonDeclineIsCleanOnTheWire:
    """SOP §1 'log reason' — the screen collects every failing reason, never
    short-circuiting. Several reasons plus the runway-boundary reason on
    one response is the exact shape the original leak shipped in."""

    def test_multiple_reasons_including_runway_boundary_all_clean(self) -> None:
        result = screen(
            _clean_extension(
                self_pay=False,
                work_or_business_purpose=True,
                days_until_expiry=PUBLISHED_FILING_DEADLINE_DAYS - 1,
            )
        )
        assert result.decision.value == "DECLINE"
        assert len(result.decline_codes) >= 3
        response = _decline_response(result.decline_codes)
        _assert_payload_clean(response.model_dump_json())
