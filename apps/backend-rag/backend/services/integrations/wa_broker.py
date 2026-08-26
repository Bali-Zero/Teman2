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
import hashlib
import logging
import os
import uuid
from dataclasses import dataclass

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

# How long a half_open gauge may sit with NO outstanding job before the next
# admission check demotes it back to open (fresh cooldown). Reachable only if
# the canary's worker crashes between consuming the result and recording the
# outcome — without this exit, half_open would be an absorbing state and the
# codex route dark forever. Sized above deadline + consume grace so it can
# never fire while a legitimate canary is still being processed.
HALF_OPEN_ORPHAN_S = 120

# Terminal-row retention (spec 2, Codex NEW-1).
TERMINAL_RETENTION_DAYS = 7

# Worker-side wait poll cadence while a job is offered/leased.
WAIT_POLL_SECONDS = 0.2

# Advisory lock key for the DB-atomic offer admission count (spec 2, Codex
# H12). xact-scoped: released automatically at commit/rollback.
_ADMISSION_LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtext('wa_broker_admission'))"

_TERMINAL_STATES = ("consumed", "expired", "failed")

# The transport's CLOSED vocabulary for typed terminal failures. error_class
# is retained on terminal rows (outside the payload-NULL guarantee), so it
# must never be able to carry free text — exception messages, identifiers,
# client content (S2 cross-family review, finding 7). The broker daemon
# (PR-6) maps its failure modes INTO this set; widening it is a reviewed
# diff by construction. The router validates against this same frozenset so
# the two surfaces cannot drift (W114).
ALLOWED_ERROR_CLASSES = frozenset(
    {
        "exec_timeout",  # codex subprocess exceeded its budget
        "cli_failure",  # codex CLI exited non-zero / unparseable output
        "cli_version_mismatch",  # daemon version pin refused to exec (chaos row 8)
        "spawn_failure",  # subprocess could not be started
        "oversized_output",  # result exceeded the transport bound (chaos row 7)
        "empty_output",  # CLI exited 0 with nothing usable
        "policy_refusal",  # CLI-level refusal, no usable text
    }
)


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


# ──────────────────────────────────────────────────────────────────────────
# Circuit breaker (persisted on the gauge — shared across workers)
# ──────────────────────────────────────────────────────────────────────────


async def breaker_admits(conn: asyncpg.Connection) -> bool:
    """Admission check WITH the half-open state machine (S2 cross-family
    review, finding 3 — the first build returned True on open-past-cooldown
    without ever consuming the canary slot, so one failed canary left
    ``cooled_down`` permanently true and the breaker stopped breaking).

    closed      -> admit.
    half_open   -> deny (exactly one canary is already out).
    open        -> CAS open->half_open once the cooldown has elapsed; the
                   single CAS winner carries the canary. ``breaker_opened_at``
                   is deliberately NOT touched here: if the offer aborts
                   before launching (fence lost -> transaction rollback, see
                   ``offer_job``), the gauge reverts to open with its clock
                   intact and the next admission needs no fresh cooldown.
    A failed canary goes half_open->open with a NEW ``breaker_opened_at``
    (in ``record_breaker_result``), so each failed canary buys a full
    cooldown before the next one — the behavior the spec names.
    """
    row = await conn.fetchrow(
        "SELECT breaker_state FROM wa_broker_gauge WHERE id = 1",
    )
    if row is None:  # gauge not seeded yet -> broker has never spoken
        return False
    if row["breaker_state"] == "closed":
        return True
    if row["breaker_state"] == "half_open":
        # Orphan guard: a half_open gauge with no outstanding job whose
        # canary result never arrived (worker crashed between consume and
        # record). Demote to open with a FRESH cooldown — conservative,
        # never admit from here. Anchored on breaker_half_open_at — the
        # transition's OWN clock (migration 271) — NEVER on updated_at:
        # every claim_job poll refreshes updated_at, so a polling broker
        # kept the orphan threshold from ever maturing and half_open was
        # absorbing forever (Codex re-verdict, finding 2).
        await conn.execute(
            """
            UPDATE wa_broker_gauge
            SET breaker_state = 'open', breaker_opened_at = now(),
                breaker_half_open_at = NULL, updated_at = now()
            WHERE id = 1 AND breaker_state = 'half_open'
              AND breaker_half_open_at IS NOT NULL
              AND breaker_half_open_at
                  <= now() - ($1 * INTERVAL '1 second')
              AND NOT EXISTS (
                  SELECT 1 FROM broker_jobs
                  WHERE state IN ('offered', 'leased',
                                  'completed_pending_consume'))
            """,
            HALF_OPEN_ORPHAN_S,
        )
        return False
    cas = await conn.fetchrow(
        """
        UPDATE wa_broker_gauge
        SET breaker_state = 'half_open', breaker_half_open_at = now(),
            updated_at = now()
        WHERE id = 1 AND breaker_state = 'open'
          AND breaker_opened_at IS NOT NULL
          AND breaker_opened_at <= now() - ($1 * INTERVAL '1 second')
        RETURNING id
        """,
        BREAKER_OPEN_SECONDS,
    )
    return cas is not None


