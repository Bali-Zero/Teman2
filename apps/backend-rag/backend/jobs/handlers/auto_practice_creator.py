"""Runner wrapper around the existing auto-practice creator job.

Domain logic: backend/jobs/auto_practice_creator.py
  async def run_auto_practice_creator(db_pool) -> dict

We import that function and wrap it in the JobContext protocol.
Schedule matches the existing Air crontab entry (07:30 WITA).

Note: The domain module is imported lazily inside handle() because it pulls in
structlog and prometheus_client at module level — those are runtime deps that
are not available in the lightweight test venv.  Registration (register_job)
still happens eagerly at package-import time.
"""
from __future__ import annotations

from backend.jobs.context import JobContext, JobResult
from backend.jobs.registry import register_job


async def handle(ctx: JobContext) -> JobResult:
    if ctx.db_pool is None:
        raise RuntimeError(
            "auto-practice-creator handler requires ctx.db_pool; "
            "runner must supply it."
        )
    # Lazy import: domain module uses structlog/prometheus at module level.
    from backend.jobs.auto_practice_creator import run_auto_practice_creator  # noqa: PLC0415

    stats = await run_auto_practice_creator(ctx.db_pool)
    ctx.logger.info("auto_practice_creator_done", extra={"stats": stats})
    return JobResult(ok=True, meta={"stats": stats or {}})


register_job(
    name="auto-practice-creator",
    cron="30 7 * * *",          # 07:30 WITA — matches existing Air cron entry
    handler=handle,
    timezone="Asia/Makassar",
    timeout_seconds=300,
)
