"""Tests for the GARUDA VOA intake orchestration (spec §3 trap 3 close).

Covers the two derivations the engine itself leaves open — passport
validity and days-until-expiry — plus the client-facing/internal Safe
Clock checkpoint boundary (spec §6, charter).
"""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta

import pytest

from backend.services.garuda_flow import freshness
from backend.services.garuda_flow.constants import (
    EVOA_USABILITY_WINDOW_DAYS,
    MIN_PASSPORT_VALIDITY_DAYS,
    PUBLISHED_FILING_DEADLINE_DAYS,
)
from backend.services.garuda_flow.eligibility import Decision
from backend.services.garuda_flow.intake import (
    CaseType,
    Purpose,
    VoaIntakeRequest,
    build_verdict,
)
from backend.services.garuda_flow.operating_calendar import COVERAGE_END


def _issuance(**overrides: object) -> VoaIntakeRequest:
    """A fully-eligible fresh issuance request; override fields per test."""
    today = date(2026, 7, 27)
    base: dict[str, object] = {
        "case_type": CaseType.ISSUANCE,
        "nationality": "USA",
        "entry_date": today + timedelta(days=5),
        "passport_expiry_date": today + timedelta(days=400),
        "purpose": Purpose.TOURISM,
        "travellers": 1,
        "self_pay": True,
    }
    base.update(overrides)
    return VoaIntakeRequest(**base)  # type: ignore[arg-type]


def _extension(**overrides: object) -> VoaIntakeRequest:
    """A fully-eligible extension request well within the runway gate."""
    today = date(2026, 7, 27)
    base: dict[str, object] = {
        "case_type": CaseType.EXTENSION,
        "nationality": "USA",
        "entry_date": today - timedelta(days=20),
        "passport_expiry_date": today + timedelta(days=400),
        "voa_expiry_date": today + timedelta(days=18),
        "extension_already_used": False,
        "purpose": Purpose.TOURISM,
        "travellers": 1,
        "self_pay": True,
    }
    base.update(overrides)
    return VoaIntakeRequest(**base)  # type: ignore[arg-type]


_TODAY = date(2026, 7, 27)


class TestPassportValidityDerivation:
    def test_passport_valid_well_beyond_6_months_accepts(self) -> None:
        verdict = build_verdict(_issuance(), today=_TODAY)
        assert verdict.decision is Decision.ACCEPT
        assert verdict.decline_reasons == []

    def test_passport_exactly_at_threshold_accepts(self) -> None:
        entry = _TODAY + timedelta(days=5)
        req = _issuance(passport_expiry_date=entry + timedelta(days=MIN_PASSPORT_VALIDITY_DAYS))
        verdict = build_verdict(req, today=_TODAY)
        assert verdict.accepted is True

    def test_passport_one_day_short_declines(self) -> None:
        entry = _TODAY + timedelta(days=5)
        req = _issuance(
            passport_expiry_date=entry + timedelta(days=MIN_PASSPORT_VALIDITY_DAYS - 1)
        )
        verdict = build_verdict(req, today=_TODAY)
        assert verdict.decision is Decision.DECLINE
        assert any("6 mont" in r for r in verdict.decline_reasons)

    def test_passport_already_expired_by_entry_declines(self) -> None:
        entry = _TODAY + timedelta(days=5)
        req = _issuance(passport_expiry_date=entry - timedelta(days=1))
        verdict = build_verdict(req, today=_TODAY)
        assert verdict.decision is Decision.DECLINE


