"""Tests for the universal events outbox helper (events_outbox table operations).

Foundation for the P0-2 EventBus replay-on-reconnect pattern. See
``apps/backend-rag/backend/services/events/outbox.py`` and migration
``backend/db/migrations_v2/144_events_outbox.sql``.

Tests use mocked asyncpg connection (AsyncMock) — same pattern as
``backend/tests/services/test_outbox.py`` for the bridge outbox.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.events.outbox import (
    InvalidChannelError,
    acknowledge,
    get_unconsumed_count,
    prune_consumed,
    publish,
    replay_unconsumed,
    validate_channel,
)


# ── validate_channel ───────────────────────────────────────────────────


def test_validate_channel_accepts_valid_names():
    """Standard channel names from PG_CHANNEL_MAP all pass."""
    for name in (
        "practice_changed",
        "client_changed",
        "compliance_alert",
        "lkpm_ingest_completed",
        "war_room_event",
        "intel_event",
        "cognitive_event",
        "abc_123",
    ):
        validate_channel(name)  # must not raise


def test_validate_channel_rejects_special_chars():
    """A malicious channel name with quotes/semicolons/spaces is rejected.

    Even though pg_notify($1, $2) parameterizes the channel name (no DDL
    interpolation), defense-in-depth: reject suspicious names early so they
    never reach the DB. Cicatrix scar (2026-04-29) requires this.
    """
    bad = [
        'evil"; DROP TABLE events_outbox; --',
        "channel with space",
        "channel'OR'1'='1",
        "channel\nnewline",
        "",
    ]
    for name in bad:
        with pytest.raises(InvalidChannelError):
            validate_channel(name)


def test_validate_channel_enforces_max_length():
    """PG identifier limit is 63 chars; we enforce the same on channel names."""
    long_name = "a" * 64
    with pytest.raises(InvalidChannelError):
        validate_channel(long_name)
    # Boundary: 63 chars is allowed
    validate_channel("a" * 63)


# ── publish ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_inserts_row_and_calls_pg_notify():
    """publish() inserts into events_outbox AND fires pg_notify with _outbox_id."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": 99})
    conn.execute = AsyncMock(return_value="SELECT 1")

    outbox_id = await publish(
        conn,
        channel="practice_changed",
        payload={"practice_id": 7, "status": "approved"},
    )

    assert outbox_id == 99

    # 1. INSERT was executed with channel + JSONB payload
    insert_args = conn.fetchrow.call_args.args
    assert "INSERT INTO events_outbox" in insert_args[0]
    assert "RETURNING id" in insert_args[0]
    assert insert_args[1] == "practice_changed"
    parsed_insert_payload = json.loads(insert_args[2])
    assert parsed_insert_payload == {"practice_id": 7, "status": "approved"}

    # 2. pg_notify was called via SELECT pg_notify($1, $2) — parameterized.
    notify_args = conn.execute.call_args.args
    assert "pg_notify" in notify_args[0].lower()
    assert "$1" in notify_args[0] and "$2" in notify_args[0]
    assert notify_args[1] == "practice_changed"
    notify_payload = json.loads(notify_args[2])
    # _outbox_id must be injected into the NOTIFY payload for consumer ack
    assert notify_payload["_outbox_id"] == 99
    assert notify_payload["practice_id"] == 7


@pytest.mark.asyncio
async def test_publish_rejects_invalid_channel_before_db_call():
    """An invalid channel raises before any SQL is executed (no DB wasted)."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": 1})

    with pytest.raises(InvalidChannelError):
        await publish(conn, "evil; DROP TABLE x", {"foo": "bar"})

    conn.fetchrow.assert_not_called()
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_publish_serializes_non_ascii_payload():
    """Non-ASCII payload survives JSON round-trip (ensure_ascii=False)."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": 1})
    conn.execute = AsyncMock()

    payload = {"client_name": "Café Bali Zéro", "city": "Dénpasar"}
    await publish(conn, "client_changed", payload)

    insert_payload_json = conn.fetchrow.call_args.args[2]
    parsed = json.loads(insert_payload_json)
    assert parsed["client_name"] == "Café Bali Zéro"


# ── acknowledge ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_acknowledge_marks_consumed_first_time():
    """acknowledge() returns True when the row was unconsumed before."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")

    ok = await acknowledge(conn, outbox_id=42, consumer_id="review_handler")

    assert ok is True
    sql = conn.execute.call_args.args[0]
    assert "UPDATE events_outbox" in sql
    assert "consumed_at IS NULL" in sql  # idempotency guard
    assert conn.execute.call_args.args[1] == 42


@pytest.mark.asyncio
async def test_acknowledge_idempotent_on_double_ack():
    """Second ack on same id returns False (no row updated, no error)."""
    conn = AsyncMock()
    # Second call: "UPDATE 0" — already consumed, WHERE clause excluded the row
    conn.execute = AsyncMock(side_effect=["UPDATE 1", "UPDATE 0"])

    first = await acknowledge(conn, 42, "h1")
    second = await acknowledge(conn, 42, "h1")

    assert first is True
    assert second is False


@pytest.mark.asyncio
async def test_acknowledge_returns_false_for_nonexistent_id():
    """ack on a row that does not exist returns False (no exception)."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 0")
    ok = await acknowledge(conn, 99999, "h1")
    assert ok is False


