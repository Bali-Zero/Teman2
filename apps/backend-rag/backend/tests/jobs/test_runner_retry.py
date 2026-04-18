"""Retry + timeout + orphan tests."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from backend.jobs.context import JobContext, JobResult
from backend.jobs.models import JobRunRepository
from backend.jobs.registry import Registry
from backend.jobs.retry import RetryPolicy, TransientError
from backend.jobs.runner import JobsRunner


async def test_transient_retries_then_succeeds(pg_pool):
    reg = Registry()
    attempts: list[int] = []

    async def flaky(ctx: JobContext) -> JobResult:
        attempts.append(ctx.attempt)
        if ctx.attempt < 3:
            raise TransientError("network hiccup")
        return JobResult(ok=True)

    reg.register(
        name="flaky", cron="*/1 * * * *", handler=flaky,
        retry_policy=RetryPolicy(max_attempts=3, backoff_seconds=(0.01, 0.01)),
    )
    reg.freeze()

    runner = JobsRunner(pool=pg_pool, registry=reg, enabled_names={"flaky"}, tick_seconds=0.01)
    tick = datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc)
    await runner.dispatch_with_retry(decl=reg.get("flaky"), scheduled_tick=tick, source="scheduled")

    assert attempts == [1, 2, 3]
    repo = JobRunRepository(pg_pool)
    rows = await repo.list_recent("flaky", limit=10)
    # exactly 3 rows, all same idempotency_key, statuses failed/failed/completed
    assert len(rows) == 3
    assert {r.attempt for r in rows} == {1, 2, 3}
    statuses_by_attempt = {r.attempt: r.status for r in rows}
    assert statuses_by_attempt[1] == "failed"
    assert statuses_by_attempt[2] == "failed"
    assert statuses_by_attempt[3] == "completed"
    assert len({r.idempotency_key for r in rows}) == 1


async def test_permanent_does_not_retry(pg_pool):
    reg = Registry()
    attempts: list[int] = []

    async def boom(ctx: JobContext) -> JobResult:
        attempts.append(ctx.attempt)
        raise ValueError("bad input")

    reg.register(name="boom", cron="*/1 * * * *", handler=boom)
    reg.freeze()

    runner = JobsRunner(pool=pg_pool, registry=reg, enabled_names={"boom"}, tick_seconds=0.01)
    tick = datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc)
    await runner.dispatch_with_retry(decl=reg.get("boom"), scheduled_tick=tick, source="scheduled")

    assert attempts == [1]
    repo = JobRunRepository(pg_pool)
    rows = await repo.list_recent("boom", limit=10)
    assert len(rows) == 1
    assert rows[0].status == "failed"


async def test_timeout_classified_as_transient(pg_pool):
    reg = Registry()

    async def slow(ctx: JobContext) -> JobResult:
        if ctx.attempt == 1:
            await asyncio.sleep(0.5)
        return JobResult(ok=True)

    reg.register(
        name="slow", cron="*/1 * * * *", handler=slow,
        timeout_seconds=0,
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=(0.01,)),
    )
    reg.freeze()

    runner = JobsRunner(pool=pg_pool, registry=reg, enabled_names={"slow"}, tick_seconds=0.01)
    tick = datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc)
    await runner.dispatch_with_retry(decl=reg.get("slow"), scheduled_tick=tick, source="scheduled")

    repo = JobRunRepository(pg_pool)
    rows = await repo.list_recent("slow", limit=10)
    assert len(rows) == 2
    assert rows[-1].attempt == 1 and rows[-1].status == "failed"
    assert rows[0].attempt == 2 and rows[0].status == "completed"


async def test_mark_orphans_on_startup(pg_pool):
    reg = Registry()
    reg.freeze()
    runner = JobsRunner(pool=pg_pool, registry=reg, enabled_names=set(), tick_seconds=0.01)

    repo = JobRunRepository(pg_pool)
    tick = datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc)
    run = await repo.create_pending("orph", tick, "k", 1)
    await repo.mark_running(run.id)
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE job_runs SET started_at = now() - interval '10 minutes' WHERE id=$1",
            run.id,
        )

    recovered = await runner.recover_orphans(grace_seconds=60)
    assert recovered == 1
    row = await repo.get(run.id)
    assert row.status == "failed"
    assert row.error == "orphaned"
