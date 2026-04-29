"""Tests for the inbound webhook background processor.

WebhookProcessor is the LISTEN-based worker that drains the
``inbound_webhooks`` table populated by the ack-first webhook routers
(P0-6 from zero-crash audit 2026-04-29).

Tests use mocked asyncpg connection (AsyncMock) — same pattern as
``backend/tests/services/events/test_outbox.py``.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.channels.webhook_processor import (
    WebhookProcessor,
    _compute_backoff_seconds,
)


# ── _compute_backoff_seconds ──────────────────────────────────────────────


def test_compute_backoff_first_attempt():
    """First retry: 5 minutes after the previous attempt."""
    # attempts=0 means we just incremented from 0 to 1 (first failure)
    assert _compute_backoff_seconds(attempts=1) == 300


def test_compute_backoff_grows_linearly():
    """Linear backoff: 5min × attempt number."""
    assert _compute_backoff_seconds(attempts=1) == 300   # 5 min
    assert _compute_backoff_seconds(attempts=2) == 600   # 10 min
    assert _compute_backoff_seconds(attempts=3) == 900   # 15 min
    assert _compute_backoff_seconds(attempts=4) == 1200  # 20 min


def test_compute_backoff_caps_at_attempt_5():
    """Attempt 5 = terminal, no further retry — but the helper still returns
    a sane value for monitoring use cases."""
    # We don't care what value it returns at 5; just that it doesn't crash.
    assert _compute_backoff_seconds(attempts=5) >= 300


# ── WebhookProcessor.drain_pending ────────────────────────────────────────


@pytest.mark.asyncio
async def test_drain_pending_processes_each_row():
    """drain_pending() fetches pending rows and dispatches each to its handler."""
    handler = AsyncMock()
    processor = WebhookProcessor(
        db_pool=_make_pool_returning(
            [
                {"id": 1, "channel": "whatsapp", "payload": {"msg": "a"}, "attempts": 0},
                {"id": 2, "channel": "whatsapp", "payload": {"msg": "b"}, "attempts": 0},
            ]
        ),
        handlers={"whatsapp": handler},
    )

    processed = await processor.drain_pending()

    assert processed == 2
    assert handler.await_count == 2


@pytest.mark.asyncio
async def test_drain_pending_marks_processed_on_success():
    """After a successful handler call, the row is UPDATEd with processed_at=NOW()."""
    handler = AsyncMock()
    pool = _make_pool_returning(
        [{"id": 42, "channel": "whatsapp", "payload": {"msg": "ok"}, "attempts": 0}]
    )
    processor = WebhookProcessor(db_pool=pool, handlers={"whatsapp": handler})

    await processor.drain_pending()

    # Verify execute called with UPDATE inbound_webhooks SET processed_at = NOW()
    conn = pool._conn
    update_calls = [
        c for c in conn.execute.await_args_list
        if "processed_at = NOW()" in str(c.args[0])
    ]
    assert len(update_calls) == 1
    assert update_calls[0].args[1] == 42  # bound id


@pytest.mark.asyncio
async def test_drain_pending_skips_rows_without_handler():
    """A row with an unknown channel is marked terminal with 'no handler' error."""
    pool = _make_pool_returning(
        [{"id": 5, "channel": "unknown_channel", "payload": {}, "attempts": 0}]
    )
    processor = WebhookProcessor(db_pool=pool, handlers={"whatsapp": AsyncMock()})

    await processor.drain_pending()

    conn = pool._conn
    # Find the UPDATE that marks no handler
    error_updates = [
        c for c in conn.execute.await_args_list
        if "processed_at = NOW()" in str(c.args[0]) and "no handler" in str(c.args)
    ]
    assert len(error_updates) == 1


@pytest.mark.asyncio
async def test_drain_pending_retry_with_backoff_on_handler_exception():
    """When handler raises, the row gets next_retry_at set and attempts++."""
    handler = AsyncMock(side_effect=RuntimeError("boom"))
    pool = _make_pool_returning(
        [{"id": 7, "channel": "whatsapp", "payload": {"msg": "x"}, "attempts": 0}]
    )
    # fetchval returns the new attempts count
    pool._conn.fetchval = AsyncMock(return_value=1)
    processor = WebhookProcessor(db_pool=pool, handlers={"whatsapp": handler})

    await processor.drain_pending()

    # Should have called fetchval for the retry update (attempts++ + next_retry_at)
    retry_calls = [
        c for c in pool._conn.fetchval.await_args_list
        if "next_retry_at" in str(c.args[0]) and "attempts + 1" in str(c.args[0])
    ]
    assert len(retry_calls) >= 1


@pytest.mark.asyncio
async def test_drain_pending_marks_terminal_after_5_attempts():
    """After the 5th failure, the row is marked processed with 'GIVING UP' error."""
    handler = AsyncMock(side_effect=RuntimeError("permafail"))
    pool = _make_pool_returning(
        [{"id": 99, "channel": "whatsapp", "payload": {"msg": "x"}, "attempts": 4}]
    )
    # After increment: attempts becomes 5
    pool._conn.fetchval = AsyncMock(return_value=5)
    processor = WebhookProcessor(db_pool=pool, handlers={"whatsapp": handler})

    await processor.drain_pending()

    # Find the terminal-mark UPDATE (processed_at + GIVING UP)
    terminal = [
        c for c in pool._conn.execute.await_args_list
        if "processed_at = NOW()" in str(c.args[0]) and "GIVING UP" in str(c.args)
    ]
    assert len(terminal) == 1


@pytest.mark.asyncio
async def test_drain_pending_idempotent_on_replay():
    """Running drain_pending() twice with the same rows processes each only once.

    Realised via FOR UPDATE SKIP LOCKED on the SELECT — second call sees
    no rows because the first call already locked them in its transaction.
    Here we verify the SQL contains the SKIP LOCKED clause.
    """
    pool = _make_pool_returning(
        [{"id": 1, "channel": "whatsapp", "payload": {}, "attempts": 0}]
    )
    processor = WebhookProcessor(
        db_pool=pool, handlers={"whatsapp": AsyncMock()}
    )

    await processor.drain_pending()

    # Find the SELECT call
    select_calls = [
        c for c in pool._conn.fetch.await_args_list
        if "SELECT" in str(c.args[0]).upper() and "inbound_webhooks" in str(c.args[0])
    ]
    assert len(select_calls) >= 1
    assert "FOR UPDATE SKIP LOCKED" in select_calls[0].args[0]


@pytest.mark.asyncio
async def test_drain_pending_decodes_payload_str_to_dict():
    """asyncpg may return JSONB as str; processor must handle both."""
    handler = AsyncMock()
    pool = _make_pool_returning(
        [
            {"id": 1, "channel": "whatsapp",
             "payload": json.dumps({"msg": "from_str"}), "attempts": 0},
        ]
    )
    processor = WebhookProcessor(db_pool=pool, handlers={"whatsapp": handler})

    await processor.drain_pending()

    # Handler must receive a dict, not a str
    handler.assert_awaited_once()
    arg = handler.await_args.args[0]
    assert isinstance(arg, dict)
    assert arg["msg"] == "from_str"


# ── helpers ───────────────────────────────────────────────────────────────


def _make_pool_returning(rows):
    """Build an asyncpg.Pool mock that yields a connection returning ``rows`` on fetch.

    The fake connection supports:
    - acquire() async context manager
    - transaction() async context manager
    - fetch / execute / fetchval as AsyncMock
    """
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows)
    conn.execute = AsyncMock(return_value="UPDATE 1")
    conn.fetchval = AsyncMock(return_value=1)

    transaction_ctx = MagicMock()
    transaction_ctx.__aenter__ = AsyncMock(return_value=None)
    transaction_ctx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=transaction_ctx)

    pool = MagicMock()
    pool._conn = conn  # for test inspection

    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_ctx)

    return pool
