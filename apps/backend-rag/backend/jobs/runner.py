"""JobsRunner — in-process async scheduler.

This is the minimal dispatch. Retry, timeout, and the tick loop come in
later tasks; for now we expose dispatch_once so we can TDD the surrounding
logic deterministically.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

import asyncpg

from backend.jobs.context import CostMeter, JobContext, JobResult
from backend.jobs.locks import advisory_lock
from backend.jobs.middleware import (
    CostCap,
    OAuthGuard,
    detect_claude_cli_available,
)
from backend.jobs.models import JobRunRepository
from backend.jobs.registry import JobDeclaration, Registry
from backend.jobs.retry import CostExceeded, OAuthViolation

logger = logging.getLogger(__name__)


def default_idempotency_key(job_name: str, scheduled_tick: datetime) -> str:
    return f"{job_name}:tick:{scheduled_tick.isoformat()}"


class JobsRunner:
    def __init__(
        self,
        pool: asyncpg.Pool,
        registry: Registry,
        enabled_names: set[str],
        tick_seconds: float = 10.0,
        cost_cap_cents: int = 100,
    ) -> None:
        self._pool = pool
        self._registry = registry
        self._enabled = set(enabled_names)
        self._tick_seconds = tick_seconds
        self._repo = JobRunRepository(pool)
        self._oauth = OAuthGuard()
        self._cost_cap = CostCap(limit_cents=cost_cap_cents)
        self._claude_cli = detect_claude_cli_available()

    async def dispatch_once(
        self,
        decl: JobDeclaration,
        scheduled_tick: datetime,
        source: Literal["scheduled", "manual"],
    ) -> int:
        """Run one dispatch of `decl` at `scheduled_tick`. Returns job_run id."""
        # enabled-allowlist check (manual bypasses it)
        if source == "scheduled" and decl.name not in self._enabled:
            run = await self._repo.create_pending(
                decl.name, scheduled_tick,
                default_idempotency_key(decl.name, scheduled_tick), 1,
            )
            await self._repo.finish(
                run.id, status="skipped", error=None, cost_cents=0,
                meta={"reason": "not in JOBS_RUNNER_ENABLED allowlist"},
            )
            return run.id

        # idempotency check (tick-based default, handler override)
        meter = CostMeter()
        # probe_ctx is intentional: run_id=0 because no DB row exists yet.
        # Handlers must not reference ctx.run_id inside idempotency_key overrides.
        probe_ctx = JobContext(
            job_name=decl.name, scheduled_tick=scheduled_tick,
            attempt=1, run_id=0,
            db_pool=self._pool,
            logger=logger.getChild(decl.name),
            meter=meter, claude_cli_available=self._claude_cli,
            source=source,
        )
        if decl.idempotency_key is not None:
            key = decl.idempotency_key(probe_ctx)
        else:
            key = default_idempotency_key(decl.name, scheduled_tick)

        existing = await self._repo.find_completed_by_idempotency_key(key)
        if existing is not None:
            run = await self._repo.create_pending(
                decl.name, scheduled_tick, key, 1,
            )
            await self._repo.finish(
                run.id, status="skipped", error=None, cost_cents=0,
                meta={"reason": "idempotent: already completed", "prior_run_id": existing.id},
            )
            return run.id

        # advisory lock + execute
        async with self._pool.acquire() as conn:
            async with advisory_lock(conn, f"job:{decl.name}:{scheduled_tick.isoformat()}") as got:
                if not got:
                    run = await self._repo.create_pending(
                        decl.name, scheduled_tick, key, 1,
                    )
                    await self._repo.finish(
                        run.id, status="skipped", error=None, cost_cents=0,
                        meta={"reason": "advisory lock not acquired"},
                    )
                    return run.id

                run = await self._repo.create_pending(decl.name, scheduled_tick, key, 1)
                await self._repo.mark_running(run.id)

                ctx = JobContext(
                    job_name=decl.name, scheduled_tick=scheduled_tick,
                    attempt=1, run_id=run.id,
                    db_pool=self._pool,
                    logger=logger.getChild(decl.name),
                    meter=meter, claude_cli_available=self._claude_cli,
                    source=source,
                )

                try:
                    # middleware pre-checks
                    if OAuthGuard.NAME not in decl.skip_middleware:
                        await self._oauth.check(ctx)

                    result = await decl.handler(ctx)

                    # post-handler cost check
                    if CostCap.NAME not in decl.skip_middleware:
                        self._cost_cap.check(ctx)

                    base_meta = result.meta if isinstance(result, JobResult) else {}
                    meta = {**base_meta, "source": source}
                    await self._repo.finish(
                        run.id, status="completed", error=None,
                        cost_cents=ctx.meter.total_cents, meta=meta,
                    )
                    return run.id

                except OAuthViolation as exc:
                    await self._repo.finish(
                        run.id, status="failed",
                        error=f"OAuthViolation: {exc}",
                        cost_cents=ctx.meter.total_cents,
                        meta={"source": source, "error_class": "OAuthViolation"},
                    )
                    raise

                except CostExceeded as exc:
                    await self._repo.finish(
                        run.id, status="cost_exceeded",
                        error=f"CostExceeded: {exc}",
                        cost_cents=ctx.meter.total_cents,
                        meta={"source": source, "error_class": "CostExceeded"},
                    )
                    return run.id

                except Exception as exc:  # noqa: BLE001
                    await self._repo.finish(
                        run.id, status="failed",
                        error=f"{type(exc).__name__}: {exc}",
                        cost_cents=ctx.meter.total_cents,
                        meta={"source": source, "error_class": type(exc).__name__},
                    )
                    raise
