"""Unified document-intake worker orchestrator (FASE 2, v2 state machine).

Forks the SKIP-LOCKED claim/lease/heartbeat/retry/DLQ pattern from
`backend.services.workflow.queue` and adapts it to the unified `intake_queue`
(migrations 212 + 224). PII stays 100% local (Law 2 / UU-PDP): no cloud LLM —
stage handlers are injected (see ``backend.services.intake.stages``).

v2 state machine (migration 224) — status = "what is DONE"
-----------------------------------------------------------
::

    pending --classify(+OCR)--> ocr_done --extract--> extracted
        --validate--> validated --route--> done

Two structural fixes over v1 (the "stuck in processing" scar):

* **Lease-only claim.** v1 flipped ``status='processing'`` at claim time, which
  DESTROYED the stage cursor: a worker crash mid-stage re-entered the machine at
  the wrong stage (jobs re-ran OCR instead of route, or skipped classify
  entirely). v2 claims by setting ``lease_owner``/``lease_expires_at`` ONLY —
  ``status`` is written exclusively by ``_advance``/``_fail``, so a crashed job
  is re-claimed at exactly the stage it was at.
* **No passthrough OCR stage.** classify already performs OCR; the v1 ``ocr``
  stage was a no-op costing one full claim round-trip per document.

Legacy rows (v1 statuses) are remapped ONCE at worker boot by
:func:`remap_legacy_statuses` — stage-aware (the ``stage`` column records the
last COMPLETED stage, which disambiguates e.g. a legacy ``extracted`` row
(validate done -> ``validated``) from a v2 one (extract done)). Migration 224's
CHECK accepts both name sets until the remap retires the old ones.

Terminal states:
  - 'done'  : routed through all stages.
  - 'dead'  : retry budget exhausted (attempts >= max_attempts). TERMINAL —
              a 'dead' job is NEVER claimable again (W61 anti-storm).

Transient infra failures (Ollama down, …) raise :class:`TransientStageError`
and DO NOT burn an attempt: the job is re-enqueued with a fixed backoff. A
poison-pill (real stage error) burns attempts as before.

The worker loop also runs the review-claim reaper every
``REAP_INTERVAL_SECONDS``: expired ``review_claimed`` proposals return to
``review_pending`` so abandoned claims never gum up the review queue.

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
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from types import ModuleType

import asyncpg

logger = logging.getLogger("zantara.intake.worker")


def _install_canonical_main_alias(
    module_name: str,
    package: str | None,
    modules: dict[str, ModuleType],
) -> str | None:
    """Keep ``python -m ...worker`` from duplicating this module.

    Launchd runs this file as ``python -m backend.services.intake.worker``, which
    executes it as ``__main__``. Later, ``stages.py`` imports
    ``backend.services.intake.worker.TransientStageError``. Without this alias,
    Python loads a second copy of worker.py, producing a distinct
    ``TransientStageError`` class; transient Ollama timeouts then miss the
    worker's ``except TransientStageError`` branch and burn retry attempts.
    """
    if module_name != "__main__" or not package:
        return None
    canonical = f"{package}.worker"
    modules[canonical] = modules[module_name]
    return canonical


_install_canonical_main_alias(__name__, __package__, sys.modules)

# --- Claimable status set (mirrors idx_iq_claimable in migration 224). ---
CLAIMABLE_STATUSES: tuple[str, ...] = (
    "pending",
    "ocr_done",
    "extracted",
    "validated",
)

# --- v2 stage machine: status -> (stage_name, next_status). ---
# The status KEY names the work ALREADY DONE; the tuple names the stage to run
# next and the status that records its completion. Terminal next_status='done'
# is NOT claimable.
STAGE_TRANSITIONS: dict[str, tuple[str, str]] = {
    "pending": ("classify", "ocr_done"),
    "ocr_done": ("extract", "extracted"),
    "extracted": ("validate", "validated"),
    "validated": ("route", "done"),
}

# --- Defaults (overridable via env / constructor for tests). ---
DEFAULT_LEASE_TTL_SECONDS = 900  # 15 min — must exceed the slowest stage.
# Parallel in-flight jobs per worker process. Default 1 = legacy sequential.
# Keep LOW: the OCR stage is bottlenecked on a single local Ollama GPU, so
# high concurrency starves VRAM and causes empty-page timeouts. 2-3 overlaps
# cheap stages (classify-advance/extract/route) with one in-flight OCR.
DEFAULT_CONCURRENCY = 1
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 120  # 2 min, like workflow/queue.
DEFAULT_POLL_INTERVAL_SECONDS = 2
DEFAULT_BASE_BACKOFF_SECONDS = 2.0  # exponential: base * 2**(attempts-1).
DEFAULT_MAX_BACKOFF_SECONDS = 600.0
# Fixed backoff for TRANSIENT infra failures (no attempt burned).
DEFAULT_TRANSIENT_BACKOFF_SECONDS = 60.0
# How often the review-claim reaper runs inside run_forever.
REAP_INTERVAL_SECONDS = 60.0

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


class TransientStageError(RuntimeError):
    """Stage failed for INFRA reasons (Ollama down, network hiccup, …).

    The worker re-enqueues the job with a fixed backoff WITHOUT burning an
    attempt: a downed local model must never DLQ a perfectly good document
    (it would burn 5 retries in minutes and go 'dead' while Ollama reboots).
    """


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
    transient_backoff_seconds: float = DEFAULT_TRANSIENT_BACKOFF_SECONDS
    concurrency: int = DEFAULT_CONCURRENCY

    @classmethod
    def from_env(cls) -> WorkerConfig:
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
            transient_backoff_seconds=float(
                os.getenv(
                    "INTAKE_TRANSIENT_BACKOFF_SECONDS",
                    DEFAULT_TRANSIENT_BACKOFF_SECONDS,
                )
            ),
            concurrency=max(
                1, int(os.getenv("INTAKE_CONCURRENCY", DEFAULT_CONCURRENCY))
            ),
        )


def make_worker_id() -> str:
    """Stable-ish per-process worker identity for lease_owner."""
    return f"{socket.gethostname()}:{os.getpid()}"


# --- Stub stage handler. Override via stage_handler for tests/production. ---
StageHandler = Callable[[dict, str], Awaitable[dict]]


async def _stub_stage(job: dict, stage: str) -> dict:
    """STUB passthrough stage: no OCR, no LLM. Returns a fixture dict.

    Production wires the real handlers (``stages.build_real_stage_handler``);
    this default exists only for unit tests that inject their own handler.
    """
    return {"stub": True, "stage": stage, "queue_id": job["id"]}


# --------------------------------------------------------------------------- #
# v1 -> v2 boot-time remap (idempotent, stage-aware)
# --------------------------------------------------------------------------- #
async def remap_legacy_statuses(pool: asyncpg.Pool) -> int:
    """Remap v1 status names to the v2 machine. Returns rows touched.

    Stage-aware: the ``stage`` column holds the last COMPLETED stage (written by
    v1 ``_advance``), which disambiguates every legacy name — including a v1
    ``processing`` row abandoned by the claim-flip bug (its stage tells where it
    really was). Idempotent: v1 names are never produced by v2 writes, and the
    only ambiguous name ('extracted') is gated on ``stage='validate'``, which a
    v2 'extracted' row (stage='extract') never carries.

    Also verifies migration 224 is applied (the CHECK must accept 'ocr_done');
    raises RuntimeError otherwise so the caller can refuse to start.
    """
    async with pool.acquire() as conn:
        constraint = await conn.fetchval(
            """
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conname = 'chk_iq_status' AND conrelid = 'intake_queue'::regclass
            """
        )
        if constraint and "ocr_done" not in constraint:
            raise RuntimeError(
                "migration 224 not applied: chk_iq_status does not accept v2 "
                "statuses — apply 224_intake_flow_v2.sql before starting the v2 worker"
            )

        result = await conn.execute(
            """
            UPDATE intake_queue
            SET status = CASE
                    -- v1 claim-flip orphans: stage = last COMPLETED stage.
                    WHEN status = 'processing' AND stage = 'classify'   THEN 'ocr_done'
                    WHEN status = 'processing' AND stage = 'ocr'        THEN 'ocr_done'
                    WHEN status = 'processing' AND stage = 'extract'    THEN 'extracted'
                    WHEN status = 'processing' AND stage = 'validate'   THEN 'validated'
                    WHEN status = 'processing'                          THEN 'pending'
                    -- v1 steady-state names.
                    WHEN status = 'ocr'                                 THEN 'ocr_done'
                    WHEN status = 'classified'                          THEN 'extracted'
                    WHEN status = 'extracted' AND stage = 'validate'    THEN 'validated'
                    ELSE status
                END,
                lease_owner      = NULL,
                lease_expires_at = NULL,
                next_visible_at  = now()
            WHERE status IN ('processing', 'ocr', 'classified')
               OR (status = 'extracted' AND stage = 'validate')
            """
        )
    touched = int(result.split()[-1]) if result else 0
    if touched:
        logger.info("remap_legacy_statuses: %d v1 rows remapped to v2", touched)
    return touched


# --------------------------------------------------------------------------- #
# Review-claim reaper (expired review_claimed -> review_pending)
# --------------------------------------------------------------------------- #
async def reap_expired_review_claims(pool: asyncpg.Pool) -> int:
    """Return expired ``review_claimed`` proposals to ``review_pending``.

    A reviewer who opened a document and walked away holds a 15-min lease
    (CLAIM_TTL_MINUTES in routers/intake_review.py). Without this reaper the
    proposal stays ``review_claimed`` forever — steal-claimable, but listed
    under the wrong status and invisible in the default review_pending feed.
    Runs at worker boot + every REAP_INTERVAL_SECONDS.
    """
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE document_routing_proposal
               SET status = 'review_pending',
                   lease_owner = NULL,
                   lease_expires_at = NULL,
                   claim_token = NULL,
                   claimed_at = NULL
             WHERE status = 'review_claimed'
               AND lease_expires_at < now()
            """
        )
    reaped = int(result.split()[-1]) if result else 0
    if reaped:
        logger.info("reap_expired_review_claims: %d stale claims -> review_pending", reaped)
    return reaped