class TestExtensionDaysUntilExpiryDerivation:
    def test_extension_well_within_the_runway_accepts(self) -> None:
        verdict = build_verdict(_extension(), today=_TODAY)
        assert verdict.accepted is True

    def test_extension_exactly_at_published_deadline_accepts(self) -> None:
        # Owner ruling 2026-07-27: the deadline day itself is still filable.
        req = _extension(
            voa_expiry_date=_TODAY + timedelta(days=PUBLISHED_FILING_DEADLINE_DAYS)
        )
        verdict = build_verdict(req, today=_TODAY)
        assert verdict.accepted is True

    def test_extension_one_day_past_published_deadline_declines_with_handoff_reason(
        self,
    ) -> None:
        req = _extension(
            voa_expiry_date=_TODAY + timedelta(days=PUBLISHED_FILING_DEADLINE_DAYS - 1)
        )
        verdict = build_verdict(req, today=_TODAY)
        assert verdict.decision is Decision.DECLINE
        assert any(
            "published" in r and "filing deadline" in r and "ordinary channel" in r
            for r in verdict.decline_reasons
        )

    def test_owner_example_8_days_out_on_a_30_day_case_now_accepts(self) -> None:
        # Owner ruling 2026-07-27's actual example: a 30-day VOA, entry 22
        # days ago, so the original expiry falls exactly 8 days from today.
        # 8 days of runway is still legally filable under the published D-7
        # deadline — the retired D-10 pilot-conservatism gate used to
        # decline this case; it must not anymore.
        entry = _TODAY - timedelta(days=22)
        req = _extension(entry_date=entry, voa_expiry_date=_TODAY + timedelta(days=8))
        verdict = build_verdict(req, today=_TODAY)
        assert verdict.accepted is True

    def test_extension_already_overstaying_declines(self) -> None:
        # The published deadline is already in the past.
        req = _extension(voa_expiry_date=_TODAY - timedelta(days=2))
        verdict = build_verdict(req, today=_TODAY)
        assert verdict.decision is Decision.DECLINE

    def test_issuance_ignores_extension_only_fields(self) -> None:
        # A fresh issuance has no expiry pressure — the runway gate must
        # not apply even if voa_expiry_date/extension_already_used are
        # populated.
        req = _issuance()
        assert req.voa_expiry_date is None
        verdict = build_verdict(req, today=_TODAY)
        assert verdict.decision is Decision.ACCEPT


class TestSecondExtensionLimit:
    """VisaType.B1 allows only one extension (30 + 1x30 days) — this is a
    VOA/B1-shape fact from the catalogue, not a generic pilot-intake
    criterion, so it is layered on top of `screen()` rather than folded
    into it."""

    def test_extension_already_used_declines_even_with_full_runway(self) -> None:
        req = _extension(extension_already_used=True, voa_expiry_date=_TODAY + timedelta(days=25))
        verdict = build_verdict(req, today=_TODAY)
        assert verdict.decision is Decision.DECLINE
        assert any("only one extension" in r for r in verdict.decline_reasons)

    def test_extension_already_used_false_does_not_trigger_the_reason(self) -> None:
        req = _extension(extension_already_used=False)
        verdict = build_verdict(req, today=_TODAY)
        assert all("only one extension" not in r for r in verdict.decline_reasons)

    def test_extension_already_used_on_issuance_is_a_no_op(self) -> None:
        # The field is structurally extension-only; an issuance case must
        # never be declined by it even if the client sent a stray True.
        req = _issuance(extension_already_used=True)
        verdict = build_verdict(req, today=_TODAY)
        assert verdict.decision is Decision.ACCEPT


