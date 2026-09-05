"""Opt-in real PostgreSQL proof; exact disposable database only, never models.

DUAL_CONSUL_TEST_DSN must explicitly name dual_consul_test. The fixture resets
only this slice's tables there and serializes schema setup with an advisory lock.
Run on Pro against a disposable PostgreSQL instance, not an operational database.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import suppress
from pathlib import Path
from textwrap import dedent
from typing import Any
from urllib.parse import unquote, urlsplit

import asyncpg
import pytest

from backend.app.core.database import init_asyncpg_connection
from backend.db.migration_base import split_migration_sql
from backend.migrations.migration_124_autonomous_lab_runtime import apply as apply_lab
from backend.services.autonomous_lab import consul_executor, consul_store
from backend.services.autonomous_lab.consul_executor import ConsulSyntheticStage, execute_synthetic
from backend.services.autonomous_lab.state_store import (
    AutonomousLabStateStore,
    LabRunQueueItem,
    resolve_runtime_placement,
)
from backend.services.autonomous_lab.worker import AutonomousLabWorker
from backend.tests.unit.services.autonomous_lab.consul_fixtures import make_request

pytestmark = pytest.mark.integration
MIGRATIONS = Path(__file__).resolve().parents[2] / "db" / "migrations_v2"
OWNER = "consul-astra"


def _dsn() -> str:
    value = os.environ.get("DUAL_CONSUL_TEST_DSN")
    if not value:
        pytest.skip("DUAL_CONSUL_TEST_DSN is required for isolated PostgreSQL proof")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"postgres", "postgresql"}
        or unquote(parsed.path) != "/dual_consul_test"
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Dual Consul tests require exactly dual_consul_test without DSN overrides")
    return value


@pytest.fixture
async def dual_db() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(_dsn())
    try:
        await init_asyncpg_connection(conn)
        if await conn.fetchval("SELECT current_database()") != "dual_consul_test":
            raise RuntimeError("connected database is not dual_consul_test")
        await conn.execute("SELECT pg_advisory_lock(hashtext('dual-consul-test-schema'))")
        await conn.execute("""
            DROP TABLE IF EXISTS autonomous_lab_consul_leases,
                autonomous_lab_events_outbox, autonomous_lab_runs, research_os_objects CASCADE;
            DROP FUNCTION IF EXISTS public.reject_research_os_objects_mutation();
        """)
        async with conn.transaction():
            await apply_lab(conn)
            for name in (
                "279_research_os_contract_core.sql",
                "280_research_os_objects_truncate_guard.sql",
                "306_autonomous_lab_consul_leases.sql",
            ):
                forward, _ = split_migration_sql((MIGRATIONS / name).read_text())
                await conn.execute(forward)
        yield conn
    finally:
        await conn.close()


def _store() -> AutonomousLabStateStore:
    store = AutonomousLabStateStore()
    store.placement = resolve_runtime_placement("Nuzantara", "nuzantara")
    return store


async def _enqueue(conn: asyncpg.Connection, run_id: str) -> AutonomousLabStateStore:
    store = _store()
    await store.enqueue_run(
        conn,
        LabRunQueueItem(
            run_id=run_id,
            idempotency_key=run_id,
            objective="Synthetic Consul ownership proof",
            receipt={"run_id": run_id, "blocked": False, "summary": "Synthetic proof only"},
        ),
    )
    return store


async def _admit(conn: asyncpg.Connection, run_id: str = "consul-db-proof") -> tuple[Any, Any]:
    store = await _enqueue(conn, run_id)
    assert await store.claim_next_run(conn, worker_id=OWNER) is not None
    request = make_request(await conn.fetchval("SELECT clock_timestamp()"), run_id)
    request.validate(await conn.fetchval("SELECT clock_timestamp()"))
    lease = await consul_store.bind(
        conn,
        run_id=run_id,
        owner_id=OWNER,
        **request.pins,
        grant_expires_at=request.review.expires_at,
    )
    return request, lease


async def _counts(conn: asyncpg.Connection) -> tuple[int, int, int]:
    return (
        await conn.fetchval(
            "SELECT count(*) FROM research_os_objects WHERE object_kind='execution_attempt'"
        ),
        await conn.fetchval(
            "SELECT count(*) FROM research_os_objects WHERE object_kind='operational_receipt'"
        ),
        await conn.fetchval(
            "SELECT count(*) FROM autonomous_lab_events_outbox WHERE payload->>'result'='synthetic_confirmed'"
        ),
    )


async def test_migration_306_reuses_every_canonical_124_statement() -> None:
    statements: list[str] = []

    class Recorder:
        async def execute(self, sql: str) -> None:
            statements.append(dedent(sql).strip())

    await apply_lab(Recorder())
    forward, _ = split_migration_sql(
        (MIGRATIONS / "306_autonomous_lab_consul_leases.sql").read_text()
    )
    snapshot = (
        forward.split("-- BEGIN LEGACY 124 APPLY SNAPSHOT\n", 1)[1]
        .split("-- END LEGACY 124 APPLY SNAPSHOT", 1)[0]
        .strip()
    )
    assert statements
    assert snapshot == "\n\n".join(statements)


async def test_migration_306_bootstraps_absent_lab_and_preserves_rows_on_rollback(
    dual_db: asyncpg.Connection,
) -> None:
    await dual_db.execute(
        "DROP TABLE public.autonomous_lab_consul_leases, "
        "public.autonomous_lab_events_outbox, public.autonomous_lab_runs"
    )
    assert await dual_db.fetchval(
        "SELECT to_regclass('public.autonomous_lab_runs') IS NULL "
        "AND to_regclass('public.autonomous_lab_events_outbox') IS NULL"
    )
    forward, rollback = split_migration_sql(
        (MIGRATIONS / "306_autonomous_lab_consul_leases.sql").read_text()
    )
    async with dual_db.transaction():
        await dual_db.execute("CREATE SCHEMA IF NOT EXISTS dual_consul_alternate")
        await dual_db.execute("SET LOCAL search_path = dual_consul_alternate, public")
        await dual_db.execute(forward)
        assert await dual_db.fetchval(
            "SELECT to_regclass('public.autonomous_lab_runs') IS NOT NULL "
            "AND to_regclass('dual_consul_alternate.autonomous_lab_runs') IS NULL"
        )
    run_id = "consul-bootstrap-proof"
    store = await _enqueue(dual_db, run_id)
    request = make_request(await dual_db.fetchval("SELECT clock_timestamp()"), run_id)
    worker = AutonomousLabWorker(
        placement=store.placement,
        state_store=store,
        stage_nodes=(ConsulSyntheticStage(dual_db, request, OWNER),),
    )
    assert (await worker.tick(dual_db, worker_id=OWNER)).status.value == "succeeded"
    assert await _counts(dual_db) == (1, 1, 1)
    assert rollback is not None
    async with dual_db.transaction():
        await dual_db.execute(rollback)
    assert await dual_db.fetchval(
        "SELECT to_regclass('public.autonomous_lab_consul_leases') IS NULL"
    )
    assert (
        await dual_db.fetchval("SELECT status FROM autonomous_lab_runs WHERE run_id=$1", run_id)
        == "succeeded"
    )
    assert await _counts(dual_db) == (1, 1, 1)


async def test_migration_306_rollback_and_reapply_preserve_existing_lifecycle(
    dual_db: asyncpg.Connection,
) -> None:
    forward, rollback = split_migration_sql(
        (MIGRATIONS / "306_autonomous_lab_consul_leases.sql").read_text()
    )
    assert rollback is not None
    async with dual_db.transaction():
        await dual_db.execute(rollback)
    assert await dual_db.fetchval(
        "SELECT to_regclass('public.autonomous_lab_consul_leases') IS NULL"
    )
    assert await dual_db.fetchval(
        "SELECT to_regclass('public.autonomous_lab_runs') IS NOT NULL "
        "AND to_regclass('public.research_os_objects') IS NOT NULL"
    )
    async with dual_db.transaction():
        await dual_db.execute(forward)
    assert await dual_db.fetchval(
        "SELECT to_regclass('public.autonomous_lab_consul_leases') IS NOT NULL"
    )
    request, lease = await _admit(dual_db, "consul-after-reapply")
    await execute_synthetic(dual_db, lease=lease, request=request)
    assert await _counts(dual_db) == (1, 1, 1)


@pytest.mark.parametrize("builder", ["astra", "fable"])
async def test_worker_tick_commits_started_attempt_result_and_one_effect(
    dual_db: asyncpg.Connection, builder: Any
) -> None:
    run_id = f"consul-worker-{builder}"
    store = await _enqueue(dual_db, run_id)
    request = make_request(
        await dual_db.fetchval("SELECT clock_timestamp()"), run_id, builder=builder
    )
    stage = ConsulSyntheticStage(dual_db, request, OWNER)
    worker = AutonomousLabWorker(placement=store.placement, state_store=store, stage_nodes=(stage,))
    result = await worker.tick(dual_db, worker_id=OWNER)
    assert result.status.value == "succeeded"
    assert await _counts(dual_db) == (1, 1, 1)
    assert (
        await dual_db.fetchval("SELECT status FROM autonomous_lab_runs WHERE run_id=$1", run_id)
        == "succeeded"
    )
    assert (
        await dual_db.fetchval(
            "SELECT payload->>'state' FROM research_os_objects WHERE object_kind='execution_attempt'"
        )
        == "started"
    )


async def test_exact_replay_returns_same_receipt_without_duplicate_effect(
    dual_db: asyncpg.Connection,
) -> None:
    request, lease = await _admit(dual_db)
    first = await execute_synthetic(dual_db, lease=lease, request=request)
    second = await execute_synthetic(dual_db, lease=lease, request=request)
    assert first == second
    assert await _counts(dual_db) == (1, 1, 1)


@pytest.mark.parametrize("new_owner", [OWNER, "consul-fable"])
async def test_takeover_fences_old_generation_even_when_owner_name_is_reused(
    dual_db: asyncpg.Connection, new_owner: str
) -> None:
    request, stale = await _admit(dual_db)
    await dual_db.execute(
        "UPDATE autonomous_lab_runs SET worker_id=$1 WHERE run_id=$2", new_owner, stale.run_id
    )
    current = await consul_store.bind(
        dual_db,
        run_id=stale.run_id,
        owner_id=new_owner,
        **request.pins,
        grant_expires_at=request.review.expires_at,
    )
    assert current.generation == stale.generation + 1
    with pytest.raises(PermissionError):
        await execute_synthetic(dual_db, lease=stale, request=request)
    assert await _counts(dual_db) == (0, 0, 0)


@pytest.mark.parametrize("condition", ["lease_expired", "grant_expired", "revoked", "cancelled"])
async def test_lapsed_authority_never_reaches_effect(
    dual_db: asyncpg.Connection, condition: str
) -> None:
    request, lease = await _admit(dual_db)
    if condition == "revoked":
        assert await consul_store.revoke(dual_db, lease)
    elif condition == "cancelled":
        await dual_db.execute(
            "UPDATE autonomous_lab_runs SET status='cancelled' WHERE run_id=$1", lease.run_id
        )
    elif condition == "grant_expired":
        await dual_db.execute(
            "UPDATE autonomous_lab_consul_leases SET lease_expires_at=clock_timestamp()-interval '2 seconds', grant_expires_at=clock_timestamp()-interval '1 second'"
        )
    else:
        await dual_db.execute(
            "UPDATE autonomous_lab_consul_leases SET lease_expires_at=clock_timestamp()-interval '1 second'"
        )
    with pytest.raises(PermissionError):
        await execute_synthetic(dual_db, lease=lease, request=request)
    assert await _counts(dual_db) == (0, 0, 0)


async def test_revoked_approval_cannot_return_after_new_grant(dual_db: asyncpg.Connection) -> None:
    request, lease = await _admit(dual_db)
    assert await consul_store.revoke(dual_db, lease)
    fresh = make_request(
        await dual_db.fetchval("SELECT clock_timestamp()"), lease.run_id, grant_revision=2
    )
    await consul_store.bind(
        dual_db,
        run_id=lease.run_id,
        owner_id=OWNER,
        **fresh.pins,
        grant_expires_at=fresh.review.expires_at,
    )
    with pytest.raises(PermissionError, match="revoked"):
        await consul_store.bind(
            dual_db,
            run_id=lease.run_id,
            owner_id=OWNER,
            **request.pins,
            grant_expires_at=request.review.expires_at,
        )


async def test_broker_revokes_superseded_approval_without_revoking_current_grant(
    dual_db: asyncpg.Connection,
) -> None:
    previous, old_lease = await _admit(dual_db)
    current = make_request(
        await dual_db.fetchval("SELECT clock_timestamp()"), old_lease.run_id, grant_revision=2
    )
    new_lease = await consul_store.bind(
        dual_db,
        run_id=old_lease.run_id,
        owner_id=OWNER,
        **current.pins,
        grant_expires_at=current.review.expires_at,
    )
    assert new_lease.generation == old_lease.generation + 1
    assert not await consul_store.revoke(dual_db, old_lease)
    assert await consul_store.revoke_approval(
        dual_db, run_id=old_lease.run_id, approval_hash=previous.approval.object_hash
    )
    assert not await consul_store.revoke_approval(
        dual_db, run_id=old_lease.run_id, approval_hash=previous.approval.object_hash
    )
    with pytest.raises(PermissionError, match="revoked"):
        await consul_store.bind(
            dual_db,
            run_id=old_lease.run_id,
            owner_id=OWNER,
            **previous.pins,
            grant_expires_at=previous.review.expires_at,
        )
    result = await execute_synthetic(dual_db, lease=new_lease, request=current)
    assert result.terminal_outcome == "succeeded"
    assert await _counts(dual_db) == (1, 1, 1)
    assert await dual_db.fetchval(
        "SELECT revoked_approval_hashes FROM autonomous_lab_consul_leases WHERE run_id=$1",
        old_lease.run_id,
    ) == [previous.approval.object_hash]


async def test_broker_revocation_of_current_approval_refuses_effect(
    dual_db: asyncpg.Connection,
) -> None:
    request, lease = await _admit(dual_db)
    assert await consul_store.revoke_approval(
        dual_db, run_id=lease.run_id, approval_hash=request.approval.object_hash
    )
    assert not await consul_store.revoke(dual_db, lease)
    with pytest.raises(PermissionError):
        await execute_synthetic(dual_db, lease=lease, request=request)
    assert await _counts(dual_db) == (0, 0, 0)


async def test_failure_after_effect_rolls_back_all_ros_objects_and_effect(
    dual_db: asyncpg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, lease = await _admit(dual_db)
    original = consul_executor._persist

    async def fail_result(
        conn: asyncpg.Connection, kind: str, identifier: object, model: Any
    ) -> None:
        if kind == "operational_receipt":
            raise RuntimeError("synthetic injected result-store failure")
        await original(conn, kind, identifier, model)

    monkeypatch.setattr(consul_executor, "_persist", fail_result)
    with pytest.raises(RuntimeError, match="injected"):
        await execute_synthetic(dual_db, lease=lease, request=request)
    assert await _counts(dual_db) == (0, 0, 0)
    assert await dual_db.fetchval("SELECT count(*) FROM research_os_objects") == 0


async def test_expiry_between_guard_and_effect_rolls_back(
    dual_db: asyncpg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, lease = await _admit(dual_db)
    original = consul_executor._persist

    async def expire_after_attempt(
        conn: asyncpg.Connection, kind: str, identifier: object, model: Any
    ) -> None:
        await original(conn, kind, identifier, model)
        if kind == "execution_attempt":
            await conn.execute(
                "UPDATE autonomous_lab_consul_leases SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE run_id=$1",
                lease.run_id,
            )

    monkeypatch.setattr(consul_executor, "_persist", expire_after_attempt)
    with pytest.raises(PermissionError):
        await execute_synthetic(dual_db, lease=lease, request=request)
    assert await _counts(dual_db) == (0, 0, 0)
    assert await dual_db.fetchval("SELECT count(*) FROM research_os_objects") == 0


async def test_concurrent_takeover_waits_for_guard_then_fences_it(
    dual_db: asyncpg.Connection,
) -> None:
    request, lease = await _admit(dual_db)
    other = await asyncpg.connect(_dsn())
    await init_asyncpg_connection(other)
    started = asyncio.Event()
    task: asyncio.Task[Any] | None = None

    async def takeover() -> Any:
        started.set()
        return await consul_store.bind(
            other,
            run_id=lease.run_id,
            owner_id=OWNER,
            **request.pins,
            grant_expires_at=request.review.expires_at,
        )

    try:
        async with consul_store.guard(dual_db, lease=lease, **request.pins):
            task = asyncio.create_task(takeover())
            await started.wait()
            async with asyncio.timeout(5):
                while not await dual_db.fetchval(
                    "SELECT $1::int = ANY(pg_blocking_pids($2::int))",
                    dual_db.get_server_pid(),
                    other.get_server_pid(),
                ):
                    assert not task.done(), "takeover passed a held owner lock"
            assert not task.done()
        newer = await asyncio.wait_for(task, timeout=5)
        assert newer.generation == lease.generation + 1
        with pytest.raises(PermissionError):
            await execute_synthetic(dual_db, lease=lease, request=request)
    finally:
        if task and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        await other.close()
