"""Runner wrapper around conversation_cleanup (daily, 04:15 WITA).

Domain logic: backend/jobs/conversation_cleanup.py
  async def cleanup_conversations(retention_days=30, anonymize_days=7) -> dict

Fetches its own db_pool internally, so ctx.db_pool is not passed through.
Staggered 15 min before the KG Curiosity cadence to avoid 04:00 pile-up
(per S10 Cron staggering guidance).

Note: The domain module is imported lazily inside handle() because it pulls in
the full app-stack (backend.app.core.database → pydantic / fastapi etc.) at
module level — those are not available in the lightweight test venv.
Registration (register_job) still happens eagerly at package-import time.
"""
from __future__ import annotations

from backend.jobs.context import JobContext, JobResult
from backend.jobs.registry import register_job


async def handle(ctx: JobContext) -> JobResult:
    # Lazy import: domain module imports backend.app.core.database at module level.
    from backend.jobs.conversation_cleanup import cleanup_conversations  # noqa: PLC0415

    stats = await cleanup_conversations()
    ctx.logger.info("conversation_cleanup_done", extra={"stats": stats})
    return JobResult(ok=True, meta={"stats": stats or {}})


register_job(
    name="conversation-cleanup",
    cron="15 4 * * *",          # 04:15 WITA
    handler=handle,
    timezone="Asia/Makassar",
    timeout_seconds=600,
)
