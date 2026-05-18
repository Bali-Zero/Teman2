"""WR3 supervisor explicit-ack contract test.

Migration 183 closes EventBus Phase 3 pending (cicatrix-scars.md): the
universal `replay_unconsumed()` in services/events/outbox.py auto-acks on
dispatch return, which is unsafe for a video pipeline where ffmpeg can
crash mid-render. WR3 supervisor must implement EXPLICIT per-handler ack
so that a handler exception leaves the outbox row unconsumed and the
event replays on next listener reconnect.

This test pins the contract at the supervisor layer (not the migration
layer — migration 183 only adds the publish helper; the ack semantics
live in scripts/wr3_supervisor.py).

Pattern mirrors test_outbox.py / test_outbox_callsite_integration.py with
AsyncMock connections — no real PG needed at unit test scope.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

# Importing here lazily so the test still runs in environments where
# scripts/wr3_supervisor.py has not yet been authored — the test will
# xfail with a clear message instead of an ImportError.
pytest.importorskip("asyncpg")


WR3_CHANNELS = (
    "wr3_episode_brief_requested",
    "wr3_episode_pre_render_ready",
    "wr3_episode_gate_passed",
    "wr3_episode_assembly_ready",
    "wr3_episode_critic_verdict",
    "wr3_episode_staged",
)


@pytest.fixture
def supervisor_module():
    """Load the WR3 supervisor module, skip if not yet authored."""
    try:
        import importlib
        return importlib.import_module("scripts.wr3_supervisor")
    except ModuleNotFoundError as exc:
        pytest.skip(f"scripts.wr3_supervisor not yet authored: {exc}")
        return None


# ── publish helper contract ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_calls_db_function_with_validated_channel(supervisor_module):
    """supervisor.publish() invokes publish_wr3_event() SQL helper."""
    conn = AsyncMock()
    conn.fetchval.return_value = 42  # outbox_id

    outbox_id = await supervisor_module.publish(
        conn,
        channel="wr3_episode_brief_requested",
        payload={"episode_id": "test-1", "topic": "smoke"},
    )

    assert outbox_id == 42
    conn.fetchval.assert_awaited_once()
    # First positional arg is the SQL statement, must reference the helper
    call_args = conn.fetchval.await_args
    assert "publish_wr3_event" in call_args.args[0]


@pytest.mark.asyncio
async def test_publish_rejects_unknown_channel(supervisor_module):
    """Defense-in-depth: supervisor refuses to call the helper with an
    unknown channel name even though the SQL function also validates."""
    conn = AsyncMock()
    with pytest.raises((ValueError, supervisor_module.InvalidWR3ChannelError)):
        await supervisor_module.publish(
            conn,
            channel="practice_changed",  # valid in other room, NOT WR3
            payload={"episode_id": "test-1"},
        )
    conn.fetchval.assert_not_awaited()


# ── explicit ack on handler success ────────────────────────────────────


@pytest.mark.asyncio
async def test_route_event_acks_on_handler_success(supervisor_module):
    """When the handler returns without raising, supervisor MUST ack the
    outbox row so the event is not replayed on reconnect."""
    conn = AsyncMock()
    ack = AsyncMock()
    handler = AsyncMock(return_value={"outcome": "PASS"})

    supervisor_module._HANDLERS = {  # type: ignore[attr-defined]
        "wr3_episode_brief_requested": handler,
    }

    payload = '{"episode_id": "e1", "_outbox_id": 7}'

    await supervisor_module.route_event(
        conn=conn,
        ack_fn=ack,
        channel="wr3_episode_brief_requested",
        payload=payload,
    )

    handler.assert_awaited_once()
    ack.assert_awaited_once_with(conn, 7)


# ── explicit ack NOT called on handler crash ───────────────────────────


@pytest.mark.asyncio
async def test_route_event_does_not_ack_on_handler_exception(supervisor_module):
    """CRITICAL: when the handler raises, supervisor MUST NOT ack the
    outbox row. The event must remain pending so replay_unconsumed() picks
    it up on reconnect.

    This is the explicit-ack contract that distinguishes WR3 supervisor
    from the universal replay_unconsumed() helper (which auto-acks on
    dispatch return — cicatrix-resolved limitation).
    """
    conn = AsyncMock()
    ack = AsyncMock()

    class FfmpegCrash(Exception):
        pass

    handler = AsyncMock(side_effect=FfmpegCrash("ffmpeg exit 137 OOM"))

    supervisor_module._HANDLERS = {  # type: ignore[attr-defined]
        "wr3_episode_assembly_ready": handler,
    }

    payload = '{"episode_id": "e2", "_outbox_id": 13}'

    with pytest.raises(FfmpegCrash):
        await supervisor_module.route_event(
            conn=conn,
            ack_fn=ack,
            channel="wr3_episode_assembly_ready",
            payload=payload,
        )

    handler.assert_awaited_once()
    ack.assert_not_awaited()  # the contract


@pytest.mark.asyncio
async def test_route_event_does_not_ack_on_handler_timeout(supervisor_module):
    """A handler that exceeds the 300s wall-clock must surface as timeout
    AND must NOT ack the outbox row — same contract as crash.

    Important: per CLAUDE.md anti-hallucination discipline + Symbiosis
    Law 4 (degrade-loud, never silent), a timeout is a loud failure,
    not a silent ack.
    """
    import asyncio

    conn = AsyncMock()
    ack = AsyncMock()

    async def hanging_handler(*args, **kwargs):
        await asyncio.sleep(10)  # would block; supervisor enforces timeout

    supervisor_module._HANDLERS = {  # type: ignore[attr-defined]
        "wr3_episode_gate_passed": hanging_handler,
    }

    payload = '{"episode_id": "e3", "_outbox_id": 21}'

    # supervisor.route_event uses an asyncio.wait_for() with a short
    # timeout in tests (overridable via _DISPATCH_TIMEOUT_S module attr).
    supervisor_module._DISPATCH_TIMEOUT_S = 0.1  # type: ignore[attr-defined]

    with pytest.raises(asyncio.TimeoutError):
        await supervisor_module.route_event(
            conn=conn,
            ack_fn=ack,
            channel="wr3_episode_gate_passed",
            payload=payload,
        )

    ack.assert_not_awaited()


# ── unknown channel handling ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_route_event_unknown_channel_does_not_ack(supervisor_module):
    """An event with an unknown channel must NOT be acked — that would
    silently drop a legitimate event during a partial migration."""
    conn = AsyncMock()
    ack = AsyncMock()

    supervisor_module._HANDLERS = {}  # type: ignore[attr-defined]

    payload = '{"episode_id": "e4", "_outbox_id": 33}'

    with pytest.raises((KeyError, supervisor_module.UnknownWR3ChannelError)):
        await supervisor_module.route_event(
            conn=conn,
            ack_fn=ack,
            channel="wr3_episode_brief_requested",  # no handler registered
            payload=payload,
        )

    ack.assert_not_awaited()
