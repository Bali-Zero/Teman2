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
from collections.abc import Callable, Iterator
from contextlib import asynccontextmanager
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


# Ceiling for "the NOTIFY never arrived", NOT a timing expectation. The happy
# path returns in milliseconds; this only bounds the failure.
NOTIFY_TIMEOUT = 30.0


@asynccontextmanager
async def notify_listener(channel: str, until: Callable[[dict], bool]) -> Iterator[list[dict]]:
    """SYNCHRONISE with the listener, never sleep-and-hope.

    PostgreSQL LISTEN/NOTIFY delivers only to sessions that are ALREADY
    listening — a payload sent before `add_listener` returns is gone for good,
    not delayed. These tests used to give the listener a flat `sleep(0.2)` head
    start and then read for a flat `sleep(2.0)`, which is a race, not a wait: on
    a loaded machine (this repo's pre-push runs the full suite, and several
    sessions push at once — measured at load-average 50+ with 27 concurrent
    pre-push scripts) the connect+LISTEN does not finish inside 200ms, the
    write fires into the void, and the test fails on a healthy database.

    Now the caller's write is not issued until the LISTEN is confirmed attached,
    and we stop as soon as a payload the caller actually cares about arrives.
    `until` matters: these tests filter for a SPECIFIC event, so stopping at the
    first payload of any kind would let an unrelated notify that happens to land
    first satisfy the wait and fail the assertion spuriously.
    """
    received: list[dict] = []
    attached = asyncio.Event()
    delivered = asyncio.Event()

    def on_notify(_conn, _pid, _channel, payload):
        event = json.loads(payload)
        received.append(event)
        if until(event):
            delivered.set()

    async def listener():
        listen_conn = await asyncpg.connect(TEST_DSN)
        try:
            await listen_conn.add_listener(channel, on_notify)
            attached.set()
            try:
                await asyncio.wait_for(delivered.wait(), timeout=NOTIFY_TIMEOUT)
            except asyncio.TimeoutError:
                pass  # let the caller's assertion report it, with its own message
        finally:
            attached.set()  # never strand the caller if connect/LISTEN raised
            await listen_conn.close()

    task = asyncio.create_task(listener())
    await asyncio.wait_for(attached.wait(), timeout=NOTIFY_TIMEOUT)
    try:
        yield received
    finally:
        await task


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

    def is_briefed(p: dict) -> bool:
        return p.get("status") == "briefed"

    async with notify_listener("war_room_event", is_briefed) as received:
        await conn.execute("""
            INSERT INTO war_room_drafts (topic, status)
            VALUES ('integration test', 'briefed');
        """)

    assert any(is_briefed(p) for p in received), received


@pytest.mark.asyncio
async def test_status_change_triggers_notify(conn):
    draft_row = await conn.fetchrow("""
        INSERT INTO war_room_drafts (topic, status)
        VALUES ('status-change test', 'briefed')
        RETURNING id;
    """)
    draft_id: UUID = draft_row["id"]

    def is_approved(p: dict) -> bool:
        return p.get("status") == "approved"

    async with notify_listener("war_room_event", is_approved) as received:
        await conn.execute(
            "UPDATE war_room_drafts SET status = 'approved' WHERE id = $1;",
            draft_id,
        )

    approved_events = [p for p in received if is_approved(p)]
    assert approved_events, f"no approved event received: {received}"
    assert UUID(approved_events[0]["draft_id"]) == draft_id


@pytest.mark.asyncio
async def test_post_insert_triggers_notify(conn):
    draft_row = await conn.fetchrow("""
        INSERT INTO war_room_drafts (topic, status)
        VALUES ('post-insert test', 'approved')
        RETURNING id;
    """)
    draft_id: UUID = draft_row["id"]

    def is_post_published(p: dict) -> bool:
        return p.get("event_type") == "post_published"

    async with notify_listener("war_room_event", is_post_published) as received:
        await conn.execute(
            """
            INSERT INTO war_room_posts (draft_id, platform, post_external_id)
            VALUES ($1, 'instagram', 'ig_test_1');
            """,
            draft_id,
        )

    post_events = [p for p in received if is_post_published(p)]
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
