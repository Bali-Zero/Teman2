"""Integration tests for migration 112 (war_room_* schema + triggers).

These tests require a reachable PostgreSQL (DATABASE_URL env var) and
are SKIPPED automatically otherwise. They execute apply() on a disposable
schema, exercise the trigger-driven pg_notify, then rollback().

Run manually:
    TEST_DATABASE_URL=postgresql://user:pw@localhost:15432/test_db \\
    PYTHONPATH=. pytest backend/tests/services/war_room/test_migration_112.py -v
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager, suppress
from uuid import UUID

import pytest

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None  # type: ignore[assignment]


from backend.migrations import migration_112_war_room_tables  # type: ignore[import-not-found]

TEST_DSN = os.environ.get("TEST_DATABASE_URL")

# Ceiling for both halves of the notify handshake (subscribe, then delivery).
# Generous on purpose: it is a deadlock guard, not a timing assumption — the
# tests wait on real events and finish as soon as they fire.
NOTIFY_TIMEOUT_S = 10.0
# The listener outlives the delivery wait, so the assertion in the test body —
# not a listener timeout — is what reports a missing event.
LISTENER_LIFETIME_S = NOTIFY_TIMEOUT_S * 3

pytestmark = pytest.mark.skipif(
    asyncpg is None or not TEST_DSN,
    reason="TEST_DATABASE_URL not set or asyncpg missing",
)


@pytest.fixture
async def conn():
    """Apply migration on a clean connection; rollback after test."""
    assert asyncpg is not None
    c = await asyncpg.connect(TEST_DSN)
    try:
        # ensure idempotent starting state
        await migration_112_war_room_tables.rollback(c)
        await migration_112_war_room_tables.apply(c)
        yield c
    finally:
        await migration_112_war_room_tables.rollback(c)
        await c.close()


@pytest.mark.asyncio
async def test_tables_exist(conn):
    rows = await conn.fetch("""
        SELECT table_name FROM information_schema.tables
         WHERE table_schema = 'public'
           AND table_name LIKE 'war_room_%'
         ORDER BY table_name;
    """)
    names = {r["table_name"] for r in rows}
    assert names >= {
        "war_room_drafts",
        "war_room_posts",
        "war_room_metrics",
        "war_room_leads",
        "war_room_rejections",
        "war_room_missed_runs",
        "war_room_costs",
    }


@asynccontextmanager
async def _listening(received: list[dict]):
    """Subscribe to war_room_event and yield only once the LISTEN is live.

    Postgres does not queue a NOTIFY for a session that has not subscribed yet,
    so a listener that is still connecting misses the event outright. These
    tests used to wait a flat `sleep(0.2)` for the subscription — measured on
    M5 2026-07-26, `connect() + add_listener()` takes 98-470ms under normal
    fleet load, i.e. it blew that budget in 3 of 8 samples. The tests were
    therefore load-flaky by construction, and blocked unrelated pushes on a
    busy machine (`AssertionError: []` — no events, wrongly read as a missing
    trigger). Waiting on the real readiness signal removes the guess.
    """
    ready = asyncio.Event()
    done = asyncio.Event()

    async def listener_task():
        listen_conn = await asyncpg.connect(TEST_DSN)
        try:
            await listen_conn.add_listener(
                "war_room_event",
                lambda c, pid, ch, payload: received.append(json.loads(payload)),
            )
            ready.set()
            # `done` is always set by the context manager's finally, so this
            # cannot hang. It must NOT raise on timeout either: a listener that
            # died first would surface as TimeoutError and mask the real
            # assertion ("no events received", with the list) that tells you
            # whether the trigger fired.
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(done.wait(), timeout=LISTENER_LIFETIME_S)
        finally:
            ready.set()  # never leave the test hanging on a failed subscribe
            await listen_conn.close()

    task = asyncio.create_task(listener_task())
    await asyncio.wait_for(ready.wait(), timeout=NOTIFY_TIMEOUT_S)
    try:
        yield
        # The NOTIFY is delivered on the listener's connection, not ours: give
        # the event loop real time to deliver it, but stop as soon as it lands.
        for _ in range(int(NOTIFY_TIMEOUT_S / 0.05)):
            if received:
                break
            await asyncio.sleep(0.05)
    finally:
        done.set()
        await task


@pytest.mark.asyncio
async def test_insert_draft_triggers_notify(conn):
    """Trigger must emit pg_notify('war_room_event', ...) on draft INSERT."""
    received: list[dict] = []

    async with _listening(received):
        await conn.execute("""
            INSERT INTO war_room_drafts (topic, status)
            VALUES ('integration test', 'briefed');
        """)

    assert any(p.get("status") == "briefed" for p in received), received


@pytest.mark.asyncio
async def test_status_change_triggers_notify(conn):
    received: list[dict] = []

    draft_row = await conn.fetchrow("""
        INSERT INTO war_room_drafts (topic, status)
        VALUES ('status-change test', 'briefed')
        RETURNING id;
    """)
    draft_id: UUID = draft_row["id"]

    async with _listening(received):
        await conn.execute(
            "UPDATE war_room_drafts SET status = 'approved' WHERE id = $1;",
            draft_id,
        )

    approved_events = [p for p in received if p.get("status") == "approved"]
    assert approved_events, f"no approved event received: {received}"
    assert UUID(approved_events[0]["draft_id"]) == draft_id


@pytest.mark.asyncio
async def test_post_insert_triggers_notify(conn):
    received: list[dict] = []
    draft_row = await conn.fetchrow("""
        INSERT INTO war_room_drafts (topic, status)
        VALUES ('post-insert test', 'approved')
        RETURNING id;
    """)
    draft_id: UUID = draft_row["id"]

    async with _listening(received):
        await conn.execute(
            """
            INSERT INTO war_room_posts (draft_id, platform, post_external_id)
            VALUES ($1, 'instagram', 'ig_test_1');
            """,
            draft_id,
        )

    post_events = [p for p in received if p.get("event_type") == "post_published"]
    assert post_events, f"no post_published event: {received}"


@pytest.mark.asyncio
async def test_status_check_constraint_rejects_invalid(conn):
    with pytest.raises(asyncpg.PostgresError):  # type: ignore[union-attr]
        await conn.execute("""
            INSERT INTO war_room_drafts (topic, status)
            VALUES ('bad status', 'totally_invalid');
        """)


@pytest.mark.asyncio
async def test_platform_unique_per_draft(conn):
    draft_row = await conn.fetchrow("""
        INSERT INTO war_room_drafts (topic, status)
        VALUES ('unique-per-platform', 'approved')
        RETURNING id;
    """)
    draft_id: UUID = draft_row["id"]
    await conn.execute(
        "INSERT INTO war_room_posts (draft_id, platform) VALUES ($1, 'instagram');",
        draft_id,
    )
    with pytest.raises(asyncpg.UniqueViolationError):  # type: ignore[union-attr]
        await conn.execute(
            "INSERT INTO war_room_posts (draft_id, platform) VALUES ($1, 'instagram');",
            draft_id,
        )


@pytest.mark.asyncio
async def test_rollback_drops_tables(conn):
    # already applied in fixture. Rollback then verify.
    await migration_112_war_room_tables.rollback(conn)
    rows = await conn.fetch("""
        SELECT table_name FROM information_schema.tables
         WHERE table_schema = 'public'
           AND table_name LIKE 'war_room_%';
    """)
    assert rows == []
    # re-apply so fixture cleanup is idempotent
    await migration_112_war_room_tables.apply(conn)
