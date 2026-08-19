"""BOT-V4 S2 — broker_jobs transport service (flag-OFF build).

The generation-subcontract layer between the WA outbox worker (Fly) and the
Pro-side codex broker daemon. Spec (panel-signed, 4 adversarial rounds):
research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md (#4333).

Split of responsibilities:
  - WORKER SIDE (called by the outbox worker's broker leg, PR 5/6):
    ``offer_job`` / ``wait_for_job`` / ``consume_result`` / ``discard_completion``
    plus the shared ``expire_stale_jobs`` reaper and the 7-day
    ``sweep_terminal_rows`` retention pass.
  - ENDPOINT SIDE (called by the /api/wa-broker router):
    ``claim_job`` / ``complete_job``.
  - Both sides read/write the single-row ``wa_broker_gauge`` (admission,
    liveness, circuit breaker). The breaker is PERSISTED on the gauge rather
    than held in memory because main_api runs WA_OUTBOX_WORKERS (default 2)
    concurrent workers — an in-memory breaker would give each worker its own
    failure count and neither would ever trip.

Hard rules carried from the spec:
  - The outbox row NEVER gains a new status (C11) — this module never touches
    ``wa_outbox.status``. Its only wa_outbox write is the ``generation_route``
    marker, in the SAME fenced transaction as the job INSERT (Codex NEW-2).
  - Every transition to a terminal job state NULLs the payload columns
    (``package``, ``evidence_inputs``, ``result_text``) in that same UPDATE
    (Codex NEW-1). Terminal rows keep ids/hashes/timestamps/typed outcome only.
  - ``completed_pending_consume`` is NON-terminal (Codex r3-NEW-1): it holds
    ``result_text`` under the fence until the single consumer (the worker's
    finalization) CASes it to ``consumed``. The reaper covers a dead consumer.
  - One serve-mode job per outbox row, ever — enforced by the DB
    (``uq_broker_jobs_serve_outbox``, migration 270); ``offer_job`` treats the
    unique violation as "already spent" and reports it, never retries.
  - Client text never in logs: this module logs job ids, states and typed
    outcomes only — never ``package`` or ``result_text`` content.
"""

from __future__ import annotations

import asyncio
import enum
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# T_exec (spec 2.1): claim-wait <=3s + exec <=12s. Config override
# WA_BROKER_DEADLINE_S; read per-call so tests and rollouts never need a
# process restart.
DEFAULT_DEADLINE_S = 15

# Broker claim lease: how long a leased job waits for /complete before the
# reaper may expire it. Slightly above the deadline so the deadline (not the
# lease) is what normally decides.
LEASE_TTL_S = 20

# Admission depth cap (spec 2.1, Codex H12): the broker is single-flight, so
# more than one outstanding (offered|leased) job means the second cannot start
# within budget by construction. DB-atomic via advisory xact lock below.
MAX_DEPTH = 1

# "Broker absent" threshold (spec 2.1). Deliberately NOT 2x the poll interval:
# the broker is single-flight and does not poll while an exec is in flight, so
# the gauge legitimately ages up to ~T_exec during a healthy job. Default
# covers a full exec plus margin. Config override WA_BROKER_ABSENT_AFTER_S.
DEFAULT_ABSENT_AFTER_S = 45

# Circuit breaker (spec 2.1): 3 consecutive expiries/typed failures -> OPEN
# for 5 minutes -> half-open canary.
BREAKER_TRIP_AFTER = 3
BREAKER_OPEN_SECONDS = 300

# Terminal-row retention (spec 2, Codex NEW-1).
TERMINAL_RETENTION_DAYS = 7

# Worker-side wait poll cadence while a job is offered/leased.
WAIT_POLL_SECONDS = 0.2

# Advisory lock key for the DB-atomic offer admission count (spec 2, Codex
# H12). xact-scoped: released automatically at commit/rollback.
_ADMISSION_LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtext('wa_broker_admission'))"