class TestB1MaxTotalStayBoundary:
    """`constants.b1_max_total_stay_exceeded()` (2026-08-23, PR #4685) fixed
    a strict-`>` inline comparison in `internal_preview_cli` that silently
    ACCEPTed a printed extension expiry exactly at the 60-day max — one day
    past the legal B1 maximum (arrival day counts as day 1). That guard
    lived in exactly ONE caller (the owner-local CLI, which raises before
    ever reaching `build_verdict`). This promotes the same boundary into
    the shared engine so a future public-funnel restore built on
    `build_verdict()` cannot silently reintroduce the bug on the
    client-facing surface — surfaced here as a DECLINE + neutral code
    (never a bare error), per the SOP's "decline always still routes to
    WhatsApp" rule.

    Dates mirror the CLI's own boundary tests (`entry_date=2026-07-01`,
    `voa_expiry_date` at +60/+59 days) for continuity. `today=_TODAY`
    (2026-07-27) keeps `days_until_expiry` at 34/33 — far beyond the
    7-day published filing deadline — so `EXPIRES_TOO_SOON` cannot fire
    and mask the boundary result.
    """

    def test_printed_expiry_exactly_at_max_total_stay_declines(self) -> None:
        # GUILT: entry 2026-07-01 + 60 days difference = 2026-08-30 — B1's
        # inclusive day-count max means this is day 61 of stay, one day
        # PAST the legal maximum of 60. Must DECLINE.
        req = _extension(entry_date=date(2026, 7, 1), voa_expiry_date=date(2026, 8, 30))
        verdict = build_verdict(req, today=_TODAY)
        assert verdict.decision is Decision.DECLINE
        assert "EXTENSION_EXCEEDS_MAX_STAY" in verdict.decline_codes

    def test_printed_expiry_one_day_inside_max_total_stay_accepts(self) -> None:
        # INNOCENCE: entry 2026-07-01 + 59 days = 2026-08-29 is day 60 of
        # stay — the legal maximum itself, still valid. Must remain ACCEPT.
        req = _extension(entry_date=date(2026, 7, 1), voa_expiry_date=date(2026, 8, 29))
        verdict = build_verdict(req, today=_TODAY)
        assert verdict.accepted is True
        assert "EXTENSION_EXCEEDS_MAX_STAY" not in verdict.decline_codes

    def test_issuance_ignores_this_gate_even_with_a_stray_voa_expiry_date(self) -> None:
        # The gate is structurally extension-only; an issuance case must
        # never be declined by it (the field isn't even populated in
        # practice, but the check itself must not run for ISSUANCE).
        req = _issuance()
        verdict = build_verdict(req, today=_TODAY)
        assert "EXTENSION_EXCEEDS_MAX_STAY" not in verdict.decline_codes


