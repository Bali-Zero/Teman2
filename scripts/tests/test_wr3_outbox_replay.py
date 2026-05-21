"""Tests for outbox replay on supervisor reconnect — Symbiosis Law 3.

When the supervisor reconnects to PG after a disconnect, unconsumed events
within the 60-minute durability window must be replayed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wr3_supervisor  # noqa: E402
from wr3_contracts import load_contracts  # noqa: E402


@pytest.fixture(scope="module")
def contracts():
    return load_contracts()


@pytest.fixture
def fake_conn_with_outbox():
    """Conn with 3 fake unconsumed outbox rows."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[
        {
            "id": 100,
            "channel": "wr3_episode_brief_requested",
            "payload": {"episode_id": "ep-replay-1", "topic": "T1"},
        },
        {
            "id": 101,
            "channel": "wr3_episode_gate_passed",
            "payload": {"episode_id": "ep-replay-2"},
        },
        {
            "id": 102,
            "channel": "wr3_episode_assembly_ready",
            "payload": json.dumps({"episode_id": "ep-replay-3"}),  # string form
        },
    ])
    conn.execute = AsyncMock()
    return conn


@pytest.mark.asyncio
async def test_reconcile_unconsumed_dispatches_all(contracts, fake_conn_with_outbox) -> None:
    with patch(
        "wr3_supervisor.route_event", new=AsyncMock()
    ) as route:
        await wr3_supervisor._reconcile_unconsumed(fake_conn_with_outbox, contracts)
        assert route.await_count == 3


@pytest.mark.asyncio
async def test_reconcile_injects_outbox_id(contracts, fake_conn_with_outbox) -> None:
    """Replayed payload must carry the _outbox_id so handler can ack on success."""
    captured: list[str] = []

    async def _capture(_conn, _contracts, _channel, payload_str):
        captured.append(payload_str)

    with patch("wr3_supervisor.route_event", new=_capture):
        await wr3_supervisor._reconcile_unconsumed(fake_conn_with_outbox, contracts)

    assert len(captured) == 3
    for payload_str in captured:
        data = json.loads(payload_str)
        assert "_outbox_id" in data
        assert data["_outbox_id"] in {100, 101, 102}


@pytest.mark.asyncio
async def test_reconcile_handles_individual_failures(contracts, fake_conn_with_outbox) -> None:
    """One replay failing must not stop the rest."""
    call_count = 0

    async def _flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("simulated mid-replay crash")

    with patch("wr3_supervisor.route_event", new=_flaky):
        await wr3_supervisor._reconcile_unconsumed(fake_conn_with_outbox, contracts)

    # All 3 attempted despite the middle one failing
    assert call_count == 3


@pytest.mark.asyncio
async def test_reconcile_empty_no_dispatch(contracts) -> None:
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    with patch(
        "wr3_supervisor.route_event", new=AsyncMock()
    ) as route:
        await wr3_supervisor._reconcile_unconsumed(conn, contracts)
        route.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconcile_query_failure_does_not_crash(contracts) -> None:
    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=Exception("PG closed"))
    # Should not propagate — just log and return
    await wr3_supervisor._reconcile_unconsumed(conn, contracts)


@pytest.mark.asyncio
async def test_reconcile_only_wr3_channels(contracts) -> None:
    """The SQL query filters by ANY($1) channel list — verify list comes from contracts.

    Note 2026-05-22: companion handoff added wr2_episode_published as additional
    consumed channel for design-architect (cross-pipeline rendezvous). Channels
    must startswith wr3_ OR wr2_ (companion).
    """
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    await wr3_supervisor._reconcile_unconsumed(conn, contracts)
    # Inspect the SQL params passed
    _args, kwargs = conn.fetch.call_args
    assert kwargs is not None or len(_args) >= 2
    # Channel list is the second positional arg to fetch
    channels = _args[-1] if _args else kwargs.get("channels", [])
    assert all(ch.startswith(("wr3_", "wr2_")) for ch in channels)
    assert "wr3_episode_brief_requested" in channels