_TERMINAL_STATES = ("consumed", "expired", "failed")


def deadline_seconds() -> int:
    """T_exec, config-overridable (spec 2.1)."""
    raw = os.getenv("WA_BROKER_DEADLINE_S", "")
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_DEADLINE_S
    return value if value > 0 else DEFAULT_DEADLINE_S


def absent_after_seconds() -> int:
    raw = os.getenv("WA_BROKER_ABSENT_AFTER_S", "")
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_ABSENT_AFTER_S
    return value if value > 0 else DEFAULT_ABSENT_AFTER_S


class OfferOutcome(str, enum.Enum):
    """Why an offer did or did not happen. The caller (worker broker leg)
    routes to the Gemini leg on anything but OFFERED."""

    OFFERED = "offered"
    BROKER_ABSENT = "broker_absent"
    BREAKER_OPEN = "breaker_open"
    QUEUE_FULL = "queue_full"
    ALREADY_SPENT = "already_spent"  # unique violation: row's codex leg used
    FENCE_LOST = "fence_lost"  # wa_outbox claim no longer ours


@dataclass
class OfferResult:
    outcome: OfferOutcome
    job_id: uuid.UUID | None = None


class WaitOutcome(str, enum.Enum):
    COMPLETED = "completed"  # completed_pending_consume observed
    FAILED = "failed"  # broker reported a typed failure (terminal)
    DEADLINE = "deadline"  # deadline_at reached without completion


@dataclass
class WaitResult:
    outcome: WaitOutcome
    error_class: str | None = None


async def _gauge_upsert(conn: asyncpg.Connection, **fields: Any) -> None:
    """Lazy-seeding upsert of the single gauge row (id=1).

    The migration deliberately seeds nothing (no DML in DDL); the first
    writer creates the row.
    """
    cols = ", ".join(fields)
    placeholders = ", ".join(f"${i + 1}" for i in range(len(fields)))
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in fields)
    await conn.execute(
        f"""
        INSERT INTO wa_broker_gauge (id, {cols}, updated_at)
        VALUES (1, {placeholders}, now())
        ON CONFLICT (id) DO UPDATE SET {updates}, updated_at = now()
        """,
        *fields.values(),
    )


# ──────────────────────────────────────────────────────────────────────────
# Circuit breaker (persisted on the gauge — shared across workers)
# ──────────────────────────────────────────────────────────────────────────


async def breaker_allows(conn: asyncpg.Connection) -> bool:
    """True when the breaker is closed, or open-past-cooldown (half-open
    canary allowed). The admission depth cap bounds half-open concurrency:
    at most MAX_DEPTH canaries can be outstanding even with several workers.
    """
    row = await conn.fetchrow(
        """
        SELECT breaker_state,
               breaker_opened_at IS NOT NULL
               AND breaker_opened_at <= now() - ($1 * INTERVAL '1 second')
                   AS cooled_down
        FROM wa_broker_gauge WHERE id = 1
        """,
        BREAKER_OPEN_SECONDS,
    )
    if row is None:  # gauge not seeded yet -> broker has never spoken
        return False
    if row["breaker_state"] == "closed":
        return True
    return bool(row["cooled_down"])


async def record_breaker_result(conn: asyncpg.Connection, *, success: bool) -> None:
    """Fold one codex-leg outcome into the shared breaker state."""
    if success:
        await _gauge_upsert(
            conn,
            breaker_state="closed",
            breaker_opened_at=None,
            consecutive_failures=0,
        )
        return
    row = await conn.fetchrow(
        """
        INSERT INTO wa_broker_gauge (id, consecutive_failures, updated_at)
        VALUES (1, 1, now())
        ON CONFLICT (id) DO UPDATE
        SET consecutive_failures = wa_broker_gauge.consecutive_failures + 1,
            updated_at = now()
        RETURNING consecutive_failures
        """,
    )
    failures = row["consecutive_failures"] if row else 1
    if failures >= BREAKER_TRIP_AFTER:
        await conn.execute(
            """
            UPDATE wa_broker_gauge
            SET breaker_state = 'open', breaker_opened_at = now(),
                updated_at = now()
            WHERE id = 1 AND breaker_state <> 'open'
            """,
        )
        logger.warning(
            "wa_broker: circuit breaker OPEN after %d consecutive failures "
            "(codex route disabled for %ds)",
            failures,
            BREAKER_OPEN_SECONDS,
        )