class TestIssuanceSubmissionWindowGate:
    """Owner ruling (2026-07-27): a VOA is issued in a few hours, so the
    online funnel accepts an issuance request up to the day BEFORE arrival
    — counting Bali Zero's systems closed on Saturday, Sunday, and any
    Indonesian national holiday/cuti bersama (`operating_calendar.py`).
    Issuance-only; the extension path (its own runway-gate test class
    above) must be completely unaffected.

    Two of these are the exact pinned dates verified by hand this session:
    departure Tue 18 Aug 2026 (cutoff Fri 14 Aug, Independence Day Monday in
    between) and departure Mon 28 Dec 2026 (cutoff Wed 23 Dec, a run of two
    decreed closed days plus the weekend in between).
    """

    def test_ordinary_midweek_departure_cutoff_is_the_previous_day(self) -> None:
        # Entry Wed 29 Jul 2026 (no weekend/holiday in between) — the
        # cutoff is simply the immediately preceding day.
        today = date(2026, 7, 28)
        req = _issuance(entry_date=date(2026, 7, 29))
        verdict = build_verdict(req, today=today)
        assert verdict.accepted is True
        assert verdict.submit_by_date == date(2026, 7, 28)

    def test_monday_departure_with_no_holiday_cutoff_is_the_previous_friday(self) -> None:
        today = date(2026, 7, 31)  # Friday
        req = _issuance(entry_date=date(2026, 8, 3))  # Monday
        verdict = build_verdict(req, today=today)
        assert verdict.accepted is True
        assert verdict.submit_by_date == date(2026, 7, 31)

    def test_departure_today_declines_the_window_has_already_closed(self) -> None:
        # Submitting ON the day of arrival is exactly one day too late — the
        # window closes the day BEFORE departure.
        today = date(2026, 7, 29)  # Wednesday
        req = _issuance(entry_date=date(2026, 7, 29))
        verdict = build_verdict(req, today=today)
        assert verdict.decision is Decision.DECLINE
        assert "ARRIVAL_TOO_SOON" in verdict.decline_codes
        assert verdict.submit_by_date == date(2026, 7, 28)

    def test_departure_tomorrow_accepts_at_the_last_possible_moment(self) -> None:
        today = date(2026, 7, 29)  # Wednesday, open
        req = _issuance(entry_date=date(2026, 7, 30))  # Thursday
        verdict = build_verdict(req, today=today)
        assert verdict.accepted is True
        assert verdict.submit_by_date == today

    def test_departure_tue_18_aug_cutoff_is_fri_14_aug(self) -> None:
        # 17 Aug is Independence Day (a Monday) — last open day before is
        # Fri 14 Aug (16/15 Aug are the weekend).
        today = date(2026, 8, 14)
        req = _issuance(entry_date=date(2026, 8, 18))
        verdict = build_verdict(req, today=today)
        assert verdict.accepted is True
        assert verdict.submit_by_date == date(2026, 8, 14)

    def test_one_day_past_the_aug_18_departure_cutoff_declines(self) -> None:
        today = date(2026, 8, 15)  # Saturday — one day past the Fri 14 Aug cutoff
        req = _issuance(entry_date=date(2026, 8, 18))
        verdict = build_verdict(req, today=today)
        assert verdict.decision is Decision.DECLINE
        assert "ARRIVAL_TOO_SOON" in verdict.decline_codes
        assert verdict.submit_by_date == date(2026, 8, 14)

    def test_departure_mon_28_dec_cutoff_is_wed_23_dec(self) -> None:
        # 24 Dec (Thu, cuti bersama) and 25 Dec (Fri, libur nasional) are
        # closed, and 26-27 Dec is the weekend -- last open day is Wed 23 Dec.
        today = date(2026, 12, 23)
        req = _issuance(entry_date=date(2026, 12, 28))
        verdict = build_verdict(req, today=today)
        assert verdict.accepted is True
        assert verdict.submit_by_date == date(2026, 12, 23)

    def test_departure_past_coverage_end_fails_closed_and_hands_off_to_a_human(
        self,
    ) -> None:
        # A 2027 arrival date -- the 2027 SKB does not exist yet, so the
        # cutoff cannot be computed without guessing. Must NEVER silently
        # guess a date, and must decline distinctly from "too soon".
        # today is chosen so the date is still INSIDE the eVOA usability
        # window: only the calendar-coverage gate may fire here.
        today = date(2026, 12, 1)
        req = _issuance(entry_date=COVERAGE_END + timedelta(days=5))
        assert (req.entry_date - today).days < EVOA_USABILITY_WINDOW_DAYS
        verdict = build_verdict(req, today=today)
        assert verdict.decision is Decision.DECLINE
        assert "ARRIVAL_DATE_UNCONFIRMED" in verdict.decline_codes
        assert "ARRIVAL_TOO_SOON" not in verdict.decline_codes
        assert "ARRIVAL_TOO_FAR" not in verdict.decline_codes
        assert verdict.submit_by_date is None

    def test_extension_path_is_completely_unaffected_by_this_gate(self) -> None:
        # An extension's entry_date is the ORIGINAL entry (always in the
        # past) -- if this issuance-only gate ever ran for extensions it
        # would decline every one of them. It must never run: the decision
        # here is governed purely by the (untouched) runway gate, and
        # submit_by_date must stay None.
        today = date(2026, 7, 27)
        req = _extension()  # entry_date = today - 20 days, well within the runway
        verdict = build_verdict(req, today=today)
        assert verdict.accepted is True
        assert verdict.submit_by_date is None

    def test_extension_past_coverage_end_entry_date_is_still_unaffected(self) -> None:
        # Belt-and-braces: even an extension whose (past) original entry_date
        # sits outside the calendar's coverage window must not trip the
        # issuance-only fail-closed path.
        #
        # entry_date is 2026-06-20 (before COVERAGE_START 2026-07-28, so
        # still "outside coverage" for this test's purpose) rather than the
        # original 2020-01-01: the max-total-stay guard (added 2026-08-23,
        # TestB1MaxTotalStayBoundary) correctly declines a printed expiry
        # implying a multi-thousand-day stay from a 2020 entry, which would
        # mask what THIS test checks. 55 days of runway keeps the
        # day-difference at 55 (< the 60-day max) and stays clear of it.
        today = date(2026, 7, 27)
        req = _extension(entry_date=date(2026, 6, 20), voa_expiry_date=today + timedelta(days=18))
        verdict = build_verdict(req, today=today)
        assert verdict.accepted is True
        assert verdict.submit_by_date is None


