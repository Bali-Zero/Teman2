"""Integration tests for the intake worker orchestrator (FASE 2).

Runs against the LOCAL nuzantara_dev DB (same default as test_intake_enqueue).
Each test enqueues its own jobs via the FASE 1 enqueue() core (unique blobs ->
unique intake_key), runs real IntakeWorker instances against them, then cleans
up by blob_hash. Short lease TTLs (2-3s) keep the reclaim test fast.

Covered:
  - exactly-once: 2 concurrent workers, 100 jobs -> each reaches 'done' exactly
    once, no double-claim (SKIP LOCKED).
  - kill -9 reclaim: a worker dies mid-job (lease held) -> after lease_ttl the
    job is re-claimable and completes; 0 jobs lost.
  - poison-pill: a stage that always raises -> job ends 'dead' after
    max_attempts, alert fired, no infinite loop.
  - attempts>max -> dead terminal transition.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import asyncpg
import pytest
import pytest_asyncio

from backend.services.intake.enqueue import enqueue
from backend.services.intake.worker import (
    IntakeWorker,
    WorkerConfig,
    STAGE_TRANSITIONS,
)

_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_dev",
)

# Number of stub stages from 'pending' to 'done'.
_N_STAGES = len(STAGE_TRANSITIONS)


@pytest_asyncio.fixture
async def pool():
    p = await asyncpg.create_pool(_DB_URL, min_size=2, max_size=12)
    try:
        yield p
    finally:
        await p.close()


async def _make_jobs(pool: asyncpg.Pool, tmp_path, n: int, tag: str) -> list[int]:
    """Enqueue n unique jobs; return their queue ids. Unique blob per job."""
    qids: list[int] = []
    for i in range(n):
        f = tmp_path / f"{tag}-{i}.bin"
        f.write_bytes(f"{tag}-{i}-{uuid.uuid4()}".encode())
        res = await enqueue(
            pool,
            source="drive",
            source_ref=f"test/{tag}/{uuid.uuid4()}",
            blob_path=str(f),
        )
        qids.append(res.queue_id)
    return qids


async def _cleanup(pool: asyncpg.Pool, qids: list[int]) -> None:
    if not qids:
        return
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM intake_stage_metrics WHERE queue_id = ANY($1)", qids)
        rows = await conn.fetch(
            "SELECT id, instance_id FROM intake_queue WHERE id = ANY($1)", qids
        )
        await conn.execute("DELETE FROM intake_queue WHERE id = ANY($1)", qids)
        inst_ids = list({r["instance_id"] for r in rows})
        if inst_ids:
            # Only delete instances no longer referenced.
            await conn.execute(
                """DELETE FROM document_instances di WHERE di.id = ANY($1)
                   AND NOT EXISTS (SELECT 1 FROM intake_queue q WHERE q.instance_id = di.id)""",
                inst_ids,
            )


async def _statuses(pool: asyncpg.Pool, qids: list[int]) -> dict[str, int]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT status, count(*) c FROM intake_queue WHERE id = ANY($1) GROUP BY status",
            qids,
        )
    return {r["status"]: r["c"] for r in rows}


async def _drive_to_done(workers, qids, pool, timeout=60.0):
    """Run workers cooperatively until all qids are 'done'/'dead' or timeout."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    # Each worker keeps calling run_once until no work, then we re-check.
    async def drain(w):
        while loop.time() < deadline:
            did = await w.run_once()
            if not did:
                # check if everything terminal
                st = await _statuses(pool, qids)
                if (st.get("done", 0) + st.get("dead", 0)) == len(qids):
                    return
                await asyncio.sleep(0.05)
    await asyncio.gather(*(drain(w) for w in workers))


@pytest.mark.asyncio
async def test_exactly_once_two_workers_100_jobs(pool, tmp_path):
    """100 jobs, 2 concurrent workers -> each job done exactly once.

    Exactly-once is proven by: (a) every job ends 'done', and (b) the number of
    successful 'route' (final-stage) metrics equals the number of jobs (no job
    completed twice), and (c) each job has exactly _N_STAGES ok metrics.
    """
    n = 100
    qids = await _make_jobs(pool, tmp_path, n, "eo")
    try:
        cfg = WorkerConfig(lease_ttl_seconds=30, heartbeat_interval_seconds=999,
                           poll_interval_seconds=0.01)
        w1 = IntakeWorker(pool, config=cfg, worker_id="w1")
        w2 = IntakeWorker(pool, config=cfg, worker_id="w2")
        await _drive_to_done([w1, w2], qids, pool, timeout=90.0)

        st = await _statuses(pool, qids)
        assert st.get("done", 0) == n, f"not all done: {st}"

        async with pool.acquire() as conn:
            # Each stage's final 'route' metric should appear exactly once/job.
            route_ok = await conn.fetchval(
                "SELECT count(*) FROM intake_stage_metrics WHERE queue_id = ANY($1) "
                "AND stage='route' AND ok = true", qids,
            )
            total_ok = await conn.fetchval(
                "SELECT count(*) FROM intake_stage_metrics WHERE queue_id = ANY($1) "
                "AND ok = true", qids,
            )
        assert route_ok == n, f"route_ok={route_ok} != {n} (double-processing!)"
        assert total_ok == n * _N_STAGES, f"total_ok={total_ok} != {n * _N_STAGES}"
        print(f"\n[exactly-once] {n} jobs, 2 workers -> done={st.get('done')}, "
              f"route_ok={route_ok}, total_ok={total_ok} (expect {n}/{n*_N_STAGES})")
    finally:
        await _cleanup(pool, qids)


