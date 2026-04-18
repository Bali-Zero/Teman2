"""Dispatch happy-path test for JobsRunner."""
#
# NOTE: The "advisory lock not acquired" skip path is NOT tested here.
# That scenario requires two concurrent runners contending on the same
# tick, which is a concurrent-execution test better landed alongside
# Task 10/11 (retry + tick loop). When that arrives, verify:
#   - Dispatch B (lock contention) returns early with status='skipped',
#     meta.reason='advisory lock not acquired'.
#   - Dispatch A (lock holder) runs to completion unaffected.
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from backend.jobs.context import JobContext, JobResult
from backend.jobs.models import JobRunRepository
from backend.jobs.registry import Registry
from backend.jobs.runner import JobsRunner


async def test_dispatch_happy_path(pg_pool):
    """Force a dispatch, observe pending->running->completed row."""
    reg = Registry()
    called: list[JobContext] = []

    async def handle(ctx: JobContext) -> JobResult:
        called.append(ctx)
        return JobResult(ok=True, meta={"processed": 1})

    reg.register(name="t", cron="*/1 * * * *", handler=handle)
    reg.freeze()

    runner = JobsRunner(
        pool=pg_pool, registry=reg, enabled_names={"t"}, tick_seconds=0.05,
    )

    tick = datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc)
    run_id = await runner.dispatch_once(decl=reg.get("t"), scheduled_tick=tick, source="scheduled")
    assert run_id is not None

    repo = JobRunRepository(pg_pool)
    row = await repo.get(run_id)
    assert row.status == "completed"
    assert row.meta.get("processed") == 1
    assert len(called) == 1
    assert called[0].job_name == "t"
    assert called[0].attempt == 1


async def test_dispatch_skipped_when_not_in_allowlist(pg_pool):
    reg = Registry()

    async def handle(ctx: JobContext) -> JobResult:
        return JobResult()

    reg.register(name="t", cron="*/1 * * * *", handler=handle)
    reg.freeze()

    runner = JobsRunner(
        pool=pg_pool, registry=reg, enabled_names=set(), tick_seconds=0.05,
    )

    tick = datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc)
    run_id = await runner.dispatch_once(decl=reg.get("t"), scheduled_tick=tick, source="scheduled")

    repo = JobRunRepository(pg_pool)
    row = await repo.get(run_id)
    assert row.status == "skipped"
    assert "allowlist" in (row.meta.get("reason") or "")


async def test_manual_source_bypasses_allowlist(pg_pool):
    reg = Registry()

    async def handle(ctx: JobContext) -> JobResult:
        return JobResult()

    reg.register(name="t", cron="*/1 * * * *", handler=handle)
    reg.freeze()

    runner = JobsRunner(
        pool=pg_pool, registry=reg, enabled_names=set(), tick_seconds=0.05,
    )

    tick = datetime(2026, 4, 18, 0, 0, tzinfo=timezone.utc)
    run_id = await runner.dispatch_once(decl=reg.get("t"), scheduled_tick=tick, source="manual")

    repo = JobRunRepository(pg_pool)
    row = await repo.get(run_id)
    assert row.status == "completed"
