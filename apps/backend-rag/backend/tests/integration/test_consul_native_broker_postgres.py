"""Native broker behavior on the explicitly disposable PostgreSQL database.

Reuses the foundation's exact-name DSN guard, canonical migrations and JSON
codec. No models run and no operational database is accepted by this fixture.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import asdict, replace
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

import asyncpg
import pytest

from backend.core.pg_json_codec import init_asyncpg_connection
from backend.db.migration_base import split_migration_sql
from backend.services.autonomous_lab import consul_native_broker, consul_store
from backend.services.autonomous_lab.consul_native_broker import NativeBroker, NativeGrant
from backend.services.autonomous_lab.state_store import LabRunQueueItem
from backend.tests.integration.test_dual_consul_postgres import (
    MIGRATIONS,
    _dsn,
    _store,
)
from backend.tests.integration.test_dual_consul_postgres import (
    dual_db as dual_db,
)
from backend.tests.unit.services.autonomous_lab.consul_fixtures import reseal
from backend.tests.unit.services.autonomous_lab.native_consul_fixtures import (
    CANARY_MODEL,
    NativeCanaryRPC,
    active_binding,
    make_native_grant,
    selected_result,
)

pytestmark = pytest.mark.integration
OWNER = "consul:nuzantara:uid:550"


@pytest.fixture
async def native_db(dual_db: asyncpg.Connection) -> AsyncIterator[asyncpg.Connection]:
    forward, _ = split_migration_sql((MIGRATIONS / "307_consul_native_broker.sql").read_text())
    async with dual_db.transaction():
        await dual_db.execute(forward)
    yield dual_db


async def _admit(
    conn: asyncpg.Connection, *, builder: str = "astra"
) -> tuple[NativeBroker, NativeGrant, consul_store.Lease]:
    broker = _broker(conn)
    grant = make_native_grant(await conn.fetchval("SELECT clock_timestamp()"), builder=builder)
    reply = await broker.admit(grant, grant.binding)
    return broker, grant, consul_store.Lease(**reply["lease"])


def _broker(conn: asyncpg.Connection) -> NativeBroker:
    from scripts.conductor.native_canary_contract import CANARY_LEASE_SECONDS

    return NativeBroker(
        conn, owner_id=OWNER, state_store=_store(), lease_seconds=CANARY_LEASE_SECONDS
    )


async def _count(conn: asyncpg.Connection, kind: str) -> int:
    return await conn.fetchval(
        "SELECT count(*) FROM research_os_objects WHERE object_kind=$1", kind
    )


async def _status(conn: asyncpg.Connection, grant: NativeGrant) -> str:
    return await conn.fetchval(
        "SELECT status FROM autonomous_lab_runs WHERE run_id=$1", grant.run_id
    )


async def _turn(broker: NativeBroker, grant: NativeGrant, lease: consul_store.Lease) -> None:
    await broker.check(grant, lease, active_binding(grant), "turn")


async def test_native_lease_covers_the_shared_qualified_consumer_budget(
    native_db: asyncpg.Connection,
) -> None:
    from scripts.conductor.native_canary_contract import CANARY_LEASE_SECONDS

    before = await native_db.fetchval("SELECT clock_timestamp()")
    _, grant, _ = await _admit(native_db)
    after = await native_db.fetchval("SELECT clock_timestamp()")
    expires = await native_db.fetchval("SELECT lease_expires_at FROM autonomous_lab_consul_leases")
    assert (
        before + timedelta(seconds=CANARY_LEASE_SECONDS)
        <= expires
        <= after + timedelta(seconds=CANARY_LEASE_SECONDS)
    )
    assert expires <= min(grant.review.expires_at, grant.approval.expires_at)


@pytest.mark.parametrize("short_window", ["approval", "review"])
async def test_short_authority_window_refuses_before_creating_a_run(
    native_db: asyncpg.Connection, short_window: str
) -> None:
    from scripts.conductor.native_canary_contract import CANARY_LEASE_SECONDS

    now = await native_db.fetchval("SELECT clock_timestamp()")
    grant = make_native_grant(now)
    grant = replace(
        grant,
        **{
            short_window: reseal(
                getattr(grant, short_window),
                expires_at=(now + timedelta(seconds=CANARY_LEASE_SECONDS - 1))
                .isoformat()
                .replace("+00:00", "Z"),
            )
        },
    )
    broker = _broker(native_db)
    with pytest.raises(PermissionError, match="native_grant_window_too_short"):
        await broker.admit(grant, grant.binding)
    assert await native_db.fetchval("SELECT count(*) FROM autonomous_lab_runs") == 0
    assert await native_db.fetchval("SELECT count(*) FROM research_os_objects") == 0


@pytest.mark.parametrize("status", ["failed", "interrupted"])
async def test_result_found_after_replay_miss_keeps_original_outcome(
    native_db: asyncpg.Connection, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    broker, grant, lease = await _admit(native_db)
    await _turn(broker, grant, lease)
    await broker.check(grant, lease, active_binding(grant), "complete")
    selected = selected_result(grant, status=status)
    original = await broker.checkpoint(grant, lease, active_binding(grant), selected)
    # Model a reconciler exposing a current result while the Lab run is running.
    # Force the second lookup path after an optimistic replay miss.
    await native_db.execute(
        "UPDATE autonomous_lab_runs SET status='running' WHERE run_id=$1", grant.run_id
    )

    async def miss(*args: Any) -> None:
        return None

    monkeypatch.setattr(broker, "_replay", miss)
    assert await broker.checkpoint(grant, lease, active_binding(grant), selected) == original
    assert original["status"] == ("failed" if status == "failed" else "needs_reconcile")
    assert await _count(native_db, "operational_receipt") == 1


async def test_unknown_counter_names_are_preserved_without_values_in_canonical_receipt(
    native_db: asyncpg.Connection,
) -> None:
    from scripts.conductor.app_server_rpc import _usage

    broker, grant, lease = await _admit(native_db)
    await _turn(broker, grant, lease)
    await broker.check(grant, lease, active_binding(grant), "complete")
    selected = selected_result(grant)
    selected["native_usage"] = _usage(
        {"last": {}, "total": {"inputTokens": 10, "futureTokens": "untrusted future value"}}
    )
    await broker.checkpoint(grant, lease, active_binding(grant), selected)
    receipt = await native_db.fetchval(
        "SELECT payload FROM research_os_objects WHERE object_kind='operational_receipt'"
    )
    stored = receipt["extensions"][consul_native_broker.EXTENSION]["payload"]["result"][
        "native_usage"
    ]
    assert stored == {
        "last": {},
        "total": {"inputTokens": 10},
        "unknownCounters": {"names": ["total.futureTokens"], "omitted": False},
    }


@pytest.mark.parametrize("builder", ["astra", "fable"])
async def test_one_started_attempt_and_confirmed_result_follow_lab_lifecycle(
    native_db: asyncpg.Connection, builder: str
) -> None:
    broker, grant, lease = await _admit(native_db, builder=builder)
    assert await _status(native_db, grant) == "running"
    assert await _count(native_db, "execution_attempt") == 0
    assert (await broker.admit(grant, grant.binding))["lease"] == {
        "run_id": lease.run_id,
        "owner_id": lease.owner_id,
        "generation": lease.generation,
    }
    await broker.check(grant, lease, grant.binding, "start")
    await _turn(broker, grant, lease)
    attempt = await native_db.fetchval(
        "SELECT payload FROM research_os_objects WHERE object_kind='execution_attempt'"
    )
    assert attempt["state"] == "started"
    assert await _count(native_db, "operational_receipt") == 0
    await broker.check(grant, lease, active_binding(grant), "complete")
    result = await broker.checkpoint(grant, lease, active_binding(grant), selected_result(grant))
    assert result["status"] == "recorded"
    assert await _status(native_db, grant) == "succeeded"
    receipt = await native_db.fetchval(
        "SELECT payload FROM research_os_objects WHERE object_kind='operational_receipt'"
    )
    assert receipt["terminal_outcome"] == "succeeded"
    assert receipt["effects"][0]["status"] == "confirmed"
    assert (
        await broker.checkpoint(grant, lease, active_binding(grant), selected_result(grant))
        == result
    )
    assert (
        await _count(native_db, "execution_attempt")
        == await _count(native_db, "operational_receipt")
        == 1
    )
    assert (
        await native_db.fetchval(
            "SELECT count(*) FROM autonomous_lab_events_outbox WHERE event_type='run_succeeded'"
        )
        == 1
    )
    with pytest.raises(PermissionError, match="result_conflict"):
        await broker.checkpoint(
            grant, lease, active_binding(grant), {**selected_result(grant), "output_hash": "f" * 64}
        )


async def test_targeted_admission_leaves_older_queue_work_pending(
    native_db: asyncpg.Connection,
) -> None:
    await _store().enqueue_run(
        native_db,
        LabRunQueueItem(
            run_id="unrelated-older",
            idempotency_key="unrelated-older",
            objective="Synthetic older work",
            receipt={"run_id": "unrelated-older", "blocked": False},
        ),
    )
    _, grant, _ = await _admit(native_db)
    assert await _status(native_db, grant) == "running"
    assert (
        await native_db.fetchval(
            "SELECT status FROM autonomous_lab_runs WHERE run_id='unrelated-older'"
        )
        == "pending"
    )


async def test_started_attempt_survives_process_loss_and_forbids_spend_replay(
    native_db: asyncpg.Connection,
) -> None:
    broker, grant, lease = await _admit(native_db)
    await _turn(broker, grant, lease)
    restarted = _broker(native_db)
    for phase in ("turn", "resume"):
        with pytest.raises(PermissionError, match="needs_reconcile"):
            await restarted.check(grant, lease, active_binding(grant), phase)
    with pytest.raises(PermissionError, match="needs_reconcile"):
        await restarted.admit(grant, grant.binding)
    assert await _count(native_db, "execution_attempt") == 1
    assert await _count(native_db, "operational_receipt") == 0


async def test_unverified_continuation_thread_cannot_resume(native_db: asyncpg.Connection) -> None:
    broker, grant, lease = await _admit(native_db)
    with pytest.raises(PermissionError, match="resume_not_checkpointed"):
        await broker.check(grant, lease, active_binding(grant), "resume")
    assert await _count(native_db, "execution_attempt") == 0


async def test_checkpoint_requires_completion_check_for_exact_current_binding(
    native_db: asyncpg.Connection,
) -> None:
    broker, grant, lease = await _admit(native_db)
    await _turn(broker, grant, lease)
    with pytest.raises(PermissionError, match="completion_not_checked"):
        await broker.checkpoint(grant, lease, active_binding(grant), selected_result(grant))
    with pytest.raises(PermissionError, match="attempt_binding_changed"):
        await broker.check(
            grant, lease, {**active_binding(grant), "thread_id": "another-thread"}, "complete"
        )
    assert await _count(native_db, "operational_receipt") == 0
    assert await _status(native_db, grant) == "running"


@pytest.mark.parametrize("status", ["incomplete", "failed", "interrupted"])
async def test_observed_terminal_failure_is_distinct_from_uncertain_invocation(
    native_db: asyncpg.Connection,
    status: str,
) -> None:
    broker, grant, lease = await _admit(native_db)
    await _turn(broker, grant, lease)
    await broker.check(grant, lease, active_binding(grant), "complete")
    result = selected_result(grant, status=status)
    reply = await broker.checkpoint(grant, lease, active_binding(grant), result)
    observed = status in {"incomplete", "failed"}
    assert reply["status"] == (status if observed else "needs_reconcile")
    assert await _status(native_db, grant) == "paused"
    receipt = await native_db.fetchval(
        "SELECT payload FROM research_os_objects WHERE object_kind='operational_receipt'"
    )
    assert receipt["terminal_outcome"] == ("failed" if observed else "unknown")
    assert receipt["effects"][0]["status"] == ("confirmed" if observed else "unknown")
    assert receipt["reconciliation"]["state"] == ("confirmed" if observed else "pending")
    assert await broker.checkpoint(grant, lease, active_binding(grant), result) == reply
    with pytest.raises(PermissionError):
        await _turn(broker, grant, lease)


async def test_pre_admit_revocation_is_durable_idempotent_and_never_enqueues(
    native_db: asyncpg.Connection,
) -> None:
    broker = _broker(native_db)
    grant = make_native_grant(await native_db.fetchval("SELECT clock_timestamp()"))
    first = await broker.cancel(grant)
    assert first == await broker.cancel(grant)
    assert first["run_cancelled"] is False
    assert first["remote_cancelled"] is None
    assert await _count(native_db, "revocation_receipt") == 1
    assert await native_db.fetchval("SELECT count(*) FROM autonomous_lab_runs") == 0
    with pytest.raises(PermissionError, match="native_grant_revoked"):
        await broker.admit(grant, grant.binding)
    assert await _count(native_db, "execution_attempt") == 0


@pytest.mark.parametrize("send_lease", [False, True])
async def test_running_cancel_revokes_and_rejects_late_completion(
    native_db: asyncpg.Connection, send_lease: bool
) -> None:
    broker, grant, lease = await _admit(native_db)
    await _turn(broker, grant, lease)
    result = await broker.cancel(grant, lease if send_lease else None)
    assert result["run_cancelled"] is True
    assert await _status(native_db, grant) == "cancelled"
    with pytest.raises(PermissionError):
        await broker.check(grant, lease, active_binding(grant), "complete")
    assert (await broker.cancel(grant, lease))["run_cancelled"] is False
    assert await _count(native_db, "revocation_receipt") == 1
    assert await _count(native_db, "operational_receipt") == 0
    assert (
        await native_db.fetchval(
            "SELECT count(*) FROM autonomous_lab_events_outbox WHERE event_type='run_cancelled'"
        )
        == 1
    )


async def test_generation_change_fences_old_attempt_even_when_owner_is_reused(
    native_db: asyncpg.Connection,
) -> None:
    broker, grant, lease = await _admit(native_db)
    await _turn(broker, grant, lease)
    replacement = await consul_store.bind(
        native_db,
        run_id=grant.run_id,
        owner_id=OWNER,
        **grant.pins,
        grant_expires_at=grant.approval.expires_at,
    )
    assert replacement.generation == lease.generation + 1
    with pytest.raises(PermissionError):
        await broker.check(grant, lease, active_binding(grant), "complete")
    with pytest.raises(PermissionError, match="needs_reconcile"):
        await _turn(broker, grant, replacement)
    with pytest.raises(PermissionError, match="attempt_binding_changed"):
        await broker.check(grant, replacement, active_binding(grant), "complete")
    assert await _count(native_db, "operational_receipt") == 0


async def test_cancelling_superseded_grant_does_not_cancel_new_binding(
    native_db: asyncpg.Connection,
) -> None:
    broker, grant_a, lease_a = await _admit(native_db)
    grant_b = make_native_grant(await native_db.fetchval("SELECT clock_timestamp()"), revision=2)
    await broker._persist_grant(grant_b)
    lease_b = await consul_store.bind(
        native_db,
        run_id=grant_b.run_id,
        owner_id=OWNER,
        **grant_b.pins,
        grant_expires_at=grant_b.approval.expires_at,
    )
    assert (await broker.cancel(grant_a, lease_a))["run_cancelled"] is False
    await broker.check(grant_b, lease_b, grant_b.binding, "start")
    assert await _status(native_db, grant_b) == "running"
    with pytest.raises(PermissionError, match="approval was revoked"):
        await consul_store.bind(
            native_db,
            run_id=grant_a.run_id,
            owner_id=OWNER,
            **grant_a.pins,
            grant_expires_at=grant_a.approval.expires_at,
        )


@pytest.mark.parametrize("column", ["lease_expires_at", "grant_expires_at"])
async def test_expired_lease_or_grant_never_starts_invocation(
    native_db: asyncpg.Connection, column: str
) -> None:
    broker, grant, lease = await _admit(native_db)
    await native_db.execute(
        "UPDATE autonomous_lab_consul_leases SET lease_expires_at=clock_timestamp()-interval '2 seconds'"
    )
    if column == "grant_expires_at":
        await native_db.execute(
            "UPDATE autonomous_lab_consul_leases SET grant_expires_at=clock_timestamp()-interval '1 second'"
        )
    with pytest.raises(PermissionError):
        await _turn(broker, grant, lease)
    assert await _count(native_db, "execution_attempt") == 0


@pytest.mark.parametrize("fault", ["expiry", "failure"])
async def test_checkpoint_transaction_rolls_back_receipt_and_lifecycle(
    native_db: asyncpg.Connection, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    broker, grant, lease = await _admit(native_db)
    await _turn(broker, grant, lease)
    await broker.check(grant, lease, active_binding(grant), "complete")
    persist = consul_native_broker._persist

    async def inject(conn: asyncpg.Connection, kind: str, identifier: Any, model: Any) -> None:
        await persist(conn, kind, identifier, model)
        if kind == "operational_receipt":
            if fault == "failure":
                raise RuntimeError("injected checkpoint failure")
            await conn.execute(
                "UPDATE autonomous_lab_consul_leases SET lease_expires_at=clock_timestamp()-interval '1 second'"
            )

    monkeypatch.setattr(consul_native_broker, "_persist", inject)
    with pytest.raises((PermissionError, RuntimeError)):
        await broker.checkpoint(grant, lease, active_binding(grant), selected_result(grant))
    assert await _count(native_db, "execution_attempt") == 1
    assert await _count(native_db, "operational_receipt") == 0
    assert await _status(native_db, grant) == "running"
    assert (
        await native_db.fetchval(
            "SELECT count(*) FROM autonomous_lab_events_outbox WHERE event_type='run_succeeded'"
        )
        == 0
    )


async def test_expiry_during_attempt_persistence_rolls_back_spend_permission(
    native_db: asyncpg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker, grant, lease = await _admit(native_db)
    persist = consul_native_broker._persist

    async def expire(conn: asyncpg.Connection, kind: str, identifier: Any, model: Any) -> None:
        await persist(conn, kind, identifier, model)
        if kind == "execution_attempt":
            await conn.execute(
                "UPDATE autonomous_lab_consul_leases SET lease_expires_at=clock_timestamp()-interval '1 second'"
            )

    monkeypatch.setattr(consul_native_broker, "_persist", expire)
    with pytest.raises(PermissionError):
        await _turn(broker, grant, lease)
    assert await _count(native_db, "execution_attempt") == 0


async def test_two_connections_cannot_admit_two_spend_attempts(
    native_db: asyncpg.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    broker, grant, lease = await _admit(native_db)
    conn2 = await asyncpg.connect(_dsn())
    await init_asyncpg_connection(conn2)
    persisted, release, competing = asyncio.Event(), asyncio.Event(), asyncio.Event()
    persist = consul_native_broker._persist

    async def hold(conn: asyncpg.Connection, kind: str, identifier: Any, model: Any) -> None:
        await persist(conn, kind, identifier, model)
        if kind == "execution_attempt":
            persisted.set()
            await release.wait()

    async def compete() -> None:
        competing.set()
        await _turn(_broker(conn2), grant, lease)

    monkeypatch.setattr(consul_native_broker, "_persist", hold)
    first = asyncio.create_task(_turn(broker, grant, lease))
    second = None
    try:
        await asyncio.wait_for(persisted.wait(), 5)
        second = asyncio.create_task(compete())
        await asyncio.wait_for(competing.wait(), 5)
        release.set()
        await asyncio.wait_for(first, 5)
        with pytest.raises(PermissionError, match="needs_reconcile"):
            await asyncio.wait_for(second, 5)
        assert await _count(native_db, "execution_attempt") == 1
    finally:
        release.set()
        for task in (first, second):
            if task is not None and not task.done():
                task.cancel()
        await asyncio.gather(
            *(task for task in (first, second) if task is not None), return_exceptions=True
        )
        await conn2.close()


async def test_migration_307_safe_rollback_and_reapply(native_db: asyncpg.Connection) -> None:
    _, grant, _ = await _admit(native_db)
    forward, rollback = split_migration_sql(
        (MIGRATIONS / "307_consul_native_broker.sql").read_text()
    )
    assert rollback is not None
    with pytest.raises(asyncpg.CheckViolationError):
        async with native_db.transaction():
            await native_db.execute(rollback)
    assert (
        await native_db.fetchval("SELECT resource FROM autonomous_lab_consul_leases")
        == f"native:{grant.run_id}"
    )
    # Explicitly delete the synthetic fixture lease only, then prove reversible DDL.
    await native_db.execute("DELETE FROM autonomous_lab_consul_leases")
    async with native_db.transaction():
        await native_db.execute(rollback)
    assert not await native_db.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='autonomous_lab_consul_leases' AND column_name='native_completion_generation')"
    )
    async with native_db.transaction():
        await native_db.execute(forward)
    assert await native_db.fetchval(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='autonomous_lab_consul_leases' AND column_name='native_completion_generation')"
    )


async def _canary_chain(
    conn: asyncpg.Connection,
    *,
    reply_text: str = "DUAL_CONSUL_NATIVE_OK",
) -> tuple[Any, Any, Any, NativeBroker, NativeGrant]:
    """Same-process protocol proof; deliberately makes no installed-UID claim."""
    from scripts.conductor.codex_shadow import CodexShadow, NativeBinding
    from scripts.conductor.consul_broker_client import ConsulBrokerClient
    from scripts.conductor.consul_native import CANARY_TEXT
    from scripts.conductor.protected_grants import parse_request
    from scripts.consul_broker import dispatch

    async def refuse(binding: Any, phase: str) -> None:
        raise PermissionError("discovery_only")

    rpc = NativeCanaryRPC(reply_text)
    adapter = CodexShadow(
        rpc,
        cwd=Path("/tmp"),
        runtime_version="0.147.0",
        host="synthetic-host",
        authorize=refuse,
        auth_fingerprint=lambda: rpc.credential_fingerprint,
    )
    observation, _ = await adapter.discover(CANARY_MODEL)
    binding = NativeBinding(
        "native-canary-chain",
        sha256(CANARY_TEXT.encode()).hexdigest(),
        observation.key,
        CANARY_MODEL,
        "medium",
    )
    grant = make_native_grant(
        await conn.fetchval("SELECT clock_timestamp()"), binding.mission_id, binding=asdict(binding)
    )
    broker = _broker(conn)

    async def exchange(request: dict[str, Any]) -> dict[str, Any]:
        parsed = parse_request(json.dumps(request, allow_nan=False).encode())
        assert parsed["grant_id"] == grant.grant_id
        return await dispatch(broker, grant, parsed)

    client = ConsulBrokerClient(grant.grant_id, exchange=exchange)
    adapter.authorize = client.authorize
    return rpc, adapter, client, broker, grant


async def test_consumer_client_dispatch_commits_once_and_refuses_second_invocation(
    native_db: asyncpg.Connection,
) -> None:
    from scripts.conductor.consul_native import invoke_canary

    rpc, adapter, client, _, grant = await _canary_chain(native_db)
    result = await invoke_canary(adapter, client, grant.run_id, model=CANARY_MODEL, effort="medium")
    assert result["broker"]["status"] == "recorded"
    assert result["canary_passed"] is True
    assert "DUAL_CONSUL_NATIVE_OK" not in json.dumps(result)
    assert await _status(native_db, grant) == "succeeded"
    assert (
        await _count(native_db, "execution_attempt")
        == await _count(native_db, "operational_receipt")
        == 1
    )
    with pytest.raises(PermissionError):
        await invoke_canary(adapter, client, grant.run_id, model=CANARY_MODEL, effort="medium")
    assert sum(method == "turn/start" for method, _ in rpc.calls) == 1
    assert rpc.local_stopped
    assert await _count(native_db, "execution_attempt") == 1


async def test_helper_handle_opens_real_connections_and_injects_shared_budget(
    native_db: asyncpg.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only protected-file and UID validation are stubs, not a deployment proof."""
    from scripts.conductor.consul_native import invoke_canary
    from scripts.conductor.native_canary_contract import CANARY_LEASE_SECONDS

    from backend.tests.unit.services.autonomous_lab.native_consul_fixtures import grant_payload
    from scripts import consul_broker as helper

    _, adapter, client, _, grant = await _canary_chain(native_db)
    monkeypatch.setattr(consul_native_broker, "service_state_store", lambda **kwargs: _store())
    monkeypatch.setattr(helper, "load_config", lambda uid: {"database_dsn": _dsn()})
    monkeypatch.setattr(helper, "load_grant", lambda identifier: grant_payload(grant))

    async def exchange(request: dict[str, Any]) -> dict[str, Any]:
        return await helper.handle(json.dumps(request, allow_nan=False).encode())

    client.exchange = exchange
    before = await native_db.fetchval("SELECT clock_timestamp()")
    result = await invoke_canary(adapter, client, grant.run_id, model=CANARY_MODEL, effort="medium")
    assert result["broker"]["status"] == "recorded"
    expires = await native_db.fetchval("SELECT lease_expires_at FROM autonomous_lab_consul_leases")
    assert expires >= before + timedelta(seconds=CANARY_LEASE_SECONDS)
    assert (
        await _count(native_db, "execution_attempt")
        == await _count(native_db, "operational_receipt")
        == 1
    )


