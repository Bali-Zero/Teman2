"""Tests for outbox helper (bridge_outbox table operations)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

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
async def test_insert_outbox_event_passes_raw_dict_payload():
    """CICATRIX 2026-05-21 — payload MUST be passed as a raw dict, NOT
    pre-serialized via json.dumps(). The asyncpg pool registers a jsonb
    codec with encoder=json.dumps in service_initializer.py; pre-encoding
    here would double-encode → JSONB string scalar → downstream
    'str' object is not a mapping. See
    research/operations/2026-05-21-nb-automations-audit.md."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": 1})

    payload = {"client_id": 7, "name": "Café Indo"}  # non-ASCII preserved
    await insert_outbox_event(conn, "crm.client_created", payload)

    args = conn.fetchrow.call_args.args
    # args[0] = SQL, args[1] = type, args[2] = the dict itself (NOT json string)
    assert args[1] == "crm.client_created"
    assert args[2] is payload, "payload must be the raw dict, not pre-serialized"
    assert isinstance(args[2], dict)


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
    conn.fetch = AsyncMock(
        return_value=[
            {"id": 10, "type": "crm.client_created", "payload": {"a": 1}, "created_at": fake_dt},
            {
                "id": 11,
                "type": "rag.low_confidence",
                "payload": {"q": "foo"},
                "created_at": fake_dt,
            },
        ]
    )

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


# ── CICATRIX 2026-05-21 defensive unwrap ──────────────────────────────


@pytest.mark.asyncio
async def test_fetch_outbox_events_unwraps_legacy_double_encoded_string():
    """CICATRIX 2026-05-21 — legacy rows written with the double-encoded
    INSERT path return payload as a `str` (JSONB string scalar) instead of
    a dict. fetch_outbox_events must defensively json.loads() so downstream
    consumers (mata-garuda nerve.py) always receive a dict and don't crash
    on **payload."""
    conn = AsyncMock()
    fake_dt = datetime(2026, 5, 21, 23, 0, 0, tzinfo=timezone.utc)
    # Simulate asyncpg returning the legacy string-encoded payload
    legacy_str_payload = json.dumps({"client_id": 99, "email": "x@y.z"})
    conn.fetch = AsyncMock(
        return_value=[
            {
                "id": 50,
                "type": "crm.client_created",
                "payload": legacy_str_payload,
                "created_at": fake_dt,
            },
        ]
    )

    rows = await fetch_outbox_events(conn, after_id=0, limit=10)

    assert len(rows) == 1
    assert isinstance(rows[0]["payload"], dict), "payload must be unwrapped to dict"
    assert rows[0]["payload"] == {"client_id": 99, "email": "x@y.z"}


@pytest.mark.asyncio
async def test_fetch_outbox_events_handles_malformed_string_payload():
    """CICATRIX 2026-05-21 — a non-JSON string payload (theoretically
    impossible but belt-and-suspenders) must not raise; coerce to empty
    dict and log a warning. The row is still surfaced so the cursor can
    advance past it."""
    conn = AsyncMock()
    fake_dt = datetime(2026, 5, 21, 23, 0, 0, tzinfo=timezone.utc)
    conn.fetch = AsyncMock(
        return_value=[
            {
                "id": 51,
                "type": "rag.low_confidence",
                "payload": "not valid json {{{",
                "created_at": fake_dt,
            },
        ]
    )

    rows = await fetch_outbox_events(conn, after_id=0, limit=10)

    assert len(rows) == 1
    assert rows[0]["payload"] == {}
    assert rows[0]["id"] == 51
