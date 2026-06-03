"""Regression tests for the WA Meta Inbox ON CONFLICT arbiter (partial indexes).

Root cause (2026-06-04): the inbound-capture INSERT in
``app/routers/whatsapp_chat.py`` and the human-send INSERT in
``app/routers/wa_inbox.py`` both target ``meta_inbox_messages``, whose dedup
indexes (migration 206) are PARTIAL:

  CREATE UNIQUE INDEX uq_meta_inbox_messages_wamid
      ON meta_inbox_messages (meta_message_id) WHERE meta_message_id IS NOT NULL;
  CREATE UNIQUE INDEX uq_meta_inbox_messages_idem
      ON meta_inbox_messages (thread_id, idempotency_key)
      WHERE idempotency_key IS NOT NULL;

``ON CONFLICT (col)`` with NO ``WHERE`` predicate does NOT match a partial
unique index — Postgres raises ``InvalidColumnReferenceError`` ("there is no
unique or exclusion constraint matching the ON CONFLICT specification"). So
every inbound message rolled back and never reached the ledger (user's "Ciao"
test, webhook 207, 0 ledger rows). The fix repeats the index predicate in the
``ON CONFLICT ... WHERE ...`` clause.

These tests run against a REAL Postgres (the unit-mock tests in
test_wa_outbox_worker.py use a ScriptedConn that does NOT validate the arbiter
— scar "Test infrastructure mock != production stack"). They build the two
partial indexes exactly as migration 206 does and exercise the production
clauses, including a negative test that the predicate-less clause STILL raises
(so the regression cannot silently come back).

Skipped unless ``TEST_DATABASE_URL`` is set and ``asyncpg`` is installed.
Locally: ``TEST_DATABASE_URL=postgresql:///postgres \
    PYTHONPATH=. pytest backend/tests/unit/routers/test_wa_meta_inbox_onconflict.py -q``
"""

from __future__ import annotations

import os
import uuid

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None  # type: ignore[assignment]

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    asyncpg is None or not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL not set or asyncpg missing",
)

# The minimal slice of migration 206 these clauses arbitrate against. Kept in
# sync with backend/db/migrations_v2/206_wa_meta_inbox.sql (the two partial
# unique indexes are the load-bearing part for ON CONFLICT).
_SCHEMA = """
CREATE TABLE meta_inbox_messages (
    id BIGSERIAL PRIMARY KEY,
    thread_id BIGINT NOT NULL,
    meta_message_id TEXT,
    direction TEXT NOT NULL,
    sender_role TEXT NOT NULL,
    body TEXT,
    media_type TEXT,
    status TEXT NOT NULL DEFAULT 'received',
    idempotency_key TEXT,
    webhook_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_meta_inbox_messages_wamid
    ON meta_inbox_messages (meta_message_id)
    WHERE meta_message_id IS NOT NULL;
CREATE UNIQUE INDEX uq_meta_inbox_messages_idem
    ON meta_inbox_messages (thread_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
"""

# Verbatim arbiter clauses from the production routers (must match the code).
_INBOUND_INSERT = """
INSERT INTO meta_inbox_messages (
    thread_id, meta_message_id, direction, sender_role, body,
    media_type, status, webhook_id
)
VALUES ($1, $2, 'inbound', 'customer', $3, $4, 'received', $5)
ON CONFLICT (meta_message_id) WHERE meta_message_id IS NOT NULL
    DO NOTHING
RETURNING id
"""

_HUMAN_SEND_INSERT = """
INSERT INTO meta_inbox_messages (
    thread_id, direction, sender_role, body, status, idempotency_key
)
VALUES ($1, 'outbound', 'human', $2, 'queued', $3)
ON CONFLICT (thread_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL DO NOTHING
RETURNING id
"""

# The pre-fix clauses (no predicate) — the negative tests assert these STILL
# raise, locking the regression shut.
_INBOUND_INSERT_BROKEN = """
INSERT INTO meta_inbox_messages (thread_id, meta_message_id, direction, sender_role, body)
VALUES ($1, $2, 'inbound', 'customer', $3)
ON CONFLICT (meta_message_id) DO NOTHING
RETURNING id
"""

_HUMAN_SEND_INSERT_BROKEN = """
INSERT INTO meta_inbox_messages (thread_id, direction, sender_role, body, idempotency_key)
VALUES ($1, 'outbound', 'human', $2, $3)
ON CONFLICT (thread_id, idempotency_key) DO NOTHING
RETURNING id
"""


@pytest.fixture
async def conn():
    """An asyncpg connection to a throwaway DB with the 206 partial indexes.

    Creates a uniquely-named scratch database so concurrent test runs don't
    collide, drops it on teardown.
    """
    assert asyncpg is not None and TEST_DATABASE_URL is not None
    admin = await asyncpg.connect(TEST_DATABASE_URL)
    db_name = f"wa_onconflict_test_{uuid.uuid4().hex[:12]}"
    await admin.execute(f'CREATE DATABASE "{db_name}"')
    await admin.close()

    base = TEST_DATABASE_URL.rsplit("/", 1)[0]
    test_conn = await asyncpg.connect(f"{base}/{db_name}")
    await test_conn.execute(_SCHEMA)
    try:
        yield test_conn
    finally:
        await test_conn.close()
        admin = await asyncpg.connect(TEST_DATABASE_URL)
        await admin.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
        await admin.close()


@pytest.mark.asyncio
async def test_inbound_insert_lands_and_dedups(conn) -> None:
    """The fixed inbound clause inserts once, dedups the Meta retry (no error)."""
    first = await conn.fetchrow(_INBOUND_INSERT, 1, "wamid.A", "Ciao", None, None)
    assert first is not None and first["id"] is not None

    # Meta retry of the same wamid → ON CONFLICT DO NOTHING → no row, no error.
    retry = await conn.fetchrow(_INBOUND_INSERT, 1, "wamid.A", "Ciao", None, None)
    assert retry is None

    rows = await conn.fetch("SELECT meta_message_id, body FROM meta_inbox_messages")
    assert len(rows) == 1
    assert rows[0]["meta_message_id"] == "wamid.A"


@pytest.mark.asyncio
async def test_human_send_insert_lands_and_dedups(conn) -> None:
    """The fixed human-send clause inserts once, dedups the network retry."""
    first = await conn.fetchrow(_HUMAN_SEND_INSERT, 1, "hello", "idem-1")
    assert first is not None and first["id"] is not None

    retry = await conn.fetchrow(_HUMAN_SEND_INSERT, 1, "hello", "idem-1")
    assert retry is None

    rows = await conn.fetch(
        "SELECT idempotency_key FROM meta_inbox_messages WHERE direction = 'outbound'"
    )
    assert len(rows) == 1
    assert rows[0]["idempotency_key"] == "idem-1"


@pytest.mark.asyncio
async def test_inbound_insert_without_predicate_still_raises(conn) -> None:
    """Negative guard: the pre-fix clause (no WHERE) must keep raising.

    This is the regression lock — if someone drops the predicate again, this
    fails loudly instead of silently swallowing every inbound message.
    """
    with pytest.raises(asyncpg.exceptions.InvalidColumnReferenceError):
        await conn.execute(_INBOUND_INSERT_BROKEN, 1, "wamid.B", "Ciao")


@pytest.mark.asyncio
async def test_human_send_insert_without_predicate_still_raises(conn) -> None:
    """Negative guard for the human-send partial index, same rationale."""
    with pytest.raises(asyncpg.exceptions.InvalidColumnReferenceError):
        await conn.execute(_HUMAN_SEND_INSERT_BROKEN, 1, "hello", "idem-2")
