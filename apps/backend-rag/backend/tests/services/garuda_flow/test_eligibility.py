"""Tests for the GARUDA VOA pilot eligibility screen.

The D-10 boundary tests are the enforceable form of the Gate-1 SIM-2 criterion
that was "not testable" on 2026-07-20 because no threshold existed.
"""

from __future__ import annotations

import dataclasses

import pytest

from backend.services.garuda_flow.constants import PILOT_INTAKE_THRESHOLD_DAYS
from backend.services.garuda_flow.eligibility import (
    Decision,
    EligibilityInput,
    screen,
)


def _clean_extension(**overrides: object) -> EligibilityInput:
    """A fully-eligible extension case; override single fields per test."""
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


class TestAccept:
    def test_clean_extension_well_within_d10_accepts(self) -> None:
        assert screen(_clean_extension()).accepted is True

    def test_fresh_issuance_ignores_d10_runway(self) -> None:
        # A fresh VOA issuance has no expiry pressure — D-10 must not apply.
        inp = _clean_extension(is_extension=False, days_until_expiry=None)
        res = screen(inp)
        assert res.decision is Decision.ACCEPT
        assert res.decline_reasons == []


class TestD10Boundary:
    def test_exactly_d10_accepts(self) -> None:
        # ">= 10 days remain" → exactly 10 is IN.
        res = screen(_clean_extension(days_until_expiry=PILOT_INTAKE_THRESHOLD_DAYS))
        assert res.accepted is True

    def test_d9_declines_with_handoff_reason(self) -> None:
        # 9 days = below threshold → decline, and the reason must point to the
        # ordinary channel (the amended SOP "never leave a bare no").
        res = screen(_clean_extension(days_until_expiry=9))
        assert res.decision is Decision.DECLINE
        assert any("below D-10" in r and "ordinary channel" in r for r in res.decline_reasons)

    def test_extension_missing_days_declines(self) -> None:
        res = screen(_clean_extension(days_until_expiry=None))
        assert res.decision is Decision.DECLINE
        assert any("missing days-until-expiry" in r for r in res.decline_reasons)

    def test_already_overstaying_declines(self) -> None:
        res = screen(_clean_extension(days_until_expiry=-2))
        assert res.decision is Decision.DECLINE


class TestExclusions:
    def test_work_purpose_declines(self) -> None:
        res = screen(_clean_extension(work_or_business_purpose=True))
        assert res.decision is Decision.DECLINE
        assert any("does not permit work" in r for r in res.decline_reasons)

    def test_family_or_group_declines(self) -> None:
        assert screen(_clean_extension(family_or_group=True)).decision is Decision.DECLINE

    def test_airport_fastlane_declines(self) -> None:
        assert screen(_clean_extension(wants_airport_fastlane=True)).decision is Decision.DECLINE

    def test_passport_under_6mo_declines(self) -> None:
        assert (
            screen(_clean_extension(passport_valid_6mo_from_entry=False)).decision
            is Decision.DECLINE
        )


class TestReasonCompleteness:
    def test_collects_all_failing_reasons_not_just_first(self) -> None:
        # SOP §1 "log reason" — the case sheet needs the COMPLETE picture,
        # so the screen must not short-circuit on the first failure.
        res = screen(
            _clean_extension(
                self_pay=False,
                work_or_business_purpose=True,
                days_until_expiry=3,
            )
        )
        assert res.decision is Decision.DECLINE
        assert len(res.decline_reasons) >= 3

    def test_accept_has_no_reasons(self) -> None:
        res = screen(_clean_extension())
        assert res.decline_reasons == []


def test_input_is_frozen() -> None:
    # Intake facts must not mutate after capture (auditability).
    inp = _clean_extension()
    with pytest.raises(dataclasses.FrozenInstanceError):
        inp.self_pay = False  # type: ignore[misc]
