"""Regression guard for the D-10 pilot-threshold leak (cross-family review,
2026-07-27): a decline reason composed as English audit prose at runtime
("below D-10 pilot threshold (...) — hand off to the ordinary channel")
was persisted, returned in `VoaResponse.reasons`, and rendered VERBATIM on
the public decline page — D-10 is an INTERNAL Bali Zero checkpoint that
constants.py and safe_clock.py both say must never be quoted to a client.

Fixed by moving decline reasons onto stable machine codes
(`VoaResponse.reason_codes`); the raw prose stays server-side only
(`VoaVerdict.decline_reasons` / `garuda_voa_checks.decline_reasons`, audit).

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
     engine can produce (every `EligibilityInput` boolean flip, both D-10
     sub-branches, the extension-already-used rule, and a multi-reason
     decline), and serializes it to JSON exactly as FastAPI would put it on
     the wire.
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
        result_url="/visa/voa/voa1234567890ab",
    )


class TestGuardIsNotVacuous:
    """Proves this guard would actually have caught the original leak — the
    pre-fix RAW engine prose for the exact leaking case (D-10 boundary,
    9 days remaining) must itself contain a forbidden token. If this class
    failed, the `IsCleanOnTheWire` passes below would be meaningless."""

    def test_raw_prose_for_the_d10_boundary_contains_a_forbidden_token(self) -> None:
        result = screen(_clean_extension(days_until_expiry=9))
        assert result.decline_reasons, "expected a decline reason for the D-10 boundary case"
        raw = json.dumps(result.decline_reasons).lower()
        assert any(tok.lower() in raw for tok in _FORBIDDEN_TOKENS), (
            "guard is vacuous: the RAW engine prose contains none of the forbidden "
            "tokens — this test would pass even without the fix"
        )

    def test_raw_prose_names_pilot_and_threshold_verbatim(self) -> None:
        result = screen(_clean_extension(days_until_expiry=9))
        raw = " ".join(result.decline_reasons).lower()
        assert "pilot" in raw
        assert "threshold" in raw


class TestEveryEligibilityBranchDeclineIsCleanOnTheWire:
    """One parametrized case per `eligibility.screen()` decline branch —
    every boolean flip (and both D-10 sub-branches) that can produce a
    decline reason. Each is serialized through the real `VoaResponse` and
    checked against the forbidden-token list."""

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
            {"days_until_expiry": 9},  # the exact case that leaked
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

        today = date(2026, 6, 1)
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
        assert verdict.submit_by_date is None  # never a guessed date
        response = _decline_response(verdict.decline_codes, submit_by_date=verdict.submit_by_date)
        _assert_payload_clean(response.model_dump_json())


class TestMultiReasonDeclineIsCleanOnTheWire:
    """SOP §1 'log reason' — the screen collects every failing reason, never
    short-circuiting. Several reasons plus the D-10 boundary reason on one
    response is the exact shape the original leak shipped in."""

    def test_multiple_reasons_including_d10_boundary_all_clean(self) -> None:
        result = screen(
            _clean_extension(
                self_pay=False,
                work_or_business_purpose=True,
                days_until_expiry=9,
            )
        )
        assert result.decision.value == "DECLINE"
        assert len(result.decline_codes) >= 3
        response = _decline_response(result.decline_codes)
        _assert_payload_clean(response.model_dump_json())
