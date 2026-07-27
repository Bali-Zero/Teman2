"""Tests for the GARUDA VOA pilot eligibility screen.

The runway-boundary tests are the enforceable form of the Gate-1 SIM-2
criterion that was "not testable" on 2026-07-20 because no threshold
existed. Owner ruling 2026-07-27 retuned the boundary itself: the gate
now derives from ``PUBLISHED_FILING_DEADLINE_DAYS`` (D-7), not the
retired ``PILOT_INTAKE_THRESHOLD_DAYS`` (D-10) — see
``TestPublishedDeadlineBoundary`` below. The old D-10-pinned tests were
DELETED, not kept alongside the new ones: they asserted the retired
(now-wrong) behaviour.
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest

from backend.services.garuda_flow.constants import PUBLISHED_FILING_DEADLINE_DAYS
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
    def test_clean_extension_well_within_the_runway_accepts(self) -> None:
        assert screen(_clean_extension()).accepted is True

    def test_fresh_issuance_ignores_the_runway_gate(self) -> None:
        # A fresh VOA issuance has no expiry pressure — the runway gate
        # (extension-only) must not apply.
        inp = _clean_extension(is_extension=False, days_until_expiry=None)
        res = screen(inp)
        assert res.decision is Decision.ACCEPT
        assert res.decline_reasons == []


class TestPublishedDeadlineBoundary:
    """Owner ruling (2026-07-27): the pilot's D-10 conservatism gate is
    retired. The runway gate now accepts an extension whenever it can
    still be filed under the PUBLISHED Ngurah Rai deadline
    (``PUBLISHED_FILING_DEADLINE_DAYS`` — D-7): our threshold and the
    office's published deadline are the same line, no added margin."""

    def test_exactly_at_the_published_deadline_accepts(self) -> None:
        # The deadline day itself is still filable — "paling lambat 7 hari
        # sebelum ... berakhir" reads as "at the latest 7 days before".
        res = screen(_clean_extension(days_until_expiry=PUBLISHED_FILING_DEADLINE_DAYS))
        assert res.accepted is True

    def test_one_day_past_the_published_deadline_declines_with_handoff_reason(
        self,
    ) -> None:
        # One day tighter than the published deadline → decline, and the
        # reason must point to the ordinary channel (the amended SOP
        # "never leave a bare no").
        res = screen(_clean_extension(days_until_expiry=PUBLISHED_FILING_DEADLINE_DAYS - 1))
        assert res.decision is Decision.DECLINE
        assert any(
            "published" in r and "filing deadline" in r and "ordinary channel" in r
            for r in res.decline_reasons
        )

    def test_owner_example_8_days_on_a_30_day_case_now_accepts(self) -> None:
        # The owner's actual example (2026-07-27): 8 days of runway is
        # still legally filable under the published D-7 deadline. The
        # retired D-10 pilot-conservatism gate used to decline this case
        # — it must not anymore.
        res = screen(_clean_extension(days_until_expiry=8))
        assert res.accepted is True

    def test_extension_missing_days_declines(self) -> None:
        res = screen(_clean_extension(days_until_expiry=None))
        assert res.decision is Decision.DECLINE
        assert any("missing days-until-expiry" in r for r in res.decline_reasons)

    def test_published_deadline_already_in_the_past_declines(self) -> None:
        res = screen(_clean_extension(days_until_expiry=-2))
        assert res.decision is Decision.DECLINE

    def test_gate_reads_the_threshold_from_the_constant_not_a_literal(self) -> None:
        # No new literal 7 (or the retired 10) may ever be hardcoded in the
        # runway gate — it must derive from PUBLISHED_FILING_DEADLINE_DAYS.
        from backend.services.garuda_flow import eligibility

        source = inspect.getsource(eligibility.screen)
        assert "PUBLISHED_FILING_DEADLINE_DAYS" in source
        assert "< 7" not in source
        assert "< 10" not in source


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