class TestIssuanceUsabilityWindowGate:
    """GARUDA B1 truth-sheet (line 41, verified 14 Jul 2026): an eVOA is
    usable for 90 days from issuance. The engine has no issuance_date input,
    so `today` is the anchor; this gate declines issuance requests whose
    arrival is strictly later than `today + EVOA_USABILITY_WINDOW_DAYS`.
    It is issuance-only and must never run for an extension case."""

    def test_entry_91_days_out_declines_with_arrival_too_far(self) -> None:
        # GUILT: 91 days is the first day outside the window.
        today = date(2026, 8, 24)
        entry = today + timedelta(days=91)
        req = _issuance(entry_date=entry)
        verdict = build_verdict(req, today=today)
        assert verdict.decision is Decision.DECLINE
        assert "ARRIVAL_TOO_FAR" in verdict.decline_codes
        assert "ARRIVAL_DATE_UNCONFIRMED" not in verdict.decline_codes
        assert "ARRIVAL_TOO_SOON" not in verdict.decline_codes
        # A usability decline must not suppress a truthful calendar cutoff.
        assert verdict.submit_by_date == date(2026, 11, 20)

    def test_entry_exactly_at_90_days_accepts(self) -> None:
        # BOUNDARY: the 90th day is still inside the window. The gate uses a
        # strict `>` comparison, so today+90 itself is accepted.
        today = date(2026, 8, 24)
        entry = today + timedelta(days=EVOA_USABILITY_WINDOW_DAYS)
        req = _issuance(entry_date=entry)
        verdict = build_verdict(req, today=today)
        assert verdict.accepted is True
        assert "ARRIVAL_TOO_FAR" not in verdict.decline_codes

    def test_ordinary_near_term_issuance_is_unaffected(self) -> None:
        # INNOCENCE: existing near-term issuance shape stays ACCEPT.
        today = date(2026, 8, 24)
        req = _issuance(entry_date=today + timedelta(days=5))
        verdict = build_verdict(req, today=today)
        assert verdict.accepted is True
        assert "ARRIVAL_TOO_FAR" not in verdict.decline_codes

    def test_extension_far_future_date_is_not_hit_by_this_gate(self) -> None:
        # EXTENSION INNOCENCE: the gate is structurally issuance-only.
        # An extension case with a far-future-shaped original entry_date would
        # exceed the window if misapplied; it must remain governed by the
        # extension runway / max-stay rules, not this gate.
        today = date(2026, 8, 24)
        req = _extension(
            entry_date=today + timedelta(days=120),
            voa_expiry_date=today + timedelta(days=150),
        )
        verdict = build_verdict(req, today=today)
        assert "ARRIVAL_TOO_FAR" not in verdict.decline_codes

    def test_beyond_coverage_and_beyond_window_collects_both_reasons(self) -> None:
        # Both independent gates report their reason; no cutoff is guessed.
        today = date(2026, 6, 1)
        req = _issuance(entry_date=COVERAGE_END + timedelta(days=5))
        assert (req.entry_date - today).days > EVOA_USABILITY_WINDOW_DAYS
        verdict = build_verdict(req, today=today)
        assert verdict.decision is Decision.DECLINE
        assert "ARRIVAL_TOO_FAR" in verdict.decline_codes
        assert "ARRIVAL_DATE_UNCONFIRMED" in verdict.decline_codes
        assert verdict.submit_by_date is None


class TestReasonCompleteness:
    def test_collects_multiple_failing_reasons(self) -> None:
        entry = _TODAY + timedelta(days=5)
        req = _issuance(
            self_pay=False,
            passport_expiry_date=entry,  # 0 days validity — well short
        )
        verdict = build_verdict(req, today=_TODAY)
        assert verdict.decision is Decision.DECLINE
        assert len(verdict.decline_reasons) >= 2

    def test_business_group_keeps_parallel_duplicate_audit_entries(self) -> None:
        verdict = build_verdict(
            _issuance(purpose=Purpose.BUSINESS_MEETING, travellers=2),
            today=_TODAY,
        )

        assert verdict.decline_codes == [
            "PURPOSE_NOT_ELIGIBLE",
            "GROUP_CASE",
            "GROUP_CASE",
            "PURPOSE_NOT_ELIGIBLE",
        ]
        assert verdict.decline_reasons == [
            "not a simple-tourism case",
            "not a single adult traveler",
            "family/group case (excluded from pilot)",
            "work/business purpose (B1 does not permit work)",
        ]
        assert len(verdict.decline_codes) == len(verdict.decline_reasons)


