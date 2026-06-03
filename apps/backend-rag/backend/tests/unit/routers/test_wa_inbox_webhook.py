"""Webhook-side tests for the WA Meta Inbox ledger persistence.

Exercises the helper functions in whatsapp_chat.py that the background task
calls, against a recording mock asyncpg connection. Asserts the panel-required
invariants (spec sezione 3):

  - inbound dedup: ON CONFLICT(meta_message_id) DO NOTHING → no bot enqueue
    on a duplicate Meta retry.
  - new inbound + bot-handled thread → bot reply enqueued (queued ledger row +
    wa_outbox needs_generation=true). Bot text NOT generated in the webhook.
  - new inbound + human_handling=true → NO bot enqueue.
  - status callback NEVER touches last_customer_at (24h window integrity).
  - orphan status (unknown wamid) → staged in wa_status_pending.
  - scope: the background task ignores changes for other phone_number_ids.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.routers import whatsapp_chat
from backend.services.integrations.wa_outbox_worker import META_INBOX_PHONE_NUMBER_ID

OTHER_PHONE_NUMBER_ID = "9999999999999"


class RecordingConn:
    """Mock asyncpg connection that records execute/fetchrow SQL + args.

    fetchrow returns values from a scripted queue (one per call, in order);
    fetchval returns from its own queue. transaction() is a no-op async CM.
    """

    def __init__(
        self,
        fetchrow_results: list[Any] | None = None,
        fetchval_results: list[Any] | None = None,
    ) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []
        self._fetchrow_results = list(fetchrow_results or [])
        self._fetchval_results = list(fetchval_results or [])

    async def execute(self, sql: str, *args: Any) -> str:
        self.executed.append((sql, args))
        return "UPDATE 1"

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        self.fetchrow_calls.append((sql, args))
        if self._fetchrow_results:
            return self._fetchrow_results.pop(0)
        return None

    async def fetchval(self, sql: str, *args: Any) -> Any:
        if self._fetchval_results:
            return self._fetchval_results.pop(0)
        return None

    def transaction(self) -> Any:
        @asynccontextmanager
        async def _cm():
            yield

        return _cm()

    def all_sql(self) -> str:
        joined = " ".join(sql for sql, _ in self.executed)
        joined += " ".join(sql for sql, _ in self.fetchrow_calls)
        return joined


def _msg(wamid: str = "wamid.A", body: str = "hello", phone: str = "628111") -> dict[str, Any]:
    return {
        "id": wamid,
        "from": phone,
        "type": "text",
        "timestamp": "1717400000",
        "text": {"body": body},
    }


@pytest.mark.asyncio
async def test_new_inbound_bot_handled_enqueues_bot_reply() -> None:
    conn = RecordingConn(
        fetchrow_results=[
            {"thread_id": 7, "human_handling": False},  # thread upsert
            {"id": 100},  # inbound ledger insert (new)
            {"id": 101},  # bot queued ledger insert
        ]
    )
    await whatsapp_chat._handle_meta_inbox_message(conn, _msg(), "Mario", webhook_id=5)

    sql = conn.all_sql()
    assert "INSERT INTO meta_inbox_threads" in sql
    assert "GREATEST" in sql  # last_customer_at via GREATEST
    assert "ON CONFLICT (meta_message_id) DO NOTHING" in sql
    assert "INSERT INTO wa_outbox" in sql
    # bot ledger row inserted as queued/bot, needs_generation enqueued
    assert any("'bot'" in s and "queued" in s for s, _ in conn.fetchrow_calls)
    assert any("needs_generation, status" in s for s, _ in conn.executed)


@pytest.mark.asyncio
async def test_duplicate_inbound_does_not_enqueue_bot() -> None:
    conn = RecordingConn(
        fetchrow_results=[
            {"thread_id": 7, "human_handling": False},  # thread upsert
            None,  # inbound insert → ON CONFLICT DO NOTHING → no row
        ]
    )
    await whatsapp_chat._handle_meta_inbox_message(conn, _msg(), "Mario", webhook_id=5)

    # No wa_outbox enqueue, no bot ledger row.
    assert not any("INSERT INTO wa_outbox" in s for s, _ in conn.executed)
    assert not any("'bot'" in s for s, _ in conn.fetchrow_calls[1:])


@pytest.mark.asyncio
async def test_new_inbound_human_handling_no_bot() -> None:
    conn = RecordingConn(
        fetchrow_results=[
            {"thread_id": 7, "human_handling": True},  # thread upsert (human owns it)
            {"id": 100},  # inbound ledger insert (new)
        ]
    )
    await whatsapp_chat._handle_meta_inbox_message(conn, _msg(), "Mario", webhook_id=5)

    assert not any("INSERT INTO wa_outbox" in s for s, _ in conn.executed)


@pytest.mark.asyncio
async def test_status_callback_never_touches_last_customer_at() -> None:
    conn = RecordingConn(
        fetchrow_results=[
            {"id": 100, "status": "sent"},  # existing ledger row lookup
        ]
    )
    await whatsapp_chat._apply_status_callback(
        conn, {"id": "wamid.A", "status": "delivered"}
    )

    # Status advanced to delivered on the ledger row...
    assert any(
        "UPDATE meta_inbox_messages SET status" in s and "delivered" in str(a)
        for s, a in conn.executed
    )
    # ...and NOTHING wrote last_customer_at / meta_inbox_threads.
    assert not any("last_customer_at" in s for s, _ in conn.executed)
    assert not any("meta_inbox_threads" in s for s, _ in conn.executed)


@pytest.mark.asyncio
async def test_status_callback_does_not_regress() -> None:
    """A 'sent' receipt arriving after 'read' must NOT downgrade the row."""
    conn = RecordingConn(fetchrow_results=[{"id": 100, "status": "read"}])
    await whatsapp_chat._apply_status_callback(conn, {"id": "wamid.A", "status": "sent"})

    assert not any("UPDATE meta_inbox_messages SET status" in s for s, _ in conn.executed)


@pytest.mark.asyncio
async def test_orphan_status_staged_in_pending() -> None:
    conn = RecordingConn(fetchrow_results=[None])  # ledger lookup → unknown wamid
    await whatsapp_chat._apply_status_callback(
        conn, {"id": "wamid.ORPHAN", "status": "read"}
    )

    assert any("INSERT INTO wa_status_pending" in s for s, _ in conn.executed)
    assert not any("UPDATE meta_inbox_messages" in s for s, _ in conn.executed)


@pytest.mark.asyncio
async def test_failed_status_records_error() -> None:
    conn = RecordingConn(fetchrow_results=[{"id": 100, "status": "sent"}])
    await whatsapp_chat._apply_status_callback(
        conn,
        {
            "id": "wamid.A",
            "status": "failed",
            "errors": [{"title": "Message undeliverable"}],
        },
    )
    assert any(
        "status = 'failed'" in s and "Message undeliverable" in str(a)
        for s, a in conn.executed
    )


@pytest.mark.asyncio
async def test_scope_other_phone_number_id_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """The background task must ignore changes for non-target phone_number_ids."""
    handled: list[dict[str, Any]] = []

    async def _fake_handle(conn, msg, sender_name, webhook_id):  # type: ignore[no-untyped-def]
        handled.append(msg)

    monkeypatch.setattr(whatsapp_chat, "_handle_meta_inbox_message", _fake_handle)

    status_applied: list[dict[str, Any]] = []

    async def _fake_status(conn, status_obj):  # type: ignore[no-untyped-def]
        status_applied.append(status_obj)

    monkeypatch.setattr(whatsapp_chat, "_apply_status_callback", _fake_status)

    # Build a pool whose acquire() yields a dummy conn.
    conn = RecordingConn()
    pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)

    request = MagicMock()
    request.app.state.db_pool = pool
    monkeypatch.setattr(whatsapp_chat, "_get_db_pool", lambda r: pool)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": OTHER_PHONE_NUMBER_ID},
                            "messages": [_msg(wamid="wamid.OTHER")],
                        },
                    }
                ],
            }
        ],
    }

    await whatsapp_chat.process_meta_inbox_payload(payload, request)

    assert handled == []  # other number → not handled by meta-inbox
    assert status_applied == []


@pytest.mark.asyncio
async def test_scope_target_phone_number_id_handled(monkeypatch: pytest.MonkeyPatch) -> None:
    handled: list[dict[str, Any]] = []

    async def _fake_handle(conn, msg, sender_name, webhook_id):  # type: ignore[no-untyped-def]
        handled.append(msg)

    monkeypatch.setattr(whatsapp_chat, "_handle_meta_inbox_message", _fake_handle)
    monkeypatch.setattr(
        whatsapp_chat, "_resolve_webhook_id", AsyncMock(return_value=None)
    )

    conn = RecordingConn()
    pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    monkeypatch.setattr(whatsapp_chat, "_get_db_pool", lambda r: pool)

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": META_INBOX_PHONE_NUMBER_ID},
                            "messages": [_msg(wamid="wamid.TARGET")],
                        },
                    }
                ],
            }
        ],
    }

    await whatsapp_chat.process_meta_inbox_payload(payload, MagicMock())

    assert len(handled) == 1
    assert handled[0]["id"] == "wamid.TARGET"
