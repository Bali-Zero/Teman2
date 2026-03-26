"""
Workflow Job Queue — PostgreSQL SKIP LOCKED pattern.

Provides resumable MCP workflow chains on Fly.io auto_stop machines.
No Redis, no Celery — PostgreSQL only.

Architecture (from NB-9 research 2026-03-27):
- SKIP LOCKED + visibility_at timeout for atomic dequeue
- Heartbeat every 2 min prevents parallel execution on LLM stall
- LangGraph AsyncPostgresSaver for step-level checkpoint/resume
- Pointer State: store only URI refs in LangGraph state (prevents TOAST bloat)
"""

import asyncio
import logging
import uuid
from typing import Any

import asyncpg

logger = logging.getLogger("zantara.workflow.queue")

# Visibility timeout must be > kill_timeout (300s = 5min) + max chain duration (8min)
VISIBILITY_TIMEOUT_MINUTES = 15
HEARTBEAT_INTERVAL_SECONDS = 120  # 2 min heartbeat to prevent parallel execution
WORKER_POLL_INTERVAL_SECONDS = 5
MAX_RETRIES = 3


async def enqueue_workflow(
    db_pool: asyncpg.Pool,
    chain_id: str,
    payload: dict[str, Any],
    thread_id: str | None = None,
) -> str:
    """
    Enqueue a workflow job. Returns job_id.
    thread_id is the LangGraph thread_id for resumable checkpointing.
    """
    job_id = str(uuid.uuid4())
    if thread_id is None:
        thread_id = f"{chain_id}:{job_id}"

    await db_pool.execute(
        """
        INSERT INTO workflow_jobs (id, chain_id, thread_id, payload)
        VALUES ($1, $2, $3, $4)
        """,
        uuid.UUID(job_id),
        chain_id,
        thread_id,
        payload,
    )
    logger.info(f"Enqueued workflow job {job_id} chain={chain_id} thread={thread_id}")
    return job_id


async def _dequeue_one(conn: asyncpg.Connection) -> dict[str, Any] | None:
    """
    Atomically claim one pending job using SKIP LOCKED.
    Sets visible_at = now + VISIBILITY_TIMEOUT to prevent parallel execution.
    """
    dequeue_sql = f"""
        WITH claimed AS (
            SELECT id FROM workflow_jobs
            WHERE status = 'pending'
              AND visible_at <= NOW()
            ORDER BY visible_at
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        UPDATE workflow_jobs
        SET status     = 'in_progress',
            visible_at = NOW() + INTERVAL '{VISIBILITY_TIMEOUT_MINUTES} minutes',
            retry_count = retry_count + 1
        WHERE id = (SELECT id FROM claimed)
        RETURNING id, chain_id, thread_id, payload, retry_count
        """
    row = await conn.fetchrow(dequeue_sql)
    return dict(row) if row else None


async def _heartbeat(conn: asyncpg.Connection, job_id: uuid.UUID) -> None:
    """
    Extend visibility_at to prevent timeout expiry during long LLM calls.
    Called every HEARTBEAT_INTERVAL_SECONDS while job is in_progress.
    """
    heartbeat_sql = f"""
        UPDATE workflow_jobs
        SET visible_at = NOW() + INTERVAL '{VISIBILITY_TIMEOUT_MINUTES} minutes'
        WHERE id = $1 AND status = 'in_progress'
        """
    await conn.execute(heartbeat_sql, job_id)


async def _ack_job(conn: asyncpg.Connection, job_id: uuid.UUID) -> None:
    await conn.execute(
        "UPDATE workflow_jobs SET status='done' WHERE id=$1",
        job_id,
    )


async def _fail_job(
    conn: asyncpg.Connection, job_id: uuid.UUID, error: str, retry_count: int
) -> None:
    new_status = "failed" if retry_count >= MAX_RETRIES else "pending"
    # If retrying: reset visible_at to now + 1 min backoff
    await conn.execute(
        """
        UPDATE workflow_jobs
        SET status    = $2,
            error_msg = $3,
            visible_at = CASE WHEN $2 = 'pending' THEN NOW() + INTERVAL '1 minute'
                              ELSE visible_at END
        WHERE id = $1
        """,
        job_id,
        new_status,
        error[:1000],
    )


async def _execute_job(job: dict[str, Any], app_state: Any) -> None:
    """
    Dispatch job to the appropriate chain executor.
    Lazy import to avoid circular deps at module load time.
    """
    chain_id = job["chain_id"]
    thread_id = job["thread_id"]
    payload = job["payload"]

    logger.info(f"Executing chain={chain_id} thread={thread_id}")

    from backend.services.workflow.executor import execute_chain

    await execute_chain(
        chain_id=chain_id,
        thread_id=thread_id,
        payload=payload,
        app_state=app_state,
    )


async def _process_job(
    job: dict[str, Any],
    db_pool: asyncpg.Pool,
    app_state: Any,
) -> None:
    """Process a single job with heartbeat and error handling."""
    job_id = job["id"]
    retry_count = job["retry_count"]

    heartbeat_task: asyncio.Task | None = None

    async def _run_heartbeat() -> None:
        async with db_pool.acquire() as hb_conn:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
                try:
                    await _heartbeat(hb_conn, job_id)
                    logger.debug(f"Heartbeat job {job_id}")
                except Exception as e:
                    logger.warning(f"Heartbeat failed for {job_id}: {e}")

    try:
        heartbeat_task = asyncio.create_task(_run_heartbeat())
        await _execute_job(job, app_state)

        async with db_pool.acquire() as conn:
            await _ack_job(conn, job_id)
        logger.info(f"Job {job_id} completed OK")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        async with db_pool.acquire() as conn:
            await _fail_job(conn, job_id, str(e), retry_count)
    finally:
        if heartbeat_task and not heartbeat_task.done():
            heartbeat_task.cancel()
            with asyncio.suppress(asyncio.CancelledError):
                await heartbeat_task


async def run_worker(db_pool: asyncpg.Pool, app_state: Any) -> None:
    """
    Background worker loop. Runs inside app lifespan via asyncio.create_task().
    Polls for pending jobs every WORKER_POLL_INTERVAL_SECONDS.
    """
    logger.info("Workflow queue worker started")
    while True:
        try:
            async with db_pool.acquire() as conn:
                async with conn.transaction():
                    job = await _dequeue_one(conn)

            if job:
                asyncio.create_task(_process_job(job, db_pool, app_state))
            else:
                await asyncio.sleep(WORKER_POLL_INTERVAL_SECONDS)

        except asyncio.CancelledError:
            logger.info("Workflow queue worker shutting down")
            break
        except Exception as e:
            logger.error(f"Worker loop error: {e}", exc_info=True)
            await asyncio.sleep(WORKER_POLL_INTERVAL_SECONDS)