class TestClientFacingBoundary:
    """Spec §6 charter: only D-7 may ever reach a visitor."""

    def test_published_filing_deadline_is_the_d7_date(self) -> None:
        verdict = build_verdict(_issuance(), today=_TODAY)
        assert verdict.published_filing_deadline == verdict.stay_window.published_filing_deadline

    def test_only_one_client_facing_checkpoint(self) -> None:
        verdict = build_verdict(_issuance(), today=_TODAY)
        assert len(verdict.client_facing_checkpoints) == 1
        assert verdict.client_facing_checkpoints[0].label == "D-7"

    def test_internal_checkpoints_cover_d14_d10_d3_d1(self) -> None:
        verdict = build_verdict(_issuance(), today=_TODAY)
        labels = {c.label for c in verdict.internal_checkpoints}
        assert labels == {"D-14", "D-10", "D-3", "D-1"}

    def test_client_and_internal_checkpoints_partition_all_of_them(self) -> None:
        verdict = build_verdict(_issuance(), today=_TODAY)
        all_labels = {c.label for c in verdict.stay_window.checkpoints}
        split_labels = {c.label for c in verdict.client_facing_checkpoints} | {
            c.label for c in verdict.internal_checkpoints
        }
        assert all_labels == split_labels

    def test_checkpoint_at_looks_up_by_label(self) -> None:
        verdict = build_verdict(_issuance(), today=_TODAY)
        d7 = verdict.checkpoint_at("D-7")
        assert d7 == verdict.published_filing_deadline


class TestNationalityEligibility:
    """End-to-end wiring of the nationality-eligibility dataset (2026-08-23)
    through `build_verdict`. `test_nationality_eligibility.py` pins the
    dataset and the pure lookup function in isolation; this class pins the
    full request -> verdict path, including the decline reason/code.

    Before this dataset existed, `nationality_entry_eligible` was hardcoded
    `True`, so `AFG` (not VOA-eligible) silently ACCEPTed — this class's
    guilt tests are the ones that were RED against that old code and are
    GREEN against the fix.
    """

    def test_afg_declines_with_the_nationality_reason(self) -> None:
        verdict = build_verdict(_issuance(nationality="AFG"), today=_TODAY)
        assert verdict.decision is Decision.DECLINE
        assert "NATIONALITY_NOT_ELIGIBLE" in verdict.decline_codes
        assert any("nationality" in r and "not eligible" in r for r in verdict.decline_reasons)

    def test_prk_also_declines_with_the_nationality_reason(self) -> None:
        # A second non-listed nationality so the guilt case isn't a
        # single-fixture coincidence.
        verdict = build_verdict(_issuance(nationality="PRK"), today=_TODAY)
        assert verdict.decision is Decision.DECLINE
        assert "NATIONALITY_NOT_ELIGIBLE" in verdict.decline_codes

    def test_usa_default_fixture_still_accepts(self) -> None:
        # `_issuance()`'s default nationality is "USA" — every other test in
        # this file already exercises this implicitly; this test makes the
        # nationality dependency explicit and named.
        verdict = build_verdict(_issuance(), today=_TODAY)
        assert verdict.accepted is True

    def test_lowercase_nationality_is_not_case_sensitive_end_to_end(self) -> None:
        # `internal_preview_cli.InternalPreviewRequest` normalises to upper
        # case before `VoaIntakeRequest` is ever built in production, but a
        # direct caller of `build_verdict` must not silently mis-decline a
        # perfectly eligible lower-case nationality.
        verdict = build_verdict(_issuance(nationality="usa"), today=_TODAY)
        assert verdict.accepted is True


class TestPurity:
    def test_intake_request_is_frozen(self) -> None:
        req = _issuance()
        with pytest.raises(dataclasses.FrozenInstanceError):
            req.self_pay = False  # type: ignore[misc]

    def test_verdict_is_frozen(self) -> None:
        verdict = build_verdict(_issuance(), today=_TODAY)
        with pytest.raises(dataclasses.FrozenInstanceError):
            verdict.decision = Decision.DECLINE  # type: ignore[misc]

    def test_same_input_and_today_is_deterministic(self) -> None:
        # No I/O, no wall-clock inside — same (request, today) must always
        # produce the same verdict.
        req = _extension()
        v1 = build_verdict(req, today=_TODAY)
        v2 = build_verdict(req, today=_TODAY)
        assert v1.decision == v2.decision
        assert v1.decline_reasons == v2.decline_reasons
        assert v1.stay_window == v2.stay_window


