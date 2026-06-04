"""Unified document-intake worker orchestrator (FASE 2).

Forks the SKIP-LOCKED claim/lease/heartbeat/retry/DLQ pattern from
`backend.services.workflow.queue` and adapts it to the unified `intake_queue`
(migration 206). PII stays 100% local (Law 2 / UU-PDP): no cloud LLM, no OCR
here (that's FASE 3) — the per-stage handlers are STUB passthroughs that emit
an `intake_stage_metrics` row and advance the job's status.

Stage machine (all stub, all claimable statuses per idx_iq_claimable):

    pending --classify--> processing --ocr--> ocr --extract--> classified
        --validate--> extracted --route--> done

Each claim advances EXACTLY ONE stage, then re-enqueues the row (next_visible_at
= now) so a sibling worker can pick up the next stage. Terminal states:
  - 'done'  : routed through all stub stages.
  - 'dead'  : retry budget exhausted (attempts >= max_attempts). TERMINAL —
              a 'dead' job is NEVER claimable again (W61 anti-storm: terminal
              stays terminal, no re-add to the claimable set).

Reuses the caller's persistent asyncpg pool (Golden Rule #10). ZERO CRM writes.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import socket
from dataclasses import dataclass
from typing import Awaitable, Callable

import asyncpg

logger = logging.getLogger("zantara.intake.worker")

# --- Claimable status set (mirrors idx_iq_claimable in migration 206). ---
CLAIMABLE_STATUSES: tuple[str, ...] = (
    "pending",
    "processing",
    "ocr",
    "classified",
    "extracted",
)

# --- Stub stage machine: status -> (stage_name, next_status). ---
# Ordered passthrough; terminal next_status='done' is NOT claimable.
STAGE_TRANSITIONS: dict[str, tuple[str, str]] = {
    "pending": ("classify", "processing"),
    "processing": ("ocr", "ocr"),
    "ocr": ("extract", "classified"),
    "classified": ("validate", "extracted"),
    "extracted": ("route", "done"),
}

# --- Defaults (overridable via env / constructor for tests). ---
DEFAULT_LEASE_TTL_SECONDS = 900  # 15 min — must exceed slowest stub stage.
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 120  # 2 min, like workflow/queue.
DEFAULT_POLL_INTERVAL_SECONDS = 2
DEFAULT_BASE_BACKOFF_SECONDS = 2.0  # exponential: base * 2**(attempts-1).
DEFAULT_MAX_BACKOFF_SECONDS = 600.0

# Number of consecutive DB-connection failures before the worker exits 0
# (anti-storm: let launchd respawn slowly via ThrottleInterval, do not flap).
DB_FAILURE_EXIT_THRESHOLD = 10

# --- PII masking for last_error (Law 2). Never persist raw doc content. ---
_PII_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b\d{16}\b"), "[KTP/CARD]"),  # 16-digit KTP / card.
    (re.compile(r"\b[A-Z]\d{7,8}\b"), "[PASSPORT]"),  # passport-ish.
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL]"),
    (re.compile(r"\b\+?\d[\d\s().-]{8,}\d\b"), "[PHONE]"),
)


def mask_pii(text: str, *, max_len: int = 1000) -> str:
    """Best-effort PII redaction for error strings persisted to last_error."""
    masked = text
    for pattern, repl in _PII_PATTERNS:
        masked = pattern.sub(repl, masked)
    return masked[:max_len]


# Alert hook: pluggable so the worker never hard-couples to a cloud channel.
# Default logs locally only (Law 2). Production can inject a Telegram callable.
AlertFn = Callable[[str], Awaitable[None]]


async def _default_alert(message: str) -> None:
    logger.error("INTAKE-ALERT %s", message)


@dataclass
class WorkerConfig:
    lease_ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS
    heartbeat_interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS
    base_backoff_seconds: float = DEFAULT_BASE_BACKOFF_SECONDS
    max_backoff_seconds: float = DEFAULT_MAX_BACKOFF_SECONDS

    @classmethod
    def from_env(cls) -> "WorkerConfig":
        return cls(
            lease_ttl_seconds=int(
                os.getenv("INTAKE_LEASE_TTL_SECONDS", DEFAULT_LEASE_TTL_SECONDS)
            ),
            heartbeat_interval_seconds=float(
                os.getenv(
                    "INTAKE_HEARTBEAT_INTERVAL_SECONDS",
                    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
                )
            ),
            poll_interval_seconds=float(
                os.getenv("INTAKE_POLL_INTERVAL_SECONDS", DEFAULT_POLL_INTERVAL_SECONDS)
            ),
            base_backoff_seconds=float(
                os.getenv("INTAKE_BASE_BACKOFF_SECONDS", DEFAULT_BASE_BACKOFF_SECONDS)
            ),
            max_backoff_seconds=float(
                os.getenv("INTAKE_MAX_BACKOFF_SECONDS", DEFAULT_MAX_BACKOFF_SECONDS)
            ),
        )


def make_worker_id() -> str:
    """Stable-ish per-process worker identity for lease_owner."""
    return f"{socket.gethostname()}:{os.getpid()}"


# --- Stub stage handler. Override via StageRunner for tests (poison-pill). ---
StageHandler = Callable[[dict, str], Awaitable[dict]]


async def _stub_stage(job: dict, stage: str) -> dict:
    """STUB passthrough stage: no OCR, no LLM. Returns a fixture dict.

    The returned dict is merged into stage_output[stage]. FASE 3 replaces this
    with real OCR/classify/extract/validate/route handlers.
    """
    return {"stub": True, "stage": stage, "queue_id": job["id"]}


class IntakeWorker:
    """Single-process intake worker: claim -> run one stub stage -> advance."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        config: WorkerConfig | None = None,
        worker_id: str | None = None,
        stage_handler: StageHandler | None = None,
        alert_fn: AlertFn | None = None,
    ) -> None:
        self.pool = pool
        self.config = config or WorkerConfig()
        self.worker_id = worker_id or make_worker_id()
        self.stage_handler = stage_handler or _stub_stage
        self.alert_fn = alert_fn or _default_alert
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def _heartbeat(self, job_id: int) -> None:
        """Extend the lease while a stage runs (only if WE still own it)."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE intake_queue
                SET lease_expires_at = now() + make_interval(secs => $2)
                WHERE id = $1 AND lease_owner = $3 AND status = 'processing'
                """,
                job_id,
                self.config.lease_ttl_seconds,
                self.worker_id,
            )

    async def _record_metric(
        self,
        conn: asyncpg.Connection,
        queue_id: int,
        stage: str,
        latency_ms: int,
        ok: bool,
    ) -> None:
        await conn.execute(
            """
            INSERT INTO intake_stage_metrics
                (queue_id, stage, latency_ms, confidence, model, ok)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            queue_id,
            stage,
            latency_ms,
            1.0 if ok else 0.0,
            "stub-passthrough",
            ok,
        )

    async def _advance(
        self,
        job_id: int,
        next_status: str,
        stage: str,
        stage_payload: dict,
    ) -> None:
        """On stage success: release lease, set next_status, re-enqueue.

        next_status='done' is terminal-success and NOT in the claimable set,
        so the row stops circulating. attempts is left as-is (success path).
        stage_output is merged (jsonb || ) so prior stages' output is kept.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE intake_queue
                    SET status           = $2,
                        stage            = $3,
                        lease_owner      = NULL,
                        lease_expires_at = NULL,
                        next_visible_at  = now(),
                        stage_output     = stage_output || $4::jsonb
                    WHERE id = $1 AND lease_owner = $5
                    """,
                    job_id,
                    next_status,
                    stage,
                    json.dumps({stage: stage_payload}),
                    self.worker_id,
                )

    async def _fail(
        self,
        job_id: int,
        stage: str,
        attempts: int,
        max_attempts: int,
        error: str,
    ) -> bool:
        """On stage failure: bump attempts; retry with backoff OR go 'dead'.

        Returns True iff the job was moved to terminal 'dead' (alert needed).

        W61 anti-storm: 'dead' is terminal and NOT claimable. We only ever
        write 'dead' here; a dead row is never re-added to the claimable set.
        Exponential backoff on retry: base * 2**(attempts-1), capped.
        """
        new_attempts = attempts + 1
        masked = mask_pii(error)

        if new_attempts >= max_attempts:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE intake_queue
                    SET status           = 'dead',
                        stage            = $2,
                        attempts         = $3,
                        last_error       = $4,
                        lease_owner      = NULL,
                        lease_expires_at = NULL
                    WHERE id = $1 AND lease_owner = $5
                    """,
                    job_id,
                    stage,
                    new_attempts,
                    masked,
                    self.worker_id,
                )
            return True

        backoff = min(
            self.config.base_backoff_seconds * (2 ** (new_attempts - 1)),
            self.config.max_backoff_seconds,
        )
        # Re-enqueue at the SAME claimable status the job had before this stage,
        # so it retries the failed stage. We stored the inbound status as 'stage'
        # context; simplest correct choice: put it back to the status that maps
        # to this stage. We reverse-map stage -> inbound status.
        inbound_status = _STAGE_TO_INBOUND_STATUS[stage]
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE intake_queue
                SET status           = $2,
                    stage            = $3,
                    attempts         = $4,
                    last_error       = $5,
                    lease_owner      = NULL,
                    lease_expires_at = NULL,
                    next_visible_at  = now() + make_interval(secs => $6)
                WHERE id = $1 AND lease_owner = $7
                """,
                job_id,
                inbound_status,
                stage,
                new_attempts,
                masked,
                float(backoff),
                self.worker_id,
            )
        return False

    async def _process_one(self, job: dict) -> None:
        """Run exactly one stub stage for a claimed job."""
        job_id = job["id"]
        # _claim_with_inbound flipped status to 'processing' but carried out the
        # PRE-claim status, which tells us which stage to run.
        inbound = job["_inbound_status"]
        if inbound not in STAGE_TRANSITIONS:
            logger.warning("job %s inbound status %s has no stage; skipping", job_id, inbound)
            return
        stage, next_status = STAGE_TRANSITIONS[inbound]

        hb_task = asyncio.create_task(self._heartbeat_loop(job_id))
        loop = asyncio.get_event_loop()
        t0 = loop.time()
        try:
            payload = await self.stage_handler(job, stage)
            latency_ms = int((loop.time() - t0) * 1000)
            async with self.pool.acquire() as conn:
                await self._record_metric(conn, job_id, stage, latency_ms, ok=True)
            await self._advance(job_id, next_status, stage, payload)
            logger.info(
                "job %s stage=%s ok %s->%s (%dms)",
                job_id, stage, inbound, next_status, latency_ms,
            )
        except Exception as exc:  # noqa: BLE001 — stage handler may raise anything.
            latency_ms = int((loop.time() - t0) * 1000)
            try:
                async with self.pool.acquire() as conn:
                    await self._record_metric(conn, job_id, stage, latency_ms, ok=False)
            except Exception:  # metric write must never mask the real failure.
                logger.exception("metric write failed for job %s", job_id)
            went_dead = await self._fail(
                job_id, stage, job["attempts"], job["max_attempts"], repr(exc)
            )
            if went_dead:
                await self.alert_fn(
                    f"intake job {job_id} DEAD at stage={stage} "
                    f"after {job['attempts'] + 1} attempts (poison-pill)"
                )
                logger.error("job %s -> DEAD stage=%s", job_id, stage)
            else:
                logger.warning("job %s stage=%s failed, will retry", job_id, stage)
        finally:
            hb_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hb_task

    async def _heartbeat_loop(self, job_id: int) -> None:
        while True:
            await asyncio.sleep(self.config.heartbeat_interval_seconds)
            try:
                await self._heartbeat(job_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("heartbeat failed job %s: %s", job_id, exc)

    async def run_once(self) -> bool:
        """Claim and process at most one job. Returns True if work was done.

        The claim is a single atomic UPDATE...FROM(CTE with FOR UPDATE SKIP
        LOCKED) statement — auto-committed, so no explicit transaction needed
        to guarantee exactly-once acquisition across concurrent workers.
        """
        async with self.pool.acquire() as conn:
            job = await self._claim_with_inbound(conn)
        if job is None:
            return False
        await self._process_one(job)
        return True

    async def _claim_with_inbound(self, conn: asyncpg.Connection) -> dict | None:
        """Claim one job, returning the PRE-claim (inbound) status too.

        The CTE selects the row (capturing its current status as inbound),
        then the UPDATE flips it to 'processing'. We RETURNING the post-update
        row but carry the inbound status out of the CTE.
        """
        ttl = self.config.lease_ttl_seconds
        row = await conn.fetchrow(
            f"""
            WITH claimed AS (
                SELECT id, status AS inbound_status
                FROM intake_queue
                WHERE status = ANY($1::text[])
                  AND next_visible_at <= now()
                  AND (lease_owner IS NULL OR lease_expires_at < now())
                ORDER BY next_visible_at, id
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            UPDATE intake_queue q
            SET lease_owner      = $2,
                lease_expires_at = now() + make_interval(secs => $3),
                status           = 'processing'
            FROM claimed
            WHERE q.id = claimed.id
            RETURNING q.id, q.attempts, q.max_attempts, q.source,
                      q.source_ref, claimed.inbound_status
            """,
            list(CLAIMABLE_STATUSES),
            self.worker_id,
            ttl,
        )
        if row is None:
            return None
        job = dict(row)
        job["_inbound_status"] = job.pop("inbound_status")
        return job

    async def run_forever(self) -> None:
        """Internal claim->process->sleep loop. Owns its own cadence.

        Does NOT rely on launchd KeepAlive for the cycle (anti-storm): KeepAlive
        is only for respawn-on-crash. We loop here until stopped or the DB is
        unreachable past DB_FAILURE_EXIT_THRESHOLD (then exit 0, no flap).
        """
        logger.info("intake worker %s started", self.worker_id)
        db_failures = 0
        while not self._stop.is_set():
            try:
                did_work = await self.run_once()
                db_failures = 0
                if not did_work:
                    await self._sleep_or_stop(self.config.poll_interval_seconds)
            except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError) as exc:
                db_failures += 1
                logger.error(
                    "DB error (%d/%d): %s",
                    db_failures, DB_FAILURE_EXIT_THRESHOLD, exc,
                )
                if db_failures >= DB_FAILURE_EXIT_THRESHOLD:
                    logger.error("DB unreachable; exiting 0 to let launchd respawn slowly")
                    return
                await self._sleep_or_stop(self.config.poll_interval_seconds)
            except asyncio.CancelledError:
                logger.info("intake worker %s cancelled", self.worker_id)
                raise
            except Exception:  # noqa: BLE001
                logger.exception("unexpected worker loop error")
                await self._sleep_or_stop(self.config.poll_interval_seconds)
        logger.info("intake worker %s stopped", self.worker_id)

    async def _sleep_or_stop(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass


# Reverse map stage -> inbound claimable status (for retry re-enqueue).
_STAGE_TO_INBOUND_STATUS: dict[str, str] = {
    stage: inbound for inbound, (stage, _next) in STAGE_TRANSITIONS.items()
}


async def _build_pool() -> asyncpg.Pool:
    """Build the asyncpg pool from DATABASE_URL (LOCAL nuzantara_dev only)."""
    dsn = os.getenv(
        "INTAKE_DATABASE_URL",
        os.getenv(
            "DATABASE_URL",
            "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev",
        ),
    )
    return await asyncpg.create_pool(dsn, min_size=1, max_size=4)


async def main() -> None:
    logging.basicConfig(
        level=os.getenv("INTAKE_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    pool = await _build_pool()
    worker = IntakeWorker(pool, config=WorkerConfig.from_env())
    try:
        await worker.run_forever()
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
