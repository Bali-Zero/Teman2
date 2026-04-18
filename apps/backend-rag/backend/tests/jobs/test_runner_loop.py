"""Tick loop + start/stop tests."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from backend.jobs.context import JobContext, JobResult
from backend.jobs.models import JobRunRepository
from backend.jobs.registry import Registry
from backend.jobs.runner import JobsRunner


async def test_tick_loop_fires_every_tick(pg_pool):
    reg = Registry()
    fires = 0

    async def handle(ctx: JobContext) -> JobResult:
        nonlocal fires
        fires += 1
        return JobResult(ok=True)

    # Every second (croniter 6-field form). Second-granularity is supported.
    reg.register(name="fast", cron="*/1 * * * * *", handler=handle)
    reg.freeze()

    runner = JobsRunner(
        pool=pg_pool, registry=reg, enabled_names={"fast"}, tick_seconds=0.1,
    )
    await runner.start()
    await asyncio.sleep(2.5)  # allow ~2 fires
    await runner.stop(grace_seconds=2)

    assert fires >= 1, f"expected at least 1 fire, got {fires}"
    repo = JobRunRepository(pg_pool)
    rows = await repo.list_recent("fast", limit=10)
    assert any(r.status == "completed" for r in rows)


async def test_stop_finishes_in_flight(pg_pool):
    reg = Registry()
    entered = asyncio.Event()

    async def slow(ctx: JobContext) -> JobResult:
        entered.set()
        await asyncio.sleep(0.3)
        return JobResult(ok=True)

    reg.register(name="slow", cron="*/1 * * * * *", handler=slow, timeout_seconds=5)
    reg.freeze()

    runner = JobsRunner(pool=pg_pool, registry=reg, enabled_names={"slow"}, tick_seconds=0.05)
    await runner.start()
    await entered.wait()
    await runner.stop(grace_seconds=2)

    repo = JobRunRepository(pg_pool)
    rows = await repo.list_recent("slow", limit=5)
    assert rows, "expected at least one slow run row"
    assert rows[0].status in ("completed", "failed")