# ──────────────────────────────────────────────────────────────────────────
# Worker side — offer / wait / consume / discard
# ──────────────────────────────────────────────────────────────────────────


async def offer_job(
    conn: asyncpg.Connection,
    *,
    outbox_id: int,
    thread_id: int,
    claim_token: uuid.UUID,
    outbox_expected_status: str,
    package: str,
    evidence_inputs: str,
    package_hash: str,
    thread_epoch: int,
) -> OfferResult:
    """Offer one serve-mode job — the row's ONE codex leg (spec 2).

    ONE TRANSACTION, fenced on the outbox claim (Codex NEW-2): the
    ``generation_route`` marker and the job INSERT commit or vanish together;
    there is no crash window in either direction. Admission (liveness,
    breaker, depth) is checked INSIDE the same transaction under an advisory
    xact lock, so two workers reading the same stale gauge cannot double-offer
    past the cap (Codex H12).

    ``package``/``evidence_inputs`` arrive as already-serialized JSON strings
    (the caller owns the allowlist schema, spec 2.2) — this module never
    introspects, logs or re-serializes their content.
    """
    t_exec = deadline_seconds()
    async with conn.transaction():
        await conn.execute(_ADMISSION_LOCK_SQL)

        gauge = await conn.fetchrow(
            """
            SELECT broker_last_seen_at >= now() - ($1 * INTERVAL '1 second')
                       AS broker_alive
            FROM wa_broker_gauge WHERE id = 1
            """,
            absent_after_seconds(),
        )
        if gauge is None or not gauge["broker_alive"]:
            return OfferResult(OfferOutcome.BROKER_ABSENT)

        if not await breaker_allows(conn):
            return OfferResult(OfferOutcome.BREAKER_OPEN)

        depth = await conn.fetchval(
            "SELECT count(*) FROM broker_jobs WHERE state IN ('offered', 'leased')",
        )
        if int(depth or 0) >= MAX_DEPTH:
            return OfferResult(OfferOutcome.QUEUE_FULL)

        # Route marker, fenced on the outbox claim. If the fence is gone the
        # transaction rolls back having written nothing.
        fenced = await conn.fetchrow(
            """
            UPDATE wa_outbox SET generation_route = 'codex'
            WHERE id = $1 AND claim_token = $2 AND status = $3
              AND generation_route IS NULL
            RETURNING id
            """,
            outbox_id,
            claim_token,
            outbox_expected_status,
        )
        if fenced is None:
            # Either the lease was lost, or the marker is already set (a
            # previous attempt spent the leg). Disambiguate for the ledger.
            already = await conn.fetchval(
                "SELECT generation_route IS NOT NULL FROM wa_outbox WHERE id = $1",
                outbox_id,
            )
            return OfferResult(
                OfferOutcome.ALREADY_SPENT if already else OfferOutcome.FENCE_LOST
            )

        try:
            job_id = await conn.fetchval(
                """
                INSERT INTO broker_jobs
                    (outbox_id, thread_id, mode, package, evidence_inputs,
                     package_hash, thread_epoch, deadline_at)
                VALUES ($1, $2, 'serve', $3::jsonb, $4::jsonb, $5, $6,
                        now() + ($7 * INTERVAL '1 second'))
                RETURNING job_id
                """,
                outbox_id,
                thread_id,
                package,
                evidence_inputs,
                package_hash,
                thread_epoch,
                t_exec,
            )
        except asyncpg.UniqueViolationError:
            # uq_broker_jobs_serve_outbox: the leg was already spent by a
            # path that did not set the marker (should not happen — the two
            # writes are one transaction — but the DB is the invariant's
            # owner, so honor its verdict rather than assume).
            return OfferResult(OfferOutcome.ALREADY_SPENT)

    logger.info(
        "wa_broker: offered job %s (outbox=%s thread=%s deadline=%ss)",
        job_id,
        outbox_id,
        thread_id,
        t_exec,
    )
    return OfferResult(OfferOutcome.OFFERED, job_id=job_id)


