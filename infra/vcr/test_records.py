"""Tests for infra/vcr/records.py — the 4-axis vocabulary.

Guilt AND innocence per validated field (scar #3): an invalid axis value must
raise; a valid one must construct cleanly and round-trip through to_dict/from_dict.
"""

from __future__ import annotations

import pytest

from infra.vcr.records import (
    CURRENT,
    FAILED,
    HEALTHY,
    MISSING,
    PRESENT,
    TRUE,
    UNVERIFIED,
    ClaimContext,
    ClaimObservation,
    MaterializedState,
)


def test_claim_context_key_is_stable():
    ctx = ClaimContext(host="m5", auth_context="interactive")
    assert ctx.key() == "m5::interactive"


def test_observation_round_trip():
    ctx = ClaimContext(host="m5", auth_context="interactive")
    obs = ClaimObservation(
        claim_id="claude::m5::interactive",
        claim_type="seat_health",
        subject_id="claude",
        context=ctx,
        observed_at="2026-08-03T12:00:00Z",
        raw_status="LIVE",
        raw_evidence="PONG",
        latency_ms=120,
        truth_state=TRUE,
        truth_reason="dispatch succeeded",
    )
    d = obs.to_dict()
    restored = ClaimObservation.from_dict(d)
    assert restored == obs


def test_observation_rejects_invalid_truth_state():
    ctx = ClaimContext(host="m5", auth_context="interactive")
    with pytest.raises(ValueError):
        ClaimObservation(
            claim_id="x", claim_type="seat_health", subject_id="claude", context=ctx,
            observed_at="2026-08-03T12:00:00Z", raw_status="LIVE", raw_evidence="",
            latency_ms=1, truth_state="MAYBE", truth_reason="",
        )


def test_materialized_state_all_healthy_true_case():
    ctx = ClaimContext(host="m5", auth_context="interactive")
    st = MaterializedState(
        seat="claude", context=ctx, truth_state=TRUE, freshness_state=CURRENT,
        coverage_state=PRESENT, verifier_state=HEALTHY, reason="ok",
        observed_at="2026-08-03T12:00:00Z",
    )
    assert st.all_healthy() is True


def test_materialized_state_all_healthy_false_when_one_axis_off():
    """Innocence's mirror: ONE bad axis must flip all_healthy() to False —
    proves the check is a conjunction, not accidentally true-by-default."""
    ctx = ClaimContext(host="m5", auth_context="interactive")
    st = MaterializedState(
        seat="claude", context=ctx, truth_state=UNVERIFIED, freshness_state=CURRENT,
        coverage_state=PRESENT, verifier_state=HEALTHY, reason="stale probe",
        observed_at=None,
    )
    assert st.all_healthy() is False


def test_materialized_state_rejects_invalid_axis():
    ctx = ClaimContext(host="m5", auth_context="interactive")
    with pytest.raises(ValueError):
        MaterializedState(
            seat="claude", context=ctx, truth_state=TRUE, freshness_state="ROTTEN",
            coverage_state=PRESENT, verifier_state=HEALTHY, reason="", observed_at=None,
        )


def test_materialized_state_coverage_missing_is_valid_and_not_healthy():
    ctx = ClaimContext(host="mini", auth_context="cron-token-1")
    st = MaterializedState(
        seat="claude", context=ctx, truth_state=UNVERIFIED, freshness_state="EXPIRED",
        coverage_state=MISSING, verifier_state=HEALTHY, reason="never observed",
        observed_at=None,
    )
    assert st.coverage_state == MISSING
    assert st.all_healthy() is False
