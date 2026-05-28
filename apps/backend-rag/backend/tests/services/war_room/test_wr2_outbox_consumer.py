"""Tests for wr2_outbox_consumer (Cluster C pattern).

Spec: research/wr2/2026-05-27-wr2-autonomous-workflow-spec.md §7
"""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.war_room.wr2_outbox_consumer import (
    DEFAULT_BATCH_SIZE,
    EVENT_TABLE,
    claim_and_process_batch,
    emit_event,
)


def _make_conn_with_rows(rows: list[dict]) -> MagicMock:
    conn = MagicMock()
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=False)
    conn.fetch = AsyncMock(return_value=rows)
    conn.execute = AsyncMock(return_value="UPDATE 1")
    conn.fetchval = AsyncMock(return_value=42)
    return conn


@pytest.mark.asyncio
async def test_constants():
    assert EVENT_TABLE == "wr2_carousel_events_outbox"
    assert DEFAULT_BATCH_SIZE == 20


@pytest.mark.asyncio
async def test_claim_empty_event_types_returns_zero():
    conn = _make_conn_with_rows([])
    handler = AsyncMock(return_value=True)
    result = await claim_and_process_batch(conn, "strategos", (), handler)
    assert result == {"claimed": 0, "processed": 0, "failed": 0, "skipped_stale": 0}
    conn.fetch.assert_not_called()


@pytest.mark.asyncio
async def test_claim_no_rows():
    conn = _make_conn_with_rows([])
    handler = AsyncMock(return_value=True)
    result = await claim_and_process_batch(conn, "strategos", ("published",), handler)
    assert result["claimed"] == 0
    assert result["processed"] == 0


@pytest.mark.asyncio
async def test_claim_and_process_success():
    rows = [
        {
            "id": 1, "carousel_id": "c1", "event_type": "published",
            "payload": json.dumps({"foo": "bar"}),
            "created_at": datetime(2026, 5, 27), "consumed_by": [],
        },
        {
            "id": 2, "carousel_id": "c2", "event_type": "published",
            "payload": {"baz": "qux"},  # already-dict
            "created_at": datetime(2026, 5, 27), "consumed_by": ["other"],
        },
    ]
    conn = _make_conn_with_rows(rows)
    handler = AsyncMock(return_value=True)

    result = await claim_and_process_batch(conn, "strategos", ("published",), handler)

    assert result["claimed"] == 2
    assert result["processed"] == 2
    assert result["failed"] == 0
    assert handler.await_count == 2
    # Two UPDATE calls — one per processed row
    assert conn.execute.await_count == 2


@pytest.mark.asyncio
async def test_handler_returns_false_marks_failed():
    rows = [{
        "id": 5, "carousel_id": "c5", "event_type": "rejected",
        "payload": {}, "created_at": datetime(2026, 5, 27), "consumed_by": [],
    }]
    conn = _make_conn_with_rows(rows)
    handler = AsyncMock(return_value=False)

    result = await claim_and_process_batch(conn, "learner", ("rejected",), handler)

    assert result["claimed"] == 1
    assert result["processed"] == 0
    assert result["failed"] == 1
    # No UPDATE if handler returned False
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_handler_exception_marks_failed():
    rows = [{
        "id": 9, "carousel_id": "c9", "event_type": "published",
        "payload": {}, "created_at": datetime(2026, 5, 27), "consumed_by": [],
    }]
    conn = _make_conn_with_rows(rows)

    async def boom(_event):
        raise RuntimeError("handler exploded")
    result = await claim_and_process_batch(conn, "strategos", ("published",), boom)

    assert result["claimed"] == 1
    assert result["failed"] == 1
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_payload_string_parsed_to_dict():
    captured = []
    rows = [{
        "id": 11, "carousel_id": "c11", "event_type": "published",
        "payload": json.dumps({"key": "value"}),
        "created_at": datetime(2026, 5, 27), "consumed_by": [],
    }]
    conn = _make_conn_with_rows(rows)

    async def capture(event):
        captured.append(event)
        return True
    await claim_and_process_batch(conn, "strategos", ("published",), capture)

    assert captured[0]["payload"] == {"key": "value"}


@pytest.mark.asyncio
async def test_emit_event_returns_id():
    conn = _make_conn_with_rows([])
    row_id = await emit_event(conn, "cid", "approved", {"score": 0.9})
    assert row_id == 42
    conn.fetchval.assert_called_once()


@pytest.mark.asyncio
async def test_emit_event_handles_pg_error():
    import asyncpg
    conn = _make_conn_with_rows([])
    conn.fetchval = AsyncMock(side_effect=asyncpg.PostgresError("boom"))
    row_id = await emit_event(conn, "cid", "approved", {})
    assert row_id is None
