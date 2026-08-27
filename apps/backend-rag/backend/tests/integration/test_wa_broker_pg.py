"""BOT-V4 S2 — broker_jobs transport against REAL PostgreSQL.

The S2 cross-family review's finding 9 (BLOCKER): the ScriptedConn unit
suite manufactures asyncpg results, so it cannot validate transaction
aborts, savepoints, row locking, SKIP LOCKED, CAS races or the migration's
CHECK constraints — removing ``fence_token = $2`` from the completion SQL
would have left every unit test green. This suite drives the REAL service
functions against the REAL migration-270 DDL on a live PostgreSQL.

Isolation: every test runs in a throwaway schema (parent-table stubs +
migration 270's forward SQL, parsed by the production
``split_migration_sql``), dropped afterwards — nothing touches public
tables, so the suite is safe on the shared CI database.

Connects to TEST_DATABASE_URL (CI provides the postgres:15 service; the
partners conftest uses the same convention and the same fail-hard-if-absent
semantics — a skipped suite would silently disarm the blocker fix, scar
family #2).
"""

from __future__ import annotations

import asyncio
import datetime
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

from backend.db.migration_base import split_migration_sql
from backend.services.integrations import wa_broker
from backend.services.integrations.wa_broker import (
    CompleteStatus,
    OfferOutcome,
    WaitOutcome,
)

_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_test",
)

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "db" / "migrations_v2"

# EVERY wa_broker migration, in order — a fixture that pins one file builds
# a schema the source has already outgrown (the 271 column would raise
# UndefinedColumnError on half the breaker paths while the suite blamed the
# code). New broker migrations get appended here in the same PR that adds
# them; the UndefinedColumnError blast radius is the tripwire for forgetting.
_BROKER_MIGRATIONS = (
    _MIGRATIONS_DIR / "270_wa_broker_jobs.sql",
    _MIGRATIONS_DIR / "271_wa_broker_gauge_half_open_at.sql",
    _MIGRATIONS_DIR / "272_wa_broker_package_text.sql",
    _MIGRATIONS_DIR / "273_wa_broker_completion_digest.sql",
    _MIGRATIONS_DIR / "274_wa_broker_completed_at_check.sql",
    _MIGRATIONS_DIR / "296_wa_broker_jobs_live_only_unique.sql",
)

_SCHEMA = "wa_broker_it"

# Minimal stand-ins for the two parent tables migration 270 references.
# Only the columns the transport actually reads/writes.
_PARENT_STUBS = """
CREATE TABLE wa_outbox (
    id BIGSERIAL PRIMARY KEY,
    claim_token UUID,
    status TEXT NOT NULL DEFAULT 'generating'
);
CREATE TABLE meta_inbox_threads (
    thread_id BIGSERIAL PRIMARY KEY
);
"""


@pytest_asyncio.fixture
async def conn() -> AsyncIterator[asyncpg.Connection]:
    """Fresh schema per test: parent stubs + the REAL migration 270 DDL."""
    c = await asyncpg.connect(_DB_URL)
    try:
        await c.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
        await c.execute(f"CREATE SCHEMA {_SCHEMA}")
        await c.execute(f"SET search_path TO {_SCHEMA}")
        await c.execute(_PARENT_STUBS)
        for migration in _BROKER_MIGRATIONS:
            forward, _rollback = split_migration_sql(migration.read_text(encoding="utf-8"))
            await c.execute(forward)
        yield c
    finally:
        await c.execute(f"DROP SCHEMA IF EXISTS {_SCHEMA} CASCADE")
        await c.close()


@pytest_asyncio.fixture
async def pool(conn: asyncpg.Connection) -> AsyncIterator[asyncpg.Pool]:
    """Pool bound to the same throwaway schema (for the pool-taking APIs)."""
    p = await asyncpg.create_pool(
        _DB_URL,
        min_size=1,
        max_size=3,
        server_settings={"search_path": _SCHEMA},
    )
    try:
        yield p
    finally:
        await p.close()