async def wait_for_job(
    pool: asyncpg.Pool,
    job_id: uuid.UUID,
    *,
    poll_seconds: float = WAIT_POLL_SECONDS,
) -> WaitResult:
    """Wait (bounded by the job's own deadline_at) for a completion.

    Polls the job row — the worker holds its thread advisory lock for the
    whole wait, exactly as it would during a slow Gemini generation (C12).
    The deadline verdict comes from the DATABASE clock (deadline_at vs
    now()), never this process's wall clock, so worker/DB skew cannot
    stretch the budget.
    """
    while True:
        row = await pool.fetchrow(
            """
            SELECT state, error_class, deadline_at <= now() AS deadline_passed
            FROM broker_jobs WHERE job_id = $1
            """,
            job_id,
        )
        if row is None:  # reaped/vanished — treat as deadline
            return WaitResult(WaitOutcome.DEADLINE)
        if row["state"] == "completed_pending_consume":
            return WaitResult(WaitOutcome.COMPLETED)
        if row["state"] == "failed":
            return WaitResult(WaitOutcome.FAILED, error_class=row["error_class"])
        if row["state"] in _TERMINAL_STATES:
            # consumed/expired under us (reaper won a race) — nothing to use.
            return WaitResult(WaitOutcome.DEADLINE)
        if row["deadline_passed"]:
            # CAS to expired ourselves so a late /complete gets 410 (spec 2).
            expired = await pool.fetchrow(
                """
                UPDATE broker_jobs
                SET state = 'expired', package = NULL, evidence_inputs = NULL,
                    result_text = NULL, outcome = 'expired_deadline'
                WHERE job_id = $1 AND state IN ('offered', 'leased')
                RETURNING job_id
                """,
                job_id,
            )
            if expired is not None:
                return WaitResult(WaitOutcome.DEADLINE)
            # A /complete slid in between our read and the CAS — loop once
            # more to observe it.
            continue
        await asyncio.sleep(poll_seconds)


async def consume_result(
    conn: asyncpg.Connection, job_id: uuid.UUID
) -> str | None:
    """Single-consumer CAS: completed_pending_consume -> consumed.

    Returns the result text, atomically NULLing every payload column in the
    same UPDATE (Codex r3-NEW-1). The pre-update value is read through the
    self-join FROM — RETURNING alone would see the NULL we just wrote.
    """
    row = await conn.fetchrow(
        """
        UPDATE broker_jobs AS b
        SET state = 'consumed', package = NULL, evidence_inputs = NULL,
            result_text = NULL, consumed_at = now(), outcome = 'consumed_ok'
        FROM broker_jobs AS old
        WHERE b.job_id = old.job_id
          AND b.job_id = $1 AND b.state = 'completed_pending_consume'
        RETURNING old.result_text AS result_text
        """,
        job_id,
    )
    return row["result_text"] if row else None


async def discard_completion(
    conn: asyncpg.Connection, job_id: uuid.UUID, *, reason: str
) -> None:
    """Consume-and-discard (thread-epoch drift, spec 2.3): the completion is
    never used, the payload is NULLed, the typed outcome names why. The
    discarded leg still counts as the row's one codex leg — generation_route
    was set at offer time and stays set.
    """
    await conn.execute(
        """
        UPDATE broker_jobs
        SET state = 'consumed', package = NULL, evidence_inputs = NULL,
            result_text = NULL, consumed_at = now(), outcome = $2
        WHERE job_id = $1 AND state = 'completed_pending_consume'
        """,
        job_id,
        f"discarded_{reason}",
    )


