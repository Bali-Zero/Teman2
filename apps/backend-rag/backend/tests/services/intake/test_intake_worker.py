"""Integration tests for the intake worker orchestrator (FASE 2).

Runs against the LOCAL nuzantara_test DB.  The operational nuzantara_dev DB is
never a test default because it contains the live Intake queue.
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
from types import ModuleType

import asyncpg
import pytest
import pytest_asyncio

from backend.services.intake.enqueue import enqueue
from backend.services.intake.worker import (
    STAGE_TRANSITIONS,
    IntakeWorker,
    TransientStageError,
    WorkerConfig,
    _install_canonical_main_alias,
    reap_expired_review_claims,
    remap_legacy_statuses,
)

_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_test",
)
_TEST_PIPELINE_VERSION = f"pytest-intake-{os.getpid()}"

# Number of stub stages from 'pending' to 'done'.
_N_STAGES = len(STAGE_TRANSITIONS)


def test_main_module_alias_prevents_transient_error_class_duplication() -> None:
    """``python -m`` must not make stages.py import a second worker module copy."""
    main_mod = ModuleType("__main__")
    modules = {"__main__": main_mod}

    alias = _install_canonical_main_alias("__main__", "backend.services.intake", modules)

    assert alias == "backend.services.intake.worker"
    assert modules["backend.services.intake.worker"] is main_mod


def test_main_module_alias_is_noop_on_normal_import() -> None:
    modules = {"backend.services.intake.worker": ModuleType("worker")}

    alias = _install_canonical_main_alias(
        "backend.services.intake.worker", "backend.services.intake", modules
    )

    assert alias is None


def test_worker_config_filters_from_env(monkeypatch):
    monkeypatch.setenv("INTAKE_SOURCE_FILTER", "whatsapp")
    monkeypatch.setenv("INTAKE_PIPELINE_VERSION_FILTER", "v2.2-qwen-text-autocatalog")

    cfg = WorkerConfig.from_env()

    assert cfg.source_filter == "whatsapp"
    assert cfg.pipeline_version_filter == "v2.2-qwen-text-autocatalog"


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
            pipeline_version=_TEST_PIPELINE_VERSION,
        )
        qids.append(res.queue_id)
    return qids


async def _cleanup(pool: asyncpg.Pool, qids: list[int]) -> None:
    if not qids:
        return
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM intake_stage_metrics WHERE queue_id = ANY($1)", qids)
        rows = await conn.fetch("SELECT id, instance_id FROM intake_queue WHERE id = ANY($1)", qids)
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
        cfg = WorkerConfig(
            lease_ttl_seconds=30,
            heartbeat_interval_seconds=999,
            poll_interval_seconds=0.01,
            pipeline_version_filter=_TEST_PIPELINE_VERSION,
        )
        w1 = IntakeWorker(pool, config=cfg, worker_id="w1")
        w2 = IntakeWorker(pool, config=cfg, worker_id="w2")
        await _drive_to_done([w1, w2], qids, pool, timeout=90.0)

        st = await _statuses(pool, qids)
        assert st.get("done", 0) == n, f"not all done: {st}"

        async with pool.acquire() as conn:
            # Each stage's final 'route' metric should appear exactly once/job.
            route_ok = await conn.fetchval(
                "SELECT count(*) FROM intake_stage_metrics WHERE queue_id = ANY($1) "
                "AND stage='route' AND ok = true",
                qids,
            )
            total_ok = await conn.fetchval(
                "SELECT count(*) FROM intake_stage_metrics WHERE queue_id = ANY($1) AND ok = true",
                qids,
            )
        assert route_ok == n, f"route_ok={route_ok} != {n} (double-processing!)"
        assert total_ok == n * _N_STAGES, f"total_ok={total_ok} != {n * _N_STAGES}"
        print(
            f"\n[exactly-once] {n} jobs, 2 workers -> done={st.get('done')}, "
            f"route_ok={route_ok}, total_ok={total_ok} (expect {n}/{n * _N_STAGES})"
        )
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
        cfg = WorkerConfig(
            lease_ttl_seconds=lease_ttl,
            heartbeat_interval_seconds=999,
            poll_interval_seconds=0.05,
            pipeline_version_filter=_TEST_PIPELINE_VERSION,
        )
        dead_worker = IntakeWorker(pool, config=cfg, worker_id="dead")

        # Claim (takes the LEASE ONLY — v2 never touches status at claim time,
        # so a crash here can never strand the stage cursor) -> sim crash.
        async with pool.acquire() as conn:
            job = await dead_worker._claim_with_inbound(conn)
        assert job is not None and job["id"] == qid

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT status, lease_owner, lease_expires_at > now() AS leased "
                "FROM intake_queue WHERE id=$1",
                qid,
            )
        assert row["status"] == "pending"  # v2: claim is lease-only, status untouched
        assert row["lease_owner"] == "dead"
        assert row["leased"] is True
        print(f"\n[reclaim] job {qid} claimed by dead worker, lease held: {dict(row)}")

        # Live worker tries immediately -> must NOT be able to claim (lease valid).
        live = IntakeWorker(
            pool,
            config=cfg,
            worker_id="live",
        )
        async with pool.acquire() as conn:
            stolen = await live._claim_with_inbound(conn)
        assert stolen is None, "lease not respected: live worker stole a held job"
        print("[reclaim] live worker correctly BLOCKED while lease valid")

        # Wait out the lease, then the live worker reclaims + completes.
        await asyncio.sleep(lease_ttl + 0.5)
        await _drive_to_done([live], qids, pool, timeout=30.0)

        st = await _statuses(pool, qids)
        assert st.get("done", 0) == 1, f"job lost / not reclaimed: {st}"
        print(f"[reclaim] after lease expiry, live worker reclaimed -> {st}")
    finally:
        await _cleanup(pool, qids)


@pytest.mark.asyncio
async def test_claim_filter_limits_worker_to_source_and_pipeline(pool, tmp_path):
    """A filtered maintenance worker claims only the staged rollout rows."""
    qids = await _make_jobs(pool, tmp_path, 3, "filter")
    version = f"flt-{uuid.uuid4().hex[:12]}"
    target, wrong_version, wrong_source = qids
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE intake_queue
                   SET source = 'whatsapp',
                       pipeline_version = $2,
                       next_visible_at = now(),
                       lease_owner = NULL,
                       lease_expires_at = NULL
                 WHERE id = $1
                """,
                target,
                version,
            )
            await conn.execute(
                """
                UPDATE intake_queue
                   SET source = 'whatsapp',
                       pipeline_version = $2,
                       next_visible_at = now(),
                       lease_owner = NULL,
                       lease_expires_at = NULL
                 WHERE id = $1
                """,
                wrong_version,
                f"{version}-other",
            )
            await conn.execute(
                """
                UPDATE intake_queue
                   SET source = 'drive',
                       pipeline_version = $2,
                       next_visible_at = now(),
                       lease_owner = NULL,
                       lease_expires_at = NULL
                 WHERE id = $1
                """,
                wrong_source,
                version,
            )

        cfg = WorkerConfig(
            lease_ttl_seconds=30,
            heartbeat_interval_seconds=999,
            poll_interval_seconds=0.01,
            source_filter="whatsapp",
            pipeline_version_filter=version,
        )
        worker = IntakeWorker(pool, config=cfg, worker_id="filter-w")
        async with pool.acquire() as conn:
            claimed = await worker._claim_with_inbound(conn)
            second_claim = await worker._claim_with_inbound(conn)

        assert claimed is not None
        assert claimed["id"] == target
        assert second_claim is None
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
        cfg = WorkerConfig(
            lease_ttl_seconds=30,
            heartbeat_interval_seconds=999,
            poll_interval_seconds=0.01,
            base_backoff_seconds=0.05,
            max_backoff_seconds=0.2,
            pipeline_version_filter=_TEST_PIPELINE_VERSION,
        )
        alerts: list[str] = []

        async def capture_alert(msg: str) -> None:
            alerts.append(msg)

        w = IntakeWorker(pool, config=cfg, worker_id="poison-w", alert_fn=capture_alert)

        # Inject a stage handler that always crashes.
        synthetic_email = "test" + "@" + "x.example"
        synthetic_ktp = "1234" * 4

        async def crash(job, stage):  # noqa: ANN001
            raise RuntimeError(f"poison stage={stage} leak {synthetic_email} KTP {synthetic_ktp}")

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
                qid,
            )
        st = await _statuses(pool, qids)
        assert st.get("dead", 0) == 1, f"poison did not go dead: {st}"
        assert row["attempts"] == row["max_attempts"], f"attempts={row['attempts']}"
        assert len(alerts) == 1, f"expected 1 alert, got {len(alerts)}: {alerts}"
        # PII masked in persisted error.
        assert synthetic_email not in row["last_error"], row["last_error"]
        assert synthetic_ktp not in row["last_error"], row["last_error"]
        assert "[EMAIL]" in row["last_error"] and "[KTP/CARD]" in row["last_error"]
        assert iters < max_iters, "ran to iter cap -> suspected infinite loop"
        print(
            f"\n[poison] dead after attempts={row['attempts']}/{row['max_attempts']}, "
            f"iters={iters}, alerts={len(alerts)}, last_error={row['last_error']!r}"
        )
    finally:
        await _cleanup(pool, qids)


