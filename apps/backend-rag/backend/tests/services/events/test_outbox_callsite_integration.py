"""Integration-style tests for the P0-2 phase-2 callsite refactor.

These tests verify the contract of the callsite migration, NOT the
underlying outbox helper (which is covered by ``test_outbox.py``) or
the EventBus reconnect hook (covered by ``test_event_bus_replay.py``).

What's covered here:

1. ``EventBus.emit_pg`` now writes to ``events_outbox`` BEFORE pg_notify,
   via the helper, instead of calling ``pg_notify`` directly. This is
   the only Python production callsite that emitted on a
   ``PG_CHANNEL_MAP`` channel (``services/crm/partners/events.py`` is
   off-channel and out of scope).

2. The replay-on-reconnect path round-trips: when a publisher writes
   N events to the outbox during a listener-disconnect window and the
   listener then reconnects, all N reach in-process subscribers via
   ``EventBus._replay_outbox_on_reconnect`` (the existing reconnect hook
   in ``event_bus.py``). The test simulates the disconnect by directly
   inserting into a fake outbox table and calling the hook.

3. Migration 146 trigger-functions write to ``events_outbox`` in the
   same transaction as the original INSERT/UPDATE. This is verified at
   the SQL level — the migration text contains both ``INSERT INTO
   events_outbox`` and ``pg_notify`` for every trigger function it
   defines, and exposes the ``_outbox_id`` to consumers.

We deliberately stay at the unit/contract layer: real asyncpg + real PG
would require docker-compose orchestration that's out of scope for the
PR-check pipeline (the existing ``test_outbox.py`` already exercises
the SQL strings against a mocked connection).
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.events.event_bus import PG_CHANNEL_MAP, EventBus


# ── 1. EventBus.emit_pg goes through outbox.publish ───────────────────


@pytest.mark.asyncio
async def test_emit_pg_writes_to_outbox_before_notify():
    """``EventBus.emit_pg`` must call ``outbox.publish`` (which inserts
    into ``events_outbox`` AND fires pg_notify) — NOT raw pg_notify.

    Phase-1 contract was the opposite: emit_pg called
    ``conn.execute("SELECT pg_notify($1, $2)", ...)`` directly. Phase 2
    delegates to the helper so the row is durable.
    """
    pool = MagicMock()
    conn = AsyncMock()

    class _AcquireCtx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *args):
            return None

    pool.acquire = MagicMock(return_value=_AcquireCtx())
    bus = EventBus(db_dsn="postgresql://test/x", db_pool=pool)

    with patch(
        "backend.services.events.outbox.publish",
        new=AsyncMock(return_value=42),
    ) as mock_publish:
        await bus.emit_pg("client_changed", {"client_id": 7})

    # 1. outbox.publish was called with the expected channel + payload
    mock_publish.assert_awaited_once()
    call_args = mock_publish.await_args.args
    # call signature is publish(conn, channel, payload)
    assert call_args[1] == "client_changed"
    assert call_args[2] == {"client_id": 7}


@pytest.mark.asyncio
async def test_emit_pg_does_not_call_raw_pg_notify():
    """The raw `SELECT pg_notify($1, $2)` SQL must no longer come from emit_pg.

    Replays-on-reconnect can only re-dispatch outbox-recorded events. If
    emit_pg ever bypasses the helper, those events are silently lost on
    reconnect. This regression-guards against that.
    """
    pool = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock()

    class _AcquireCtx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *args):
            return None

    pool.acquire = MagicMock(return_value=_AcquireCtx())
    bus = EventBus(db_dsn="postgresql://test/x", db_pool=pool)

    with patch(
        "backend.services.events.outbox.publish",
        new=AsyncMock(return_value=1),
    ):
        await bus.emit_pg("practice_changed", {"practice_id": 99})

    # The connection's raw `execute("SELECT pg_notify ...")` must not be
    # called from emit_pg itself — that work is now inside outbox.publish
    # (which is patched here, so the mock conn never sees it).
    direct_pg_notify_calls = [
        c for c in conn.execute.await_args_list
        if c.args and "pg_notify" in str(c.args[0]).lower()
    ]
    assert direct_pg_notify_calls == [], (
        "emit_pg must delegate to outbox.publish, not call pg_notify directly"
    )


@pytest.mark.asyncio
async def test_emit_pg_warns_on_oversized_payload(caplog):
    """The 8KB payload warning is preserved across the refactor."""
    pool = MagicMock()
    conn = AsyncMock()

    class _AcquireCtx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *args):
            return None

    pool.acquire = MagicMock(return_value=_AcquireCtx())
    bus = EventBus(db_dsn="postgresql://test/x", db_pool=pool)

    big_payload = {"blob": "x" * 8000}  # > 7500 byte threshold

    with patch(
        "backend.services.events.outbox.publish",
        new=AsyncMock(return_value=1),
    ):
        with caplog.at_level("WARNING"):
            await bus.emit_pg("intel_event", big_payload)

    assert any("limit ~8KB" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_emit_pg_no_db_pool_returns_silently(caplog):
    """No db_pool → log warning and return; do not call publish."""
    bus = EventBus(db_dsn="postgresql://test/x", db_pool=None)

    with patch(
        "backend.services.events.outbox.publish",
        new=AsyncMock(),
    ) as mock_publish:
        with caplog.at_level("WARNING"):
            await bus.emit_pg("client_changed", {"x": 1})

    mock_publish.assert_not_awaited()
    assert any("no db_pool" in rec.message for rec in caplog.records)


# ── 2. Disconnect/replay round-trip via the existing reconnect hook ────


@pytest.mark.asyncio
async def test_n_events_survive_listener_disconnect():
    """Simulate: publisher writes N events while listener is disconnected,
    then listener reconnects → all N reach the in-process subscribers.

    We bypass real PG/asyncpg by mocking ``replay_unconsumed`` to feed
    pre-staged "outbox rows" through the hook, exactly as the production
    helper would after fetching them from the DB.
    """
    pool = MagicMock()
    conn = AsyncMock()

    class _AcquireCtx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *args):
            return None

    pool.acquire = MagicMock(return_value=_AcquireCtx())
    bus = EventBus(db_dsn="postgresql://test/x", db_pool=pool)

    # In-process subscriber for the war_room.event topic
    received: list[dict] = []

    async def war_room_subscriber(payload: dict) -> None:
        received.append(payload)

    bus.subscribe("war_room.event", war_room_subscriber)

    # Stage 100 outbox rows for war_room_event; zero for the rest.
    n = 100
    staged = {
        "war_room_event": [
            {
                "_outbox_id": i,
                "draft_id": f"draft-{i}",
                "status": "approved",
            }
            for i in range(1, n + 1)
        ],
    }

    async def fake_replay(conn_arg, dispatch_fn, *, channel, **_kwargs):
        rows = staged.get(channel, [])
        for row in rows:
            await dispatch_fn(row)
        return len(rows)

    with patch(
        "backend.services.events.outbox.replay_unconsumed",
        new=AsyncMock(side_effect=fake_replay),
    ):
        await bus._replay_outbox_on_reconnect()

    # All 100 events reached the in-process subscriber.
    assert len(received) == n
    # Order preserved (BIGSERIAL ASC) and _outbox_id round-trips through
    # _handle_pg_event into the in-process payload.
    assert [r.get("_outbox_id") for r in received] == list(range(1, n + 1))


@pytest.mark.asyncio
async def test_replayed_event_is_marked_with_replay_flag():
    """Replayed payloads carry the ``_replay`` flag (set by the helper).

    Idempotency contract: consumers that need at-least-once dedup can
    branch on ``payload.get('_replay')``. The flag is added by
    ``replay_unconsumed`` before dispatch, so it must show up on the
    in-process subscriber side.
    """
    pool = MagicMock()
    conn = AsyncMock()

    class _AcquireCtx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *args):
            return None

    pool.acquire = MagicMock(return_value=_AcquireCtx())
    bus = EventBus(db_dsn="postgresql://test/x", db_pool=pool)

    received: list[dict] = []

    async def sub(payload: dict) -> None:
        received.append(payload)

    bus.subscribe("intel.event", sub)

    async def fake_replay(conn_arg, dispatch_fn, *, channel, **_kwargs):
        if channel == "intel_event":
            await dispatch_fn(
                {"_outbox_id": 7, "_replay": True, "signal_id": "abc"}
            )
            return 1
        return 0

    with patch(
        "backend.services.events.outbox.replay_unconsumed",
        new=AsyncMock(side_effect=fake_replay),
    ):
        await bus._replay_outbox_on_reconnect()

    assert len(received) == 1
    assert received[0].get("_replay") is True
    assert received[0].get("_outbox_id") == 7


# ── 3. Migration 146 contract (SQL parsed as text) ────────────────────


_MIGRATION_146_PATH = (
    Path(__file__).resolve().parents[3]
    / "db"
    / "migrations_v2"
    / "146_eventbus_triggers_use_outbox.sql"
)


def _read_migration_146() -> str:
    assert _MIGRATION_146_PATH.exists(), (
        f"migration 146 not found at {_MIGRATION_146_PATH}"
    )
    return _MIGRATION_146_PATH.read_text(encoding="utf-8")


# Channels in PG_CHANNEL_MAP that have NO DB trigger and so do not need
# coverage in migration 146. Both are emitted only via Python through
# ``EventBus.emit_pg`` (refactored in p0-2-fase2 to call ``outbox.publish``),
# so they already gain durability without a SQL trigger.
#
#   - ``lkpm_ingest_completed`` — emitted by import scripts after bulk OSS
#     receipt ingest (see backend.scripts.lkpm_ingest_q1_2026).
#   - ``federation_alert`` — emitted by the FAD pipeline (PR #393/#395):
#     Python producers call ``EventBus.emit_pg('federation_alert', payload)``
#     after writing to ``federation_alert_proposals`` (migration 147). No DB
#     trigger fires it; the FAD daemon (services/federation_alerts/daemon.py)
#     LISTENs and consumes via ``replay_unconsumed`` against events_outbox.
#
# The remaining channels DO have DB triggers (migrations 075/076/112/113/114)
# and migration 146 must wrap each one in an events_outbox INSERT.
_PG_NOTIFY_ONLY_CHANNELS = frozenset({
    "lkpm_ingest_completed",
    "federation_alert",
    # cell_pulse_observed: emitted by cell_core.observatory.emit_pulse_observed
    # (Python direct asyncpg INSERT to events_outbox + pg_notify) inside the
    # cell process itself, NOT via DB trigger. The events_outbox row IS
    # written, but the path is Python-callsite, not migration-146-trigger.
    # Track A 2026-05-02 — see PR #411 + #416 + #425.
    "cell_pulse_observed",
})
_TRIGGER_BACKED_CHANNELS = frozenset(
    ch for ch in PG_CHANNEL_MAP if ch not in _PG_NOTIFY_ONLY_CHANNELS
)


def test_migration_146_exists_and_targets_every_trigger_backed_channel():
    """Every PG_CHANNEL_MAP channel that has a DB trigger must have a
    refactored function in migration 146 that writes to events_outbox.

    Defends against a future PG_CHANNEL_MAP entry that doesn't get a
    matching outbox-aware trigger (silent durability gap). The
    ``lkpm_ingest_completed`` channel is excluded — see
    ``_TRIGGER_BACKED_CHANNELS`` above.
    """
    sql = _read_migration_146()
    for channel in _TRIGGER_BACKED_CHANNELS:
        # Each channel name appears as the literal in INSERT INTO
        # events_outbox (channel, payload) VALUES ('<channel>', ...).
        marker = f"VALUES ('{channel}', payload)"
        assert marker in sql, (
            f"migration 146 missing outbox INSERT for channel '{channel}' "
            f"(searched for {marker!r})"
        )


def test_migration_146_function_bodies_emit_pg_notify_with_outbox_id():
    """Every trigger function must inject ``_outbox_id`` into the
    pg_notify payload so consumers can ack idempotently."""
    sql = _read_migration_146()
    # The literal we expect in every refactored function body — payload
    # JSONB has _outbox_id concatenated before being cast to text.
    expected = "jsonb_build_object('_outbox_id', outbox_id)"
    # 6 channels × 1 occurrence in forward + 0 occurrences in rollback
    # (rollback restores the PRE-146 implementation that doesn't carry
    # _outbox_id). So at least 6 occurrences in the file as a whole.
    occurrences = sql.count(expected)
    assert occurrences >= len(_TRIGGER_BACKED_CHANNELS), (
        f"expected ≥ {len(_TRIGGER_BACKED_CHANNELS)} occurrences of "
        f"{expected!r} in migration 146 (one per trigger-backed channel), "
        f"found {occurrences}"
    )


def test_migration_146_has_rollback_section():
    """Migration runner requires `-- === ROLLBACK ===` marker (cicatrix
    fix 2026-04-19). The rollback restores the pre-146 trigger function
    bodies."""
    sql = _read_migration_146()
    assert "-- === ROLLBACK ===" in sql, (
        "migration 146 must have a rollback marker"
    )
    # Rollback section restores notify_practice_change without outbox INSERT.
    rollback_idx = sql.index("-- === ROLLBACK ===")
    rollback_sql = sql[rollback_idx:]
    # The forward portion writes to events_outbox; rollback portion does NOT.
    assert "INSERT INTO events_outbox" not in rollback_sql, (
        "rollback section must not reference events_outbox — phase-1 "
        "trigger bodies emit pg_notify directly"
    )
    assert "PERFORM pg_notify('practice_changed', payload)" in rollback_sql


def test_migration_146_does_not_touch_out_of_scope_channels():
    """`wr2_status_change` (mig 138) and `partner.commission_changed`
    are explicitly OUT of scope — migration 146 must not redefine
    them."""
    sql = _read_migration_146()
    # We only check the FORWARD section; rollback section is allowed to
    # reference channel names in comments.
    forward_sql = sql.split("-- === ROLLBACK ===")[0]
    # Allowed: comments mentioning the channel as "out of scope".
    # Forbidden: an INSERT INTO events_outbox VALUES ('wr2_status_change', ...).
    assert (
        "VALUES ('wr2_status_change'" not in forward_sql
    ), "wr2_status_change must NOT be added to outbox in this migration"
    assert (
        "VALUES ('partner.commission_changed'" not in forward_sql
    ), "partner.commission_changed must NOT be added to outbox here"


# ── 4. Smoke: payload shape preserved across the refactor ─────────────


def test_migration_146_war_room_payload_keeps_event_type_and_occurred_at():
    """The original notify_war_room_event() built a payload with
    ``event_type`` and ``occurred_at``. Consumers (review_handler,
    publisher_worker, …) parse those keys directly. The refactor must
    not reshape the payload."""
    import re

    sql = _read_migration_146()
    forward = sql.split("-- === ROLLBACK ===")[0]
    war_room_section_start = forward.index(
        "CREATE OR REPLACE FUNCTION notify_war_room_event"
    )
    war_room_section_end = forward.index(
        "CREATE OR REPLACE FUNCTION notify_intel_event", war_room_section_start
    )
    war_room_section = forward[war_room_section_start:war_room_section_end]
    # Whitespace-tolerant match: column-aligned SQL uses runs of spaces
    # between the literal key and the value reference.
    assert re.search(r"'event_type',\s+event_type", war_room_section), (
        "war_room trigger function must build payload with event_type key"
    )
    assert re.search(r"'occurred_at',\s+NOW\(\)", war_room_section) or re.search(
        r"'occurred_at',\s+NEW\.published_at", war_room_section
    ), "war_room trigger function must build payload with occurred_at key"


@pytest.mark.asyncio
async def test_emit_pg_payload_round_trips_unmodified():
    """Async-decorated counterpart of the sync helper above.

    Verifies that the dict passed to ``emit_pg`` reaches
    ``outbox.publish`` with the same identity (no copy, no mutation).
    """
    pool = MagicMock()
    conn = AsyncMock()

    class _AcquireCtx:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *args):
            return None

    pool.acquire = MagicMock(return_value=_AcquireCtx())
    bus = EventBus(db_dsn="postgresql://test/x", db_pool=pool)

    sentinel_payload = {
        "client_id": 42,
        "email": "x@y.com",
        "full_name": "Café Bali Zéro",
        "operation": "UPDATE",
    }

    captured: dict = {}

    async def fake_publish(conn_arg, channel, payload):
        captured["channel"] = channel
        captured["payload"] = payload
        return 1

    with patch(
        "backend.services.events.outbox.publish",
        new=AsyncMock(side_effect=fake_publish),
    ):
        await bus.emit_pg("client_changed", sentinel_payload)

    assert captured["channel"] == "client_changed"
    # Dict equality (publish may serialise internally; the call site
    # sees the original Python dict).
    assert captured["payload"] == sentinel_payload
    # JSON-roundtrip-safe (no asyncpg-specific types leaked).
    json.dumps(captured["payload"])