# ──────────────────────────────────────────────────────────────────────────
# Endpoint side — claim / complete
# ──────────────────────────────────────────────────────────────────────────


async def claim_job(
    conn: asyncpg.Connection,
    *,
    in_flight: int,
    last_exec_ms: int | None,
) -> asyncpg.Record | None:
    """CAS one offered job -> leased and return it (with package + clocks).

    EVERY call — including one that finds no job — refreshes the gauge
    (spec 2.1: the /claim poll IS the heartbeat channel). Returns the leased
    row or None.
    """
    # broker_last_seen_at is the DB's clock, never a bound parameter from
    # the broker's machine (Kimi N2's skew concern, applied to the gauge).
    await conn.execute(
        """
        INSERT INTO wa_broker_gauge
            (id, broker_last_seen_at, in_flight, last_exec_ms, updated_at)
        VALUES (1, now(), $1, $2, now())
        ON CONFLICT (id) DO UPDATE
        SET broker_last_seen_at = now(),
            in_flight = EXCLUDED.in_flight,
            last_exec_ms = COALESCE(EXCLUDED.last_exec_ms,
                                    wa_broker_gauge.last_exec_ms),
            updated_at = now()
        """,
        in_flight,
        last_exec_ms,
    )

    fence_token = uuid.uuid4()
    row = await conn.fetchrow(
        """
        UPDATE broker_jobs
        SET state = 'leased', fence_token = $1, leased_at = now(),
            lease_expires_at = now() + ($2 * INTERVAL '1 second')
        WHERE job_id = (
            SELECT job_id FROM broker_jobs
            WHERE state = 'offered' AND deadline_at > now()
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        RETURNING job_id, fence_token, package, package_hash, deadline_at,
                  now() AS server_now
        """,
        fence_token,
        LEASE_TTL_S,
    )
    if row is not None:
        logger.info("wa_broker: job %s leased", row["job_id"])
    return row


class CompleteStatus(str, enum.Enum):
    ACCEPTED = "accepted"  # -> completed_pending_consume (or failed, typed)
    REPLAY = "replay"  # same completion_key re-POST -> same 200
    CONFLICT = "conflict"  # different payload for a completed job -> 409
    GONE = "gone"  # no such leased job under this fence / expired -> 410


async def complete_job(
    conn: asyncpg.Connection,
    *,
    job_id: uuid.UUID,
    fence_token: uuid.UUID,
    completion_key: str,
    result_text: str | None,
    error_class: str | None,
    exec_ms: int | None,
) -> CompleteStatus:
    """Idempotent completion CAS (spec 2, Codex H5/H6).

    Success path: leased -> completed_pending_consume, result under fence.
    Typed-failure path (``error_class`` set, no text): leased -> failed,
    terminal, payload NULLed in the same UPDATE.
    A lost HTTP response re-POSTs the same ``completion_key`` -> REPLAY (200,
    no state change). A DIFFERENT payload for an already-completed job ->
    CONFLICT (409) — never a second generation. Anything else -> GONE (410).
    """
    if result_text is not None and error_class is not None:
        raise ValueError("completion carries either result_text or error_class")

    if error_class is not None:
        row = await conn.fetchrow(
            """
            UPDATE broker_jobs
            SET state = 'failed', package = NULL, evidence_inputs = NULL,
                result_text = NULL, completed_at = now(),
                completion_key = $3, error_class = $4, exec_ms = $5,
                outcome = 'broker_failed'
            WHERE job_id = $1 AND fence_token = $2 AND state = 'leased'
              AND deadline_at > now()
            RETURNING job_id
            """,
            job_id,
            fence_token,
            completion_key,
            error_class,
            exec_ms,
        )
    else:
        row = await conn.fetchrow(
            """
            UPDATE broker_jobs
            SET state = 'completed_pending_consume', result_text = $4,
                completed_at = now(), completion_key = $3, exec_ms = $5
            WHERE job_id = $1 AND fence_token = $2 AND state = 'leased'
              AND deadline_at > now()
            RETURNING job_id
            """,
            job_id,
            fence_token,
            completion_key,
            result_text,
            exec_ms,
        )
    if row is not None:
        return CompleteStatus.ACCEPTED

    # CAS missed. Same completion_key on the same job = the retry of a
    # completion we already accepted (the first response was lost in
    # transit): idempotent 200. Note the replay check deliberately does NOT
    # compare text — the consumer may already have NULLed it; completion_key
    # equality IS the identity of the attempt (it is minted once per exec).
    prior = await conn.fetchrow(
        "SELECT completion_key, state FROM broker_jobs WHERE job_id = $1",
        job_id,
    )
    if prior is not None and prior["completion_key"] == completion_key:
        return CompleteStatus.REPLAY
    if prior is not None and prior["state"] in (
        "completed_pending_consume",
        "consumed",
        "failed",
    ):
        return CompleteStatus.CONFLICT
    return CompleteStatus.GONE


