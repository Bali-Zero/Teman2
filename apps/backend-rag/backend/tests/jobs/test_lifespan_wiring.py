"""Verify the runner start/stop lifecycle the lifespan will orchestrate.

This is a unit test of the JobsRunner's double-stop idempotency — the
actual lifespan wiring in app_factory.py is integration-tested via
the existing app startup smoke. Its behavior is:

  on _background_init():   runner = JobsRunner(...); await runner.start()
  on shutdown:             await runner.stop(grace_seconds=30)

We cannot fully spin up the FastAPI app here (heavy deps / psutil missing
in the jobs venv), so this test exercises the contract the wiring
depends on: runner.start() / runner.stop() / runner.stop() again is
safe and does not leak tasks.
"""
from __future__ import annotations

import asyncio

from backend.jobs.registry import Registry
from backend.jobs.runner import JobsRunner


async def test_runner_start_stop_stop_idempotent(pg_pool):
    reg = Registry()
    reg.freeze()
    runner = JobsRunner(
        pool=pg_pool, registry=reg, enabled_names=set(), tick_seconds=0.05,
    )
    await runner.start()
    await asyncio.sleep(0.1)
    await runner.stop(grace_seconds=2)
    # Second stop is a no-op, never raises.
    await runner.stop(grace_seconds=1)


async def test_runner_with_empty_allowlist_schedules_nothing_live(pg_pool):
    """Runner created with enabled_names=set() does NOT execute scheduled jobs.

    The allowlist gate lives in _dispatch_attempt (attempt==1 branch); manual
    kicks bypass it. Registered jobs can still be kicked via runner manually.
    """
    reg = Registry()

    async def handle(ctx):
        from backend.jobs.context import JobResult
        return JobResult(ok=True)

    reg.register(name="gated", cron="*/1 * * * * *", handler=handle)
    reg.freeze()

    runner = JobsRunner(pool=pg_pool, registry=reg, enabled_names=set(), tick_seconds=0.05)
    await runner.start()
    await asyncio.sleep(1.2)  # enough for >= 1 would-be tick
    await runner.stop(grace_seconds=2)

    from backend.jobs.models import JobRunRepository
    repo = JobRunRepository(pg_pool)
    rows = await repo.list_recent("gated", limit=10)
    # Every run must be status=skipped with the allowlist reason.
    for r in rows:
        assert r.status == "skipped", f"expected skipped, got {r.status}"
        assert "allowlist" in (r.meta.get("reason") or ""), r.meta
