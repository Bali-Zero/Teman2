"""Integration tests for the WhatsApp media PULL endpoints (Anello 1, Piece B).

Runs against the LOCAL nuzantara_dev DB (same default as the intake tests). The
endpoint functions are invoked directly (FastAPI Depends bypassed) with a real
asyncpg pool, exercising the real events_outbox table. Each test publishes its
own rows on the whatsapp_media_pending channel and purges them in teardown.

M5 note: if the DB is unreachable the pool fixture errors (not silently skips) —
an M5 skip is NOT a pass for DB-touching tests.
"""

from __future__ import annotations

import os

import asyncpg
import pytest
import pytest_asyncio

import backend.app.routers.bridge as bridge
from backend.services.events import outbox as events_outbox

_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_dev",
)
_CHANNEL = "whatsapp_media_pending"
_AUTH = "test-bridge-key-piece-b"


@pytest_asyncio.fixture
async def pool() -> asyncpg.Pool:
    p = await asyncpg.create_pool(dsn=_DB_URL, min_size=1, max_size=3)
    try:
        yield p
    finally:
        await p.close()


@pytest_asyncio.fixture
async def published_ids(pool: asyncpg.Pool):
    """Publish 2 metadata-only rows; track ids; purge all tracked ids at teardown."""
    ids: list[int] = []

    async with pool.acquire() as conn:
        async with conn.transaction():
            for i in (1, 2):
                oid = await events_outbox.publish(
                    conn,
                    _CHANNEL,
                    {
                        "media_id": f"media-piece-b-{i}",
                        "mime_type": "application/pdf",
                        "message_type": "document",
                        "filename": f"doc-{i}.pdf",
                        "declared_sha256": f"sha-{i}",
                        "wa_message_id": f"wamid.PB{i}",
                        "from_phone": "62811",
                        "phone_number_id": "1104946272705747",
                        "sender_name": "Tester",
                    },
                )
                ids.append(oid)

    yield ids

    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM events_outbox WHERE id = ANY($1::bigint[])", ids)


@pytest.fixture(autouse=True)
def _bridge_key(monkeypatch):
    monkeypatch.setenv("BRIDGE_API_KEY", _AUTH)


@pytest.mark.asyncio
async def test_pending_returns_published_metadata(pool, published_ids):
    resp = await bridge.get_wa_media_pending(
        since=min(published_ids) - 1,
        limit=50,
        db_pool=pool,
        x_bridge_auth=_AUTH,
    )
    got = {it.outbox_id: it for it in resp.items if it.outbox_id in published_ids}
    assert set(got) == set(published_ids)
    one = got[min(published_ids)]
    assert one.media_id == "media-piece-b-1"
    assert one.mime_type == "application/pdf"
    assert one.message_type == "document"
    assert one.filename == "doc-1.pdf"
    assert one.declared_sha256 == "sha-1"
    assert one.wa_message_id == "wamid.PB1"
    assert one.phone_number_id == "1104946272705747"
    assert resp.last_id == max(published_ids)


@pytest.mark.asyncio
async def test_pending_rejects_bad_auth(pool, published_ids):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ei:
        await bridge.get_wa_media_pending(
            since=0, limit=50, db_pool=pool, x_bridge_auth="wrong"
        )
    assert ei.value.status_code == 401


@pytest.mark.asyncio
async def test_ack_marks_consumed_and_excludes_from_pending(pool, published_ids):
    # Ack the first row.
    ack = await bridge.ack_wa_media(
        bridge.WaMediaAckRequest(outbox_ids=[published_ids[0]]),
        db_pool=pool,
        x_bridge_auth=_AUTH,
    )
    assert ack.acked == [published_ids[0]]

    # It must no longer appear in pending; the second still does.
    resp = await bridge.get_wa_media_pending(
        since=min(published_ids) - 1, limit=50, db_pool=pool, x_bridge_auth=_AUTH
    )
    pending_ids = {it.outbox_id for it in resp.items}
    assert published_ids[0] not in pending_ids
    assert published_ids[1] in pending_ids


@pytest.mark.asyncio
async def test_ack_is_idempotent(pool, published_ids):
    first = await bridge.ack_wa_media(
        bridge.WaMediaAckRequest(outbox_ids=[published_ids[1]]),
        db_pool=pool,
        x_bridge_auth=_AUTH,
    )
    assert first.acked == [published_ids[1]]
    # Second ack of the same id: already consumed → not re-acked.
    second = await bridge.ack_wa_media(
        bridge.WaMediaAckRequest(outbox_ids=[published_ids[1]]),
        db_pool=pool,
        x_bridge_auth=_AUTH,
    )
    assert second.acked == []


@pytest.mark.asyncio
async def test_since_cursor_pagination(pool, published_ids):
    # since = first id → only the second row comes back.
    resp = await bridge.get_wa_media_pending(
        since=published_ids[0], limit=50, db_pool=pool, x_bridge_auth=_AUTH
    )
    ids = {it.outbox_id for it in resp.items}
    assert published_ids[0] not in ids
    assert published_ids[1] in ids
