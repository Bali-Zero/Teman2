"""Tests for infra/vcr/store.py — append-only observation log.

Guilt AND innocence (scar #3): a corrupt line must surface as an error, never
silently vanish; a clean log must read back exactly what was appended, in order.
"""

from __future__ import annotations

import os

import pytest

from infra.vcr.records import ClaimContext, ClaimObservation
from infra.vcr import store as store_mod


@pytest.fixture()
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setenv("VCR_STORE_HOME", str(tmp_path))
    return tmp_path


def _obs(subject="claude", status="LIVE", truth="TRUE", ts="2026-08-03T12:00:00Z"):
    ctx = ClaimContext(host="m5", auth_context="interactive")
    return ClaimObservation(
        claim_id=f"{subject}::{ctx.key()}", claim_type="seat_health", subject_id=subject,
        context=ctx, observed_at=ts, raw_status=status, raw_evidence="ev",
        latency_ms=10, truth_state=truth, truth_reason="r",
    )


def test_append_then_read_round_trip(tmp_store):
    o1 = _obs(ts="2026-08-03T12:00:00Z")
    o2 = _obs(ts="2026-08-03T12:01:00Z", status="AUTH_DEAD", truth="FALSE")
    store_mod.append_observation(o1)
    store_mod.append_observation(o2)
    obs, errors = store_mod.read_observations("claude", o1.context)
    assert errors == []
    assert obs == [o1, o2]


def test_read_missing_log_returns_empty_not_error(tmp_store):
    ctx = ClaimContext(host="m5", auth_context="interactive")
    obs, errors = store_mod.read_observations("nonexistent-seat", ctx)
    assert obs == []
    assert errors == []


def test_corrupt_line_surfaces_as_error_not_silently_dropped(tmp_store):
    """Guilt: corruption must be VISIBLE (fail-visible discipline)."""
    o1 = _obs()
    store_mod.append_observation(o1)
    path = store_mod.log_path("claude", o1.context)
    with path.open("a", encoding="utf-8") as f:
        f.write("{not json\n")
    obs, errors = store_mod.read_observations("claude", o1.context)
    assert obs == [o1]
    assert len(errors) == 1
    assert "corrupt" in errors[0]


def test_limit_returns_last_n_in_chronological_order(tmp_store):
    ctx = ClaimContext(host="m5", auth_context="interactive")
    for i in range(5):
        store_mod.append_observation(_obs(ts=f"2026-08-03T12:0{i}:00Z"))
    obs, _ = store_mod.read_observations("claude", ctx, limit=2)
    assert [o.observed_at for o in obs] == ["2026-08-03T12:03:00Z", "2026-08-03T12:04:00Z"]


def test_different_contexts_are_isolated_logs(tmp_store):
    """Innocence: writing under one context must not leak into another's log —
    this is R1's whole point (context-keyed, never a shared bucket)."""
    ctx_a = ClaimContext(host="m5", auth_context="interactive")
    ctx_b = ClaimContext(host="mini", auth_context="cron-token-1")
    obs_a = ClaimObservation(
        claim_id="claude::a", claim_type="seat_health", subject_id="claude", context=ctx_a,
        observed_at="t", raw_status="LIVE", raw_evidence="", latency_ms=1,
        truth_state="TRUE", truth_reason="",
    )
    obs_b = ClaimObservation(
        claim_id="claude::b", claim_type="seat_health", subject_id="claude", context=ctx_b,
        observed_at="t", raw_status="AUTH_DEAD", raw_evidence="", latency_ms=1,
        truth_state="FALSE", truth_reason="",
    )
    store_mod.append_observation(obs_a)
    store_mod.append_observation(obs_b)
    read_a, _ = store_mod.read_observations("claude", ctx_a)
    read_b, _ = store_mod.read_observations("claude", ctx_b)
    assert read_a == [obs_a]
    assert read_b == [obs_b]
