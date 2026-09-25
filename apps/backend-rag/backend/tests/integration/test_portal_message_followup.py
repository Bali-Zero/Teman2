"""Real PostgreSQL acceptance with an explicitly isolated synthetic database."""

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock
from urllib.parse import urlparse
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from fastapi import HTTPException

from backend.app.routers import crm_portal_integration as router
from backend.services.portal import portal_message_email as delivery
from backend.services.portal.portal_notification_service import PortalNotificationService
from backend.services.portal.portal_reply_service import get_pending_replies

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def pool(monkeypatch):
    dsn = os.getenv("PORTAL_FOLLOWUP_TEST_DSN")
    if not dsn:
        pytest.skip("Explicit synthetic PostgreSQL fixture not configured")
    target = urlparse(dsn)
    assert target.hostname == "127.0.0.1" and target.path == "/portal_reply_test"
    assert target.username == "portal_reply_test"
    schema = "portal_reply_" + uuid4().hex
    admin = await asyncpg.connect(dsn, ssl=False)
    await admin.execute(f'CREATE SCHEMA "{schema}"')
    db = await asyncpg.create_pool(
        dsn, min_size=1, max_size=3, ssl=False, server_settings={"search_path": schema}
    )
    async with db.acquire() as conn:
        await conn.execute("""
          CREATE TABLE clients(id INTEGER PRIMARY KEY, full_name TEXT, assigned_to TEXT, email TEXT, deleted_at TIMESTAMPTZ);
          CREATE TABLE portal_messages(id SERIAL PRIMARY KEY, client_id INTEGER REFERENCES clients(id), practice_id INTEGER, subject TEXT, direction TEXT, content TEXT, sent_by TEXT, read_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW());
          INSERT INTO clients VALUES(1, 'Synthetic client name', 'lead@balizero.com', 'client@example.com', NULL);
        """)
        migration = (
            Path(__file__).resolve().parents[2] / "db/migrations_v2/321_portal_reply_and_email.sql"
        )
        await conn.execute(migration.read_text())
    monkeypatch.setattr(router, "verify_client_access", AsyncMock())
    try:
        yield db
    finally:
        await db.close()
        await admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
        await admin.close()


async def manual(pool):
    return await router.send_message_to_client(
        client_id=1,
        request=router.TeamMessageRequest(content="Synthetic answer content"),
        current_user={"email": "lead@balizero.com", "role": "admin"},
        db_pool=pool,
    )


async def test_read_and_automatic_notice_do_not_clear_but_reply_does(pool):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO portal_messages(client_id,direction,content,sent_by,read_at) VALUES(1,'client_to_team','Synthetic question','synthetic-client',NOW())"
        )
        assert (await get_pending_replies(conn, "lead@balizero.com"))["total_pending"] == 1
    await PortalNotificationService(pool).notify_profile_updated(1, ["email"], "lead@balizero.com")
    async with pool.acquire() as conn:
        assert (await get_pending_replies(conn, "lead@balizero.com"))["total_pending"] == 1
    await manual(pool)
    async with pool.acquire() as conn:
        assert (await get_pending_replies(conn, "lead@balizero.com"))["total_pending"] == 0
        assert await conn.fetchval("SELECT COUNT(*) FROM portal_message_email_outbox") == 1
        await conn.execute(
            "INSERT INTO portal_messages(client_id,direction,content,sent_by) VALUES(1,'client_to_team','Synthetic follow-up','synthetic-client')"
        )
        assert (await get_pending_replies(conn, "lead@balizero.com"))["total_pending"] == 1


async def test_outbox_failure_rolls_back_manual_message(pool):
    async with pool.acquire() as conn:
        await conn.execute(
            "ALTER TABLE portal_message_email_outbox ADD CONSTRAINT reject_test CHECK(FALSE)"
        )
    with pytest.raises(HTTPException) as error:
        await manual(pool)
    assert error.value.status_code == 500
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT COUNT(*) FROM portal_messages") == 0


async def test_concurrent_workers_send_once_and_notice_has_no_message_content(pool, monkeypatch):
    await manual(pool)
    sender = AsyncMock()
    monkeypatch.setattr(delivery, "send_internal_email", sender)
    assert sorted(await asyncio.gather(delivery.deliver_one(pool), delivery.deliver_one(pool))) == [
        False,
        True,
    ]
    sender.assert_awaited_once()
    kwargs = sender.call_args.kwargs
    assert kwargs["to"] == "client@example.com"
    assert "Synthetic" not in kwargs["body"] and "Synthetic" not in kwargs["subject"]
    assert kwargs["idempotency_key"] and kwargs["raise_on_failure"] is True
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT state FROM portal_message_email_outbox") == "sent"
    assert await delivery.deliver_one(pool) is False