async def record_breaker_result(
    conn: asyncpg.Connection | asyncpg.Pool, *, success: bool, count: int = 1
) -> None:
    """Fold codex-leg outcomes into the shared breaker state.

    Every terminal serve transition folds HERE, by its transition owner, in
    the owner's own transaction (Codex re-verdict r2, finding 2):
    ``wait_for_job``'s deadline CAS and ``complete_job``'s two accepted
    branches each fold the outcome they committed, and the reaper folds only
    what IT expired — one fold per terminal outcome, no double count, no
    "the caller will remember to forward it" (scar family #2).

    The success path is GUARDED — it closes from half_open (canary success)
    and resets the streak from closed, but never touches an ``open`` gauge:
    a success arriving while open is a straggler leased before the trip, and
    the cooldown+canary discipline stays the only exit from open.

    The failure path is ONE atomic statement — increment, trip decision and
    half_open->open demotion together — so no offer can slip between "the
    count reached the threshold" and "the breaker opened" (finding 3's
    threshold race), and no second statement is needed for the failed-canary
    demotion. ``count`` lets the reaper report a batch of expiries in one
    call (finding 4).

    The failure path also takes the ADMISSION advisory xact lock before
    flipping state (Codex re-verdict, finding 3): ``offer_job`` holds that
    lock from its admission read to its transaction COMMIT, so an
    open-flip can no longer land between ``breaker_admits`` saying yes and
    the job INSERT committing — "no new admission after open" becomes a
    serialization fact, not a hope. A ``Pool`` argument is wrapped in its
    own transaction here; a bare ``Connection`` MUST already be inside one
    (the advisory xact lock would otherwise release at statement end) —
    the reaper's atomic fold is exactly that caller.
    """
    if isinstance(conn, asyncpg.Pool):
        async with conn.acquire() as leased_conn, leased_conn.transaction():
            await record_breaker_result(leased_conn, success=success, count=count)
        return
    if success:
        # Guarded: never close from 'open'. A success arriving while the
        # breaker is open is a STRAGGLER — a job leased before the trip —
        # and the failures that opened the breaker are fresher evidence;
        # letting it slam the state closed would bypass the cooldown+canary
        # discipline that is the one sanctioned exit from open. From
        # half_open this IS the canary succeeding (-> closed); from closed
        # it resets the consecutive-failure streak.
        await conn.execute(
            """
            INSERT INTO wa_broker_gauge
                (id, breaker_state, breaker_opened_at, breaker_half_open_at,
                 consecutive_failures, updated_at)
            VALUES (1, 'closed', NULL, NULL, 0, now())
            ON CONFLICT (id) DO UPDATE
            SET breaker_state = 'closed', breaker_opened_at = NULL,
                breaker_half_open_at = NULL, consecutive_failures = 0,
                updated_at = now()
            WHERE wa_broker_gauge.breaker_state <> 'open'
            """
        )
        return
    if count < 1:
        return
    await conn.execute(_ADMISSION_LOCK_SQL)
    row = await conn.fetchrow(
        """
        INSERT INTO wa_broker_gauge
            (id, consecutive_failures, breaker_state, breaker_opened_at,
             breaker_half_open_at, updated_at)
        VALUES (1, $2::int,
                CASE WHEN $2::int >= $1::int THEN 'open' ELSE 'closed' END,
                CASE WHEN $2::int >= $1::int THEN now() ELSE NULL END,
                NULL,
                now())
        ON CONFLICT (id) DO UPDATE
        SET consecutive_failures
                = wa_broker_gauge.consecutive_failures + $2::int,
            breaker_state = CASE
                WHEN wa_broker_gauge.breaker_state = 'half_open' THEN 'open'
                WHEN wa_broker_gauge.breaker_state = 'closed'
                     AND wa_broker_gauge.consecutive_failures + $2::int
                         >= $1::int THEN 'open'
                ELSE wa_broker_gauge.breaker_state END,
            breaker_opened_at = CASE
                WHEN wa_broker_gauge.breaker_state = 'half_open' THEN now()
                WHEN wa_broker_gauge.breaker_state = 'closed'
                     AND wa_broker_gauge.consecutive_failures + $2::int
                         >= $1::int THEN now()
                ELSE wa_broker_gauge.breaker_opened_at END,
            breaker_half_open_at = NULL,
            updated_at = now()
        RETURNING breaker_state, consecutive_failures
        """,
        BREAKER_TRIP_AFTER,
        count,
    )
    if row is not None and row["breaker_state"] == "open":
        logger.warning(
            "wa_broker: circuit breaker OPEN (%d consecutive failures; "
            "codex route disabled for %ds per cooldown)",
            row["consecutive_failures"],
            BREAKER_OPEN_SECONDS,
        )