async def _seed_alive_gauge(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        INSERT INTO wa_broker_gauge (id, broker_last_seen_at, updated_at)
        VALUES (1, now(), now())
        ON CONFLICT (id) DO UPDATE
        SET broker_last_seen_at = now(), updated_at = now()
        """
    )


async def _outbox_row(conn: asyncpg.Connection) -> tuple[int, int, uuid.UUID]:
    claim = uuid.uuid4()
    outbox_id = await conn.fetchval(
        "INSERT INTO wa_outbox (claim_token, status) VALUES ($1, 'generating') RETURNING id",
        claim,
    )
    thread_id = await conn.fetchval(
        "INSERT INTO meta_inbox_threads DEFAULT VALUES RETURNING thread_id"
    )
    return outbox_id, thread_id, claim


async def _offer(
    conn: asyncpg.Connection,
    outbox_id: int,
    thread_id: int,
    claim: uuid.UUID,
) -> wa_broker.OfferResult:
    return await wa_broker.offer_job(
        conn,
        outbox_id=outbox_id,
        thread_id=thread_id,
        claim_token=claim,
        outbox_expected_status="generating",
        package='{"history": [], "chunks": []}',
        evidence_inputs='{"evidence": []}',
        package_hash="deadbeef",
        thread_epoch=1,
    )


# ──────────────────────────────────────────────────────────────────────────
# Protocol happy path + fences
# ──────────────────────────────────────────────────────────────────────────


async def test_full_lifecycle_offer_claim_complete_consume(
    conn: asyncpg.Connection, pool: asyncpg.Pool
) -> None:
    await _seed_alive_gauge(conn)
    outbox_id, thread_id, claim = await _outbox_row(conn)

    offered = await _offer(conn, outbox_id, thread_id, claim)
    assert offered.outcome is OfferOutcome.OFFERED
    assert offered.job_id is not None

    # The route fence committed with the INSERT.
    assert (
        await conn.fetchval("SELECT generation_route FROM wa_outbox WHERE id = $1", outbox_id)
        == "codex"
    )

    leased = await wa_broker.claim_job(conn, in_flight=0, last_exec_ms=None)
    assert leased is not None
    assert leased["job_id"] == offered.job_id
    assert leased["package"] is not None
    fence = leased["fence_token"]

    status = await wa_broker.complete_job(
        conn,
        job_id=offered.job_id,
        fence_token=fence,
        completion_key="key-0001",
        result_text="the answer",
        error_class=None,
        exec_ms=1200,
    )
    assert status is CompleteStatus.ACCEPTED

    waited = await wa_broker.wait_for_job(pool, offered.job_id)
    assert waited.outcome is WaitOutcome.COMPLETED

    # Single-consumer CAS returns the pre-NULL text through the self-join…
    text = await wa_broker.consume_result(conn, offered.job_id)
    assert text == "the answer"
    # …and the SAME statement left the row terminal with payload NULL.
    row = await conn.fetchrow(
        "SELECT state, package, evidence_inputs, result_text FROM broker_jobs WHERE job_id = $1",
        offered.job_id,
    )
    assert row["state"] == "consumed"
    assert row["package"] is None
    assert row["evidence_inputs"] is None
    assert row["result_text"] is None

    # Second consume finds nothing (CAS already spent).
    assert await wa_broker.consume_result(conn, offered.job_id) is None


async def test_retry_after_terminal_prior_leg_admits_a_new_job(
    conn: asyncpg.Connection,
) -> None:
    """THE FIX (spec gradino 2/5, migration 296): the historical version of
    this test proved the OLD 'ever' invariant — a durable generation_route
    marker permanently refusing any second leg, even a recoverable one.
    That is exactly what made every recoverable codex failure a silent
    Gemini fall-off. Now: terminalize the first leg WITHOUT deleting it
    (a real reaper/complete_job transition never deletes — only the 7-day
    sweep does), re-offer on the SAME claim, and require a FRESH OFFERED
    with a NEW job_id — both rows persist, proving the live-only unique
    index (not row deletion) is what makes the second INSERT succeed."""
    await _seed_alive_gauge(conn)
    outbox_id, thread_id, claim = await _outbox_row(conn)
    first = await _offer(conn, outbox_id, thread_id, claim)
    assert first.outcome is OfferOutcome.OFFERED
    await conn.execute(
        "UPDATE broker_jobs SET state = 'expired', package = NULL, "
        "evidence_inputs = NULL, result_text = NULL, outcome = 'expired_leased' "
        "WHERE job_id = $1",
        first.job_id,
    )

    second = await _offer(conn, outbox_id, thread_id, claim)

    assert second.outcome is OfferOutcome.OFFERED
    assert second.job_id is not None
    assert second.job_id != first.job_id
    # BOTH rows persist — the first terminal leg is history, not deleted.
    rows = await conn.fetch(
        "SELECT job_id, state FROM broker_jobs WHERE outbox_id = $1 ORDER BY created_at",
        outbox_id,
    )
    assert [r["job_id"] for r in rows] == [first.job_id, second.job_id]
    assert rows[0]["state"] == "expired"
    assert rows[1]["state"] == "offered"
    # The durable marker stays 'codex' throughout (it now means "this row
    # has ever touched codex", not "spent" — the per-row leg count is what
    # actually gates a retry).
    assert (
        await conn.fetchval("SELECT generation_route FROM wa_outbox WHERE id = $1", outbox_id)
        == "codex"
    )


async def test_retry_while_prior_leg_still_alive_reattaches(
    conn: asyncpg.Connection,
) -> None:
    """A retry offered while the row's OWN prior leg is still 'leased'
    (mid-exec) must REATTACH to it, not fall behind the depth cap — the
    depth query excludes THIS outbox_id's own live job precisely so a
    reattach never competes with itself for the one global admission
    slot (a live DB proof that the exclusion in offer_job's depth query
    actually works, not just the unit-mocked shape)."""
    await _seed_alive_gauge(conn)
    outbox_id, thread_id, claim = await _outbox_row(conn)
    first = await _offer(conn, outbox_id, thread_id, claim)
    assert first.outcome is OfferOutcome.OFFERED
    # Simulate the broker having claimed it (still non-terminal).
    await conn.execute(
        "UPDATE broker_jobs SET state = 'leased', fence_token = gen_random_uuid(), "
        "leased_at = now() WHERE job_id = $1",
        first.job_id,
    )

    second = await _offer(conn, outbox_id, thread_id, claim)

    assert second.outcome is OfferOutcome.REATTACHED
    assert second.job_id == first.job_id
    # No second row was created.
    count = await conn.fetchval(
        "SELECT count(*) FROM broker_jobs WHERE outbox_id = $1", outbox_id
    )
    assert count == 1


async def test_retry_budget_exhausts_after_max_codex_legs(
    conn: asyncpg.Connection,
) -> None:
    """INNOCENCE for the budget cap: MAX_CODEX_LEGS terminal legs are all
    admitted (proving the cap is >=, not off-by-one), and the very NEXT
    retry gets the NAMED LEGS_EXHAUSTED — never a silent fall-off
    conflated with a different cause."""
    await _seed_alive_gauge(conn)
    outbox_id, thread_id, claim = await _outbox_row(conn)

    job_ids: list[uuid.UUID] = []
    for _ in range(wa_broker.MAX_CODEX_LEGS):
        offered = await _offer(conn, outbox_id, thread_id, claim)
        assert offered.outcome is OfferOutcome.OFFERED
        job_ids.append(offered.job_id)
        await conn.execute(
            "UPDATE broker_jobs SET state = 'failed', package = NULL, "
            "evidence_inputs = NULL, result_text = NULL, outcome = 'broker_failed' "
            "WHERE job_id = $1",
            offered.job_id,
        )

    assert len(set(job_ids)) == wa_broker.MAX_CODEX_LEGS  # every leg was distinct

    exhausted = await _offer(conn, outbox_id, thread_id, claim)
    assert exhausted.outcome is OfferOutcome.LEGS_EXHAUSTED
    assert exhausted.job_id is None
    total_rows = await conn.fetchval(
        "SELECT count(*) FROM broker_jobs WHERE outbox_id = $1", outbox_id
    )
    assert total_rows == wa_broker.MAX_CODEX_LEGS  # the exhausted call created nothing


async def test_two_concurrent_offers_on_the_same_row_never_create_two_live_jobs(
    conn: asyncpg.Connection, pool: asyncpg.Pool
) -> None:
    """INNOCENCE, real concurrency: two workers racing an offer for the
    SAME outbox row (same claim_token+status — the realistic shape of a
    worker retry racing a slow-to-reclaim sibling) must never both create
    a live job. The advisory xact lock serializes them; whichever runs
    second must see the first's job (REATTACHED if still live) rather
    than a second INSERT — this is exactly what uq_broker_jobs_serve_outbox_live
    plus the advisory lock are for, and only a real DB proves it (a mock
    cannot manufacture a genuine UniqueViolation race)."""
    await _seed_alive_gauge(conn)
    outbox_id, thread_id, claim = await _outbox_row(conn)

    async def _one_offer() -> wa_broker.OfferResult:
        async with pool.acquire() as c:
            return await _offer(c, outbox_id, thread_id, claim)

    results = await asyncio.gather(_one_offer(), _one_offer())
    outcomes = sorted(r.outcome.value for r in results)
    # Exactly one OFFERED (the winner) and one REATTACHED (the loser
    # catching the winner's still-live job) — never two OFFERED.
    assert outcomes == ["offered", "reattached"]
    job_ids = {r.job_id for r in results}
    assert len(job_ids) == 1  # both results point at the SAME job
    live_count = await conn.fetchval(
        "SELECT count(*) FROM broker_jobs WHERE outbox_id = $1 "
        "AND state IN ('offered', 'leased', 'completed_pending_consume')",
        outbox_id,
    )
    assert live_count == 1


async def test_offer_depth_cap_and_fence_lost(conn: asyncpg.Connection) -> None:
    await _seed_alive_gauge(conn)
    a = await _outbox_row(conn)
    b = await _outbox_row(conn)
    assert (await _offer(conn, *a)).outcome is OfferOutcome.OFFERED
    assert (await _offer(conn, *b)).outcome is OfferOutcome.QUEUE_FULL

    # Fence lost: wrong claim token on a fresh row (queue drained first).
    await conn.execute("DELETE FROM broker_jobs")
    c = await _outbox_row(conn)
    lost = await wa_broker.offer_job(
        conn,
        outbox_id=c[0],
        thread_id=c[1],
        claim_token=uuid.uuid4(),  # not the row's token
        outbox_expected_status="generating",
        package="{}",
        evidence_inputs="{}",
        package_hash="x",
        thread_epoch=1,
    )
    assert lost.outcome is OfferOutcome.FENCE_LOST
    # And the fence write did not stick.
    assert await conn.fetchval("SELECT generation_route FROM wa_outbox WHERE id = $1", c[0]) is None


async def test_unique_violation_savepoint_repairs_the_marker(
    conn: asyncpg.Connection,
) -> None:
    """Finding 2: UniqueViolationError must NOT roll back the historical
    'spent' fence. Pre-insert a LIVE serve job WITHOUT the marker (the
    compatibility/defensive scenario — a write inconsistency the code
    never expects but the DB, as the invariant's owner, must still be
    honored against) and offer: the retry-lookup branch never runs
    (route_before is NULL, since the marker was bypassed), so this drives
    the INSERT straight into uq_broker_jobs_serve_outbox_live's REAL
    UniqueViolationError — not merely a terminal row, which migration 296
    deliberately no longer blocks (see test_retry_after_terminal_prior_
    leg_admits_a_new_job for that case). Requires BOTH the ALREADY_SPENT
    verdict AND a persisted generation_route."""
    await _seed_alive_gauge(conn)
    outbox_id, thread_id, claim = await _outbox_row(conn)
    # A LIVE serve job that already holds the leg but never set the marker.
    await conn.execute(
        """
        INSERT INTO broker_jobs
            (outbox_id, thread_id, mode, state, package_hash, thread_epoch,
             deadline_at)
        VALUES ($1, $2, 'serve', 'offered', 'h', 1, now() + interval '1 minute')
        """,
        outbox_id,
        thread_id,
    )
    result = await _offer(conn, outbox_id, thread_id, claim)
    assert result.outcome is OfferOutcome.ALREADY_SPENT
    # The repaired marker COMMITTED despite the aborted INSERT (savepoint).
    assert (
        await conn.fetchval("SELECT generation_route FROM wa_outbox WHERE id = $1", outbox_id)
        == "codex"
    )


async def test_skip_locked_claim_skips_a_locked_job(
    conn: asyncpg.Connection,
) -> None:
    """Finding 9's 'duplicate claim race': a second claimant must skip (not
    block on, not double-lease) a row another transaction holds locked."""
    await _seed_alive_gauge(conn)
    outbox_id, thread_id, claim = await _outbox_row(conn)
    offered = await _offer(conn, outbox_id, thread_id, claim)
    assert offered.outcome is OfferOutcome.OFFERED

    other = await asyncpg.connect(_DB_URL)
    try:
        await other.execute(f"SET search_path TO {_SCHEMA}")
        async with conn.transaction():
            await conn.execute(
                "SELECT 1 FROM broker_jobs WHERE job_id = $1 FOR UPDATE",
                offered.job_id,
            )
            # While the row is locked, the other connection's claim must
            # return None IMMEDIATELY (SKIP LOCKED), not wait for the lock.
            assert (await wa_broker.claim_job(other, in_flight=0, last_exec_ms=None)) is None
        # Lock released: now the claim CAS succeeds exactly once.
        first = await wa_broker.claim_job(other, in_flight=0, last_exec_ms=None)
        assert first is not None and first["job_id"] == offered.job_id
        assert (await wa_broker.claim_job(other, in_flight=0, last_exec_ms=None)) is None
    finally:
        await other.close()


# ──────────────────────────────────────────────────────────────────────────
# Completion idempotency + fence/state classification (findings 5, 6)
# ──────────────────────────────────────────────────────────────────────────


async def _offer_and_claim(
    conn: asyncpg.Connection,
) -> tuple[uuid.UUID, uuid.UUID]:
    await _seed_alive_gauge(conn)
    outbox_id, thread_id, claim = await _outbox_row(conn)
    offered = await _offer(conn, outbox_id, thread_id, claim)
    assert offered.outcome is OfferOutcome.OFFERED
    leased = await wa_broker.claim_job(conn, in_flight=0, last_exec_ms=None)
    assert leased is not None
    return offered.job_id, leased["fence_token"]


async def test_replay_requires_key_and_fence_and_never_resurrects(
    conn: asyncpg.Connection,
) -> None:
    job_id, fence = await _offer_and_claim(conn)
    accepted = await wa_broker.complete_job(
        conn,
        job_id=job_id,
        fence_token=fence,
        completion_key="key-A",
        result_text="answer",
        error_class=None,
        exec_ms=None,
    )
    assert accepted is CompleteStatus.ACCEPTED

    # Lost-response retry: same key, same fence -> REPLAY.
    assert (
        await wa_broker.complete_job(
            conn,
            job_id=job_id,
            fence_token=fence,
            completion_key="key-A",
            result_text="answer",
            error_class=None,
            exec_ms=None,
        )
    ) is CompleteStatus.REPLAY

    # Same key, WRONG fence -> not a replay (finding 6).
    assert (
        await wa_broker.complete_job(
            conn,
            job_id=job_id,
            fence_token=uuid.uuid4(),
            completion_key="key-A",
            result_text="answer",
            error_class=None,
            exec_ms=None,
        )
    ) is CompleteStatus.CONFLICT

    # Different attempt for a completed job -> CONFLICT, never a second
    # generation.
    assert (
        await wa_broker.complete_job(
            conn,
            job_id=job_id,
            fence_token=fence,
            completion_key="key-B",
            result_text="other",
            error_class=None,
            exec_ms=None,
        )
    ) is CompleteStatus.CONFLICT

    # After consume, the replay still answers 200/REPLAY and the payload
    # stays NULL — no resurrection.
    assert await wa_broker.consume_result(conn, job_id) == "answer"
    assert (
        await wa_broker.complete_job(
            conn,
            job_id=job_id,
            fence_token=fence,
            completion_key="key-A",
            result_text="answer",
            error_class=None,
            exec_ms=None,
        )
    ) is CompleteStatus.REPLAY
    assert (
        await conn.fetchval("SELECT result_text FROM broker_jobs WHERE job_id = $1", job_id) is None
    )


async def test_expired_acceptance_answers_gone_even_with_matching_key(
    conn: asyncpg.Connection,
) -> None:
    """Finding 6: expired takes precedence — a reaped acceptance must not
    tell the broker its result was delivered."""
    job_id, fence = await _offer_and_claim(conn)
    assert (
        await wa_broker.complete_job(
            conn,
            job_id=job_id,
            fence_token=fence,
            completion_key="key-A",
            result_text="answer",
            error_class=None,
            exec_ms=None,
        )
    ) is CompleteStatus.ACCEPTED
    # Consumer died; the reaper expired the acceptance.
    await conn.execute(
        "UPDATE broker_jobs SET state = 'expired', package = NULL, "
        "evidence_inputs = NULL, result_text = NULL, "
        "outcome = 'expired_completed_pending_consume' WHERE job_id = $1",
        job_id,
    )
    assert (
        await wa_broker.complete_job(
            conn,
            job_id=job_id,
            fence_token=fence,
            completion_key="key-A",
            result_text="answer",
            error_class=None,
            exec_ms=None,
        )
    ) is CompleteStatus.GONE


async def test_late_completion_after_deadline_is_gone(
    conn: asyncpg.Connection, pool: asyncpg.Pool
) -> None:
    """Chaos row 5 (expiry/GONE half): deadline passes, the worker's DB-clock
    CAS expires the job, a late /complete gets 410 and payload stays NULL."""
    job_id, fence = await _offer_and_claim(conn)
    await conn.execute(
        "UPDATE broker_jobs SET deadline_at = now() - INTERVAL '1 second' WHERE job_id = $1",
        job_id,
    )
    waited = await wa_broker.wait_for_job(pool, job_id)
    assert waited.outcome is WaitOutcome.DEADLINE
    row = await conn.fetchrow(
        "SELECT state, package, result_text FROM broker_jobs WHERE job_id = $1",
        job_id,
    )
    assert row["state"] == "expired"
    assert row["package"] is None and row["result_text"] is None
    assert (
        await wa_broker.complete_job(
            conn,
            job_id=job_id,
            fence_token=fence,
            completion_key="late-key",
            result_text="too late",
            error_class=None,
            exec_ms=None,
        )
    ) is CompleteStatus.GONE


async def test_service_level_xor_and_error_vocabulary(
    conn: asyncpg.Connection,
) -> None:
    """Findings 5 + 7 at the reusable boundary (not just the router)."""
    job_id, fence = await _offer_and_claim(conn)
    with pytest.raises(ValueError):
        await wa_broker.complete_job(
            conn,
            job_id=job_id,
            fence_token=fence,
            completion_key="k",
            result_text=None,
            error_class=None,
            exec_ms=None,
        )
    with pytest.raises(ValueError):
        await wa_broker.complete_job(
            conn,
            job_id=job_id,
            fence_token=fence,
            completion_key="k",
            result_text="text",
            error_class="cli_failure",
            exec_ms=None,
        )
    with pytest.raises(ValueError):
        await wa_broker.complete_job(
            conn,
            job_id=job_id,
            fence_token=fence,
            completion_key="k",
            result_text=None,
            error_class="SomeException: user@example.com",
            exec_ms=None,
        )
    # A vocabulary member lands the typed terminal failure, payload NULL.
    assert (
        await wa_broker.complete_job(
            conn,
            job_id=job_id,
            fence_token=fence,
            completion_key="k",
            result_text=None,
            error_class="cli_failure",
            exec_ms=900,
        )
    ) is CompleteStatus.ACCEPTED
    row = await conn.fetchrow(
        "SELECT state, error_class, package FROM broker_jobs WHERE job_id = $1",
        job_id,
    )
    assert row["state"] == "failed"
    assert row["error_class"] == "cli_failure"
    assert row["package"] is None


# ──────────────────────────────────────────────────────────────────────────
# Breaker state machine (finding 3)
# ──────────────────────────────────────────────────────────────────────────


async def _age_breaker(conn: asyncpg.Connection, seconds: int) -> None:
    await conn.execute(
        "UPDATE wa_broker_gauge SET breaker_opened_at = "
        "now() - ($1 * INTERVAL '1 second') WHERE id = 1",
        seconds,
    )


async def test_half_open_canary_consumes_slot_and_failed_canary_recools(
    conn: asyncpg.Connection,
) -> None:
    await _seed_alive_gauge(conn)
    for _ in range(wa_broker.BREAKER_TRIP_AFTER):
        await wa_broker.record_breaker_result(conn, success=False)
    gauge = await conn.fetchrow("SELECT * FROM wa_broker_gauge WHERE id = 1")
    assert gauge["breaker_state"] == "open"

    # Not cooled: denied.
    assert await wa_broker.breaker_admits(conn) is False

    # Cooled: the FIRST admit wins the open->half_open CAS…
    await _age_breaker(conn, wa_broker.BREAKER_OPEN_SECONDS + 1)
    assert await wa_broker.breaker_admits(conn) is True
    # …and the second is refused — exactly one canary (finding 3's
    # "MAX_DEPTH limits simultaneous jobs, not an unlimited sequence").
    assert await wa_broker.breaker_admits(conn) is False

    aged = await conn.fetchval("SELECT breaker_opened_at FROM wa_broker_gauge WHERE id = 1")
    # The failed canary demotes half_open->open with a FRESH clock: the
    # next canary needs a FULL new cooldown.
    await wa_broker.record_breaker_result(conn, success=False)
    gauge = await conn.fetchrow("SELECT * FROM wa_broker_gauge WHERE id = 1")
    assert gauge["breaker_state"] == "open"
    assert gauge["breaker_opened_at"] > aged
    assert await wa_broker.breaker_admits(conn) is False

    # A SUCCESSFUL canary closes the breaker fully.
    await _age_breaker(conn, wa_broker.BREAKER_OPEN_SECONDS + 1)
    assert await wa_broker.breaker_admits(conn) is True
    await wa_broker.record_breaker_result(conn, success=True)
    gauge = await conn.fetchrow("SELECT * FROM wa_broker_gauge WHERE id = 1")
    assert gauge["breaker_state"] == "closed"
    assert gauge["consecutive_failures"] == 0
    assert await wa_broker.breaker_admits(conn) is True


async def test_aborted_offer_does_not_spend_the_canary_slot(
    conn: asyncpg.Connection,
) -> None:
    """An offer admitted through the half-open CAS that then loses the fence
    must put the canary slot back (with the ORIGINAL cooldown clock)."""
    await _seed_alive_gauge(conn)
    for _ in range(wa_broker.BREAKER_TRIP_AFTER):
        await wa_broker.record_breaker_result(conn, success=False)
    await _age_breaker(conn, wa_broker.BREAKER_OPEN_SECONDS + 1)
    opened_at = await conn.fetchval("SELECT breaker_opened_at FROM wa_broker_gauge WHERE id = 1")

    outbox_id, thread_id, _claim = await _outbox_row(conn)
    lost = await wa_broker.offer_job(
        conn,
        outbox_id=outbox_id,
        thread_id=thread_id,
        claim_token=uuid.uuid4(),  # wrong token -> fence lost after the CAS
        outbox_expected_status="generating",
        package="{}",
        evidence_inputs="{}",
        package_hash="x",
        thread_epoch=1,
    )
    assert lost.outcome is OfferOutcome.FENCE_LOST
    gauge = await conn.fetchrow("SELECT * FROM wa_broker_gauge WHERE id = 1")
    assert gauge["breaker_state"] == "open"  # reverted, not stuck half_open
    assert gauge["breaker_opened_at"] == opened_at  # clock untouched
    # And the slot is immediately claimable by the next (valid) offer.
    assert await wa_broker.breaker_admits(conn) is True


# ──────────────────────────────────────────────────────────────────────────
# Reaper accounting (findings 4 + 8) and retention (finding 11)
# ──────────────────────────────────────────────────────────────────────────


async def test_reaper_classifies_expiries_and_feeds_only_serve_to_breaker(
    conn: asyncpg.Connection, pool: asyncpg.Pool
) -> None:
    await _seed_alive_gauge(conn)
    a = await _outbox_row(conn)
    b = await _outbox_row(conn)
    c = await _outbox_row(conn)
    d = await _outbox_row(conn)
    e = await _outbox_row(conn)
    # Two serve jobs past deadline (breaker signal).
    for outbox_id, thread_id, _tok in (a, b):
        await conn.execute(
            """
            INSERT INTO broker_jobs
                (outbox_id, thread_id, mode, state, package, package_hash,
                 thread_epoch, deadline_at)
            VALUES ($1, $2, 'serve', 'leased', '{}'::jsonb, 'h', 1,
                    now() - INTERVAL '1 second')
            """,
            outbox_id,
            thread_id,
        )
    # One dead-consumer acceptance past the grace. completed_at was NULL in
    # the pre-274 version of this row (exercising finding 8's COALESCE on
    # created_at); migration 274's CHECK now makes that malformed shape
    # UNWRITABLE — pinned by test_completed_pending_consume_requires_completed_at
    # — so the reachable dead-consumer world always carries completed_at and
    # the COALESCE stays as belt-and-braces for pre-274 rows only.
    await conn.execute(
        """
        INSERT INTO broker_jobs
            (outbox_id, thread_id, mode, state, result_text, package_hash,
             thread_epoch, deadline_at, completed_at)
        VALUES ($1, $2, 'serve', 'completed_pending_consume', 'secret', 'h',
                1, now(), now() - INTERVAL '10 minutes')
        """,
        c[0],
        c[1],
    )
    # One shadow job past its own expires_at.
    await conn.execute(
        """
        INSERT INTO broker_jobs
            (outbox_id, thread_id, mode, state, package_hash, thread_epoch,
             deadline_at, expires_at)
        VALUES ($1, $2, 'shadow', 'offered', 'h', 1,
                now() + INTERVAL '1 hour', now() - INTERVAL '1 second')
        """,
        d[0],
        d[1],
    )
    # Innocence: one fresh serve job that must survive untouched.
    await conn.execute(
        """
        INSERT INTO broker_jobs
            (outbox_id, thread_id, mode, state, package, package_hash,
             thread_epoch, deadline_at)
        VALUES ($1, $2, 'serve', 'offered', '{}'::jsonb, 'h', 1,
                now() + INTERVAL '1 hour')
        """,
        e[0],
        e[1],
    )

    result = await wa_broker.expire_stale_jobs(pool)
    assert result.serve_expired == 2
    assert result.consumer_expired == 1
    assert result.shadow_expired == 1
    assert result.total == 4

    # Every expired row lost its payload (the dead-consumer one held text).
    leaked = await conn.fetchval(
        "SELECT count(*) FROM broker_jobs WHERE state = 'expired' AND "
        "(package IS NOT NULL OR result_text IS NOT NULL)"
    )
    assert leaked == 0
    # The fresh job survived.
    assert (
        await conn.fetchval("SELECT state FROM broker_jobs WHERE outbox_id = $1", e[0]) == "offered"
    )
    # Only the TWO serve expiries reached the breaker — consumer/shadow
    # housekeeping is not a codex-leg failure signal.
    assert await conn.fetchval("SELECT consecutive_failures FROM wa_broker_gauge WHERE id = 1") == 2


async def test_terminal_payload_check_is_enforced_by_the_db(
    conn: asyncpg.Connection,
) -> None:
    """The migration's CHECK is the invariant's owner: code cannot mint a
    terminal row that still holds payload."""
    outbox_id, thread_id, _tok = await _outbox_row(conn)
    with pytest.raises(asyncpg.CheckViolationError):
        await conn.execute(
            """
            INSERT INTO broker_jobs
                (outbox_id, thread_id, mode, state, result_text, package_hash,
                 thread_epoch, deadline_at)
            VALUES ($1, $2, 'serve', 'failed', 'leftover', 'h', 1, now())
            """,
            outbox_id,
            thread_id,
        )


async def test_retention_sweep_under_one_snapshot(
    conn: asyncpg.Connection, pool: asyncpg.Pool
) -> None:
    outbox_id, thread_id, _tok = await _outbox_row(conn)
    old = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=wa_broker.TERMINAL_RETENTION_DAYS + 1
    )
    await conn.execute(
        """
        INSERT INTO broker_jobs
            (outbox_id, thread_id, mode, state, package_hash, thread_epoch,
             deadline_at, created_at, outcome)
        VALUES ($1, $2, 'serve', 'expired', 'h', 1, now(), $3,
                'expired_leased')
        """,
        outbox_id,
        thread_id,
        old,
    )
    removed = await wa_broker.sweep_terminal_rows(pool)
    assert removed == 1
    assert await conn.fetchval("SELECT count(*) FROM broker_jobs") == 0


# ── S2 re-verdict round: findings 2, 4, 5 driven on the REAL schema ─────────


async def test_orphaned_half_open_demotes_despite_fresh_polling(
    conn: asyncpg.Connection,
) -> None:
    """finding 2 (GUILT): a half_open gauge whose canary result was lost
    must demote to open after the orphan window EVEN WHILE the broker keeps
    polling — every claim_job refreshes updated_at, so the guard must
    anchor on breaker_half_open_at, never on the heartbeat. This is the
    exact input that kept the old guard from ever firing."""
    await conn.execute(
        """
        INSERT INTO wa_broker_gauge
            (id, broker_last_seen_at, breaker_state, breaker_opened_at,
             breaker_half_open_at, updated_at)
        VALUES (1, now(), 'half_open',
                now() - INTERVAL '10 minutes',
                now() - ($1 * INTERVAL '1 second') - INTERVAL '1 second',
                now())
        """,
        wa_broker.HALF_OPEN_ORPHAN_S,
    )
    # Fresh heartbeat right now — the old updated_at anchor reads "recent".
    await wa_broker.claim_job(conn, in_flight=0, last_exec_ms=None)

    assert await wa_broker.breaker_admits(conn) is False
    row = await conn.fetchrow(
        "SELECT breaker_state, breaker_half_open_at FROM wa_broker_gauge WHERE id = 1"
    )
    assert row["breaker_state"] == "open"
    assert row["breaker_half_open_at"] is None


async def test_fresh_half_open_survives_the_orphan_guard(
    conn: asyncpg.Connection,
) -> None:
    """finding 2 (INNOCENCE): a half_open entered moments ago (canary
    legitimately in flight) is NOT demoted — denial yes, demotion no."""
    await conn.execute(
        """
        INSERT INTO wa_broker_gauge
            (id, broker_last_seen_at, breaker_state, breaker_opened_at,
             breaker_half_open_at, updated_at)
        VALUES (1, now(), 'half_open', now() - INTERVAL '10 minutes',
                now(), now())
        """
    )

    assert await wa_broker.breaker_admits(conn) is False
    assert (
        await conn.fetchval("SELECT breaker_state FROM wa_broker_gauge WHERE id = 1")
    ) == "half_open"


async def test_reaper_fold_is_atomic_with_terminalization(
    pool: asyncpg.Pool, conn: asyncpg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """finding 4 (GUILT): if the breaker fold crashes, the terminalization
    must roll back WITH it — otherwise the expired jobs became unfindable
    while their failures never reached the breaker. Proven by making
    record_breaker_result raise: the jobs must still be 'offered'
    afterwards, and a clean retry must then expire them AND open the
    breaker."""
    await _seed_alive_gauge(conn)

    async def _offer_one_and_expire_deadline() -> None:
        outbox_id, thread_id, tok = await _outbox_row(conn)
        offered = await wa_broker.offer_job(
            conn,
            outbox_id=outbox_id,
            thread_id=thread_id,
            claim_token=tok,
            outbox_expected_status="generating",
            package='{"k": 1}',
            evidence_inputs="{}",
            package_hash="h",
            thread_epoch=1,
        )
        assert offered.outcome is OfferOutcome.OFFERED
        await conn.execute(
            "UPDATE broker_jobs SET deadline_at = now() - INTERVAL '1 second' "
            "WHERE state = 'offered'"
        )

    # Cycle 1 — the crash: the fold raises, so terminalization must roll
    # back with it and the job must still be reappable.
    await _offer_one_and_expire_deadline()
    real_record = wa_broker.record_breaker_result

    async def _exploding_record(*args: object, **kwargs: object) -> None:
        raise RuntimeError("crash between terminalize and fold")

    monkeypatch.setattr(wa_broker, "record_breaker_result", _exploding_record)
    with pytest.raises(RuntimeError):
        await wa_broker.expire_stale_jobs(pool)

    states = [r["state"] for r in await conn.fetch("SELECT state FROM broker_jobs")]
    assert states and all(s == "offered" for s in states)

    # Clean retry observes the SAME job again — nothing was lost.
    monkeypatch.setattr(wa_broker, "record_breaker_result", real_record)
    result = await wa_broker.expire_stale_jobs(pool)
    assert result.serve_expired == 1

    # MAX_DEPTH is 1, so reach the trip threshold one offer at a time.
    for _ in range(wa_broker.BREAKER_TRIP_AFTER - 1):
        await _offer_one_and_expire_deadline()
        result = await wa_broker.expire_stale_jobs(pool)
        assert result.serve_expired == 1
    assert (
        await conn.fetchval("SELECT breaker_state FROM wa_broker_gauge WHERE id = 1")
    ) == "open"


async def test_offer_evidence_inputs_is_a_jsonb_object_under_the_production_codec(
    conn: asyncpg.Connection,
) -> None:
    """finding 5 (GUILT): the production pool registers a jsonb codec whose
    encoder is json.dumps (backend/app/core/database.py) — a bare
    ``::jsonb`` bind made asyncpg re-serialize the already-serialized
    string, storing a JSONB *string* instead of an object while every
    codec-less test stayed green. The ``::text::jsonb`` double cast types
    the bind as text, so no codec applies on either pool. Asserted on
    evidence_inputs — the one payload still stored as jsonb; package moved
    to TEXT in migration 272 (see the byte-fidelity test below)."""
    import json as _json

    codec_conn = await asyncpg.connect(_DB_URL)
    try:
        await codec_conn.execute(f"SET search_path TO {_SCHEMA}")
        await codec_conn.set_type_codec(
            "jsonb", encoder=_json.dumps, decoder=_json.loads, schema="pg_catalog"
        )
        await _seed_alive_gauge(codec_conn)
        outbox_id, thread_id, tok = await _outbox_row(codec_conn)
        offered = await wa_broker.offer_job(
            codec_conn,
            outbox_id=outbox_id,
            thread_id=thread_id,
            claim_token=tok,
            outbox_expected_status="generating",
            package='{"messages": [], "persona_digest": "d"}',
            evidence_inputs='{"domain": "visa"}',
            package_hash="h",
            thread_epoch=1,
        )
        assert offered.outcome is OfferOutcome.OFFERED
        assert (
            await codec_conn.fetchval(
                "SELECT jsonb_typeof(evidence_inputs) FROM broker_jobs WHERE job_id = $1",
                offered.job_id,
            )
        ) == "object"
        assert await codec_conn.fetchval(
            "SELECT evidence_inputs ? 'domain' FROM broker_jobs WHERE job_id = $1",
            offered.job_id,
        )
    finally:
        await codec_conn.close()


async def test_package_bytes_survive_offer_to_claim_verbatim(
    conn: asyncpg.Connection,
) -> None:
    """Codex re-verdict r4 (GUILT): the package is a hash-sealed envelope —
    wa_package_builder computes package_hash ONCE over the canonical
    serialization, and the broker verifies the claimed bytes against it.
    Stored as JSONB the bytes could not survive: Postgres normalizes key
    order and whitespace on ingest ('{"history": [], "chunks": []}' came
    back '{"chunks": [], "history": []}', measured), so every hash
    verification would reject a valid package, the job would expire, and
    repeated rejections would open the breaker on healthy traffic.
    Migration 272 makes the column TEXT: this offers a deliberately
    NON-canonical serialization (spaces, reverse-sorted keys) under the
    PRODUCTION codec and asserts the claimed value is byte-identical —
    the exact property sha256 needs."""
    import hashlib as _hashlib
    import json as _json

    quirky = '{"history": [ ],   "chunks": [],  "zeta": {"b": 1, "a": 2}}'
    codec_conn = await asyncpg.connect(_DB_URL)
    try:
        await codec_conn.execute(f"SET search_path TO {_SCHEMA}")
        await codec_conn.set_type_codec(
            "jsonb", encoder=_json.dumps, decoder=_json.loads, schema="pg_catalog"
        )
        await _seed_alive_gauge(codec_conn)
        outbox_id, thread_id, tok = await _outbox_row(codec_conn)
        offered = await wa_broker.offer_job(
            codec_conn,
            outbox_id=outbox_id,
            thread_id=thread_id,
            claim_token=tok,
            outbox_expected_status="generating",
            package=quirky,
            evidence_inputs="{}",
            package_hash=_hashlib.sha256(quirky.encode("utf-8")).hexdigest(),
            thread_epoch=1,
        )
        assert offered.outcome is OfferOutcome.OFFERED
        leased = await wa_broker.claim_job(codec_conn, in_flight=0, last_exec_ms=None)
        assert leased is not None
        assert leased["package"] == quirky  # byte-identical, not just equivalent
        assert (
            _hashlib.sha256(leased["package"].encode("utf-8")).hexdigest()
            == leased["package_hash"]
        )
    finally:
        await codec_conn.close()


# ──────────────────────────────────────────────────────────────────────────
# Codex round-2: every terminal serve transition folds atomically into the
# breaker — deadline (worker-observed), typed-failure, success, and the
# straggler-success guard against a stale success bypassing the cooldown.
# ──────────────────────────────────────────────────────────────────────────


async def test_claim_returns_package_as_text_under_the_production_codec(
    conn: asyncpg.Connection,
) -> None:
    """The router's ClaimResponse contract is a STRING (the broker verifies
    the exact bytes against package_hash) — a bare ``package`` bind under the
    production pool's jsonb codec (backend/app/core/database.py) decodes to a
    dict and 500s the router AFTER the lease UPDATE already autocommitted,
    stranding the job leased until its deadline. ``claim_job``'s
    ``package::text AS package`` types the RETURNING column as text so no
    codec applies, mirroring ``offer_job``'s own ``::text::jsonb`` double
    cast (see test_offer_package_is_a_jsonb_object_under_the_production_codec
    above — same defect class, opposite side of the wire)."""
    import json as _json

    await _seed_alive_gauge(conn)
    outbox_id, thread_id, claim = await _outbox_row(conn)
    offered = await _offer(conn, outbox_id, thread_id, claim)
    assert offered.outcome is OfferOutcome.OFFERED

    codec_conn = await asyncpg.connect(_DB_URL)
    try:
        await codec_conn.execute(f"SET search_path TO {_SCHEMA}")
        await codec_conn.set_type_codec(
            "jsonb", encoder=_json.dumps, decoder=_json.loads, schema="pg_catalog"
        )
        leased = await wa_broker.claim_job(codec_conn, in_flight=0, last_exec_ms=None)
        assert leased is not None
        assert leased["job_id"] == offered.job_id
        # GUILT (without the ::text cure): the codec decodes package to a
        # dict here, and this isinstance(..., str) fails.
        assert isinstance(leased["package"], str)
        assert _json.loads(leased["package"]) == {"history": [], "chunks": []}
    finally:
        await codec_conn.close()


async def test_worker_observed_deadline_expiry_folds_into_the_breaker(
    conn: asyncpg.Connection, pool: asyncpg.Pool
) -> None:
    """GUILT: ``wait_for_job``'s own deadline CAS — not only the reaper — must
    feed the breaker. A live worker that observes its OWN job blow its
    deadline is exactly the codex-leg-failure signal the breaker exists to
    count; if this fold were missing, a broker that always polls its own
    jobs (never leaving expiry to the reaper) would never trip the breaker
    at all. MAX_DEPTH is 1, so the loop offers one job at a time — the prior
    job's deadline CAS terminalizes it before the next offer can admit."""
    await _seed_alive_gauge(conn)
    for i in range(wa_broker.BREAKER_TRIP_AFTER):
        outbox_id, thread_id, claim = await _outbox_row(conn)
        offered = await _offer(conn, outbox_id, thread_id, claim)
        assert offered.outcome is OfferOutcome.OFFERED
        await conn.execute(
            "UPDATE broker_jobs SET deadline_at = now() - INTERVAL '1 second' "
            "WHERE job_id = $1",
            offered.job_id,
        )
        waited = await wa_broker.wait_for_job(pool, offered.job_id, poll_seconds=0)
        assert waited.outcome is WaitOutcome.DEADLINE
        if i == 0:
            assert (
                await conn.fetchval(
                    "SELECT consecutive_failures FROM wa_broker_gauge WHERE id = 1"
                )
            ) == 1
    assert (
        await conn.fetchval("SELECT breaker_state FROM wa_broker_gauge WHERE id = 1")
    ) == "open"


