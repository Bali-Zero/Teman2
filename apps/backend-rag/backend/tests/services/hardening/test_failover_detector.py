"""Tests for FailoverDetector — peer state thresholds + graceful lookup errors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.services.hardening.failover_detector import (
    FailoverDetector,
    PeerState,
)


def _now() -> datetime:
    return datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_state_up_when_heartbeat_fresh():
    async def lookup(peer):
        return _now() - timedelta(minutes=5)

    det = FailoverDetector(heartbeat_lookup_fn=lookup)
    state = await det.check("Nuzantara", now=_now())
    assert state.state == PeerState.UP
    assert state.should_failover is False
    assert state.minutes_since_beat == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_state_stale_between_15_and_30_min():
    async def lookup(peer):
        return _now() - timedelta(minutes=20)

    det = FailoverDetector(heartbeat_lookup_fn=lookup)
    state = await det.check("Nuzantara", now=_now())
    assert state.state == PeerState.STALE
    # stale does NOT poach yet (Pro may wake) — per design
    assert state.should_failover is False


@pytest.mark.asyncio
async def test_state_down_above_30_min():
    async def lookup(peer):
        return _now() - timedelta(minutes=45)

    det = FailoverDetector(heartbeat_lookup_fn=lookup)
    state = await det.check("Nuzantara", now=_now())
    assert state.state == PeerState.DOWN
    assert state.should_failover is True


@pytest.mark.asyncio
async def test_no_heartbeat_ever_is_conservatively_down():
    async def lookup(peer):
        return None

    det = FailoverDetector(heartbeat_lookup_fn=lookup)
    state = await det.check("Nuzantara", now=_now())
    assert state.state == PeerState.DOWN
    assert state.should_failover is True
    assert state.reason == "no_heartbeat_ever"
    assert state.last_beat is None


@pytest.mark.asyncio
async def test_lookup_exception_treated_as_down():
    async def lookup(peer):
        raise RuntimeError("pg pool broken")

    det = FailoverDetector(heartbeat_lookup_fn=lookup)
    state = await det.check("Nuzantara", now=_now())
    assert state.state == PeerState.DOWN
    assert state.should_failover is True
    assert "lookup_error" in state.reason


@pytest.mark.asyncio
async def test_custom_thresholds_honoured():
    async def lookup(peer):
        return _now() - timedelta(minutes=6)

    det = FailoverDetector(
        heartbeat_lookup_fn=lookup,
        stale_after_min=5,
        down_after_min=10,
    )
    state = await det.check("Nuzantara", now=_now())
    assert state.state == PeerState.STALE