async def _revert_canary_cas(conn: asyncpg.Connection) -> None:
    """Undo a ``breaker_admits`` open->half_open CAS when the offer aborts
    after admission WITHOUT creating a job (fence lost / leg already spent):
    early returns commit the offer transaction, so the CAS must be reverted
    explicitly or the canary slot is consumed by a non-offer. The CAS never
    touched ``breaker_opened_at``, so the original cooldown clock stands.
    Safe unconditionally: offers serialize on the admission lock, and a
    half_open state at this point can only be this transaction's own CAS —
    a PRIOR canary's half_open would have refused admission before the
    fence code ran.
    """
    await conn.execute(
        """
        UPDATE wa_broker_gauge
        SET breaker_state = 'open', breaker_half_open_at = NULL,
            updated_at = now()
        WHERE id = 1 AND breaker_state = 'half_open'
        """,
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

        depth = await conn.fetchval(
            "SELECT count(*) FROM broker_jobs WHERE state IN ('offered', 'leased')",
        )
        if int(depth or 0) >= MAX_DEPTH:
            return OfferResult(OfferOutcome.QUEUE_FULL)

        # Breaker LAST among the admission checks: breaker_admits may CAS
        # open->half_open (consuming the canary slot), so it must not run
        # when depth/liveness would refuse anyway. NOTE: the early returns
        # below COMMIT this transaction (only exceptions roll back), so the
        # post-admission failure exits explicitly revert the CAS via
        # _revert_canary_cas — a canary slot is only spent by an offer that
        # actually creates a job.
        if not await breaker_admits(conn):
            return OfferResult(OfferOutcome.BREAKER_OPEN)

        # Route marker, fenced on the outbox claim.
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
            await _revert_canary_cas(conn)
            return OfferResult(OfferOutcome.ALREADY_SPENT if already else OfferOutcome.FENCE_LOST)

        # SAVEPOINT around the INSERT (S2 cross-family review, finding 2):
        # a UniqueViolationError aborts the enclosing PostgreSQL transaction,
        # so catching it WITHOUT a savepoint would roll back the
        # generation_route marker written above — reporting ALREADY_SPENT
        # while leaving the durable fence NULL, exactly the historical hole
        # the marker exists to close (once retention removes the job row,
        # the outbox row could spend a second codex leg). The nested
        # transaction() is a savepoint here: the unique violation rolls back
        # only the INSERT, and the marker repair COMMITS with the outer
        # transaction.
        try:
            # The two payload casts are DELIBERATELY different (do not
            # unify): package is TEXT (migration 272 — a hash-sealed
            # envelope whose bytes must survive verbatim; jsonb would
            # normalize key order/whitespace and break package_hash for
            # every job), while evidence_inputs stays jsonb via
            # ::text::jsonb (no byte contract; the double cast keeps the
            # bind codec-agnostic under the production pool's jsonb codec).
            async with conn.transaction():
                job_id = await conn.fetchval(
                    """
                    INSERT INTO broker_jobs
                        (outbox_id, thread_id, mode, package, evidence_inputs,
                         package_hash, thread_epoch, deadline_at)
                    VALUES ($1, $2, 'serve', $3::text,
                            $4::text::jsonb, $5, $6,
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
            # owner, so honor its verdict rather than assume). The marker
            # written above survives the savepoint rollback and commits,
            # repairing the missing historical fence.
            await _revert_canary_cas(conn)
            return OfferResult(OfferOutcome.ALREADY_SPENT)

    logger.info(
        "wa_broker: offered job %s (outbox=%s thread=%s deadline=%ss)",
        job_id,
        outbox_id,
        thread_id,
        t_exec,
    )
    return OfferResult(OfferOutcome.OFFERED, job_id=job_id)


async def offer_client_job(
    conn: asyncpg.Connection,
    *,
    request_id: uuid.UUID,
    surface: str,
    package: str,
    package_hash: str,
    output_schema_version: str,
    deadline_s: int | None = None,
) -> OfferResult:
    """Offer one client-bot codex-broker job (I DUE BOT F1/F3,
    ``job_kind='client_answer_v1'``, migration 290).

    Sibling of ``offer_job`` for the WA-outbox leg, sharing the SAME table
    and the SAME admission/breaker machinery (F1: "do not create a second
    jobs table" — the broker is single-flight per seat regardless of which
    job_kind is asking, so depth/breaker accounting must stay unified) —
    but with NO wa_outbox fencing transaction. A client-bot ``BrainRequest``
    (``services/client_bot/contracts.py``) has no outbox row to fence
    against at all, and ``ClientBrainProviderRouter.route()`` calls a
    provider's ``generate()`` at most ONCE per request (one primary attempt,
    one fallback attempt, no retry ladder) — the WA leg's
    ``generation_route`` marker and its SAVEPOINT-guarded unique-violation
    handling exist ONLY to protect against the outbox WORKER's own retry
    ladder re-offering after a crash, a failure mode this call site cannot
    have. Consequently this function needs no savepoint: if the INSERT
    below raises for any reason, the enclosing ``async with
    conn.transaction()`` rolls back the WHOLE block automatically —
    including the breaker's own open->half_open CAS inside
    ``breaker_admits``, so the canary slot is never spent by a failed offer
    without a manual revert (contrast ``offer_job``'s explicit
    ``_revert_canary_cas`` calls, which exist only because ITS early-return
    paths COMMIT past a successful CAS).

    ``package`` is the caller's own hash-sealed wire envelope (a JSON
    string) — this function never introspects, logs, or re-serializes it
    (same discipline as ``offer_job``'s ``package``/``evidence_inputs``).
    ``deadline_s`` defaults to the shared ``deadline_seconds()`` (T_exec)
    when omitted; callers with a tighter request deadline (e.g. a
    ``BrainRequest.deadline_at`` already close) should pass the smaller of
    the two explicitly — this function does not know about request
    deadlines, only about the broker's own budget.
    """
    t_exec = deadline_s if deadline_s is not None else deadline_seconds()
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

        depth = await conn.fetchval(
            "SELECT count(*) FROM broker_jobs WHERE state IN ('offered', 'leased')",
        )
        if int(depth or 0) >= MAX_DEPTH:
            return OfferResult(OfferOutcome.QUEUE_FULL)

        # Breaker LAST, same admission order as offer_job (spec 2.1): a
        # CAS-consuming canary must never be spent when depth/liveness would
        # refuse the offer anyway.
        if not await breaker_admits(conn):
            return OfferResult(OfferOutcome.BREAKER_OPEN)

        job_id = await conn.fetchval(
            """
            INSERT INTO broker_jobs
                (job_kind, surface, request_id, mode, package,
                 package_hash, output_schema_version, deadline_at)
            VALUES ('client_answer_v1', $1, $2, 'serve', $3::text,
                    $4, $5, now() + ($6 * INTERVAL '1 second'))
            RETURNING job_id
            """,
            surface,
            request_id,
            package,
            package_hash,
            output_schema_version,
            t_exec,
        )

    logger.info(
        "wa_broker: offered client job %s (surface=%s deadline=%ss)",
        job_id,
        surface,
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
            # The CAS owner folds its own transition into the breaker, in the
            # SAME transaction (Codex re-verdict r2, finding 2): this is the
            # COMMON serve-expiry path — a live worker terminalizes the row
            # here, so the reaper never sees it, and before this fold the
            # breaker was blind to every deadline expiry a live worker
            # observed. Serve only: shadow expiries are housekeeping, exactly
            # as in the reaper's classification.
            async with pool.acquire() as cas_conn:
                async with cas_conn.transaction():
                    expired = await cas_conn.fetchrow(
                        """
                        UPDATE broker_jobs
                        SET state = 'expired', package = NULL,
                            evidence_inputs = NULL, result_text = NULL,
                            outcome = 'expired_deadline'
                        WHERE job_id = $1 AND state IN ('offered', 'leased')
                        RETURNING job_id, mode
                        """,
                        job_id,
                    )
                    if expired is not None and expired["mode"] == "serve":
                        await record_breaker_result(cas_conn, success=False)
            if expired is not None:
                return WaitResult(WaitOutcome.DEADLINE)
            # A /complete slid in between our read and the CAS — loop once
            # more to observe it.
            continue
        await asyncio.sleep(poll_seconds)


async def consume_result(conn: asyncpg.Connection, job_id: uuid.UUID) -> str | None:
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


async def discard_completion(conn: asyncpg.Connection, job_id: uuid.UUID, *, reason: str) -> None:
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
    # package is a TEXT column (migration 272, Codex re-verdict r4): the
    # envelope's bytes must survive offer->claim untouched so the broker's
    # hash verification against package_hash can ever hold — jsonb storage
    # normalized key order and whitespace, silently breaking the hash for
    # every package. TEXT also closes r2 finding 1 by construction: no jsonb
    # codec applies, so the row value is always the str the router's
    # ClaimResponse requires (a bare jsonb bind decoded to a dict under the
    # production codec and 500'd AFTER this lease UPDATE autocommitted).
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
        RETURNING job_id, fence_token, package, package_hash,
                  deadline_at, now() AS server_now
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
    # XOR, enforced HERE and not only at the router (S2 cross-family review,
    # finding 5): this is a reusable transport boundary that claims the
    # invariant, so a direct call with both None must not slide into the
    # success branch and mint a completed_pending_consume with a NULL result.
    if (result_text is None) == (error_class is None):
        raise ValueError("completion carries exactly one of result_text / error_class")
    # Closed vocabulary for the retained terminal field (finding 7): the
    # router validates the same set at the HTTP edge; this second copy of the
    # check guards direct callers of the reusable boundary.
    if error_class is not None and error_class not in ALLOWED_ERROR_CLASSES:
        raise ValueError("unknown error_class (not in transport vocabulary)")
    # Empty/whitespace output is a FAILURE wearing the success shape (Codex
    # re-verdict r6, finding 1): '' passes the XOR, would mint a
    # completed_pending_consume with nothing to send, and would fold
    # success=True — a half_open canary returning nothing would CLOSE the
    # breaker. The vocabulary already names this failure: empty_output.
    if result_text is not None and not result_text.strip():
        raise ValueError(
            "empty result_text is not a completion — report it as "
            "error_class='empty_output'"
        )
    # PostgreSQL TEXT cannot store U+0000 (Codex re-verdict r9, proven by
    # probe: CharacterNotInRepertoireError on the bind). Without this check
    # the completion UPDATE itself failed AFTER the guards passed — a 500
    # the broker retries identically until the lease deadline, turning one
    # poisoned output into a stuck job plus a breaker fold. The router
    # rejects the same shape at the HTTP edge (422); this copy guards
    # direct callers of the reusable boundary. error_class needs no check:
    # the closed vocabulary above already excludes NUL.
    if "\x00" in completion_key or (result_text is not None and "\x00" in result_text):
        raise ValueError(
            "NUL (U+0000) is not storable in TEXT — sanitize the output or "
            "report it as error_class='cli_failure'"
        )

    # Non-PII fingerprint of THIS attempt's payload, frozen on the row at
    # accept time (migration 273; Codex re-verdict r5, finding 2): the
    # replay check compares it, so the promised CONFLICT for "same
    # completion_key, different payload" is actually reachable — and it
    # survives consume_result NULLing result_text, so a late corrupted
    # retry conflicts instead of replaying even after consumption.
    completion_digest = (
        f"err:{error_class}"
        if error_class is not None
        else "ok:" + hashlib.sha256((result_text or "").encode("utf-8")).hexdigest()
    )

    # Each accepted CAS folds its own outcome into the breaker in the SAME
    # transaction (Codex re-verdict r2, finding 2): a typed failure that
    # commits leased->failed without folding is permanently invisible — the
    # reaper only accounts rows IT transitions and skips already-terminal
    # ones. Success folds too, or the breaker can never close: nothing else
    # in the transport ever records success, so consecutive_failures never
    # reset and a half_open canary's success never landed (the orphan guard
    # then demoted it back to open — open forever). Serve only, matching the
    # reaper's classification; shadow legs are housekeeping.
    if error_class is not None:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE broker_jobs
                SET state = 'failed', package = NULL, evidence_inputs = NULL,
                    result_text = NULL, completed_at = now(),
                    completion_key = $3, error_class = $4, exec_ms = $5,
                    completion_digest = $6, outcome = 'broker_failed'
                WHERE job_id = $1 AND fence_token = $2 AND state = 'leased'
                  AND deadline_at > now()
                RETURNING job_id, mode
                """,
                job_id,
                fence_token,
                completion_key,
                error_class,
                exec_ms,
                completion_digest,
            )
            if row is not None and row["mode"] == "serve":
                await record_breaker_result(conn, success=False)
    else:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE broker_jobs
                SET state = 'completed_pending_consume', result_text = $4,
                    completed_at = now(), completion_key = $3, exec_ms = $5,
                    completion_digest = $6
                WHERE job_id = $1 AND fence_token = $2 AND state = 'leased'
                  AND deadline_at > now()
                RETURNING job_id, mode
                """,
                job_id,
                fence_token,
                completion_key,
                result_text,
                exec_ms,
                completion_digest,
            )
            if row is not None and row["mode"] == "serve":
                await record_breaker_result(conn, success=True)
    if row is not None:
        return CompleteStatus.ACCEPTED

    # CAS missed. Same (completion_key, fence_token, payload fingerprint)
    # on the same job = the retry of a completion we already accepted (the
    # first response was lost in transit): idempotent 200. The replay check
    # compares the frozen completion_digest, NOT the live text — the
    # consumer may already have NULLed result_text, but the digest survives
    # (migration 273), so a corrupted retry that reuses key+fence with a
    # DIFFERENT payload gets the CONFLICT the contract promises instead of
    # a false REPLAY (Codex re-verdict r5, finding 2). Replay eligibility
    # REQUIRES the original fence and a post-acceptance state, and
    # 'expired' takes precedence over key equality (S2 cross-family
    # review, finding 6): a completion whose consumer died and was reaped
    # is GONE — its acceptance no longer stands, and answering REPLAY
    # would tell the broker its result was delivered.
    prior = await conn.fetchrow(
        """
        SELECT completion_key, fence_token, state, completion_digest
        FROM broker_jobs WHERE job_id = $1
        """,
        job_id,
    )
    if prior is None or prior["state"] == "expired":
        return CompleteStatus.GONE
    if prior["state"] in ("completed_pending_consume", "consumed", "failed"):
        if (
            prior["completion_key"] == completion_key
            and prior["fence_token"] == fence_token
            and prior["completion_digest"] == completion_digest
        ):
            return CompleteStatus.REPLAY
        return CompleteStatus.CONFLICT
    return CompleteStatus.GONE


# ──────────────────────────────────────────────────────────────────────────
# Reaper + retention (shared)
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class ReapResult:
    """Per-cause expiry counts (S2 cross-family review, finding 4): the
    aggregate mixed serve expiry, dead-consumer cleanup and shadow expiry,
    so no caller could reconstruct the breaker signal. Only ``serve_expired``
    is a codex-leg failure; the other two are housekeeping."""

    serve_expired: int = 0
    consumer_expired: int = 0
    shadow_expired: int = 0

    @property
    def total(self) -> int:
        return self.serve_expired + self.consumer_expired + self.shadow_expired


async def expire_stale_jobs(pool: asyncpg.Pool) -> ReapResult:
    """Expire whatever outlived its budget, NULLing payloads in the same
    UPDATE (spec 2): serve jobs past deadline_at (offered/leased), a
    completed_pending_consume whose consumer died (grace passed), and
    shadow jobs past their own expires_at (Kimi N1).

    Serve-mode deadline expiries are folded into the breaker HERE, not left
    to the caller (finding 4 + scar family #2 — a signal a caller must
    remember to forward is a signal that dies): if a worker crashes and the
    reaper becomes the only observer, repeated serve expiries still open the
    breaker. No double count: the worker's own ``wait_for_job`` CAS makes
    the row terminal, so the reaper never sees the expiries a live worker
    already observed and recorded.

    The dead-consumer predicate anchors on COALESCE(completed_at,
    created_at) (finding 8). Migration 274 (landed with PR-5) now makes a
    completed_pending_consume row WITHOUT completed_at unwritable at the
    schema, so the COALESCE is belt-and-braces for rows minted before 274
    — the reaper stays safe regardless of which side the row came from.

    Terminalization and the breaker fold run in ONE transaction (Codex
    re-verdict, finding 4): as separate statements, a crash between them
    made the expired jobs unfindable forever while their failures never
    reached the breaker — the fold was lost, the breaker stayed closed.
    Atomic: a crash before COMMIT leaves the jobs offered/leased and the
    next reaper tick observes them again.
    """
    async with pool.acquire() as conn, conn.transaction():
        rows = await conn.fetch(
            """
            UPDATE broker_jobs
            SET state = 'expired', package = NULL, evidence_inputs = NULL,
                result_text = NULL,
                outcome = COALESCE(outcome, 'expired_' || state)
            WHERE (mode = 'serve' AND state IN ('offered', 'leased')
                     AND deadline_at <= now())
               OR (state = 'completed_pending_consume'
                     AND COALESCE(completed_at, created_at)
                         <= now() - ($1 * INTERVAL '1 second'))
               OR (mode = 'shadow' AND state IN ('offered', 'leased')
                     AND expires_at IS NOT NULL AND expires_at <= now())
            RETURNING mode, outcome
            """,
            LEASE_TTL_S * 3,
        )
        result = ReapResult()
        for row in rows:
            if row["outcome"] == "expired_completed_pending_consume":
                result.consumer_expired += 1
            elif row["mode"] == "shadow":
                result.shadow_expired += 1
            else:
                result.serve_expired += 1
        if result.serve_expired:
            await record_breaker_result(
                conn, success=False, count=result.serve_expired
            )
    if result.total:
        logger.info(
            "wa_broker: reaper expired %d stale job(s) (serve=%d consumer=%d shadow=%d)",
            result.total,
            result.serve_expired,
            result.consumer_expired,
            result.shadow_expired,
        )
    return result


async def sweep_terminal_rows(pool: asyncpg.Pool) -> int:
    """Retention sweep: remove terminal rows past the 7-day TTL, then VERIFY
    the effect (spec 2 / scar family #2: a sweep that silently stops is how
    'DONE' retention turns out unenforced). Returns the number removed;
    logs an ERROR with a distinctive marker if the post-sweep count is not
    zero — that marker is the alarm hook.
    """
    # DELETE and the residue check run under ONE repeatable-read snapshot
    # (S2 cross-family review, finding 11): as separate autocommit
    # statements, a row turning terminal between them read as "SWEEP
    # INEFFECTIVE" though it was never eligible during the sweep — a false
    # alarm on the alarm hook. Under one snapshot the check sees exactly the
    # world the DELETE acted on, minus what it deleted: residue > 0 now
    # means the DELETE genuinely failed to remove an eligible row. (RR
    # serialization conflicts are not a practical concern here: nothing
    # updates week-old terminal rows.)
    async with pool.acquire() as conn:
        async with conn.transaction(isolation="repeatable_read"):
            result = await conn.execute(
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

            residue = await conn.fetchval(
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