async def test_shadow_deadline_observed_by_a_waiter_does_not_fold(
    conn: asyncpg.Connection, pool: asyncpg.Pool
) -> None:
    """INNOCENCE twin of the previous test: a shadow-mode job hitting its own
    deadline_at is housekeeping, not a codex-leg failure — mirroring the
    reaper's own mode == 'serve' gate on the fold. Only a live SERVE waiter's
    deadline CAS may touch the breaker."""
    await _seed_alive_gauge(conn)
    outbox_id, thread_id, _claim = await _outbox_row(conn)
    job_id = await conn.fetchval(
        """
        INSERT INTO broker_jobs
            (outbox_id, thread_id, mode, state, package_hash, thread_epoch,
             deadline_at, expires_at)
        VALUES ($1, $2, 'shadow', 'offered', 'h', 1,
                now() - INTERVAL '1 second', now() + INTERVAL '1 hour')
        RETURNING job_id
        """,
        outbox_id,
        thread_id,
    )
    waited = await wa_broker.wait_for_job(pool, job_id, poll_seconds=0)
    assert waited.outcome is WaitOutcome.DEADLINE
    gauge = await conn.fetchrow("SELECT * FROM wa_broker_gauge WHERE id = 1")
    assert gauge["consecutive_failures"] == 0
    assert gauge["breaker_state"] == "closed"


