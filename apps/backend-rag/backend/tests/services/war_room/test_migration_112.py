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
from uuid import UUID

import pytest

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None  # type: ignore[assignment]


from backend.migrations import migration_112_war_room_tables  # type: ignore[import-not-found]

TEST_DSN = os.environ.get("TEST_DATABASE_URL")

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


@pytest.mark.asyncio
async def test_insert_draft_triggers_notify(conn):
    """Trigger must emit pg_notify('war_room_event', ...) on draft INSERT."""
    received: list[dict] = []

    async def listener_task():
        listen_conn = await asyncpg.connect(TEST_DSN)
        await listen_conn.add_listener(
            "war_room_event",
            lambda c, pid, ch, payload: received.append(json.loads(payload)),
        )
        await asyncio.sleep(2.0)
        await listen_conn.close()

    task = asyncio.create_task(listener_task())
    # give the listener a tick to subscribe
    await asyncio.sleep(0.2)

    await conn.execute("""
        INSERT INTO war_room_drafts (topic, status)
        VALUES ('integration test', 'briefed');
    """)

    await task
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

    async def listener_task():
        listen_conn = await asyncpg.connect(TEST_DSN)
        await listen_conn.add_listener(
            "war_room_event",
            lambda c, pid, ch, payload: received.append(json.loads(payload)),
        )
        await asyncio.sleep(2.0)
        await listen_conn.close()

    task = asyncio.create_task(listener_task())
    await asyncio.sleep(0.2)

    await conn.execute(
        "UPDATE war_room_drafts SET status = 'approved' WHERE id = $1;",
        draft_id,
    )

    await task
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

    async def listener_task():
        listen_conn = await asyncpg.connect(TEST_DSN)
        await listen_conn.add_listener(
            "war_room_event",
            lambda c, pid, ch, payload: received.append(json.loads(payload)),
        )
        await asyncio.sleep(2.0)
        await listen_conn.close()

    task = asyncio.create_task(listener_task())
    await asyncio.sleep(0.2)

    await conn.execute(
        """
        INSERT INTO war_room_posts (draft_id, platform, post_external_id)
        VALUES ($1, 'instagram', 'ig_test_1');
        """,
        draft_id,
    )

    await task
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
