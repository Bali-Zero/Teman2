"""Tests for infra/vcr/materializer.py — hysteresis debounce (R2).

Guilt: 2 consecutive same-value observations flip the confirmed state.
Innocence: a single flaky observation (in either direction) must NOT flip it —
this is the whole point of R2 and the pilot's own false-positive criterion.
"""

from __future__ import annotations

from infra.vcr.materializer import derive_truth_state
from infra.vcr.records import ClaimContext, ClaimObservation, FALSE, TRUE, UNVERIFIED


def _o(status_truth: str, ts: str):
    ctx = ClaimContext(host="m5", auth_context="interactive")
    return ClaimObservation(
        claim_id="claude::m5::interactive", claim_type="seat_health", subject_id="claude",
        context=ctx, observed_at=ts, raw_status="x", raw_evidence="", latency_ms=1,
        truth_state=status_truth, truth_reason="",
    )


def test_empty_log_is_unverified():
    state, reason = derive_truth_state([])
    assert state == UNVERIFIED
    assert "no observations" in reason


def test_single_observation_trusted_as_is():
    obs = [_o(TRUE, "t0")]
    state, _ = derive_truth_state(obs)
    assert state == TRUE


def test_innocence_single_flaky_failure_does_not_flip():
    """A lone FALSE between two TRUEs must not flip the confirmed state."""
    obs = [_o(TRUE, "t0"), _o(TRUE, "t1"), _o(FALSE, "t2"), _o(TRUE, "t3")]
    state, reason = derive_truth_state(obs)
    assert state == TRUE, reason


def test_guilt_two_consecutive_failures_flip():
    obs = [_o(TRUE, "t0"), _o(TRUE, "t1"), _o(FALSE, "t2"), _o(FALSE, "t3")]
    state, reason = derive_truth_state(obs)
    assert state == FALSE, reason


def test_symmetric_recovery_requires_two_consecutive_true():
    """After a confirmed FALSE, a single TRUE must not recover it; two must."""
    obs = [_o(TRUE, "t0"), _o(FALSE, "t1"), _o(FALSE, "t2"), _o(TRUE, "t3")]
    state, reason = derive_truth_state(obs)
    assert state == FALSE, "one recovery sample must not flip it back: " + reason

    obs2 = obs + [_o(TRUE, "t4")]
    state2, reason2 = derive_truth_state(obs2)
    assert state2 == TRUE, reason2


def test_alternating_never_confirms_a_flip():
    """Pure alternation (no 2 consecutive agreement) must never leave the
    original confirmed value — proves the debounce isn't accidentally a
    majority-vote or a last-value passthrough."""
    obs = [_o(TRUE, "t0"), _o(FALSE, "t1"), _o(TRUE, "t2"), _o(FALSE, "t3"), _o(TRUE, "t4")]
    state, reason = derive_truth_state(obs)
    assert state == TRUE, reason


def test_reason_mentions_debounce_when_pending_not_confirmed():
    obs = [_o(TRUE, "t0"), _o(TRUE, "t1"), _o(FALSE, "t2")]
    state, reason = derive_truth_state(obs)
    assert state == TRUE
    assert "not yet confirmed" in reason