class TestTruthFreshnessGate:
    """G-FRESHNESS-FAIL-CLOSED (DECISIONS.md Q9, `freshness.py`) at the
    `build_verdict` integration point. `conftest.py`'s autouse fixture pins
    both checks to FRESH for every OTHER test in this file — these tests
    override that pin, on top of it, to exercise the STALE path
    specifically. Proven to bite both ways: an otherwise-ACCEPT request
    DECLINEs the moment either dependency goes stale, and reverts to its
    original verdict the moment freshness is restored.
    """

    def _stale(self, source: str) -> freshness.FreshnessReport:
        return freshness.FreshnessReport(
            source=source,
            verdict=freshness.FreshnessVerdict.STALE,
            stamp="2020-01-01",
            age_days=9999,
            max_age_days=freshness.MAX_AGE_DAYS[source],
            detail="test: forced stale",
        )

    def test_stale_nationality_eligibility_declines_an_otherwise_accepted_case(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        baseline = build_verdict(_issuance(), today=_TODAY)
        assert baseline.accepted is True  # sanity: this request is a real ACCEPT

        monkeypatch.setattr(
            freshness,
            "nationality_eligibility_freshness",
            lambda *, today: self._stale("nationality_eligibility"),
        )
        verdict = build_verdict(_issuance(), today=_TODAY)
        assert verdict.decision is Decision.DECLINE
        assert "ELIGIBILITY_UNCONFIRMED" in verdict.decline_codes

    def test_stale_rule_constants_declines_an_otherwise_accepted_case(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        baseline = build_verdict(_issuance(), today=_TODAY)
        assert baseline.accepted is True

        monkeypatch.setattr(
            freshness,
            "rule_constants_freshness",
            lambda *, today: self._stale("rule_constants"),
        )
        verdict = build_verdict(_issuance(), today=_TODAY)
        assert verdict.decision is Decision.DECLINE
        assert "ELIGIBILITY_UNCONFIRMED" in verdict.decline_codes

    def test_restoring_freshness_restores_the_original_verdict(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The other direction of the same guard: once patched back to FRESH
        # (conftest's own default, reapplied here explicitly for clarity),
        # the request accepts again exactly as it did before the gate ever
        # ran — the guard adds a decline path, it does not change the
        # underlying eligibility computation.
        monkeypatch.setattr(
            freshness,
            "nationality_eligibility_freshness",
            lambda *, today: self._stale("nationality_eligibility"),
        )
        assert build_verdict(_issuance(), today=_TODAY).decision is Decision.DECLINE

        monkeypatch.undo()
        assert build_verdict(_issuance(), today=_TODAY).accepted is True

    def test_stale_source_does_not_suppress_other_decline_reasons(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # House style: never short-circuit, collect every failing reason.
        # A request that is ALSO ineligible on nationality must show BOTH
        # codes when the truth sheet is stale, not just one.
        monkeypatch.setattr(
            freshness,
            "nationality_eligibility_freshness",
            lambda *, today: self._stale("nationality_eligibility"),
        )
        verdict = build_verdict(_issuance(nationality="PRK"), today=_TODAY)
        assert verdict.decision is Decision.DECLINE
        assert "ELIGIBILITY_UNCONFIRMED" in verdict.decline_codes
        assert "NATIONALITY_NOT_ELIGIBLE" in verdict.decline_codes

    def test_extension_path_is_also_covered_by_the_gate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Unconditional per DECISIONS.md Q9 — both case shapes depend on
        # the rule bundle, not issuance alone.
        baseline = build_verdict(_extension(), today=_TODAY)
        assert baseline.accepted is True

        monkeypatch.setattr(
            freshness,
            "rule_constants_freshness",
            lambda *, today: self._stale("rule_constants"),
        )
        verdict = build_verdict(_extension(), today=_TODAY)
        assert verdict.decision is Decision.DECLINE
        assert "ELIGIBILITY_UNCONFIRMED" in verdict.decline_codes