# ──────────────────────────────────────────────────────────────────────────
# Reaper + retention (shared)
# ──────────────────────────────────────────────────────────────────────────


async def expire_stale_jobs(pool: asyncpg.Pool) -> int:
    """Expire whatever outlived its budget, NULLing payloads in the same
    UPDATE (spec 2): serve jobs past deadline_at (offered/leased), a
    completed_pending_consume whose consumer died (lease grace passed), and
    shadow jobs past their own expires_at (Kimi N1).
    """
    result = await pool.execute(
        """
        UPDATE broker_jobs
        SET state = 'expired', package = NULL, evidence_inputs = NULL,
            result_text = NULL,
            outcome = COALESCE(outcome, 'expired_' || state)
        WHERE (mode = 'serve' AND state IN ('offered', 'leased')
                 AND deadline_at <= now())
           OR (state = 'completed_pending_consume'
                 AND completed_at <= now() - ($1 * INTERVAL '1 second'))
           OR (mode = 'shadow' AND state IN ('offered', 'leased')
                 AND expires_at IS NOT NULL AND expires_at <= now())
        """,
        LEASE_TTL_S * 3,
    )
    try:
        count = int(result.split()[-1])
    except (ValueError, IndexError, AttributeError):
        count = 0
    if count:
        logger.info("wa_broker: reaper expired %d stale job(s)", count)
    return count


async def sweep_terminal_rows(pool: asyncpg.Pool) -> int:
    """Retention sweep: remove terminal rows past the 7-day TTL, then VERIFY
    the effect (spec 2 / scar family #2: a sweep that silently stops is how
    'DONE' retention turns out unenforced). Returns the number removed;
    logs an ERROR with a distinctive marker if the post-sweep count is not
    zero — that marker is the alarm hook.
    """
    result = await pool.execute(
        """
        DELETE FROM broker_jobs
        WHERE state IN ('consumed', 'expired', 'failed')
          AND created_at <= now() - ($1 * INTERVAL '1 day')
        """,
        TERMINAL_RETENTION_DAYS,
    )
    try:
        removed = int(result.split()[-1])
    except (ValueError, IndexError, AttributeError):
        removed = 0

    residue = await pool.fetchval(
        """
        SELECT count(*) FROM broker_jobs
        WHERE state IN ('consumed', 'expired', 'failed')
          AND created_at <= now() - ($1 * INTERVAL '1 day')
        """,
        TERMINAL_RETENTION_DAYS,
    )
    if int(residue or 0) != 0:
        logger.error(
            "wa_broker: RETENTION SWEEP INEFFECTIVE — %d terminal broker_jobs "
            "rows remain past the %dd TTL after the sweep ran",
            residue,
            TERMINAL_RETENTION_DAYS,
        )
    return removed
