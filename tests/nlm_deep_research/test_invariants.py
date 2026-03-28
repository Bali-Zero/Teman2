"""Tests for invariants.py — all 10 invariant checks."""

from __future__ import annotations

import pytest

from apps.evaluator.nlm_deep_research.invariants import (
    EXPECTED_STATE_VERSION,
    ILM_THRESHOLD,
    MAX_ACTIVE_SOURCES,
    MAX_CONSECUTIVE_FAILURES,
    MAX_QUARANTINE_SOURCES,
    MAX_WEEKLY_API_CALLS,
    MIN_MASTER_DIGEST_SOURCES,
    InvariantResult,
    InvariantSeverity,
    check_active_count,
    check_all_invariants,
    check_claims_append_only,
    check_consecutive_failures,
    check_ilm,
    check_master_digest_count,
    check_no_balizero,
    check_pipeline_deadline,
    check_quarantine_count,
    check_state_version,
    check_weekly_budget,
)

from .conftest import make_pipeline_state, make_sources_dict


# =====================================================================
# INV_ACTIVE_COUNT
# =====================================================================


class TestActiveCount:
    """INV_ACTIVE_COUNT: ACTIVE sources must be <= 70."""

    def test_below_limit_passes(self):
        sources = make_sources_dict(active=50)
        result = check_active_count(sources)
        assert result.passed is True
        assert result.invariant_id == "INV_ACTIVE_COUNT"
        assert result.severity == InvariantSeverity.CRITICAL

    def test_at_limit_passes(self):
        sources = make_sources_dict(active=MAX_ACTIVE_SOURCES)
        result = check_active_count(sources)
        assert result.passed is True

    def test_above_limit_fails(self):
        sources = make_sources_dict(active=MAX_ACTIVE_SOURCES + 1)
        result = check_active_count(sources)
        assert result.passed is False
        assert result.current_value == MAX_ACTIVE_SOURCES + 1

    def test_zero_active_passes(self):
        sources = make_sources_dict(active=0)
        result = check_active_count(sources)
        assert result.passed is True


# =====================================================================
# INV_QUARANTINE_COUNT
# =====================================================================


class TestQuarantineCount:
    """INV_QUARANTINE_COUNT: QUARANTINE sources must be <= 30."""

    def test_below_limit_passes(self):
        sources = make_sources_dict(quarantine=10)
        result = check_quarantine_count(sources)
        assert result.passed is True
        assert result.severity == InvariantSeverity.WARNING

    def test_above_limit_fails(self):
        sources = make_sources_dict(quarantine=MAX_QUARANTINE_SOURCES + 5)
        result = check_quarantine_count(sources)
        assert result.passed is False


# =====================================================================
# INV_ILM
# =====================================================================


class TestILM:
    """INV_ILM: Information Loss Metric must be < 0.05."""

    def test_no_loss_passes(self):
        result = check_ilm(claims_before=100, claims_after=100)
        assert result.passed is True
        assert result.current_value == pytest.approx(0.0)

    def test_minimal_loss_passes(self):
        result = check_ilm(claims_before=100, claims_after=96)
        assert result.passed is True
        assert result.current_value < ILM_THRESHOLD

    def test_significant_loss_fails(self):
        result = check_ilm(claims_before=100, claims_after=90)
        assert result.passed is False
        assert result.severity == InvariantSeverity.CRITICAL
        assert result.current_value == pytest.approx(0.10)

    def test_zero_before_passes(self):
        result = check_ilm(claims_before=0, claims_after=0)
        assert result.passed is True
        assert result.severity == InvariantSeverity.INFO

    def test_negative_before_passes(self):
        result = check_ilm(claims_before=-1, claims_after=5)
        assert result.passed is True

    def test_exactly_at_threshold_fails(self):
        # ILM = 0.05 exactly — spec says "< 0.05", not "<="
        result = check_ilm(claims_before=100, claims_after=95)
        assert result.passed is False  # 0.05 is NOT < 0.05


# =====================================================================
# INV_NO_BALIZERO
# =====================================================================


class TestNoBalizero:
    """INV_NO_BALIZERO: No source URL may contain denied domains."""

    def test_clean_sources_pass(self):
        sources = make_sources_dict(active=5)
        result = check_no_balizero(sources)
        assert result.passed is True

    def test_balizero_url_fails(self):
        sources = make_sources_dict(denied_urls=["https://balizero.com/article"])
        result = check_no_balizero(sources)
        assert result.passed is False
        assert result.severity == InvariantSeverity.CRITICAL

    def test_tripadvisor_url_fails(self):
        sources = make_sources_dict(denied_urls=["https://tripadvisor.com/bali"])
        result = check_no_balizero(sources)
        assert result.passed is False

    def test_multiple_violations_counted(self):
        sources = make_sources_dict(
            denied_urls=[
                "https://reddit.com/r/bali",
                "https://quora.com/bali-visa",
                "https://youtube.com/watch?v=abc",
            ]
        )
        result = check_no_balizero(sources)
        assert result.passed is False
        assert result.current_value == 3.0

    def test_empty_sources_pass(self):
        result = check_no_balizero({})
        assert result.passed is True


# =====================================================================
# INV_MASTER_DIGEST_COUNT
# =====================================================================


class TestMasterDigestCount:
    """INV_MASTER_DIGEST_COUNT: Master Digest sources must be >= 4."""

    def test_sufficient_digests_pass(self):
        sources = make_sources_dict(active=10, master_digests=5)
        result = check_master_digest_count(sources)
        assert result.passed is True

    def test_insufficient_digests_fail(self):
        sources = make_sources_dict(active=10, master_digests=2)
        result = check_master_digest_count(sources)
        assert result.passed is False
        assert result.severity == InvariantSeverity.CRITICAL

    def test_exactly_at_minimum_passes(self):
        sources = make_sources_dict(active=4, master_digests=4)
        result = check_master_digest_count(sources)
        assert result.passed is True