class IntakeWorker:
    """Single-process intake worker: claim (lease-only) -> run one stage -> advance."""

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
                WHERE id = $1 AND lease_owner = $3
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
        *,
        payload: dict | None = None,
    ) -> None:
        """One metrics row per stage run.

        Model/confidence come from the stage's own ``_metric`` payload when
        present (the REAL model name), not a hardcoded placeholder.
        """
        metric = (payload or {}).get("_metric") if isinstance(payload, dict) else None
        if not isinstance(metric, dict):
            metric = {}
        await conn.execute(
            """
            INSERT INTO intake_stage_metrics
                (queue_id, stage, latency_ms, confidence, model, ok)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            queue_id,
            stage,
            latency_ms,
            float(metric.get("confidence", 1.0 if ok else 0.0)),
            str(metric.get("model", "unknown"))[:80],
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
        The ``lease_owner = $5`` guard makes a stolen-lease advance a no-op —
        logged loudly, because it means the lease TTL is too short for the stage.
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(
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
        if result == "UPDATE 0":
            logger.error(
                "advance LOST for job %s stage=%s: lease no longer ours "
                "(expired mid-stage and stolen?). Raise INTAKE_LEASE_TTL_SECONDS.",
                job_id,
                stage,
            )

    async def _fail(
        self,
        job_id: int,
        stage: str,
        attempts: int,
        max_attempts: int,
        error: str,
        *,
        transient: bool = False,
    ) -> bool:
        """On stage failure: bump attempts; retry with backoff OR go 'dead'.

        Returns True iff the job was moved to terminal 'dead' (alert needed).

        v2: status is NEVER touched on a retryable failure — the lease-only
        claim left it at the stage cursor, so clearing the lease + scheduling
        next_visible_at is the whole retry story. ``transient=True`` (infra
        down) does NOT bump attempts and uses a fixed backoff.

        W61 anti-storm: 'dead' is terminal and NOT claimable. We only ever
        write 'dead' here; a dead row is never re-added to the claimable set.
        """
        masked = mask_pii(error)

        if transient:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE intake_queue
                    SET last_error       = $2,
                        lease_owner      = NULL,
                        lease_expires_at = NULL,
                        next_visible_at  = now() + make_interval(secs => $3)
                    WHERE id = $1 AND lease_owner = $4
                    """,
                    job_id,
                    f"transient: {masked}"[:1000],
                    float(self.config.transient_backoff_seconds),
                    self.worker_id,
                )
            return False

        new_attempts = attempts + 1
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
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE intake_queue
                SET attempts         = $2,
                    last_error       = $3,
                    lease_owner      = NULL,
                    lease_expires_at = NULL,
                    next_visible_at  = now() + make_interval(secs => $4)
                WHERE id = $1 AND lease_owner = $5
                """,
                job_id,
                new_attempts,
                masked,
                float(backoff),
                self.worker_id,
            )
        return False

    async def _process_one(self, job: dict) -> None:
        """Run exactly one stage for a claimed job."""
        job_id = job["id"]
        # v2: the claim is lease-only, so the job's status IS the stage cursor
        # (what is already done) and selects the stage to run now.
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
                await self._record_metric(
                    conn, job_id, stage, latency_ms, ok=True, payload=payload
                )
            await self._advance(job_id, next_status, stage, payload)
            logger.info(
                "job %s stage=%s ok %s->%s (%dms)",
                job_id, stage, inbound, next_status, latency_ms,
            )
        except TransientStageError as exc:
            latency_ms = int((loop.time() - t0) * 1000)
            with contextlib.suppress(Exception):
                async with self.pool.acquire() as conn:
                    await self._record_metric(conn, job_id, stage, latency_ms, ok=False)
            await self._fail(
                job_id, stage, job["attempts"], job["max_attempts"], repr(exc),
                transient=True,
            )
            logger.warning(
                "job %s stage=%s TRANSIENT failure (no attempt burned), retry in %ss: %s",
                job_id, stage, self.config.transient_backoff_seconds, exc,
            )
        except Exception as exc:
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
            except Exception as exc:
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
        """Claim one job — LEASE-ONLY (v2).

        The CTE selects the row; the UPDATE sets ONLY the lease columns. The
        status is carried out as the stage cursor (``_inbound_status``) and is
        NEVER modified by the claim — the structural fix for the v1 "claim
        destroys the cursor" scar: a crash mid-stage leaves the status exactly
        where it was, and the expired lease makes the row re-claimable at the
        SAME stage.
        """
        ttl = self.config.lease_ttl_seconds
        row = await conn.fetchrow(
            """
            WITH claimed AS (
                SELECT id, status AS inbound_status
                FROM intake_queue
                WHERE status = ANY($1::text[])
                  AND next_visible_at <= now()
                  AND (lease_owner IS NULL OR lease_expires_at < now())
                -- Downstream stages (extract/validate/route) cost ~3ms; the
                -- classify+OCR stage costs ~50-90s on the local VLM. Pure FIFO
                -- lets a backlog of 'pending' jobs starve the cheap downstream
                -- stages, so 'ocr_done' piles up and nothing reaches 'done'
                -- (SCAR 2026-06-21). Drain near-done work FIRST: later pipeline
                -- stages rank ahead of 'pending', then FIFO within each rank.
                ORDER BY
                  CASE status
                    WHEN 'validated'    THEN 0
                    WHEN 'extracted'    THEN 1
                    WHEN 'ocr_done'     THEN 2
                    WHEN 'classified'   THEN 3
                    WHEN 'ocr'          THEN 4
                    WHEN 'processing'   THEN 5
                    ELSE 9  -- 'pending' last
                  END,
                  -- WhatsApp mirror is the client-facing intake lane. Once all
                  -- cheap downstream stages are drained, do not let historical
                  -- Drive backfills bury fresh WA attachments behind tens of
                  -- thousands of pending OCR jobs.
                  CASE
                    WHEN status = 'pending' AND source = 'whatsapp' THEN 0
                    WHEN status = 'pending'                         THEN 1
                    ELSE 0
                  END,
                  next_visible_at, id
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            UPDATE intake_queue q
            SET lease_owner      = $2,
                lease_expires_at = now() + make_interval(secs => $3)
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

        Boot sequence: remap legacy v1 statuses once, reap stale review claims,
        then poll. The reaper re-runs every REAP_INTERVAL_SECONDS.
        """
        logger.info("intake worker %s started", self.worker_id)
        try:
            await remap_legacy_statuses(self.pool)
            await reap_expired_review_claims(self.pool)
        except RuntimeError:
            logger.critical(
                "intake worker %s refusing to start (migration 224 missing)",
                self.worker_id,
            )
            return
        except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError) as exc:
            logger.error("boot remap/reap failed (continuing): %s", exc)

        loop = asyncio.get_event_loop()
        last_reap = loop.time()
        db_failures = 0
        while not self._stop.is_set():
            try:
                if loop.time() - last_reap >= REAP_INTERVAL_SECONDS:
                    last_reap = loop.time()
                    await reap_expired_review_claims(self.pool)
                n = self.config.concurrency
                if n <= 1:
                    did_work = await self.run_once()
                else:
                    # Fan out N concurrent claims. FOR UPDATE SKIP LOCKED in the
                    # claim CTE guarantees each task grabs a distinct row (or None).
                    results = await asyncio.gather(
                        *(self.run_once() for _ in range(n)),
                        return_exceptions=True,
                    )
                    for r in results:
                        if isinstance(r, (asyncpg.PostgresError, asyncpg.InterfaceError, OSError)):
                            raise r
                    did_work = any(r is True for r in results)
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
            except Exception:
                logger.exception("unexpected worker loop error")
                await self._sleep_or_stop(self.config.poll_interval_seconds)
        logger.info("intake worker %s stopped", self.worker_id)

    async def _sleep_or_stop(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass


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
    # Production entrypoint: wire the REAL FASE-3/4 stage handlers (OCR/classify/
    # extract/validate/route → creates document_routing_proposal). Without this the
    # worker would run _stub_stage passthroughs and silently advance rows to 'done'
    # with NO OCR and NO routing proposal. The stub default on IntakeWorker exists
    # only for unit tests that inject their own handler. Set INTAKE_WORKER_STUB=1 to
    # force the stub path (diagnostics / smoke only).
    if os.getenv("INTAKE_WORKER_STUB", "").strip().lower() in {"1", "true", "yes", "on"}:
        logger.warning("intake worker: INTAKE_WORKER_STUB set — running STUB stages (no OCR/route)")
        worker = IntakeWorker(pool, config=WorkerConfig.from_env())
    else:
        from backend.services.intake.stages import build_real_stage_handler

        worker = IntakeWorker(
            pool,
            config=WorkerConfig.from_env(),
            stage_handler=build_real_stage_handler(pool),
        )
    try:
        await worker.run_forever()
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