# ── replay_unconsumed ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_replay_unconsumed_dispatches_in_id_asc_order():
    """Unconsumed rows are dispatched in id ASC order, then auto-acked."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {"id": 10, "channel": "war_room_event", "payload": {"draft_id": "a"}},
            {"id": 11, "channel": "war_room_event", "payload": {"draft_id": "b"}},
            {"id": 12, "channel": "war_room_event", "payload": {"draft_id": "c"}},
        ]
    )
    conn.execute = AsyncMock(return_value="UPDATE 1")

    dispatched: list[dict] = []

    async def dispatch_fn(payload: dict) -> None:
        dispatched.append(payload)

    count = await replay_unconsumed(
        conn,
        dispatch_fn,
        channel="war_room_event",
        max_age_minutes=60,
    )

    assert count == 3
    # ASC order preserved
    assert [d["draft_id"] for d in dispatched] == ["a", "b", "c"]
    # _outbox_id injected into each dispatched payload
    assert all("_outbox_id" in d for d in dispatched)
    assert [d["_outbox_id"] for d in dispatched] == [10, 11, 12]
    # 3 acks fired (one per dispatched row)
    assert conn.execute.await_count == 3


@pytest.mark.asyncio
async def test_replay_unconsumed_filters_by_channel_and_max_age():
    """SQL WHERE clause includes channel filter + max_age + consumed_at IS NULL."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value="UPDATE 0")

    async def noop(_: dict) -> None:
        pass

    await replay_unconsumed(
        conn,
        noop,
        channel="practice_changed",
        max_age_minutes=15,
    )

    sql = conn.fetch.call_args.args[0]
    assert "consumed_at IS NULL" in sql
    assert "channel" in sql
    # max_age filter applied
    assert "INTERVAL" in sql or "interval" in sql
    # channel passed as parameter, not interpolated
    fetch_args = conn.fetch.call_args.args
    assert "practice_changed" in fetch_args


@pytest.mark.asyncio
async def test_replay_unconsumed_continues_on_dispatch_error():
    """If one handler raises, replay logs and continues with the rest.

    Phase-1 contract: a crashing handler does NOT block other unconsumed
    events. Failed events stay unconsumed (no ack), so they will be
    retried on the next replay.
    """
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {"id": 1, "channel": "intel_event", "payload": {"x": 1}},
            {"id": 2, "channel": "intel_event", "payload": {"x": 2}},
            {"id": 3, "channel": "intel_event", "payload": {"x": 3}},
        ]
    )
    conn.execute = AsyncMock(return_value="UPDATE 1")

    dispatched: list[int] = []

    async def flaky(payload: dict) -> None:
        dispatched.append(payload["x"])
        if payload["x"] == 2:
            raise RuntimeError("simulated handler crash")

    count = await replay_unconsumed(conn, flaky, channel="intel_event")

    # All 3 dispatched (even after one raised)
    assert dispatched == [1, 2, 3]
    # 2 acks (the ones that didn't raise) — id 2 stays unconsumed
    assert conn.execute.await_count == 2
    # count returned = successfully replayed (acked)
    assert count == 2


# ── prune_consumed ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_prune_consumed_deletes_only_old_consumed_rows():
    """prune_consumed() filters by consumed_at IS NOT NULL AND age threshold."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="DELETE 17")

    deleted = await prune_consumed(conn, older_than_days=30)

    assert deleted == 17
    sql = conn.execute.call_args.args[0]
    assert "DELETE FROM events_outbox" in sql
    assert "consumed_at IS NOT NULL" in sql
    # interval expressed in days
    assert "INTERVAL" in sql or "interval" in sql


@pytest.mark.asyncio
async def test_prune_consumed_returns_zero_on_no_match():
    """If no rows match, prune returns 0 (no exception)."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="DELETE 0")
    deleted = await prune_consumed(conn, older_than_days=30)
    assert deleted == 0


# ── get_unconsumed_count ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_unconsumed_count_returns_int():
    """get_unconsumed_count() returns COUNT(*) as int."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=5)
    n = await get_unconsumed_count(conn)
    assert n == 5
    assert "COUNT" in conn.fetchval.call_args.args[0].upper()
    assert "consumed_at IS NULL" in conn.fetchval.call_args.args[0]


@pytest.mark.asyncio
async def test_get_unconsumed_count_with_channel_filter():
    """Channel filter passed as bound parameter."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=2)
    n = await get_unconsumed_count(conn, channel="war_room_event")
    assert n == 2
    args = conn.fetchval.call_args.args
    assert "channel" in args[0]
    assert "war_room_event" in args
