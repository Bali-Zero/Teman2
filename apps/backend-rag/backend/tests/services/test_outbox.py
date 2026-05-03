"""Tests for outbox helper (bridge_outbox table operations)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.bridge.outbox import (
    ALLOWED_TYPES,
    fetch_outbox_events,
    insert_outbox_event,
)


# ── ALLOWED_TYPES contract ─────────────────────────────────────────────


def test_allowed_types_contains_phase1_events():
    """ALLOWED_TYPES whitelist contains the 6 spec-defined event types."""
    expected = {
        "crm.client_created",
        "crm.client_sector_changed",
        "crm.practice_completed",
        "crm.practice_created",
        "compliance.critical_alert",
        "rag.low_confidence",
    }
    assert ALLOWED_TYPES == expected


# ── insert_outbox_event ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_insert_outbox_event_returns_id():
    """insert_outbox_event() returns the BIGSERIAL id from RETURNING clause."""
    conn = AsyncMock()
    # asyncpg returns a Record-like; we mock fetchrow to return {"id": 42}
    conn.fetchrow = AsyncMock(return_value={"id": 42})

    new_id = await insert_outbox_event(
        conn,
        event_type="crm.client_created",
        payload={"client_id": 7},
    )

    assert new_id == 42
    conn.fetchrow.assert_called_once()
    # Verify SQL contains INSERT and RETURNING id
    sql = conn.fetchrow.call_args.args[0]
    assert "INSERT INTO bridge_outbox" in sql
    assert "RETURNING id" in sql


@pytest.mark.asyncio
async def test_insert_outbox_event_serializes_payload_json():
    """Payload dict is serialized to JSON string before passing to asyncpg."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": 1})

    payload = {"client_id": 7, "name": "Café Indo"}  # non-ASCII to verify ensure_ascii=False
    await insert_outbox_event(conn, "crm.client_created", payload)

    args = conn.fetchrow.call_args.args
    # args[0] = SQL, args[1] = type, args[2] = JSON string
    assert args[1] == "crm.client_created"
    parsed = json.loads(args[2])
    assert parsed == payload
    # Verify non-ASCII not escaped
    assert "Café" in args[2]


@pytest.mark.asyncio
async def test_insert_outbox_event_rejects_unknown_type():
    """ValueError raised for type not in ALLOWED_TYPES."""
    conn = AsyncMock()
    with pytest.raises(ValueError, match="not in ALLOWED_TYPES"):
        await insert_outbox_event(conn, "unknown.type", {})
    # Conn must not be touched
    conn.fetchrow.assert_not_called()


# ── fetch_outbox_events ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_outbox_events_returns_list_of_dicts():
    """fetch_outbox_events() returns list of dicts with id/type/payload/created_at."""
    conn = AsyncMock()
    fake_dt = datetime(2026, 4, 14, 10, 0, 0, tzinfo=timezone.utc)
    conn.fetch = AsyncMock(return_value=[
        {"id": 10, "type": "crm.client_created", "payload": {"a": 1}, "created_at": fake_dt},
        {"id": 11, "type": "rag.low_confidence", "payload": {"q": "foo"}, "created_at": fake_dt},
    ])

    rows = await fetch_outbox_events(conn, after_id=5, limit=10)

    assert len(rows) == 2
    assert rows[0]["id"] == 10
    assert rows[0]["type"] == "crm.client_created"
    assert rows[0]["payload"] == {"a": 1}
    assert rows[0]["created_at"] == fake_dt.isoformat()


@pytest.mark.asyncio
async def test_fetch_outbox_events_uses_after_id_and_limit():
    """SQL WHERE id > $1 with LIMIT $2."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    await fetch_outbox_events(conn, after_id=42, limit=25)

    args = conn.fetch.call_args.args
    sql = args[0]
    assert "WHERE id > $1" in sql
    assert "ORDER BY id ASC" in sql
    assert "LIMIT $2" in sql
    assert args[1] == 42
    assert args[2] == 25


@pytest.mark.asyncio
async def test_fetch_outbox_events_empty_returns_empty_list():
    """Empty fetch returns []."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    rows = await fetch_outbox_events(conn, after_id=0, limit=50)
    assert rows == []
