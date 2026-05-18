"""Tests for wr3_supervisor.route_event — explicit per-handler ack contract.

Symbiosis Law 3 (Event-driven durabilità). Closes EventBus Phase 3 — handler
crash must NOT ack the outbox row (so it replays on reconnect).
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

from wr3_contracts import load_contracts  # noqa: E402
from wr3_dispatch_agent import (  # noqa: E402
    CascadeExhaustedError,
    DispatchResult,
    HardHaltException,
    OSINTLeakError,
)
import wr3_supervisor  # noqa: E402


@pytest.fixture(scope="module")
def contracts():
    return load_contracts()


@pytest.fixture
def fake_conn():
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    return conn


@pytest.mark.asyncio
async def test_route_event_acks_on_handler_success(contracts, fake_conn) -> None:
    payload = json.dumps({
        "episode_id": "ep-success",
        "_outbox_id": 42,
        "topic": "Manifesto Zantara",
    })
    fake_result = DispatchResult(
        agent="wr3-design-architect",
        cost_usd_estimated=0.12,
        duration_ms=1000,
        cascade_tier=1,
        raw_output="ok",
    )
    with patch(
        "wr3_supervisor.dispatch_agent",
        new=AsyncMock(return_value=fake_result),
    ), patch(
        "wr3_supervisor._acknowledge_outbox", new=AsyncMock()
    ) as ack:
        await wr3_supervisor.route_event(
            fake_conn, contracts, "wr3_episode_brief_requested", payload
        )
        ack.assert_awaited_once_with(fake_conn, 42)


@pytest.mark.asyncio
async def test_route_event_does_not_ack_on_handler_exception(contracts, fake_conn) -> None:
    """Handler crash → do NOT ack — outbox row stays unconsumed, replays later."""
    payload = json.dumps({
        "episode_id": "ep-crash",
        "_outbox_id": 99,
        "topic": "Manifesto Zantara",
    })
    with patch(
        "wr3_supervisor.dispatch_agent",
        new=AsyncMock(side_effect=RuntimeError("ffmpeg segfault")),
    ), patch(
        "wr3_supervisor._acknowledge_outbox", new=AsyncMock()
    ) as ack, patch(
        "wr3_supervisor.telegram_p0", new=AsyncMock()
    ) as p0:
        with pytest.raises(RuntimeError):
            await wr3_supervisor.route_event(
                fake_conn, contracts, "wr3_episode_assembly_ready", payload
            )
        ack.assert_not_awaited()
        # hot path → P0 fires
        p0.assert_awaited_once()


@pytest.mark.asyncio
async def test_route_event_does_not_ack_on_osint_leak(contracts, fake_conn) -> None:
    """Law 2 trumps everything — OSINT leak halts, do NOT ack."""
    payload = json.dumps({
        "episode_id": "ep-leak",
        "_outbox_id": 7,
    })
    with patch(
        "wr3_supervisor.dispatch_agent",
        new=AsyncMock(side_effect=OSINTLeakError("source_id in brief.json")),
    ), patch(
        "wr3_supervisor._acknowledge_outbox", new=AsyncMock()
    ) as ack, patch(
        "wr3_supervisor.telegram_p0", new=AsyncMock()
    ) as p0:
        with pytest.raises(OSINTLeakError):
            await wr3_supervisor.route_event(
                fake_conn, contracts, "wr3_episode_brief_requested", payload
            )
        ack.assert_not_awaited()
        p0.assert_awaited_once()


@pytest.mark.asyncio
async def test_route_event_does_not_ack_on_hard_halt(contracts, fake_conn) -> None:
    """HARD HALT exception is not acked — manual intervention needed."""
    payload = json.dumps({"episode_id": "ep-budget", "_outbox_id": 13})
    with patch(
        "wr3_supervisor.dispatch_agent",
        new=AsyncMock(side_effect=HardHaltException("gate ceiling hit")),
    ), patch(
        "wr3_supervisor._acknowledge_outbox", new=AsyncMock()
    ) as ack:
        with pytest.raises(HardHaltException):
            await wr3_supervisor.route_event(
                fake_conn, contracts, "wr3_episode_brief_requested", payload
            )
        ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_event_does_not_ack_on_cascade_exhausted(contracts, fake_conn) -> None:
    payload = json.dumps({"episode_id": "ep-cascade", "_outbox_id": 21})
    with patch(
        "wr3_supervisor.dispatch_agent",
        new=AsyncMock(side_effect=CascadeExhaustedError("Tier 2 also out")),
    ), patch(
        "wr3_supervisor._acknowledge_outbox", new=AsyncMock()
    ) as ack:
        with pytest.raises(CascadeExhaustedError):
            await wr3_supervisor.route_event(
                fake_conn, contracts, "wr3_episode_brief_requested", payload
            )
        ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_event_malformed_payload_swallowed(contracts, fake_conn) -> None:
    """Malformed JSON payload: log and drop. Cannot ack what we cannot parse."""
    with patch(
        "wr3_supervisor.dispatch_agent", new=AsyncMock()
    ) as dispatch, patch(
        "wr3_supervisor._acknowledge_outbox", new=AsyncMock()
    ) as ack:
        await wr3_supervisor.route_event(
            fake_conn, contracts, "wr3_episode_brief_requested", "this-is-not-json"
        )
        dispatch.assert_not_awaited()
        ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_event_unknown_channel_raises(contracts, fake_conn) -> None:
    payload = json.dumps({"episode_id": "ep", "_outbox_id": 1})
    with pytest.raises(KeyError):
        await wr3_supervisor.route_event(
            fake_conn, contracts, "wr3_episode_fake", payload
        )


@pytest.mark.asyncio
async def test_dry_run_does_not_dispatch_or_ack(contracts, fake_conn) -> None:
    payload = json.dumps({"episode_id": "ep-dry", "_outbox_id": 50})
    with patch(
        "wr3_supervisor.dispatch_agent", new=AsyncMock()
    ) as dispatch, patch(
        "wr3_supervisor._acknowledge_outbox", new=AsyncMock()
    ) as ack:
        await wr3_supervisor.route_event(
            fake_conn, contracts, "wr3_episode_brief_requested", payload, dry_run=True
        )
        dispatch.assert_not_awaited()
        ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_cold_channel_handler_crash_no_telegram(contracts, fake_conn) -> None:
    """Non-hot-path channel: crash logs but no telegram P0."""
    payload = json.dumps({"episode_id": "ep", "_outbox_id": 2})
    with patch(
        "wr3_supervisor.dispatch_agent",
        new=AsyncMock(side_effect=RuntimeError("oops")),
    ), patch(
        "wr3_supervisor._acknowledge_outbox", new=AsyncMock()
    ), patch(
        "wr3_supervisor.telegram_p0", new=AsyncMock()
    ) as p0:
        with pytest.raises(RuntimeError):
            await wr3_supervisor.route_event(
                fake_conn, contracts, "wr3_episode_staged", payload
            )
        # staged is COLD path — no P0
        p0.assert_not_awaited()