async def test_typed_failure_completion_folds_into_the_breaker(
    conn: asyncpg.Connection,
) -> None:
    """GUILT: ``complete_job``'s typed-failure branch (``error_class`` set,
    terminal 'failed') must fold into the breaker exactly like a deadline
    expiry. This is the ONLY observer for a codex CLI that reports its own
    error before ever reaching its deadline (``cli_failure``/``exec_timeout``
    with time to spare) — uncured, ``complete_job`` never calls
    ``record_breaker_result`` at all, so this failure signal never reaches
    the gauge and the breaker stays permanently closed no matter how many
    typed failures land. MAX_DEPTH is 1; 'failed' is terminal, so depth frees
    each cycle for the next offer."""
    await _seed_alive_gauge(conn)
    for i in range(wa_broker.BREAKER_TRIP_AFTER):
        outbox_id, thread_id, claim = await _outbox_row(conn)
        offered = await _offer(conn, outbox_id, thread_id, claim)
        assert offered.outcome is OfferOutcome.OFFERED
        leased = await wa_broker.claim_job(conn, in_flight=0, last_exec_ms=None)
        assert leased is not None
        status = await wa_broker.complete_job(
            conn,
            job_id=offered.job_id,
            fence_token=leased["fence_token"],
            completion_key=f"fail-{i}",
            result_text=None,
            error_class="exec_timeout",
            exec_ms=5,
        )
        assert status is CompleteStatus.ACCEPTED
    assert (
        await conn.fetchval("SELECT breaker_state FROM wa_broker_gauge WHERE id = 1")
    ) == "open"