async def test_canary_wrong_marker_records_known_failure_without_reconciliation(
    native_db: asyncpg.Connection,
) -> None:
    from scripts.conductor.consul_native import invoke_canary

    _, adapter, client, _, grant = await _canary_chain(native_db, reply_text="WRONG_MARKER")
    result = await invoke_canary(adapter, client, grant.run_id, model=CANARY_MODEL, effort="medium")
    assert result["canary_passed"] is False
    assert result["broker"]["status"] == "failed"
    assert await _status(native_db, grant) == "paused"
    receipt = await native_db.fetchval(
        "SELECT payload FROM research_os_objects WHERE object_kind='operational_receipt'"
    )
    assert receipt["terminal_outcome"] == "failed"
    assert receipt["effects"][0]["status"] == "confirmed"
    assert receipt["reconciliation"]["state"] == "confirmed"
    assert await _count(native_db, "revocation_receipt") == 0


async def test_consumer_discards_late_completion_after_real_pg_revocation(
    native_db: asyncpg.Connection,
) -> None:
    from scripts.conductor.consul_native import invoke_canary

    rpc, adapter, client, broker, grant = await _canary_chain(native_db)
    call = rpc.call

    async def revoke_before_reply(
        method: str, params: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        if method == "turn/start":
            assert await _count(native_db, "execution_attempt") == 1
            await broker.cancel(grant, consul_store.Lease(**client.lease))
        return await call(method, params, **kwargs)

    rpc.call = revoke_before_reply
    with pytest.raises(PermissionError):
        await invoke_canary(adapter, client, grant.run_id, model=CANARY_MODEL, effort="medium")
    assert await _status(native_db, grant) == "cancelled"
    assert await _count(native_db, "operational_receipt") == 0
    assert await _count(native_db, "revocation_receipt") == 1
    assert rpc.local_stopped