@pytest.mark.asyncio
async def test_transient_stage_error_does_not_burn_attempt(pool, tmp_path):
    """Infra-down transient failures stay retryable and do not consume attempts."""
    qids = await _make_jobs(pool, tmp_path, 1, "transient")
    qid = qids[0]
    try:
        worker_id = "transient-worker"
        cfg = WorkerConfig(
            lease_ttl_seconds=30,
            heartbeat_interval_seconds=999,
            poll_interval_seconds=0.01,
            transient_backoff_seconds=30,
            pipeline_version_filter=_TEST_PIPELINE_VERSION,
        )
        alerts: list[str] = []

        async def capture_alert(msg: str) -> None:
            alerts.append(msg)

        async def transient_handler(job: dict, stage: str) -> dict:
            raise TransientStageError("local model warming up")

        worker = IntakeWorker(
            pool,
            config=cfg,
            worker_id=worker_id,
            alert_fn=capture_alert,
            stage_handler=transient_handler,
        )

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT attempts, max_attempts, source, source_ref FROM intake_queue WHERE id=$1",
                qid,
            )
            await conn.execute(
                """
                UPDATE intake_queue
                   SET lease_owner = $2,
                       lease_expires_at = now() + interval '30 seconds'
                 WHERE id = $1
                """,
                qid,
                worker_id,
            )

        await worker._process_one(
            {
                "id": qid,
                "attempts": row["attempts"],
                "max_attempts": row["max_attempts"],
                "source": row["source"],
                "source_ref": row["source_ref"],
                "_inbound_status": "pending",
            }
        )

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT status, attempts, last_error, lease_owner, lease_expires_at,
                       next_visible_at > now() AS delayed
                  FROM intake_queue
                 WHERE id = $1
                """,
                qid,
            )
            metric_count = await conn.fetchval(
                """
                SELECT count(*)
                  FROM intake_stage_metrics
                 WHERE queue_id = $1 AND stage = 'classify' AND ok = false
                """,
                qid,
            )

        assert row["status"] == "pending"
        assert row["attempts"] == 0
        assert row["lease_owner"] is None
        assert row["lease_expires_at"] is None
        assert row["delayed"] is True
        assert row["last_error"].startswith("transient:")
        assert metric_count == 1
        assert alerts == []
    finally:
        await _cleanup(pool, qids)


@pytest.mark.asyncio
async def test_remap_legacy_statuses_stage_aware(pool, tmp_path):
    """v1 -> v2 boot remap: stage-aware status mapping + ghost-lease release.

    The ``stage`` column holds the last COMPLETED stage, so every v1 name maps
    deterministically:
      ('processing','classify') -> ocr_done    ('ocr','ocr')          -> ocr_done
      ('processing','extract')  -> extracted   ('classified','extract')-> extracted
      ('processing','validate') -> validated   ('extracted','validate')-> validated
    A genuine v2 row ('extracted', stage='extract') must NOT be touched.
    NOTE: we never assert on the returned count — the live dev DB may carry
    other legacy rows that the (idempotent, boot-time) remap also touches.
    """
    qids = await _make_jobs(pool, tmp_path, 6, "remap")
    extra: list[int] = []
    try:
        v1_shapes = [
            ("processing", "classify", "ocr_done"),
            ("processing", "extract", "extracted"),
            ("processing", "validate", "validated"),
            ("ocr", "ocr", "ocr_done"),
            ("classified", "extract", "extracted"),
            ("extracted", "validate", "validated"),
        ]
        async with pool.acquire() as conn:
            for qid, (v1_status, v1_stage, _) in zip(qids, v1_shapes, strict=True):
                await conn.execute(
                    "UPDATE intake_queue SET status=$2, stage=$3, "
                    "lease_owner='ghost', lease_expires_at=now() + interval '1 hour' "
                    "WHERE id=$1",
                    qid,
                    v1_status,
                    v1_stage,
                )

        await remap_legacy_statuses(pool)

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, status, lease_owner, next_visible_at <= now() AS visible "
                "FROM intake_queue WHERE id = ANY($1)",
                qids,
            )
        by_id = {r["id"]: r for r in rows}
        for qid, (v1_status, v1_stage, expected) in zip(qids, v1_shapes, strict=True):
            row = by_id[qid]
            assert row["status"] == expected, (
                f"({v1_status},{v1_stage}) remapped to {row['status']!r}, expected {expected!r}"
            )
            assert row["lease_owner"] is None, (
                f"ghost lease NOT released for ({v1_status},{v1_stage})"
            )
            assert row["visible"] is True, (
                f"next_visible_at not reset to now() for ({v1_status},{v1_stage})"
            )

        # 7th check: a genuine v2 row (extract done -> status='extracted',
        # stage='extract') is OUTSIDE the remap WHERE and must stay untouched.
        extra = await _make_jobs(pool, tmp_path, 1, "remap-v2")
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE intake_queue SET status='extracted', stage='extract' WHERE id=$1", extra[0]
            )
        await remap_legacy_statuses(pool)
        async with pool.acquire() as conn:
            v2_status = await conn.fetchval("SELECT status FROM intake_queue WHERE id=$1", extra[0])
        assert v2_status == "extracted", (
            f"v2 row (status='extracted', stage='extract') was wrongly remapped to {v2_status!r}"
        )
        print(
            f"\n[remap] 6 v1 shapes remapped stage-aware, leases released; "
            f"v2 row untouched ({v2_status})"
        )
    finally:
        await _cleanup(pool, qids + extra)


@pytest.mark.asyncio
async def test_reap_expired_review_claims(pool, tmp_path):
    """Expired review_claimed proposals return to review_pending; live ones don't.

    The reaper must clear ALL four lease columns (lease_owner, claim_token,
    claimed_at, lease_expires_at) on the expired claim and leave a still-live
    claim fully intact. No count assertion (live DB may have other stale claims).
    """
    qids = await _make_jobs(pool, tmp_path, 2, "reap")
    pids: list[int] = []
    try:
        async with pool.acquire() as conn:
            p_expired = await conn.fetchval(
                """
                INSERT INTO document_routing_proposal
                    (queue_id, doc_index, pipeline_version, routing_key,
                     entity_resolution, routing, commit_gate, status,
                     lease_owner, lease_expires_at, claim_token, claimed_at)
                VALUES ($1, 0, 'v1', $2, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb,
                        'review_claimed', 'x', now() - interval '1 minute', $3, now())
                RETURNING id
                """,
                qids[0],
                f"reap-exp-{uuid.uuid4().hex[:8]}",
                uuid.uuid4(),
            )
            p_live = await conn.fetchval(
                """
                INSERT INTO document_routing_proposal
                    (queue_id, doc_index, pipeline_version, routing_key,
                     entity_resolution, routing, commit_gate, status,
                     lease_owner, lease_expires_at, claim_token, claimed_at)
                VALUES ($1, 0, 'v1', $2, '{}'::jsonb, '{}'::jsonb, '{}'::jsonb,
                        'review_claimed', 'y', now() + interval '10 minutes', $3, now())
                RETURNING id
                """,
                qids[1],
                f"reap-live-{uuid.uuid4().hex[:8]}",
                uuid.uuid4(),
            )
            pids += [p_expired, p_live]

        await reap_expired_review_claims(pool)

        async with pool.acquire() as conn:
            exp = await conn.fetchrow(
                "SELECT status, lease_owner, claim_token, claimed_at, lease_expires_at "
                "FROM document_routing_proposal WHERE id=$1",
                p_expired,
            )
            live = await conn.fetchrow(
                "SELECT status, lease_owner, claim_token, claimed_at, lease_expires_at "
                "FROM document_routing_proposal WHERE id=$1",
                p_live,
            )

        assert exp["status"] == "review_pending", f"expired claim not reaped: {dict(exp)}"
        assert exp["lease_owner"] is None
        assert exp["claim_token"] is None
        assert exp["claimed_at"] is None
        assert exp["lease_expires_at"] is None

        assert live["status"] == "review_claimed", f"live claim wrongly reaped: {dict(live)}"
        assert live["lease_owner"] == "y"
        assert live["claim_token"] is not None
        assert live["claimed_at"] is not None
        assert live["lease_expires_at"] is not None
        print(
            f"\n[reap] expired claim {p_expired} -> review_pending (lease cleared); "
            f"live claim {p_live} intact"
        )
    finally:
        async with pool.acquire() as conn:
            for pid in pids:
                await conn.execute("DELETE FROM document_routing_proposal WHERE id=$1", pid)
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
                "next_visible_at=now() WHERE id=$1",
                qid,
            )
        cfg = WorkerConfig(
            lease_ttl_seconds=30,
            poll_interval_seconds=0.01,
            pipeline_version_filter=_TEST_PIPELINE_VERSION,
        )
        w = IntakeWorker(pool, config=cfg, worker_id="term-w")
        async with pool.acquire() as conn:
            claimed = await w._claim_with_inbound(conn)
        # claimed could be another test's row only if ids overlap; assert it's not ours.
        assert claimed is None or claimed["id"] != qid, (
            f"DEAD job was claimable (W61 violation): {claimed}"
        )
        st = await _statuses(pool, qids)
        assert st.get("dead", 0) == 1
        print(f"\n[dead-terminal] job {qid} status=dead, never re-claimed -> {st}")
    finally:
        await _cleanup(pool, qids)