async def test_successful_completion_resets_the_failure_streak(
    conn: asyncpg.Connection,
) -> None:
    """GUILT: a codex leg that SUCCEEDS after some failures must reset
    ``consecutive_failures`` and close the breaker via ``complete_job``'s OWN
    success fold — not only via the standalone ``record_breaker_result``
    API surface an operator might call by hand. Two typed failures first
    (below trip threshold), then one success."""
    await _seed_alive_gauge(conn)
    for i in range(2):
        outbox_id, thread_id, claim = await _outbox_row(conn)
        offered = await _offer(conn, outbox_id, thread_id, claim)
        assert offered.outcome is OfferOutcome.OFFERED
        leased = await wa_broker.claim_job(conn, in_flight=0, last_exec_ms=None)
        assert leased is not None
        status = await wa_broker.complete_job(
            conn,
            job_id=offered.job_id,
            fence_token=leased["fence_token"],
            completion_key=f"fail-{i}",
            result_text=None,
            error_class="exec_timeout",
            exec_ms=5,
        )
        assert status is CompleteStatus.ACCEPTED
    assert (
        await conn.fetchval(
            "SELECT consecutive_failures FROM wa_broker_gauge WHERE id = 1"
        )
    ) == 2

    outbox_id, thread_id, claim = await _outbox_row(conn)
    offered = await _offer(conn, outbox_id, thread_id, claim)
    assert offered.outcome is OfferOutcome.OFFERED
    leased = await wa_broker.claim_job(conn, in_flight=0, last_exec_ms=None)
    assert leased is not None
    status = await wa_broker.complete_job(
        conn,
        job_id=offered.job_id,
        fence_token=leased["fence_token"],
        completion_key="ok-1",
        result_text="ok",
        error_class=None,
        exec_ms=100,
    )
    assert status is CompleteStatus.ACCEPTED
    gauge = await conn.fetchrow("SELECT * FROM wa_broker_gauge WHERE id = 1")
    assert gauge["consecutive_failures"] == 0
    assert gauge["breaker_state"] == "closed"