# =====================================================================
# INV_CONSECUTIVE_FAILURES
# =====================================================================


class TestConsecutiveFailures:
    """INV_CONSECUTIVE_FAILURES: Consecutive NLM failures must be < 3."""

    def test_zero_failures_passes(self):
        result = check_consecutive_failures(0)
        assert result.passed is True

    def test_two_failures_passes(self):
        result = check_consecutive_failures(2)
        assert result.passed is True

    def test_three_failures_fails(self):
        result = check_consecutive_failures(3)
        assert result.passed is False
        assert result.severity == InvariantSeverity.CRITICAL

    def test_many_failures_fails(self):
        result = check_consecutive_failures(10)
        assert result.passed is False


# =====================================================================
# INV_WEEKLY_BUDGET
# =====================================================================


class TestWeeklyBudget:
    """INV_WEEKLY_BUDGET: Weekly API calls must be <= 40."""

    def test_under_budget_passes(self):
        result = check_weekly_budget(10)
        assert result.passed is True
        assert result.severity == InvariantSeverity.WARNING

    def test_at_budget_passes(self):
        result = check_weekly_budget(MAX_WEEKLY_API_CALLS)
        assert result.passed is True

    def test_over_budget_fails(self):
        result = check_weekly_budget(MAX_WEEKLY_API_CALLS + 1)
        assert result.passed is False


# =====================================================================
# INV_PIPELINE_DEADLINE
# =====================================================================


class TestPipelineDeadline:
    """INV_PIPELINE_DEADLINE: Pipeline must complete by 02:30 WITA."""

    def test_before_deadline_passes(self):
        result = check_pipeline_deadline("2026-03-28T01:00:00+08:00")
        assert result.passed is True

    def test_at_deadline_passes(self):
        result = check_pipeline_deadline("2026-03-28T02:30:00+08:00")
        assert result.passed is True

    def test_after_deadline_fails(self):
        result = check_pipeline_deadline("2026-03-28T03:00:00+08:00")
        assert result.passed is False

    def test_utc_time_converted_to_wita(self):
        # 18:30 UTC = 02:30 WITA (next day)
        result = check_pipeline_deadline("2026-03-27T18:30:00+00:00")
        assert result.passed is True

    def test_invalid_time_fails(self):
        result = check_pipeline_deadline("not-a-time")
        assert result.passed is False
        assert result.severity == InvariantSeverity.WARNING

    def test_naive_datetime_assumed_wita(self):
        result = check_pipeline_deadline("2026-03-28T01:30:00")
        assert result.passed is True


# =====================================================================
# INV_STATE_VERSION
# =====================================================================


class TestStateVersion:
    """INV_STATE_VERSION: State file version must match expected."""

    def test_matching_version_passes(self):
        result = check_state_version(EXPECTED_STATE_VERSION)
        assert result.passed is True

    def test_mismatched_version_fails(self):
        result = check_state_version(999)
        assert result.passed is False
        assert result.severity == InvariantSeverity.CRITICAL


# =====================================================================
# INV_CLAIMS_APPEND_ONLY
# =====================================================================


class TestClaimsAppendOnly:
    """INV_CLAIMS_APPEND_ONLY: Claims count must never decrease."""

    def test_increase_passes(self):
        result = check_claims_append_only(previous_count=10, current_count=15)
        assert result.passed is True

    def test_equal_passes(self):
        result = check_claims_append_only(previous_count=10, current_count=10)
        assert result.passed is True

    def test_decrease_fails(self):
        result = check_claims_append_only(previous_count=10, current_count=8)
        assert result.passed is False
        assert result.severity == InvariantSeverity.CRITICAL

    def test_zero_to_zero_passes(self):
        result = check_claims_append_only(previous_count=0, current_count=0)
        assert result.passed is True


# =====================================================================
# check_all_invariants — aggregate
# =====================================================================


class TestCheckAllInvariants:
    """Tests for the aggregate invariant runner."""

    def test_all_pass_with_healthy_state(self):
        sources = make_sources_dict(active=50, master_digests=5)
        state = make_pipeline_state()
        results = check_all_invariants(sources, state, claims_count=15)
        assert len(results) == 10
        assert all(r.passed for r in results)

    def test_returns_10_results_always(self):
        sources = make_sources_dict()
        state = make_pipeline_state()
        results = check_all_invariants(sources, state, claims_count=10)
        assert len(results) == 10

    def test_critical_failures_detected(self):
        sources = make_sources_dict(active=80, master_digests=1)
        state = make_pipeline_state(
            consecutive_failures=5,
            version=999,
        )
        results = check_all_invariants(sources, state, claims_count=5)
        failed_critical = [
            r for r in results
            if not r.passed and r.severity == InvariantSeverity.CRITICAL
        ]
        assert len(failed_critical) >= 2  # active_count, master_digest, failures, version

    def test_claims_decrease_detected(self):
        sources = make_sources_dict()
        state = make_pipeline_state(previous_claims_count=20)
        results = check_all_invariants(sources, state, claims_count=10)
        append_check = [r for r in results if r.invariant_id == "INV_CLAIMS_APPEND_ONLY"]
        assert len(append_check) == 1
        assert append_check[0].passed is False

    def test_invariant_result_is_frozen(self):
        """InvariantResult is frozen — attributes cannot be modified."""
        result = InvariantResult(
            invariant_id="TEST",
            passed=True,
            severity=InvariantSeverity.INFO,
            message="test",
        )
        with pytest.raises(AttributeError):
            result.passed = False  # type: ignore
