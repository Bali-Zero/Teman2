"""Tests for the WA Meta Inbox outbox worker (process_outbox_once).

Covers (spec sezione 3 "Worker"):
  - happy path: claim a pending human send → Graph send → ledger sent + wamid +
    apply staged status receipt → outbox done.
  - human_handling re-check abort for a bot reply (takeover after enqueue).
  - 24h window closed → ledger failed + outbox failed (no send).
  - send HTTP failure → backoff retry (attempts++, status back to pending).
  - idle when no due row.

The mock connection is scripted: fetchrow/fetchval return queued values in
call order, execute records SQL. transaction() is a no-op async CM. The pool
exposes execute() (reclaim) + acquire() (the claim/work conn).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.integrations import wa_outbox_worker
from backend.services.integrations.wa_outbox_worker import process_outbox_once


class ScriptedConn:
    def __init__(
        self,
        fetchrow_results: list[Any],
        fetchval_results: list[Any] | None = None,
    ) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self._fetchrow = list(fetchrow_results)
        self._fetchval = list(fetchval_results or [])

    async def execute(self, sql: str, *args: Any) -> str:
        self.executed.append((sql, args))
        return "UPDATE 1"

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        return self._fetchrow.pop(0) if self._fetchrow else None

    async def fetchval(self, sql: str, *args: Any) -> Any:
        return self._fetchval.pop(0) if self._fetchval else None

    def transaction(self) -> Any:
        @asynccontextmanager
        async def _cm():
            yield

        return _cm()

    def sql_contains(self, needle: str) -> bool:
        return any(needle in sql for sql, _ in self.executed)

    def sql_with_args(self, needle: str) -> list[tuple[str, tuple[Any, ...]]]:
        return [(s, a) for s, a in self.executed if needle in s]


def _make_pool(conn: ScriptedConn) -> MagicMock:
    pool = MagicMock()
    pool.execute = AsyncMock(return_value="UPDATE 0")  # reclaim stale
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool


def _wa_service(send_result: dict[str, Any] | None = None, raise_exc: Exception | None = None):
    svc = MagicMock()
    if raise_exc is not None:
        svc.send_message = AsyncMock(side_effect=raise_exc)
    else:
        svc.send_message = AsyncMock(return_value=send_result or {})
    return svc


async def _bot_gen(_thread: Any) -> str:
    return "generated bot reply"


@pytest.mark.asyncio
async def test_idle_when_no_due_row() -> None:
    conn = ScriptedConn(fetchrow_results=[None])  # claim → nothing
    pool = _make_pool(conn)
    result = await process_outbox_once(pool, _wa_service(), _bot_gen)
    assert result == "idle"
    # Reclaim stale always runs first.
    pool.execute.assert_awaited()


@pytest.mark.asyncio
async def test_human_send_happy_path_applies_staged_status() -> None:
    conn = ScriptedConn(
        fetchrow_results=[
            # claim
            {
                "id": 1,
                "thread_id": 7,
                "message_id": 100,
                "needs_generation": False,
                "attempts": 0,
            },
            # thread load (human_handling gate + window source)
            {
                "thread_id": 7,
                "counterpart_phone": "628111",
                "human_handling": True,
                "last_customer_at": "x",
            },
            # ledger body load (human send)
            {"body": "ciao dal team"},
            # _apply_pending_status: staged receipt exists for the wamid
            {"status": "delivered", "error": None},
        ],
        fetchval_results=[True],  # window_open
    )
    pool = _make_pool(conn)
    svc = _wa_service(send_result={"messages": [{"id": "wamid.SENT.1"}]})

    result = await process_outbox_once(pool, svc, _bot_gen)

    assert result == "sent"
    svc.send_message.assert_awaited_once()
    # ledger marked sent with the wamid
    assert any(
        "status = 'sent'" in s and "wamid.SENT.1" in str(a) for s, a in conn.executed
    )
    # outbox marked done
    assert conn.sql_contains("UPDATE wa_outbox SET status = 'done'")
    # staged receipt folded in + deleted
    assert any(
        "UPDATE meta_inbox_messages" in s and "delivered" in str(a) for s, a in conn.executed
    )
    assert conn.sql_contains("DELETE FROM wa_status_pending")


@pytest.mark.asyncio
async def test_bot_reply_aborts_on_human_takeover() -> None:
    conn = ScriptedConn(
        fetchrow_results=[
            # claim (bot reply, needs generation)
            {
                "id": 2,
                "thread_id": 7,
                "message_id": 200,
                "needs_generation": True,
                "attempts": 0,
            },
            # thread load → human took over
            {
                "thread_id": 7,
                "counterpart_phone": "628111",
                "human_handling": True,
                "last_customer_at": "x",
            },
        ]
    )
    pool = _make_pool(conn)
    svc = _wa_service()

    result = await process_outbox_once(pool, svc, _bot_gen)

    assert result == "aborted_human"
    svc.send_message.assert_not_awaited()
    assert any("aborted_human_takeover" in s for s, _ in conn.executed)
    assert conn.sql_contains("UPDATE wa_outbox SET status = 'failed'")


@pytest.mark.asyncio
async def test_window_closed_fails_without_send() -> None:
    conn = ScriptedConn(
        fetchrow_results=[
            {
                "id": 3,
                "thread_id": 7,
                "message_id": 300,
                "needs_generation": False,
                "attempts": 0,
            },
            {
                "thread_id": 7,
                "counterpart_phone": "628111",
                "human_handling": True,
                "last_customer_at": "x",
            },
            {"body": "late reply"},
        ],
        fetchval_results=[False],  # window_open = False (>24h)
    )
    pool = _make_pool(conn)
    svc = _wa_service()

    result = await process_outbox_once(pool, svc, _bot_gen)

    assert result == "window_closed"
    svc.send_message.assert_not_awaited()
    assert any("24h_window_closed" in s for s, _ in conn.executed)


@pytest.mark.asyncio
async def test_send_failure_retries_with_backoff() -> None:
    conn = ScriptedConn(
        fetchrow_results=[
            {
                "id": 4,
                "thread_id": 7,
                "message_id": 400,
                "needs_generation": False,
                "attempts": 0,
            },
            {
                "thread_id": 7,
                "counterpart_phone": "628111",
                "human_handling": True,
                "last_customer_at": "x",
            },
            {"body": "retry me"},
        ],
        fetchval_results=[True],  # window open
    )
    pool = _make_pool(conn)
    svc = _wa_service(raise_exc=RuntimeError("graph 500"))

    result = await process_outbox_once(pool, svc, _bot_gen)

    assert result == "retry"
    # back to pending with attempts incremented + next_retry_at backoff
    retry_updates = conn.sql_with_args("status = 'pending'")
    assert retry_updates, "expected an UPDATE back to pending for retry"
    assert any("next_retry_at" in s for s, _ in retry_updates)
    assert any(1 in a for _, a in retry_updates)  # attempts == 1


@pytest.mark.asyncio
async def test_send_failure_terminal_after_max_attempts() -> None:
    conn = ScriptedConn(
        fetchrow_results=[
            {
                "id": 5,
                "thread_id": 7,
                "message_id": 500,
                "needs_generation": False,
                "attempts": wa_outbox_worker.MAX_ATTEMPTS - 1,
            },
            {
                "thread_id": 7,
                "counterpart_phone": "628111",
                "human_handling": True,
                "last_customer_at": "x",
            },
            {"body": "last try"},
        ],
        fetchval_results=[True],
    )
    pool = _make_pool(conn)
    svc = _wa_service(raise_exc=RuntimeError("graph 500"))

    result = await process_outbox_once(pool, svc, _bot_gen)

    assert result == "failed"
    assert conn.sql_contains("UPDATE wa_outbox SET status = 'failed', attempts")
    assert any("send_failed_after_" in str(a) for _, a in conn.executed)
