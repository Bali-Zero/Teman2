"""Tests for JobRunRepository."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.jobs.models import JobRun, JobRunRepository


async def _repo(pg_pool) -> JobRunRepository:
    return JobRunRepository(pg_pool)


async def test_create_pending_returns_row(pg_pool):
    repo = await _repo(pg_pool)
    tick = datetime(2026, 4, 18, 7, 30, tzinfo=timezone.utc)
    run = await repo.create_pending(
        job_name="a", scheduled_tick=tick,
        idempotency_key="a:tick:2026-04-18T07:30:00+00:00", attempt=1,
    )
    assert isinstance(run, JobRun)
    assert run.job_name == "a"
    assert run.status == "pending"
    assert run.attempt == 1


async def test_mark_running_then_finish_completed(pg_pool):
    repo = await _repo(pg_pool)
    tick = datetime(2026, 4, 18, 7, 30, tzinfo=timezone.utc)
    run = await repo.create_pending("a", tick, "k1", 1)

    await repo.mark_running(run.id)
    started = await repo.get(run.id)
    assert started.status == "running"
    assert started.started_at is not None

    await repo.finish(run.id, status="completed", error=None, cost_cents=42, meta={"x": 1})
    done = await repo.get(run.id)
    assert done.status == "completed"
    assert done.cost_cents == 42
    assert done.meta == {"x": 1}
    assert done.finished_at is not None


async def test_find_by_idempotency_key_completed(pg_pool):
    repo = await _repo(pg_pool)
    tick = datetime(2026, 4, 18, 7, 30, tzinfo=timezone.utc)
    run = await repo.create_pending("a", tick, "dup", 1)
    await repo.mark_running(run.id)
    await repo.finish(run.id, status="completed", error=None, cost_cents=0, meta={})

    found = await repo.find_completed_by_idempotency_key("dup")
    assert found is not None
    assert found.id == run.id


async def test_find_by_idempotency_key_failed_returns_none(pg_pool):
    repo = await _repo(pg_pool)
    tick = datetime(2026, 4, 18, 7, 30, tzinfo=timezone.utc)
    run = await repo.create_pending("a", tick, "f1", 1)
    await repo.mark_running(run.id)
    await repo.finish(run.id, status="failed", error="boom", cost_cents=0, meta={})
    assert await repo.find_completed_by_idempotency_key("f1") is None


async def test_list_recent(pg_pool):
    repo = await _repo(pg_pool)
    base = datetime(2026, 4, 18, 7, 30, tzinfo=timezone.utc)
    for i in range(3):
        r = await repo.create_pending("a", base + timedelta(hours=i), f"k{i}", 1)
        await repo.mark_running(r.id)
        await repo.finish(r.id, status="completed", error=None, cost_cents=0, meta={})

    recent = await repo.list_recent("a", limit=2)
    assert len(recent) == 2
    assert recent[0].scheduled_tick > recent[1].scheduled_tick


async def test_mark_orphans(pg_pool):
    repo = await _repo(pg_pool)
    tick = datetime(2026, 4, 18, 7, 30, tzinfo=timezone.utc)
    run = await repo.create_pending("a", tick, "orphan", 1)
    await repo.mark_running(run.id)
    # Force started_at backwards
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE job_runs SET started_at = now() - interval '1 hour' WHERE id=$1",
            run.id,
        )
    orphaned = await repo.mark_orphans(older_than=datetime.now(timezone.utc) - timedelta(minutes=5))
    assert orphaned == 1
    row = await repo.get(run.id)
    assert row.status == "failed"
    assert row.error == "orphaned"