async def test_straggler_success_while_open_does_not_close_the_breaker(
    conn: asyncpg.Connection,
) -> None:
    """INNOCENCE guard on ``record_breaker_result(success=True)``: stale
    evidence from BEFORE the trip (a canary-unrelated success landing while
    the breaker is already open — e.g. a slow-but-eventually-successful
    completion for a job offered before the breaker tripped) must NOT bypass
    the cooldown+canary discipline. Only a canary win (through
    ``breaker_admits``'s half_open CAS) may close the breaker; an unguarded
    success reset would let a straggler undo an open breaker's cooldown
    entirely."""
    await _seed_alive_gauge(conn)
    for _ in range(wa_broker.BREAKER_TRIP_AFTER):
        await wa_broker.record_breaker_result(conn, success=False)
    gauge = await conn.fetchrow("SELECT * FROM wa_broker_gauge WHERE id = 1")
    assert gauge["breaker_state"] == "open"

    await wa_broker.record_breaker_result(conn, success=True)
    gauge = await conn.fetchrow("SELECT * FROM wa_broker_gauge WHERE id = 1")
    assert gauge["breaker_state"] == "open"
    assert gauge["breaker_opened_at"] is not None


async def test_typed_failure_fold_is_atomic_with_terminalization(
    conn: asyncpg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mirrors test_reaper_fold_is_atomic_with_terminalization for the
    complete_job typed-failure path (Codex re-verdict pattern, applied to a
    second call site): if the breaker fold crashes, the UPDATE that
    terminalizes the job to 'failed' must roll back WITH it — otherwise the
    job vanishes into a state the caller's CAS-based retry can never
    re-observe (fence_token already spent server-side, state no longer
    'leased') while its failure never reached the breaker. Proven by making
    record_breaker_result raise mid-completion: the job must still be
    'leased' afterwards, and a clean retry with the SAME completion_key must
    then both accept and terminalize it."""
    await _seed_alive_gauge(conn)
    outbox_id, thread_id, claim = await _outbox_row(conn)
    offered = await _offer(conn, outbox_id, thread_id, claim)
    assert offered.outcome is OfferOutcome.OFFERED
    leased = await wa_broker.claim_job(conn, in_flight=0, last_exec_ms=None)
    assert leased is not None
    fence = leased["fence_token"]

    real_record = wa_broker.record_breaker_result

    async def _exploding_record(*args: object, **kwargs: object) -> None:
        raise RuntimeError("crash between terminalize and fold")

    # Cycle 1 — the crash: the fold raises, so terminalization must roll
    # back with it and the job must still be leased (re-completable).
    monkeypatch.setattr(wa_broker, "record_breaker_result", _exploding_record)
    with pytest.raises(RuntimeError):
        await wa_broker.complete_job(
            conn,
            job_id=offered.job_id,
            fence_token=fence,
            completion_key="crash-key",
            result_text=None,
            error_class="exec_timeout",
            exec_ms=5,
        )
    assert (
        await conn.fetchval(
            "SELECT state FROM broker_jobs WHERE job_id = $1", offered.job_id
        )
    ) == "leased"

    # Clean retry, SAME completion_key: nothing was lost.
    monkeypatch.setattr(wa_broker, "record_breaker_result", real_record)
    status = await wa_broker.complete_job(
        conn,
        job_id=offered.job_id,
        fence_token=fence,
        completion_key="crash-key",
        result_text=None,
        error_class="exec_timeout",
        exec_ms=5,
    )
    assert status is CompleteStatus.ACCEPTED
    assert (
        await conn.fetchval(
            "SELECT state FROM broker_jobs WHERE job_id = $1", offered.job_id
        )
    ) == "failed"


async def test_builder_wire_text_survives_transport_with_matching_hash(
    conn: asyncpg.Connection,
) -> None:
    """Codex re-verdict r5, finding 1 — end to end: the bytes the BUILDER
    emits (wire_text, the SSOT serializer) travel offer->claim untouched
    and still hash to the package_hash the builder computed. This is the
    whole contract the broker daemon will verify; the earlier fidelity test
    proved the column, this proves the domain — to_payload()'s 7-field
    serialization could never satisfy it (it contains the hash itself)."""
    import hashlib as _hashlib

    from backend.services.rag.agentic import wa_package_builder as wpb

    fields = {
        "history": [{"role": "user", "content": "berapa modal disetor?"}],
        "chunks": [{"text": "BKPM 5/2025", "source": "kb"}],
        "pricing_block": None,
        "persona_digest": "persona-d",
        "evidence_inputs": {"domain": "company", "evidence_score": 0.8},
        "thread_epoch": 2,
    }
    pkg = wpb.ContextPackage(package_hash=wpb._package_hash(**fields), **fields)

    await _seed_alive_gauge(conn)
    outbox_id, thread_id, tok = await _outbox_row(conn)
    offered = await wa_broker.offer_job(
        conn,
        outbox_id=outbox_id,
        thread_id=thread_id,
        claim_token=tok,
        outbox_expected_status="generating",
        package=pkg.wire_text(),
        evidence_inputs="{}",
        package_hash=pkg.package_hash,
        thread_epoch=2,
    )
    assert offered.outcome is OfferOutcome.OFFERED
    leased = await wa_broker.claim_job(conn, in_flight=0, last_exec_ms=None)
    assert leased is not None
    assert (
        _hashlib.sha256(leased["package"].encode("utf-8")).hexdigest()
        == leased["package_hash"]
    )


async def test_same_completion_key_with_different_payload_conflicts(
    conn: asyncpg.Connection,
) -> None:
    """Codex re-verdict r5, finding 2 (GUILT): the contract promises
    CONFLICT for a corrupted retry — same completion_key and fence, but a
    DIFFERENT payload. Before completion_digest (migration 273) the replay
    check compared only key/fence/state, so that branch was unreachable:
    result B under A's key answered REPLAY 200 while the worker consumed A."""
    await _seed_alive_gauge(conn)
    outbox_id, thread_id, tok = await _outbox_row(conn)
    offered = await _offer(conn, outbox_id, thread_id, tok)
    assert offered.outcome is OfferOutcome.OFFERED
    leased = await wa_broker.claim_job(conn, in_flight=0, last_exec_ms=None)
    assert leased is not None
    fence = leased["fence_token"]

    accepted = await wa_broker.complete_job(
        conn,
        job_id=offered.job_id,
        fence_token=fence,
        completion_key="attempt-1",
        result_text="result A",
        error_class=None,
        exec_ms=10,
    )
    assert accepted is CompleteStatus.ACCEPTED

    # Same key, different TEXT -> CONFLICT (never a silent 200).
    different_text = await wa_broker.complete_job(
        conn,
        job_id=offered.job_id,
        fence_token=fence,
        completion_key="attempt-1",
        result_text="result B",
        error_class=None,
        exec_ms=10,
    )
    assert different_text is CompleteStatus.CONFLICT

    # Same key, typed FAILURE instead of the accepted success -> CONFLICT.
    different_kind = await wa_broker.complete_job(
        conn,
        job_id=offered.job_id,
        fence_token=fence,
        completion_key="attempt-1",
        result_text=None,
        error_class="exec_timeout",
        exec_ms=10,
    )
    assert different_kind is CompleteStatus.CONFLICT


async def test_identical_retry_still_replays_after_consumption(
    conn: asyncpg.Connection,
) -> None:
    """INNOCENCE twin: the digest is frozen OUTSIDE the payload columns, so
    consume_result NULLing result_text does not turn a legitimate identical
    retry (lost HTTP response, late re-POST) into a false CONFLICT."""
    await _seed_alive_gauge(conn)
    outbox_id, thread_id, tok = await _outbox_row(conn)
    offered = await _offer(conn, outbox_id, thread_id, tok)
    assert offered.outcome is OfferOutcome.OFFERED
    leased = await wa_broker.claim_job(conn, in_flight=0, last_exec_ms=None)
    assert leased is not None
    fence = leased["fence_token"]

    accepted = await wa_broker.complete_job(
        conn,
        job_id=offered.job_id,
        fence_token=fence,
        completion_key="attempt-1",
        result_text="the reply",
        error_class=None,
        exec_ms=10,
    )
    assert accepted is CompleteStatus.ACCEPTED
    assert (await wa_broker.consume_result(conn, offered.job_id)) == "the reply"

    replay = await wa_broker.complete_job(
        conn,
        job_id=offered.job_id,
        fence_token=fence,
        completion_key="attempt-1",
        result_text="the reply",
        error_class=None,
        exec_ms=10,
    )
    assert replay is CompleteStatus.REPLAY


@pytest.mark.asyncio
async def test_completed_pending_consume_requires_completed_at(pool) -> None:
    """GUILT for migration 274 (the follow-up expire_stale_jobs' docstring
    promised to PR-5): a malformed writer minting completed_pending_consume
    WITHOUT completed_at would anchor the dead-consumer grace on nothing —
    the CHECK makes that row unwritable, not merely reapable."""
    async with pool.acquire() as conn:
        await _seed_alive_gauge(conn)
        outbox_id, thread_id, tok = await _outbox_row(conn)
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                """
                INSERT INTO broker_jobs
                    (outbox_id, thread_id, mode, state, package,
                     package_hash, thread_epoch, deadline_at)
                VALUES ($1, $2, 'serve', 'completed_pending_consume',
                        '{}', 'h', 1, now() + INTERVAL '15 second')
                """,
                outbox_id,
                thread_id,
            )
        # INNOCENCE: the same row WITH completed_at is accepted.
        await conn.execute(
            """
            INSERT INTO broker_jobs
                (outbox_id, thread_id, mode, state, package,
                 package_hash, thread_epoch, deadline_at, completed_at)
            VALUES ($1, $2, 'serve', 'completed_pending_consume',
                    '{}', 'h', 1, now() + INTERVAL '15 second', now())
            """,
            outbox_id,
            thread_id,
        )
