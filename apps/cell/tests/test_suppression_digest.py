from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from cell.slow.suppression_digest import (
    DIGEST_ACTION,
    build_suppression_digest,
    run_suppression_digest,
    should_run_suppression_digest,
)


def _pool_with_rows(
    rows: list[dict],
    *,
    recent_digest: dict | None = None,
) -> tuple[MagicMock, MagicMock]:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=recent_digest)
    conn.fetch = AsyncMock(return_value=rows)
    conn.execute = AsyncMock()

    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_ctx)
    return pool, conn


@pytest.mark.asyncio
async def test_suppression_digest_emits_once_for_active_sustained_headline() -> None:
    now = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)
    headline = "backup stale 113h (fly_pg_backup.sql.gz)"
    pool, conn = _pool_with_rows([
        {
            "message": headline,
            "suppressed_count": 25,
            "first_seen_at": now - timedelta(hours=3),
            "last_seen_at": now - timedelta(minutes=5),
        }
    ])
    emitter = AsyncMock()

    result = await run_suppression_digest(
        pool,
        current_headline=headline,
        health_status="red",
        pulse_number=60,
        emitter=emitter,
        now=now,
    )

    assert result.should_emit is True
    assert len(result.groups) == 1
    assert "25 suppressed alert" in result.text
    assert headline in result.text
    assert "active for 3h" in result.text
    emitter.assert_awaited_once_with(result.text)
    conn.execute.assert_awaited_once()
    assert conn.execute.call_args.args[2] == DIGEST_ACTION
    assert conn.execute.call_args.args[4] == "red"
    assert conn.execute.call_args.args[5] == 60


@pytest.mark.asyncio
async def test_suppression_digest_respects_digest_cooldown() -> None:
    now = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)
    pool, conn = _pool_with_rows(
        [],
        recent_digest={"created_at": now - timedelta(hours=1)},
    )

    result = await build_suppression_digest(
        pool,
        current_headline="backup stale 113h",
        now=now,
    )

    assert result.should_emit is False
    assert result.reason == "cooldown"
    conn.fetch.assert_not_awaited()
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_suppression_digest_skips_when_current_headline_is_empty() -> None:
    pool, conn = _pool_with_rows([])

    result = await build_suppression_digest(pool, current_headline="")

    assert result.should_emit is False
    assert result.reason == "no-active-headline"
    conn.fetchrow.assert_not_awaited()
    conn.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_suppression_digest_filters_to_active_headline_parts() -> None:
    now = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)
    backup = "backup stale 3h"
    cron = "cron blocked: failed=a"
    outbox = "outbox lag 500 events"
    pool, _conn = _pool_with_rows([
        {
            "message": backup,
            "suppressed_count": 10,
            "first_seen_at": now - timedelta(hours=4),
            "last_seen_at": now,
        },
        {
            "message": cron,
            "suppressed_count": 5,
            "first_seen_at": now - timedelta(hours=3),
            "last_seen_at": now,
        },
        {
            "message": outbox,
            "suppressed_count": 20,
            "first_seen_at": now - timedelta(hours=5),
            "last_seen_at": now,
        },
    ])

    result = await build_suppression_digest(
        pool,
        current_headline=f"{backup}; {cron}",
        now=now,
    )

    assert result.should_emit is True
    assert [group.message for group in result.groups] == [backup, cron]
    assert outbox not in result.text


def test_should_run_suppression_digest_is_hourly_and_kill_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CELL_SUPPRESSION_DIGEST_ENABLED", raising=False)
    assert should_run_suppression_digest(0) is False
    assert should_run_suppression_digest(59) is False
    assert should_run_suppression_digest(60) is True

    monkeypatch.setenv("CELL_SUPPRESSION_DIGEST_ENABLED", "false")
    assert should_run_suppression_digest(60) is False
