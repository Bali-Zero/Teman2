"""Tests for the wa_broker transport service (BOT-V4 S2, #4333).

Covers the worker-side leg (offer_job/wait_for_job/consume_result/
discard_completion), the shared circuit breaker persisted on
wa_broker_gauge (breaker_admits/record_breaker_result), and the
reaper/retention passes (expire_stale_jobs, sweep_terminal_rows). The
endpoint-side leg (claim_job/complete_job) is exercised mainly through the
router suite (mocked there) and the real-PG integration suite; the one
exception here is complete_job's blank-result_text refusal (r6), asserted
directly because it must fire BEFORE any SQL runs.

Updated for the S2 cross-family review fixes (2 BLOCKER + 7 MAJOR): the
breaker gained a half_open state (renamed breaker_allows -> breaker_admits),
record_breaker_result folds the trip/demotion/count logic into one atomic
statement, offer_job checks admission in gauge -> depth -> breaker order and
reverts a won canary CAS on any post-admission failure exit, the INSERT
runs in a savepoint so a unique violation cannot roll back the
generation_route marker, expire_stale_jobs now classifies expiries by cause
(serve/consumer/shadow) via RETURNING and folds serve expiries into the
breaker, and sweep_terminal_rows runs its DELETE + residue check inside one
repeatable-read transaction.

The mock connection is scripted, matching the house pattern from
test_wa_outbox_worker.py: fetchrow/fetchval/fetch/execute pop queued
results in call order (one independent queue per method), and every call
is recorded into `executed` as a uniform (sql, args) audit trail so a
fenced UPDATE done via `fetchrow(...RETURNING ...)` is just as assertable
as a plain `execute()` call. A queued item that is an exception instance is
RAISED instead of returned, so the same class can script asyncpg errors
(e.g. the UniqueViolationError offer_job must swallow into ALREADY_SPENT).
`acquire()` yields the SAME instance (so sweep_terminal_rows' acquired conn
and the caller's pool share one audit trail) and `transaction(isolation=...)`
accepts and ignores the isolation kwarg.

Functions taking `conn: asyncpg.Connection` (offer_job, breaker_admits,
record_breaker_result, consume_result, discard_completion) get a
ScriptedConn instance directly. Functions taking `pool: asyncpg.Pool`
(wait_for_job, expire_stale_jobs, sweep_terminal_rows) call
fetchrow/fetchval/fetch/execute/acquire directly on the pool (asyncpg.Pool
exposes those as convenience passthroughs) — the SAME ScriptedConn class
serves both roles since it implements that interface.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
import pytest

from backend.services.integrations import wa_broker

OUTBOX_ID = 501
THREAD_ID = 42
CLAIM_TOKEN = uuid.uuid4()
EXPECTED_STATUS = "claimed"
PACKAGE = '{"messages": []}'
EVIDENCE_INPUTS = '{"facts": []}'
PACKAGE_HASH = "hash-abc123"
THREAD_EPOCH = 7

# The offer_job post-admission failure exits (fence-lost/already-spent,
# unique-violation) unconditionally call _revert_canary_cas, whose WHERE
# clause is this exact, single-line, unambiguous substring — it never
# appears in the CAS-win statement (which sets breaker_state = 'half_open',
# a different clause) or the orphan-demote statement (whose WHERE clause is
# this same phrase, but that one is only reachable via breaker_admits
# itself when the gauge is ALREADY half_open, never as a side effect of
# offer_job's own revert call).
_REVERT_CANARY_WHERE = "WHERE id = 1 AND breaker_state = 'half_open'"


class ScriptedConn:
    def __init__(
        self,
        fetchrow_results: list[Any] | None = None,
        fetchval_results: list[Any] | None = None,
        execute_results: list[Any] | None = None,
        fetch_results: list[Any] | None = None,
    ) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self._fetchrow = list(fetchrow_results or [])
        self._fetchval = list(fetchval_results or [])
        self._execute = list(execute_results or [])
        self._fetch = list(fetch_results or [])

    async def execute(self, sql: str, *args: Any) -> str:
        self.executed.append((sql, args))
        if self._execute:
            result = self._execute.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result
        return "UPDATE 1"

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        self.executed.append((sql, args))
        if self._fetchrow:
            result = self._fetchrow.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result
        return None

    async def fetchval(self, sql: str, *args: Any) -> Any:
        self.executed.append((sql, args))
        if self._fetchval:
            result = self._fetchval.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result
        return None

    async def fetch(self, sql: str, *args: Any) -> list[Any]:
        self.executed.append((sql, args))
        if self._fetch:
            result = self._fetch.pop(0)
            if isinstance(result, BaseException):
                raise result
            return result
        return []

    def acquire(self) -> Any:
        """Pool.acquire() convenience — yields THIS SAME instance, so calls
        made on the acquired conn land in the one shared `executed` audit
        trail (matching production, where pool and acquired-conn resolve to
        a single physical connection for the lifetime of the `async with`)."""

        @asynccontextmanager
        async def _cm():
            yield self

        return _cm()

    def transaction(self, isolation: str | None = None) -> Any:
        @asynccontextmanager
        async def _cm():
            yield

        return _cm()

    def sql_contains(self, needle: str) -> bool:
        return any(needle in sql for sql, _ in self.executed)

    def sql_with_args(self, needle: str) -> list[tuple[str, tuple[Any, ...]]]:
        return [(s, a) for s, a in self.executed if needle in s]


def _offer_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "outbox_id": OUTBOX_ID,
        "thread_id": THREAD_ID,
        "claim_token": CLAIM_TOKEN,
        "outbox_expected_status": EXPECTED_STATUS,
        "package": PACKAGE,
        "evidence_inputs": EVIDENCE_INPUTS,
        "package_hash": PACKAGE_HASH,
        "thread_epoch": THREAD_EPOCH,
    }
    kwargs.update(overrides)
    return kwargs


# ── offer_job ────────────────────────────────────────────────────────────
# Admission order is gauge liveness -> depth -> breaker (breaker LAST, so a
# CAS-consuming canary is never spent when depth/liveness would refuse
# anyway). fetchrow/fetchval are independent queues popped in per-method
# call order, so queuing order here must match the call order WITHIN each
# method, not the interleaving between them.


@pytest.mark.asyncio
async def test_offer_job_happy_path_offers_fences_and_inserts() -> None:
    job_id = uuid.uuid4()
    conn = ScriptedConn(
        fetchrow_results=[
            {"broker_alive": True},  # gauge liveness
            {"breaker_state": "closed"},  # breaker_admits -> True, no CAS
            {"id": OUTBOX_ID},  # fenced UPDATE RETURNING id
        ],
        fetchval_results=[
            0,  # admission depth
            job_id,  # INSERT ... RETURNING job_id (inside the savepoint)
        ],
    )

    result = await wa_broker.offer_job(conn, **_offer_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.OFFERED
    assert result.job_id == job_id

    # advisory-lock statement ran, first thing in the transaction
    assert conn.executed[0][0] == wa_broker._ADMISSION_LOCK_SQL

    update_calls = conn.sql_with_args("UPDATE wa_outbox SET generation_route")
    assert update_calls, "expected the fenced wa_outbox UPDATE to run"
    update_sql, update_args = update_calls[0]
    assert "claim_token = $2" in update_sql
    assert "status = $3" in update_sql
    assert "generation_route IS NULL" in update_sql
    assert update_args == (OUTBOX_ID, CLAIM_TOKEN, EXPECTED_STATUS)

    insert_calls = conn.sql_with_args("INSERT INTO broker_jobs")
    assert insert_calls, "expected the job INSERT to run"
    insert_sql, insert_args = insert_calls[0]
    assert insert_args == (
        OUTBOX_ID,
        THREAD_ID,
        PACKAGE,
        EVIDENCE_INPUTS,
        PACKAGE_HASH,
        THREAD_EPOCH,
        wa_broker.deadline_seconds(),
    )

    # the INSERT ran after the fenced UPDATE, on the same connection — i.e.
    # inside the same `async with conn.transaction()` block.
    assert conn.executed.index(insert_calls[0]) > conn.executed.index(update_calls[0])

    # no post-admission failure occurred, so the canary CAS revert must
    # never have run.
    assert not conn.sql_with_args(_REVERT_CANARY_WHERE)


@pytest.mark.asyncio
async def test_offer_job_broker_absent_when_gauge_missing() -> None:
    conn = ScriptedConn(fetchrow_results=[None])

    result = await wa_broker.offer_job(conn, **_offer_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.BROKER_ABSENT
    assert result.job_id is None
    assert not conn.sql_contains("UPDATE wa_outbox SET generation_route")


@pytest.mark.asyncio
async def test_offer_job_broker_absent_when_gauge_stale() -> None:
    conn = ScriptedConn(fetchrow_results=[{"broker_alive": False}])

    result = await wa_broker.offer_job(conn, **_offer_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.BROKER_ABSENT
    assert not conn.sql_contains("UPDATE wa_outbox SET generation_route")


@pytest.mark.asyncio
async def test_offer_job_queue_full_when_depth_at_cap() -> None:
    """Depth is checked BEFORE the breaker (new order) — QUEUE_FULL must
    short-circuit without ever consulting breaker_admits."""
    conn = ScriptedConn(
        fetchrow_results=[{"broker_alive": True}],
        fetchval_results=[wa_broker.MAX_DEPTH],  # depth >= MAX_DEPTH
    )

    result = await wa_broker.offer_job(conn, **_offer_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.QUEUE_FULL
    assert not conn.sql_contains("UPDATE wa_outbox SET generation_route")
    # lock + gauge fetchrow + depth fetchval only — the breaker was never touched
    assert len(conn.executed) == 3


@pytest.mark.asyncio
async def test_offer_job_admits_when_depth_below_cap() -> None:
    """INNOCENCE for the depth cap: depth one below MAX_DEPTH must still be
    admitted — the boundary is >=, not >."""
    job_id = uuid.uuid4()
    conn = ScriptedConn(
        fetchrow_results=[
            {"broker_alive": True},
            {"breaker_state": "closed"},
            {"id": OUTBOX_ID},
        ],
        fetchval_results=[wa_broker.MAX_DEPTH - 1, job_id],
    )

    result = await wa_broker.offer_job(conn, **_offer_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.OFFERED


@pytest.mark.asyncio
async def test_offer_job_breaker_open_blocks_offer() -> None:
    conn = ScriptedConn(
        fetchrow_results=[
            {"broker_alive": True},  # gauge
            {"breaker_state": "open"},  # breaker_admits: state check
            None,  # breaker_admits: CAS fails (not cooled)
        ],
        fetchval_results=[0],  # depth, checked before breaker
    )

    result = await wa_broker.offer_job(conn, **_offer_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.BREAKER_OPEN
    assert not conn.sql_contains("UPDATE wa_outbox SET generation_route")
    # breaker_admits itself refused — no canary was ever consumed, so
    # offer_job's own revert call site is never reached.
    assert not conn.sql_with_args(_REVERT_CANARY_WHERE)


@pytest.mark.asyncio
async def test_offer_job_already_spent_when_fence_lost_but_marker_set() -> None:
    conn = ScriptedConn(
        fetchrow_results=[
            {"broker_alive": True},
            {"breaker_state": "closed"},  # breaker admits
            None,  # fenced UPDATE RETURNING id -> 0 rows
        ],
        fetchval_results=[
            0,  # depth
            True,  # generation_route IS NOT NULL -> marker already set
        ],
    )

    result = await wa_broker.offer_job(conn, **_offer_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.ALREADY_SPENT
    assert result.job_id is None
    assert not conn.sql_contains("INSERT INTO broker_jobs")
    # post-admission failure exit -> the won canary CAS must be reverted.
    assert conn.sql_with_args(_REVERT_CANARY_WHERE)


@pytest.mark.asyncio
async def test_offer_job_fence_lost_when_marker_not_set() -> None:
    conn = ScriptedConn(
        fetchrow_results=[
            {"broker_alive": True},
            {"breaker_state": "closed"},
            None,
        ],
        fetchval_results=[0, False],  # depth, generation_route IS NOT NULL -> False
    )

    result = await wa_broker.offer_job(conn, **_offer_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.FENCE_LOST
    assert not conn.sql_contains("INSERT INTO broker_jobs")
    assert conn.sql_with_args(_REVERT_CANARY_WHERE)


@pytest.mark.asyncio
async def test_offer_job_already_spent_on_insert_unique_violation() -> None:
    """The INSERT runs inside a savepoint (S2 finding 2): the unique
    violation must roll back ONLY the INSERT, never the generation_route
    marker written just before it — so the marker UPDATE must still be
    present in the audit trail even though the statement after it raised.
    The canary CAS must also be reverted, same as the other post-admission
    failure exits."""
    conn = ScriptedConn(
        fetchrow_results=[
            {"broker_alive": True},
            {"breaker_state": "closed"},
            {"id": OUTBOX_ID},  # fenced UPDATE succeeds this time
        ],
        fetchval_results=[
            0,  # depth
            asyncpg.UniqueViolationError(
                'duplicate key value violates unique constraint "uq_broker_jobs_serve_outbox"'
            ),
        ],
    )

    result = await wa_broker.offer_job(conn, **_offer_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.ALREADY_SPENT
    assert result.job_id is None

    update_calls = conn.sql_with_args("UPDATE wa_outbox SET generation_route")
    assert update_calls, (
        "the generation_route marker UPDATE must survive the savepoint "
        "rollback of the failing INSERT"
    )
    assert conn.sql_with_args(_REVERT_CANARY_WHERE)


# ── offer_client_job (I DUE BOT F1/F3, migration 290) ───────────────────────
# Same admission order as offer_job (gauge -> depth -> breaker), but NO
# wa_outbox fencing UPDATE and no savepoint — a client-bot request has no
# outbox row and no retry ladder to protect against (see the function's own
# docstring). An INSERT failure here must propagate rather than being
# swallowed into a typed OfferResult, since there is no "already spent"
# collision this call site is meant to recover from.

REQUEST_ID = uuid.uuid4()
SURFACE = "whatsapp"
CLIENT_PACKAGE = '{"query": "hello"}'
CLIENT_PACKAGE_HASH = "hash-client-abc123"
OUTPUT_SCHEMA_VERSION = "1.0"


def _offer_client_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "request_id": REQUEST_ID,
        "surface": SURFACE,
        "package": CLIENT_PACKAGE,
        "package_hash": CLIENT_PACKAGE_HASH,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
    }
    kwargs.update(overrides)
    return kwargs


@pytest.mark.asyncio
async def test_offer_client_job_happy_path_inserts_no_outbox_fence() -> None:
    job_id = uuid.uuid4()
    conn = ScriptedConn(
        fetchrow_results=[
            {"broker_alive": True},  # gauge liveness
            {"breaker_state": "closed"},  # breaker_admits -> True, no CAS
        ],
        fetchval_results=[
            0,  # admission depth
            job_id,  # INSERT ... RETURNING job_id
        ],
    )

    result = await wa_broker.offer_client_job(conn, **_offer_client_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.OFFERED
    assert result.job_id == job_id

    # No wa_outbox fencing UPDATE — this leg has no outbox row to fence.
    assert not conn.sql_contains("UPDATE wa_outbox")

    insert_calls = conn.sql_with_args("INSERT INTO broker_jobs")
    assert insert_calls, "expected the job INSERT to run"
    insert_sql, insert_args = insert_calls[0]
    assert "'client_answer_v1'" in insert_sql
    assert insert_args == (
        SURFACE,
        REQUEST_ID,
        CLIENT_PACKAGE,
        CLIENT_PACKAGE_HASH,
        OUTPUT_SCHEMA_VERSION,
        wa_broker.deadline_seconds(),
    )


@pytest.mark.asyncio
async def test_offer_client_job_respects_explicit_deadline_s() -> None:
    job_id = uuid.uuid4()
    conn = ScriptedConn(
        fetchrow_results=[{"broker_alive": True}, {"breaker_state": "closed"}],
        fetchval_results=[0, job_id],
    )

    result = await wa_broker.offer_client_job(
        conn, **_offer_client_kwargs(deadline_s=5)
    )

    assert result.outcome is wa_broker.OfferOutcome.OFFERED
    insert_sql, insert_args = conn.sql_with_args("INSERT INTO broker_jobs")[0]
    assert insert_args[-1] == 5


@pytest.mark.asyncio
async def test_offer_client_job_broker_absent_when_gauge_stale() -> None:
    """Behavioral requirement (research capture §2.5):
    codex_broker_heartbeat_age_seconds > 45s -> mark host offline, never
    offer. Shares the exact same gauge-liveness query as offer_job."""
    conn = ScriptedConn(fetchrow_results=[{"broker_alive": False}])

    result = await wa_broker.offer_client_job(conn, **_offer_client_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.BROKER_ABSENT
    assert result.job_id is None
    assert not conn.sql_contains("INSERT INTO broker_jobs")


@pytest.mark.asyncio
async def test_offer_client_job_broker_absent_when_gauge_missing() -> None:
    conn = ScriptedConn(fetchrow_results=[None])

    result = await wa_broker.offer_client_job(conn, **_offer_client_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.BROKER_ABSENT


@pytest.mark.asyncio
async def test_offer_client_job_queue_full_when_depth_at_cap() -> None:
    """Behavioral requirement (research capture §2.5):
    codex_broker_queue_depth >= 1 -> bypass Codex, never grow the queue.
    Shares the exact same MAX_DEPTH admission check as offer_job — a
    client-bot job and a WA job compete for the SAME single-flight slot
    (F3: 'queue depth 1' is a broker-wide budget)."""
    conn = ScriptedConn(
        fetchrow_results=[{"broker_alive": True}],
        fetchval_results=[wa_broker.MAX_DEPTH],
    )

    result = await wa_broker.offer_client_job(conn, **_offer_client_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.QUEUE_FULL
    assert not conn.sql_contains("INSERT INTO broker_jobs")


@pytest.mark.asyncio
async def test_offer_client_job_breaker_open_blocks_offer() -> None:
    conn = ScriptedConn(
        fetchrow_results=[
            {"broker_alive": True},  # gauge
            {"breaker_state": "open"},  # breaker_admits: state check
            None,  # breaker_admits: CAS fails (not cooled)
        ],
        fetchval_results=[0],
    )

    result = await wa_broker.offer_client_job(conn, **_offer_client_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.BREAKER_OPEN
    assert not conn.sql_contains("INSERT INTO broker_jobs")


@pytest.mark.asyncio
async def test_offer_client_job_insert_failure_propagates_not_swallowed() -> None:
    """No savepoint, no ALREADY_SPENT recovery path for this leg (unlike
    offer_job): an INSERT failure here is a genuine, uncertain fault and
    must propagate so the caller (the provider adapter) can classify it as
    such, rather than being silently absorbed into a typed OfferResult that
    would mis-imply a normal, recoverable outcome."""
    conn = ScriptedConn(
        fetchrow_results=[{"broker_alive": True}, {"breaker_state": "closed"}],
        fetchval_results=[0, RuntimeError("db exploded")],
    )

    with pytest.raises(RuntimeError, match="db exploded"):
        await wa_broker.offer_client_job(conn, **_offer_client_kwargs())


# ── wait_for_job ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wait_for_job_completed_pending_consume_observed() -> None:
    pool = ScriptedConn(
        fetchrow_results=[
            {"state": "completed_pending_consume", "error_class": None, "deadline_passed": False},
        ],
    )

    result = await wa_broker.wait_for_job(pool, uuid.uuid4(), poll_seconds=0)

    assert result.outcome is wa_broker.WaitOutcome.COMPLETED
    assert result.error_class is None


@pytest.mark.asyncio
async def test_wait_for_job_failed_passes_error_class_through() -> None:
    pool = ScriptedConn(
        fetchrow_results=[
            {"state": "failed", "error_class": "exec_timeout", "deadline_passed": False},
        ],
    )

    result = await wa_broker.wait_for_job(pool, uuid.uuid4(), poll_seconds=0)

    assert result.outcome is wa_broker.WaitOutcome.FAILED
    assert result.error_class == "exec_timeout"


@pytest.mark.asyncio
async def test_wait_for_job_deadline_cas_expires_and_nulls_payload() -> None:
    job_id = uuid.uuid4()
    pool = ScriptedConn(
        fetchrow_results=[
            {"state": "offered", "error_class": None, "deadline_passed": True},
            {"job_id": job_id, "mode": "serve"},  # expiry CAS succeeded
        ],
    )

    result = await wa_broker.wait_for_job(pool, job_id, poll_seconds=0)

    assert result.outcome is wa_broker.WaitOutcome.DEADLINE
    cas_sql, cas_args = pool.executed[1]
    assert "state = 'expired'" in cas_sql
    assert "package = NULL" in cas_sql
    assert "evidence_inputs = NULL" in cas_sql
    assert "result_text = NULL" in cas_sql
    assert cas_args == (job_id,)
    # The CAS owner folds its own serve expiry into the breaker, in the same
    # transaction (Codex re-verdict r2, finding 2): lock, then the failure
    # fold. Before this, the COMMON path — a live worker observing its own
    # deadline — never reached the breaker at all.
    assert len(pool.executed) == 4
    lock_sql, _ = pool.executed[2]
    assert "pg_advisory_xact_lock" in lock_sql
    fold_sql, fold_args = pool.executed[3]
    assert "consecutive_failures" in fold_sql
    assert fold_args == (wa_broker.BREAKER_TRIP_AFTER, 1)


@pytest.mark.asyncio
async def test_wait_for_job_shadow_deadline_expiry_does_not_fold() -> None:
    """INNOCENCE twin: a shadow-mode expiry is housekeeping (same
    classification the reaper uses) — terminalized, never folded."""
    job_id = uuid.uuid4()
    pool = ScriptedConn(
        fetchrow_results=[
            {"state": "offered", "error_class": None, "deadline_passed": True},
            {"job_id": job_id, "mode": "shadow"},
        ],
    )

    result = await wa_broker.wait_for_job(pool, job_id, poll_seconds=0)

    assert result.outcome is wa_broker.WaitOutcome.DEADLINE
    assert len(pool.executed) == 2  # poll + CAS, no lock, no fold


@pytest.mark.asyncio
async def test_wait_for_job_deadline_cas_lost_race_then_observes_completion() -> None:
    """A /complete slid in between our SELECT and the expiry CAS: the CAS
    matches zero rows, so the loop goes around once more instead of
    reporting a false DEADLINE for a job that just completed."""
    job_id = uuid.uuid4()
    pool = ScriptedConn(
        fetchrow_results=[
            {"state": "offered", "error_class": None, "deadline_passed": True},
            None,  # expiry CAS -> 0 rows, a /complete slid in
            {"state": "completed_pending_consume", "error_class": None, "deadline_passed": False},
        ],
    )

    result = await wa_broker.wait_for_job(pool, job_id, poll_seconds=0)

    assert result.outcome is wa_broker.WaitOutcome.COMPLETED
    assert len(pool.executed) == 3


@pytest.mark.asyncio
async def test_wait_for_job_row_vanished_treated_as_deadline() -> None:
    pool = ScriptedConn(fetchrow_results=[None])

    result = await wa_broker.wait_for_job(pool, uuid.uuid4(), poll_seconds=0)

    assert result.outcome is wa_broker.WaitOutcome.DEADLINE


# ── consume_result ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_consume_result_returns_old_text_and_nulls_payload_in_one_statement() -> None:
    job_id = uuid.uuid4()
    conn = ScriptedConn(fetchrow_results=[{"result_text": "the generated reply"}])

    result = await wa_broker.consume_result(conn, job_id)

    assert result == "the generated reply"
    sql, args = conn.executed[0]
    assert "state = 'consumed'" in sql
    assert "package = NULL" in sql
    assert "evidence_inputs = NULL" in sql
    assert "result_text = NULL" in sql
    assert args == (job_id,)


@pytest.mark.asyncio
async def test_consume_result_returns_none_when_cas_misses() -> None:
    conn = ScriptedConn(fetchrow_results=[None])

    result = await wa_broker.consume_result(conn, uuid.uuid4())

    assert result is None


# ── discard_completion ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discard_completion_records_typed_reason_and_nulls_payload() -> None:
    job_id = uuid.uuid4()
    conn = ScriptedConn()

    await wa_broker.discard_completion(conn, job_id, reason="thread_epoch_drift")

    sql, args = conn.executed[0]
    assert "state = 'consumed'" in sql
    assert "package = NULL" in sql
    assert "evidence_inputs = NULL" in sql
    assert "result_text = NULL" in sql
    assert args == (job_id, "discarded_thread_epoch_drift")


# ── circuit breaker: breaker_admits (half-open state machine) ──────────────


@pytest.mark.asyncio
async def test_breaker_admits_when_closed() -> None:
    conn = ScriptedConn(fetchrow_results=[{"breaker_state": "closed"}])

    assert await wa_broker.breaker_admits(conn) is True
    assert len(conn.executed) == 1  # single state-check fetchrow, no CAS needed


@pytest.mark.asyncio
async def test_breaker_denies_when_gauge_never_seeded() -> None:
    conn = ScriptedConn(fetchrow_results=[None])

    assert await wa_broker.breaker_admits(conn) is False


@pytest.mark.asyncio
async def test_breaker_denies_and_demotes_orphaned_half_open() -> None:
    """GUILT: half_open ALWAYS denies — exactly one canary is already out —
    and it must additionally run the orphan-demote UPDATE, otherwise a
    canary whose worker crashed between consuming the result and recording
    the outcome leaves the breaker stuck half-open (and the codex route
    dark) forever."""
    conn = ScriptedConn(fetchrow_results=[{"breaker_state": "half_open"}])

    result = await wa_broker.breaker_admits(conn)

    assert result is False
    demote_calls = conn.sql_with_args("breaker_state = 'half_open'")
    assert demote_calls, "expected the orphan-demote UPDATE to run"
    sql, args = demote_calls[0]
    assert "breaker_state = 'open', breaker_opened_at = now()" in sql
    assert "NOT EXISTS" in sql
    # The orphan window anchors on the transition's OWN clock — NEVER on
    # updated_at, which every claim_job poll refreshes (a polling broker
    # kept the threshold from ever maturing; Codex re-verdict, finding 2).
    # Whitespace-normalized: the raw SQL wraps across lines, and a bare
    # substring check on the pretty-printed text passes vacuously when the
    # anchor column and the comparator sit on different lines (mutation run
    # 2026-08-19 proved the un-normalized form blind to exactly the
    # regression it exists to catch).
    flat_sql = " ".join(sql.split())
    assert "breaker_half_open_at <= now()" in flat_sql
    assert "updated_at <=" not in flat_sql
    assert args == (wa_broker.HALF_OPEN_ORPHAN_S,)


@pytest.mark.asyncio
async def test_breaker_denies_when_open_and_cas_loses() -> None:
    """GUILT: past-open but not-yet-cooled — the CAS attempt runs but
    matches zero rows, so admission is still refused. The CAS also stamps
    breaker_half_open_at (the orphan guard's anchor — finding 2)."""
    conn = ScriptedConn(fetchrow_results=[{"breaker_state": "open"}, None])

    assert await wa_broker.breaker_admits(conn) is False
    cas_calls = conn.sql_with_args(
        "SET breaker_state = 'half_open', breaker_half_open_at = now()"
    )
    assert cas_calls
    _, args = cas_calls[0]
    assert args == (wa_broker.BREAKER_OPEN_SECONDS,)


@pytest.mark.asyncio
async def test_breaker_admits_when_open_and_cas_wins() -> None:
    """INNOCENCE: past cooldown, the CAS wins and the single canary slot is
    admitted."""
    conn = ScriptedConn(fetchrow_results=[{"breaker_state": "open"}, {"id": 1}])

    assert await wa_broker.breaker_admits(conn) is True


# ── circuit breaker: record_breaker_result ──────────────────────────────────


@pytest.mark.asyncio
async def test_record_breaker_result_success_resets_to_closed_but_never_from_open() -> None:
    """The success upsert must carry the straggler guard IN THE STATEMENT: a
    success arriving while the breaker is open belongs to a job leased
    before the trip, and closing on it would bypass the cooldown+canary
    discipline. (The behavioral proof runs on real PG; this pins the guard's
    presence so a 'simplifying' rewrite cannot drop it.)"""
    conn = ScriptedConn()

    await wa_broker.record_breaker_result(conn, success=True)

    assert len(conn.executed) == 1
    sql, args = conn.executed[0]
    flat_sql = " ".join(sql.split())
    assert "breaker_state = 'closed'" in flat_sql
    assert "consecutive_failures = 0" in flat_sql
    assert "WHERE wa_broker_gauge.breaker_state <> 'open'" in flat_sql
    assert args == ()


@pytest.mark.asyncio
async def test_record_breaker_result_count_below_one_issues_no_sql() -> None:
    """INNOCENCE: a caller passing count=0 (e.g. expire_stale_jobs with zero
    serve expiries in a batch) must not touch the database at all."""
    conn = ScriptedConn()

    await wa_broker.record_breaker_result(conn, success=False, count=0)

    assert conn.executed == []


@pytest.mark.asyncio
async def test_record_breaker_result_failure_is_one_statement_and_logs_only_when_open(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """GUILT + INNOCENCE together: the failure path is the ADMISSION
    advisory lock followed by ONE atomic INSERT..ON CONFLICT..RETURNING per
    call — the lock serializes the open-flip against in-flight offers
    (Codex re-verdict, finding 3: without it an offer admitted before the
    third failure could still create a job after the breaker opened), and
    the CASE logic (threshold trip, half_open->open demotion, count
    folding) runs entirely DB-side, so this test cannot re-derive it; it
    asserts the WIRING: lock-then-INSERT per call, and the WARNING log
    tracks the RETURNED state (never a locally-recomputed count) — silent
    for 'closed', loud for 'open'."""
    conn = ScriptedConn(
        fetchrow_results=[
            {"breaker_state": "closed", "consecutive_failures": 1},
            {"breaker_state": "closed", "consecutive_failures": 2},
            {"breaker_state": "open", "consecutive_failures": 3},
        ],
    )

    with caplog.at_level(logging.WARNING, logger="backend.services.integrations.wa_broker"):
        await wa_broker.record_breaker_result(conn, success=False)
        assert not any("circuit breaker OPEN" in r.message for r in caplog.records)

        await wa_broker.record_breaker_result(conn, success=False)
        assert not any("circuit breaker OPEN" in r.message for r in caplog.records)

        await wa_broker.record_breaker_result(conn, success=False)
        assert any("circuit breaker OPEN" in r.message for r in caplog.records)

    assert len(conn.executed) == 6
    locks = conn.executed[0::2]
    inserts = conn.executed[1::2]
    for sql, args in locks:
        assert "pg_advisory_xact_lock" in sql
        assert args == ()
    for sql, args in inserts:
        assert "INSERT INTO wa_broker_gauge" in sql
        assert "RETURNING breaker_state, consecutive_failures" in sql
        assert args == (wa_broker.BREAKER_TRIP_AFTER, 1)


@pytest.mark.asyncio
async def test_record_breaker_result_folds_a_batch_count_into_one_call() -> None:
    """count lets a batch of expiries (the reaper) fold into ONE statement
    (after the admission lock) instead of looping record_breaker_result
    once per row (finding 4)."""
    conn = ScriptedConn(
        fetchrow_results=[{"breaker_state": "open", "consecutive_failures": 5}],
    )

    await wa_broker.record_breaker_result(conn, success=False, count=5)

    assert len(conn.executed) == 2
    lock_sql, lock_args = conn.executed[0]
    assert "pg_advisory_xact_lock" in lock_sql
    assert lock_args == ()
    _, args = conn.executed[1]
    assert args == (wa_broker.BREAKER_TRIP_AFTER, 5)


# ── expire_stale_jobs (reaper) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_expire_stale_jobs_classifies_by_outcome_and_mode_and_folds_breaker() -> None:
    pool = ScriptedConn(
        fetch_results=[
            [
                {"mode": "serve", "outcome": "expired_offered"},
                {"mode": "serve", "outcome": "expired_leased"},
                {"mode": "serve", "outcome": "expired_completed_pending_consume"},
                {"mode": "shadow", "outcome": "expired_offered"},
            ]
        ],
        # the nested record_breaker_result(success=False, count=2) call
        fetchrow_results=[{"breaker_state": "open", "consecutive_failures": 2}],
    )

    result = await wa_broker.expire_stale_jobs(pool)

    assert result.serve_expired == 2
    assert result.consumer_expired == 1
    assert result.shadow_expired == 1
    assert result.total == 4

    fetch_sql, fetch_args = pool.executed[0]
    assert "COALESCE(completed_at, created_at)" in fetch_sql
    assert "RETURNING mode, outcome" in fetch_sql
    assert fetch_args == (wa_broker.LEASE_TTL_S * 3,)

    # the breaker was folded with the SERVE count only (2), never the total (4)
    breaker_calls = pool.sql_with_args("INSERT INTO wa_broker_gauge")
    assert breaker_calls
    _, breaker_args = breaker_calls[0]
    assert breaker_args == (wa_broker.BREAKER_TRIP_AFTER, 2)


@pytest.mark.asyncio
async def test_expire_stale_jobs_does_not_touch_breaker_without_serve_expiries() -> None:
    """INNOCENCE: consumer/shadow housekeeping expiries are not codex-leg
    failures — the breaker must stay untouched when serve_expired == 0."""
    pool = ScriptedConn(
        fetch_results=[
            [
                {"mode": "serve", "outcome": "expired_completed_pending_consume"},
                {"mode": "shadow", "outcome": "expired_offered"},
            ]
        ],
    )

    result = await wa_broker.expire_stale_jobs(pool)

    assert result.serve_expired == 0
    assert result.consumer_expired == 1
    assert result.shadow_expired == 1
    assert not pool.sql_with_args("INSERT INTO wa_broker_gauge")


@pytest.mark.asyncio
async def test_expire_stale_jobs_empty_reap_is_a_no_op() -> None:
    pool = ScriptedConn(fetch_results=[[]])

    result = await wa_broker.expire_stale_jobs(pool)

    assert result.total == 0
    assert len(pool.executed) == 1  # only the RETURNING fetch — no breaker call


# ── sweep_terminal_rows (retention) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_sweep_terminal_rows_removed_count_no_error_when_residue_zero(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pool = ScriptedConn(execute_results=["DELETE 2"], fetchval_results=[0])

    with caplog.at_level(logging.ERROR, logger="backend.services.integrations.wa_broker"):
        removed = await wa_broker.sweep_terminal_rows(pool)

    assert removed == 2
    assert not any("RETENTION SWEEP INEFFECTIVE" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_sweep_terminal_rows_logs_error_marker_when_residue_remains(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pool = ScriptedConn(execute_results=["DELETE 2"], fetchval_results=[5])

    with caplog.at_level(logging.ERROR, logger="backend.services.integrations.wa_broker"):
        removed = await wa_broker.sweep_terminal_rows(pool)

    assert removed == 2
    assert any("RETENTION SWEEP INEFFECTIVE" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_complete_job_refuses_blank_result_text_before_any_sql() -> None:
    """Codex re-verdict r6, finding 1 — the reusable boundary enforces the
    same rule as the HTTP edge: blank output is a failure wearing the
    success shape (it would fold success=True and close a half_open
    canary's breaker). Refused BEFORE any SQL runs."""
    conn = ScriptedConn()

    for blank in ("", "   ", "\n\t"):
        with pytest.raises(ValueError, match="empty_output"):
            await wa_broker.complete_job(
                conn,
                job_id=uuid.uuid4(),
                fence_token=uuid.uuid4(),
                completion_key="key-blank",
                result_text=blank,
                error_class=None,
                exec_ms=1,
            )
    assert conn.executed == []


@pytest.mark.asyncio
async def test_complete_job_refuses_nul_before_any_sql() -> None:
    """GUILT (Codex re-verdict r9): PostgreSQL TEXT cannot store U+0000
    (proven by probe: CharacterNotInRepertoireError on the bind), so a NUL
    that reaches the UPDATE becomes a 500 the broker retries identically
    until the lease deadline — a stuck job plus a breaker fold. The
    reusable boundary refuses it BEFORE any SQL, in both string inputs."""
    conn = ScriptedConn()

    with pytest.raises(ValueError, match="NUL"):
        await wa_broker.complete_job(
            conn,
            job_id=uuid.uuid4(),
            fence_token=uuid.uuid4(),
            completion_key="key-nul-1",
            result_text="answer\x00tail",
            error_class=None,
            exec_ms=1,
        )
    with pytest.raises(ValueError, match="NUL"):
        await wa_broker.complete_job(
            conn,
            job_id=uuid.uuid4(),
            fence_token=uuid.uuid4(),
            completion_key="key\x00nul-2",
            result_text="a real answer",
            error_class=None,
            exec_ms=1,
        )
    assert conn.executed == []
