"""Integration tests for migration 113 (trend_signals + research_dossiers + triggers)."""

from __future__ import annotations

import asyncio
import json
import os

import pytest

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None  # type: ignore[assignment]


from backend.migrations import migration_113_intel_dossiers  # type: ignore[import-not-found]

TEST_DSN = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    asyncpg is None or not TEST_DSN,
    reason="TEST_DATABASE_URL not set or asyncpg missing",
)


@pytest.fixture
async def conn():
    assert asyncpg is not None
    c = await asyncpg.connect(TEST_DSN)
    try:
        await migration_113_intel_dossiers.rollback(c)
        await migration_113_intel_dossiers.apply(c)
        yield c
    finally:
        await migration_113_intel_dossiers.rollback(c)
        await c.close()


@pytest.mark.asyncio
async def test_tables_exist(conn):
    rows = await conn.fetch("""
        SELECT table_name FROM information_schema.tables
         WHERE table_schema = 'public'
           AND table_name IN (
               'trend_signals', 'research_dossiers',
               'dossier_reuses', 'dossier_refresh_log'
           )
         ORDER BY table_name;
    """)
    names = {r["table_name"] for r in rows}
    assert names == {
        "trend_signals", "research_dossiers",
        "dossier_reuses", "dossier_refresh_log",
    }


@pytest.mark.asyncio
async def test_trend_signal_insert_sets_expires_at(conn):
    row = await conn.fetchrow("""
        INSERT INTO trend_signals (source, topic, urgency_score, decay_half_life_hours)
        VALUES ('rss', 'test topic', 75, 48)
        RETURNING detected_at, expires_at;
    """)
    assert row["expires_at"] is not None
    delta = (row["expires_at"] - row["detected_at"]).total_seconds()
    assert 47 * 3600 < delta < 49 * 3600


@pytest.mark.asyncio
async def test_trend_insert_notifies_intel_event(conn):
    received: list[dict] = []

    async def listener():
        listen_conn = await asyncpg.connect(TEST_DSN)
        await listen_conn.add_listener(
            "intel_event",
            lambda c, pid, ch, payload: received.append(json.loads(payload)),
        )
        await asyncio.sleep(2.0)
        await listen_conn.close()

    task = asyncio.create_task(listener())
    await asyncio.sleep(0.2)

    await conn.execute("""
        INSERT INTO trend_signals (source, topic, urgency_score)
        VALUES ('rss', 'integration test topic', 60);
    """)

    await task
    assert any(p.get("event_type") == "trend_signal_detected" for p in received)


@pytest.mark.asyncio
async def test_dossier_upsert_unique_slug(conn):
    from datetime import datetime, timedelta, timezone

    expiry = datetime.now(timezone.utc) + timedelta(days=30)
    await conn.execute("""
        INSERT INTO research_dossiers (slug, title, topic_category, freshness_expiry)
        VALUES ('unique-slug', 'first', 'visa', $1);
    """, expiry)

    with pytest.raises(asyncpg.UniqueViolationError):  # type: ignore[union-attr]
        await conn.execute("""
            INSERT INTO research_dossiers (slug, title, topic_category, freshness_expiry)
            VALUES ('unique-slug', 'second', 'visa', $1);
        """, expiry)


@pytest.mark.asyncio
async def test_urgency_range_check_rejects_bad_values(conn):
    with pytest.raises(asyncpg.PostgresError):  # type: ignore[union-attr]
        await conn.execute("""
            INSERT INTO trend_signals (source, topic, urgency_score)
            VALUES ('rss', 'bad', 150);
        """)


@pytest.mark.asyncio
async def test_dossier_category_check_rejects_unknown(conn):
    from datetime import datetime, timedelta, timezone

    with pytest.raises(asyncpg.PostgresError):  # type: ignore[union-attr]
        await conn.execute(
            """
            INSERT INTO research_dossiers (slug, title, topic_category, freshness_expiry)
            VALUES ('bad-cat', 'x', 'gambling', $1);
            """,
            datetime.now(timezone.utc) + timedelta(days=30),
        )


@pytest.mark.asyncio
async def test_rollback_drops_all_four_tables(conn):
    await migration_113_intel_dossiers.rollback(conn)
    rows = await conn.fetch("""
        SELECT table_name FROM information_schema.tables
         WHERE table_schema = 'public'
           AND table_name IN (
               'trend_signals', 'research_dossiers',
               'dossier_reuses', 'dossier_refresh_log'
           );
    """)
    assert rows == []
    await migration_113_intel_dossiers.apply(conn)  # restore for fixture teardown