async def test_failed_attempt_reuses_key_but_expired_lease_is_not_blindly_resent(pool, monkeypatch):
    await manual(pool)
    sender = AsyncMock(side_effect=RuntimeError("provider_unavailable"))
    monkeypatch.setattr(delivery, "send_internal_email", sender)
    await delivery.deliver_one(pool)
    first_key = sender.call_args.kwargs["idempotency_key"]
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT state FROM portal_message_email_outbox") == "pending"
        await conn.execute("UPDATE portal_message_email_outbox SET next_attempt_at=NOW()")
    sender.side_effect = None
    await delivery.deliver_one(pool)
    assert sender.call_args.kwargs["idempotency_key"] == first_key
    await manual(pool)
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE portal_message_email_outbox SET state='sending', attempts=1, first_attempt_at=NOW()-INTERVAL '20 minutes', lease_until=NOW()-INTERVAL '1 minute' WHERE state='pending'"
        )
    sender.reset_mock()
    await delivery.deliver_one(pool)
    sender.assert_not_awaited()
    async with pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT COUNT(*) FROM portal_message_email_outbox WHERE state='uncertain'"
            )
            == 1
        )


@pytest.mark.parametrize(
    "change, reason",
    [
        ("UPDATE clients SET email=NULL", "recipient_unavailable"),
        ("UPDATE clients SET email='invalid'", "recipient_unavailable"),
        ("UPDATE clients SET deleted_at=NOW()", "message_ineligible"),
        ("UPDATE portal_messages SET is_system_generated=TRUE", "message_ineligible"),
    ],
)
async def test_ineligible_email_never_reaches_provider(pool, monkeypatch, change, reason):
    await manual(pool)
    sender = AsyncMock()
    monkeypatch.setattr(delivery, "send_internal_email", sender)
    async with pool.acquire() as conn:
        await conn.execute(change)
    await delivery.deliver_one(pool)
    sender.assert_not_awaited()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT state,last_error FROM portal_message_email_outbox")
        assert dict(row) == {"state": "failed", "last_error": reason}


@pytest.mark.parametrize(
    "error, terminal",
    [
        (delivery.EmailProviderRejected("rejected"), "failed"),
        (RuntimeError("timeout"), "uncertain"),
    ],
)
async def test_three_provider_failures_stop_automatic_retries(pool, monkeypatch, error, terminal):
    await manual(pool)
    sender = AsyncMock(side_effect=error)
    monkeypatch.setattr(delivery, "send_internal_email", sender)
    for _attempt in range(3):
        async with pool.acquire() as conn:
            await conn.execute("UPDATE portal_message_email_outbox SET next_attempt_at=NOW()")
        assert await delivery.deliver_one(pool)
    assert sender.await_count == 3
    assert len({call.kwargs["idempotency_key"] for call in sender.call_args_list}) == 1
    assert not await delivery.deliver_one(pool)
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT state FROM portal_message_email_outbox") == terminal


@pytest.mark.parametrize("is_system", [True, False])
async def test_automatic_incoming_profile_notice_does_not_open_pending(pool, is_system):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO portal_messages(client_id,direction,content,sent_by,is_system_generated) VALUES(1,'client_to_team','Synthetic update','portal',$1)",
            is_system,
        )
        assert (await get_pending_replies(conn, "lead@balizero.com"))["total_pending"] == 0


async def test_exhausted_lease_is_not_sent_and_stale_completion_cannot_overwrite(pool, monkeypatch):
    await manual(pool)
    sender = AsyncMock()
    monkeypatch.setattr(delivery, "send_internal_email", sender)
    async with pool.acquire() as conn:
        old = await conn.fetchrow(
            "UPDATE portal_message_email_outbox SET state='sending', attempts=3, first_attempt_at=NOW()-INTERVAL '5 minutes',lease_until=NOW()-INTERVAL '1 minute' RETURNING *"
        )
    await delivery.deliver_one(pool)
    sender.assert_not_awaited()
    await delivery._finish(pool, old, "sent")
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT state,attempts FROM portal_message_email_outbox")
        assert dict(row) == {"state": "uncertain", "attempts": 3}
