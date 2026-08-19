"""Tests for the wa_broker transport service (BOT-V4 S2, #4333).

Covers the worker-side leg (offer_job/wait_for_job/consume_result/
discard_completion), the shared circuit breaker persisted on
wa_broker_gauge, and the reaper/retention passes (expire_stale_jobs,
sweep_terminal_rows). The endpoint-side leg (claim_job/complete_job) is
exercised indirectly through the router test suite (it is mocked there,
never given real SQL), so it is not duplicated here.

The mock connection is scripted, matching the house pattern from
test_wa_outbox_worker.py: fetchrow/fetchval/execute pop queued results in
call order (one independent queue per method), and every call is recorded
into `executed` as a uniform (sql, args) audit trail so a fenced UPDATE
done via `fetchrow(...RETURNING ...)` is just as assertable as a plain
`execute()` call. A queued item that is an exception instance is RAISED
instead of returned, so the same class can script asyncpg errors (e.g. the
UniqueViolationError offer_job must swallow into ALREADY_SPENT).

Functions taking `conn: asyncpg.Connection` (offer_job, breaker_allows,
record_breaker_result, consume_result, discard_completion) get a
ScriptedConn instance directly. Functions taking `pool: asyncpg.Pool`
(wait_for_job, expire_stale_jobs, sweep_terminal_rows) call
fetchrow/fetchval/execute directly on the pool with no .acquire() step
(asyncpg.Pool exposes those as convenience passthroughs) — the SAME
ScriptedConn class serves both roles since it implements that interface.
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


class ScriptedConn:
    def __init__(
        self,
        fetchrow_results: list[Any] | None = None,
        fetchval_results: list[Any] | None = None,
        execute_results: list[Any] | None = None,
    ) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self._fetchrow = list(fetchrow_results or [])
        self._fetchval = list(fetchval_results or [])
        self._execute = list(execute_results or [])

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

    def transaction(self) -> Any:
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


@pytest.mark.asyncio
async def test_offer_job_happy_path_offers_fences_and_inserts() -> None:
    job_id = uuid.uuid4()
    conn = ScriptedConn(
        fetchrow_results=[
            {"broker_alive": True},  # gauge liveness
            {"breaker_state": "closed", "cooled_down": False},  # breaker_allows
            {"id": OUTBOX_ID},  # fenced UPDATE RETURNING id
        ],
        fetchval_results=[
            0,  # admission depth
            job_id,  # INSERT ... RETURNING job_id
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
async def test_offer_job_breaker_open_blocks_offer() -> None:
    conn = ScriptedConn(
        fetchrow_results=[
            {"broker_alive": True},
            {"breaker_state": "open", "cooled_down": False},
        ],
    )

    result = await wa_broker.offer_job(conn, **_offer_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.BREAKER_OPEN
    assert not conn.sql_contains("UPDATE wa_outbox SET generation_route")


@pytest.mark.asyncio
async def test_offer_job_queue_full_when_depth_at_cap() -> None:
    conn = ScriptedConn(
        fetchrow_results=[
            {"broker_alive": True},
            {"breaker_state": "closed", "cooled_down": False},
        ],
        fetchval_results=[wa_broker.MAX_DEPTH],  # depth >= MAX_DEPTH
    )

    result = await wa_broker.offer_job(conn, **_offer_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.QUEUE_FULL
    assert not conn.sql_contains("UPDATE wa_outbox SET generation_route")


@pytest.mark.asyncio
async def test_offer_job_admits_when_depth_below_cap() -> None:
    """INNOCENCE for the depth cap: depth one below MAX_DEPTH must still be
    admitted — the boundary is >=, not >."""
    job_id = uuid.uuid4()
    conn = ScriptedConn(
        fetchrow_results=[
            {"broker_alive": True},
            {"breaker_state": "closed", "cooled_down": False},
            {"id": OUTBOX_ID},
        ],
        fetchval_results=[wa_broker.MAX_DEPTH - 1, job_id],
    )

    result = await wa_broker.offer_job(conn, **_offer_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.OFFERED


@pytest.mark.asyncio
async def test_offer_job_already_spent_when_fence_lost_but_marker_set() -> None:
    conn = ScriptedConn(
        fetchrow_results=[
            {"broker_alive": True},
            {"breaker_state": "closed", "cooled_down": False},
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


@pytest.mark.asyncio
async def test_offer_job_fence_lost_when_marker_not_set() -> None:
    conn = ScriptedConn(
        fetchrow_results=[
            {"broker_alive": True},
            {"breaker_state": "closed", "cooled_down": False},
            None,
        ],
        fetchval_results=[0, False],  # depth, generation_route IS NOT NULL -> False
    )

    result = await wa_broker.offer_job(conn, **_offer_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.FENCE_LOST
    assert not conn.sql_contains("INSERT INTO broker_jobs")


@pytest.mark.asyncio
async def test_offer_job_already_spent_on_insert_unique_violation() -> None:
    conn = ScriptedConn(
        fetchrow_results=[
            {"broker_alive": True},
            {"breaker_state": "closed", "cooled_down": False},
            {"id": OUTBOX_ID},
        ],
        fetchval_results=[
            0,
            asyncpg.UniqueViolationError(
                "duplicate key value violates unique constraint "
                '"uq_broker_jobs_serve_outbox"'
            ),
        ],
    )

    result = await wa_broker.offer_job(conn, **_offer_kwargs())

    assert result.outcome is wa_broker.OfferOutcome.ALREADY_SPENT
    assert result.job_id is None


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
            {"state": "failed", "error_class": "codex_timeout", "deadline_passed": False},
        ],
    )

    result = await wa_broker.wait_for_job(pool, uuid.uuid4(), poll_seconds=0)

    assert result.outcome is wa_broker.WaitOutcome.FAILED
    assert result.error_class == "codex_timeout"


@pytest.mark.asyncio
async def test_wait_for_job_deadline_cas_expires_and_nulls_payload() -> None:
    job_id = uuid.uuid4()
    pool = ScriptedConn(
        fetchrow_results=[
            {"state": "offered", "error_class": None, "deadline_passed": True},
            {"job_id": job_id},  # expiry CAS succeeded
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


# ── circuit breaker ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_breaker_allows_when_closed() -> None:
    conn = ScriptedConn(fetchrow_results=[{"breaker_state": "closed", "cooled_down": False}])

    assert await wa_broker.breaker_allows(conn) is True


@pytest.mark.asyncio
async def test_breaker_denies_when_open_and_not_cooled_down() -> None:
    conn = ScriptedConn(fetchrow_results=[{"breaker_state": "open", "cooled_down": False}])

    assert await wa_broker.breaker_allows(conn) is False


@pytest.mark.asyncio
async def test_breaker_allows_when_open_but_cooled_down() -> None:
    """INNOCENCE for the open state: past cooldown, a half-open canary is let
    through even though the breaker never flipped back to 'closed'."""
    conn = ScriptedConn(fetchrow_results=[{"breaker_state": "open", "cooled_down": True}])

    assert await wa_broker.breaker_allows(conn) is True


@pytest.mark.asyncio
async def test_breaker_denies_when_gauge_never_seeded() -> None:
    conn = ScriptedConn(fetchrow_results=[None])

    assert await wa_broker.breaker_allows(conn) is False


@pytest.mark.asyncio
async def test_record_breaker_result_success_resets_to_closed() -> None:
    conn = ScriptedConn()

    await wa_broker.record_breaker_result(conn, success=True)

    reset_calls = conn.sql_with_args("breaker_state")
    assert reset_calls
    _, args = reset_calls[0]
    assert args == ("closed", None, 0)


@pytest.mark.asyncio
async def test_record_breaker_result_trips_open_only_at_threshold() -> None:
    """GUILT + INNOCENCE together: the OPEN UPDATE must stay silent for
    failures 1 and 2, and fire only once the RETURNING count reaches
    BREAKER_TRIP_AFTER (3)."""
    conn = ScriptedConn(
        fetchrow_results=[
            {"consecutive_failures": 1},
            {"consecutive_failures": 2},
            {"consecutive_failures": 3},
        ],
    )

    await wa_broker.record_breaker_result(conn, success=False)
    assert not conn.sql_contains("breaker_state = 'open'")

    await wa_broker.record_breaker_result(conn, success=False)
    assert not conn.sql_contains("breaker_state = 'open'")

    await wa_broker.record_breaker_result(conn, success=False)
    assert conn.sql_contains("breaker_state = 'open'")


# ── expire_stale_jobs (reaper) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_expire_stale_jobs_parses_count_and_covers_all_three_clauses() -> None:
    pool = ScriptedConn(execute_results=["UPDATE 3"])

    count = await wa_broker.expire_stale_jobs(pool)

    assert count == 3
    sql, args = pool.executed[0]
    assert "mode = 'serve' AND state IN ('offered', 'leased')" in sql
    assert "state = 'completed_pending_consume'" in sql
    assert "mode = 'shadow' AND state IN ('offered', 'leased')" in sql
    assert "package = NULL" in sql
    assert "evidence_inputs = NULL" in sql
    assert "result_text = NULL" in sql
    assert args == (wa_broker.LEASE_TTL_S * 3,)


@pytest.mark.asyncio
async def test_expire_stale_jobs_defaults_to_zero_on_unparseable_result() -> None:
    """INNOCENCE-ish edge: a driver result string with no trailing count
    must degrade to 0, never raise."""
    pool = ScriptedConn(execute_results=["SOMETHING WEIRD"])

    count = await wa_broker.expire_stale_jobs(pool)

    assert count == 0


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