@pytest.mark.asyncio
async def test_kill9_reclaim_no_job_lost(pool, tmp_path):
    """A worker holds a lease then 'dies'; after lease_ttl the job is reclaimed.

    Simulate kill -9 by claiming a job, NOT releasing it, then dropping the
    worker. A second worker must reclaim it after lease_expires_at < now() and
    drive it to done.
    """
    qids = await _make_jobs(pool, tmp_path, 1, "kr")
    qid = qids[0]
    try:
        lease_ttl = 2  # seconds
        cfg = WorkerConfig(lease_ttl_seconds=lease_ttl, heartbeat_interval_seconds=999,
                           poll_interval_seconds=0.05)
        dead_worker = IntakeWorker(pool, config=cfg, worker_id="dead")

        # Claim (takes lease, flips to 'processing') but DO NOT process -> sim crash.
        async with pool.acquire() as conn:
            job = await dead_worker._claim_with_inbound(conn)
        assert job is not None and job["id"] == qid

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status, lease_owner, lease_expires_at > now() AS leased "
                "FROM intake_queue WHERE id=$1", qid)
        assert row["status"] == "processing"
        assert row["lease_owner"] == "dead"
        assert row["leased"] is True
        print(f"\n[reclaim] job {qid} claimed by dead worker, lease held: {dict(row)}")

        # Live worker tries immediately -> must NOT be able to claim (lease valid).
        live = IntakeWorker(pool, config=cfg, worker_id="live", )
        async with pool.acquire() as conn:
            stolen = await live._claim_with_inbound(conn)
        assert stolen is None, "lease not respected: live worker stole a held job"
        print(f"[reclaim] live worker correctly BLOCKED while lease valid")

        # Wait out the lease, then the live worker reclaims + completes.
        await asyncio.sleep(lease_ttl + 0.5)
        await _drive_to_done([live], qids, pool, timeout=30.0)

        st = await _statuses(pool, qids)
        assert st.get("done", 0) == 1, f"job lost / not reclaimed: {st}"
        print(f"[reclaim] after lease expiry, live worker reclaimed -> {st}")
    finally:
        await _cleanup(pool, qids)


@pytest.mark.asyncio
async def test_poison_pill_goes_dead_with_alert(pool, tmp_path):
    """A job whose first stage always crashes -> 'dead' after max_attempts.

    Verifies: terminal 'dead', attempts == max_attempts, alert fired once,
    last_error is PII-masked, and NO infinite loop (bounded run_once calls).
    """
    qids = await _make_jobs(pool, tmp_path, 1, "poison")
    qid = qids[0]
    try:
        # max_attempts default 5 in schema; short backoff so it's fast.
        cfg = WorkerConfig(lease_ttl_seconds=30, heartbeat_interval_seconds=999,
                           poll_interval_seconds=0.01, base_backoff_seconds=0.05,
                           max_backoff_seconds=0.2)
        alerts: list[str] = []

        async def capture_alert(msg: str) -> None:
            alerts.append(msg)

        w = IntakeWorker(pool, config=cfg, worker_id="poison-w",
                         alert_fn=capture_alert)
        # Inject a stage handler that always crashes.
        async def crash(job, stage):  # noqa: ANN001
            raise RuntimeError(
                "poison stage=%s leak test@x.com KTP 1234567890123456" % stage
            )
        w.stage_handler = crash

        # Drive with a hard cap on iterations to prove NO infinite loop.
        max_iters = 200
        iters = 0
        loop = asyncio.get_event_loop()
        deadline = loop.time() + 30
        while iters < max_iters and loop.time() < deadline:
            iters += 1
            did = await w.run_once()
            if not did:
                st = await _statuses(pool, qids)
                if st.get("dead", 0) == 1:
                    break
                await asyncio.sleep(0.02)

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status, attempts, max_attempts, last_error FROM intake_queue WHERE id=$1",
                qid)
        st = await _statuses(pool, qids)
        assert st.get("dead", 0) == 1, f"poison did not go dead: {st}"
        assert row["attempts"] == row["max_attempts"], f"attempts={row['attempts']}"
        assert len(alerts) == 1, f"expected 1 alert, got {len(alerts)}: {alerts}"
        # PII masked in persisted error.
        assert "test@x.com" not in row["last_error"], row["last_error"]
        assert "1234567890123456" not in row["last_error"], row["last_error"]
        assert "[EMAIL]" in row["last_error"] and "[KTP/CARD]" in row["last_error"]
        assert iters < max_iters, "ran to iter cap -> suspected infinite loop"
        print(f"\n[poison] dead after attempts={row['attempts']}/{row['max_attempts']}, "
              f"iters={iters}, alerts={len(alerts)}, last_error={row['last_error']!r}")
    finally:
        await _cleanup(pool, qids)


@pytest.mark.asyncio
async def test_attempts_over_max_is_terminal_dead(pool, tmp_path):
    """A 'dead' job is terminal: it is NOT in the claimable set (W61)."""
    qids = await _make_jobs(pool, tmp_path, 1, "term")
    qid = qids[0]
    try:
        # Force the row to dead directly, then assert no worker can claim it.
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE intake_queue SET status='dead', attempts=max_attempts, "
                "next_visible_at=now() WHERE id=$1", qid)
        cfg = WorkerConfig(lease_ttl_seconds=30, poll_interval_seconds=0.01)
        w = IntakeWorker(pool, config=cfg, worker_id="term-w")
        async with pool.acquire() as conn:
            claimed = await w._claim_with_inbound(conn)
        # claimed could be another test's row only if ids overlap; assert it's not ours.
        assert claimed is None or claimed["id"] != qid, \
            f"DEAD job was claimable (W61 violation): {claimed}"
        st = await _statuses(pool, qids)
        assert st.get("dead", 0) == 1
        print(f"\n[dead-terminal] job {qid} status=dead, never re-claimed -> {st}")
    finally:
        await _cleanup(pool, qids)
