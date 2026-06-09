from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from backend.services.autonomous_lab.state_store import (
    AutonomousLabStateStore,
    LabEventType,
    LabMachineRole,
    LabOutboxStatus,
    LabRunQueueItem,
    LabRunStatus,
    assert_outbox_consumer_allowed,
    assert_run_worker_allowed,
    resolve_runtime_placement,
)


class FakeAsyncConnection:
    def __init__(
        self,
        *,
        fetchrow_results: list[Any] | None = None,
        fetch_results: list[list[Any]] | None = None,
    ) -> None:
        self.fetchrow_results = fetchrow_results or []
        self.fetch_results = fetch_results or []
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetch_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, query: str, *args: Any) -> Any:
        self.fetchrow_calls.append((query, args))
        if not self.fetchrow_results:
            return None
        return self.fetchrow_results.pop(0)

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        self.fetch_calls.append((query, args))
        if not self.fetch_results:
            return []
        return self.fetch_results.pop(0)

    async def execute(self, query: str, *args: Any) -> str:
        self.execute_calls.append((query, args))
        return "UPDATE 1"


def _row(**overrides: Any) -> dict[str, Any]:
    row = {
        "run_id": "lab-runtime-test",
        "idempotency_key": "lab-runtime-test:v1",
        "status": "pending",
        "objective": "Build receipt-safe Lab runtime",
        "receipt": _receipt(),
        "target_paths": ["apps/backend-rag/backend/services/autonomous_lab/state_store.py"],
        "metadata": {"lane": "ops"},
        "priority": 10,
        "attempts": 0,
        "max_attempts": 3,
        "inserted": True,
    }
    row.update(overrides)
    return row


def _receipt() -> dict[str, Any]:
    return {
        "run_id": "lab-runtime-test",
        "blocked": False,
        "summary": "Derived receipt-safe runtime state only.",
    }


def _queue_item() -> LabRunQueueItem:
    return LabRunQueueItem(
        run_id="lab-runtime-test",
        idempotency_key="lab-runtime-test:v1",
        objective="Build receipt-safe Lab runtime",
        receipt=_receipt(),
        target_paths=("apps/backend-rag/backend/services/autonomous_lab/state_store.py",),
        metadata={"lane": "ops"},
        priority=10,
    )


def _pro_store() -> AutonomousLabStateStore:
    with patch(
        "backend.services.autonomous_lab.state_store.current_runtime_placement",
        return_value=resolve_runtime_placement("Nuzantara", "nuzantara"),
    ):
        return AutonomousLabStateStore()


def _mini_store() -> AutonomousLabStateStore:
    with patch(
        "backend.services.autonomous_lab.state_store.current_runtime_placement",
        return_value=resolve_runtime_placement("Mini-Pro2", "nuzantara"),
    ):
        return AutonomousLabStateStore()


def _air_store() -> AutonomousLabStateStore:
    with patch(
        "backend.services.autonomous_lab.state_store.current_runtime_placement",
        return_value=resolve_runtime_placement("Air-M5", "balizero"),
    ):
        return AutonomousLabStateStore()


@pytest.mark.asyncio
async def test_enqueue_run_is_idempotent_and_appends_creation_event() -> None:
    conn = FakeAsyncConnection(fetchrow_results=[_row(event_id=41)])
    store = AutonomousLabStateStore()

    record = await store.enqueue_run(conn, _queue_item())

    assert record.run_id == "lab-runtime-test"
    assert record.status == LabRunStatus.PENDING
    assert record.inserted is True
    assert len(conn.fetchrow_calls) == 1
    enqueue_sql = conn.fetchrow_calls[0][0]
    assert "ON CONFLICT (idempotency_key) DO NOTHING" in enqueue_sql
    assert "autonomous_lab_events_outbox" in enqueue_sql
    assert "'run_enqueued'" in enqueue_sql


@pytest.mark.asyncio
async def test_enqueue_existing_run_does_not_duplicate_outbox_event() -> None:
    conn = FakeAsyncConnection(fetchrow_results=[_row(inserted=False)])
    store = AutonomousLabStateStore()

    record = await store.enqueue_run(conn, _queue_item())

    assert record.inserted is False
    assert len(conn.fetchrow_calls) == 1


@pytest.mark.asyncio
async def test_claim_next_run_uses_skip_locked_and_pro_runtime_only() -> None:
    conn = FakeAsyncConnection(fetchrow_results=[_row(status="running", attempts=1, event_id=42)])
    store = _pro_store()

    record = await store.claim_next_run(
        conn,
        worker_id="lab-worker-pro-1",
        machine_role=LabMachineRole.PRO_RUNTIME,
    )

    assert record is not None
    assert record.status == LabRunStatus.RUNNING
    claim_sql, claim_args = conn.fetchrow_calls[0]
    assert "FOR UPDATE SKIP LOCKED" in claim_sql
    assert "status = 'running'" in claim_sql
    assert "'run_claimed'" in claim_sql
    assert claim_args == ("lab-worker-pro-1", LabMachineRole.PRO_RUNTIME.value)


@pytest.mark.asyncio
async def test_air_m5_cannot_claim_lab_runs() -> None:
    conn = FakeAsyncConnection(fetchrow_results=[_row(status="running")])
    store = _air_store()

    with pytest.raises(ValueError, match="Pro runtime"):
        await store.claim_next_run(
            conn,
            worker_id="air-worker",
            machine_role=LabMachineRole.PRO_RUNTIME,
        )

    assert conn.fetchrow_calls == []


@pytest.mark.asyncio
async def test_outbox_claim_uses_skip_locked_and_bounds_limit() -> None:
    conn = FakeAsyncConnection(
        fetch_results=[
            [
                {
                    "event_id": 7,
                    "run_id": "lab-runtime-test",
                    "event_type": "candidate_ready",
                    "payload": {"run_id": "lab-runtime-test"},
                    "status": "in_progress",
                    "attempts": 1,
                }
            ]
        ]
    )
    store = _mini_store()

    events = await store.claim_outbox_events(
        conn,
        consumer_id="mini-outbox-1",
        machine_role=LabMachineRole.MINI_SCHEDULER,
        limit=999,
    )

    assert events[0].event_id == 7
    assert events[0].status == LabOutboxStatus.IN_PROGRESS
    claim_sql, claim_args = conn.fetch_calls[0]
    assert "FOR UPDATE SKIP LOCKED" in claim_sql
    assert claim_args == (500, "mini-outbox-1")


@pytest.mark.asyncio
async def test_ack_and_retry_outbox_events_are_owner_scoped() -> None:
    conn = FakeAsyncConnection()
    store = _mini_store()

    acked = await store.ack_outbox_event(conn, event_id=9, consumer_id="consumer-1")
    retried = await store.retry_outbox_event(
        conn,
        event_id=9,
        consumer_id="consumer-1",
        error="handler failed after partial downstream work",
    )

    assert acked is True
    assert retried is True
    ack_sql, ack_args = conn.execute_calls[0]
    retry_sql, retry_args = conn.execute_calls[1]
    assert "claimed_by = $2" in ack_sql
    assert "status = 'in_progress'" in ack_sql
    assert "consumed_at IS NULL" in ack_sql
    assert ack_args == (9, "consumer-1")
    assert "failed_dlq" in retry_sql
    assert "claimed_by = NULL" in retry_sql
    assert retry_args[0:2] == (9, "consumer-1")
    assert str(retry_args[2]).startswith("evidence_fingerprint:sha256:")
    assert "handler failed after partial downstream work" not in str(retry_args)


@pytest.mark.asyncio
async def test_completion_and_failure_append_receipt_safe_events() -> None:
    conn = FakeAsyncConnection(
        fetchrow_results=[
            {"updated_count": 1, "event_id": 51},
            {"updated_count": 1, "event_id": 52},
        ]
    )
    store = _pro_store()

    succeeded = await store.mark_run_succeeded(
        conn,
        run_id="lab-runtime-test",
        worker_id="worker-1",
        summary={"result": "verified"},
    )
    failed = await store.mark_run_failed(
        conn,
        run_id="lab-runtime-test",
        worker_id="worker-1",
        error="downstream verifier returned code 1",
    )

    assert succeeded is True
    assert failed is True
    assert "status = 'succeeded'" in conn.fetchrow_calls[0][0]
    assert "'run_succeeded'" in conn.fetchrow_calls[0][0]
    assert "CASE WHEN attempts >= max_attempts" in conn.fetchrow_calls[1][0]
    assert "'run_failed'" in conn.fetchrow_calls[1][0]
    assert "downstream verifier returned code 1" not in str(conn.fetchrow_calls[1][1])


@pytest.mark.asyncio
async def test_completion_does_not_emit_event_when_owner_update_misses() -> None:
    conn = FakeAsyncConnection(
        fetchrow_results=[
            {"updated_count": 0, "event_id": None},
            {"updated_count": 0, "event_id": None},
        ]
    )
    store = _pro_store()

    succeeded = await store.mark_run_succeeded(
        conn,
        run_id="lab-runtime-test",
        worker_id="wrong-worker",
        summary={"result": "ignored"},
    )
    failed = await store.mark_run_failed(
        conn,
        run_id="lab-runtime-test",
        worker_id="wrong-worker",
        error="ignored error",
    )

    assert succeeded is False
    assert failed is False
    assert len(conn.fetchrow_calls) == 2


@pytest.mark.asyncio
async def test_heartbeat_ack_and_retry_surface_update_zero() -> None:
    conn = FakeAsyncConnection()
    conn.execute = _execute_update_zero(conn)
    run_store = _pro_store()
    outbox_store = _mini_store()

    assert await run_store.heartbeat_run(conn, run_id="lab-runtime-test", worker_id="stale") is False
    assert await outbox_store.ack_outbox_event(conn, event_id=1, consumer_id="stale") is False
    assert (
        await outbox_store.retry_outbox_event(
            conn,
            event_id=1,
            consumer_id="stale",
            error="stale consumer",
        )
        is False
    )


@pytest.mark.asyncio
async def test_air_m5_cannot_mutate_claimed_run_or_outbox_state() -> None:
    conn = FakeAsyncConnection(
        fetchrow_results=[
            {"updated_count": 1, "event_id": 51},
            {"updated_count": 1, "event_id": 52},
        ]
    )
    store = _air_store()

    with pytest.raises(ValueError, match="Pro runtime"):
        await store.heartbeat_run(conn, run_id="lab-runtime-test", worker_id="air-worker")
    with pytest.raises(ValueError, match="Pro runtime"):
        await store.mark_run_succeeded(
            conn,
            run_id="lab-runtime-test",
            worker_id="air-worker",
            summary={"result": "verified"},
        )
    with pytest.raises(ValueError, match="Pro runtime"):
        await store.mark_run_failed(
            conn,
            run_id="lab-runtime-test",
            worker_id="air-worker",
            error="verifier failed",
        )
    with pytest.raises(ValueError, match="Pro/Mini"):
        await store.ack_outbox_event(conn, event_id=1, consumer_id="air-consumer")
    with pytest.raises(ValueError, match="Pro/Mini"):
        await store.retry_outbox_event(
            conn,
            event_id=1,
            consumer_id="air-consumer",
            error="handler failed",
        )

    assert conn.fetchrow_calls == []
    assert conn.execute_calls == []


@pytest.mark.asyncio
async def test_enqueue_rejects_unsafe_metadata_and_objective() -> None:
    store = AutonomousLabStateStore()
    conn = FakeAsyncConnection(fetchrow_results=[_row()])

    with pytest.raises(ValueError, match="unsafe raw or secret-like value"):
        await store.enqueue_run(
            conn,
            LabRunQueueItem(
                run_id="unsafe-metadata",
                idempotency_key="unsafe-metadata:v1",
                objective="Build Lab runtime",
                receipt=_receipt(),
                metadata={"details": "operator phone +62-812-3456-7890"},
            ),
        )

    with pytest.raises(ValueError, match="mutating command-like value"):
        await store.enqueue_run(
            conn,
            LabRunQueueItem(
                run_id="unsafe-objective",
                idempotency_key="unsafe-objective:v1",
                objective="run git -C . push origin main",
                receipt=_receipt(),
            ),
        )

    assert conn.fetchrow_calls == []


@pytest.mark.asyncio
async def test_enqueue_rejects_unsafe_top_level_target_paths() -> None:
    store = AutonomousLabStateStore()
    conn = FakeAsyncConnection(fetchrow_results=[_row()])

    for target_path in ("/etc/passwd", "../outside.py"):
        with pytest.raises(ValueError, match="unsafe_target_path"):
            await store.enqueue_run(
                conn,
                LabRunQueueItem(
                    run_id="unsafe-target",
                    idempotency_key=f"unsafe-target:{target_path}",
                    objective="Build Lab runtime",
                    receipt=_receipt(),
                    target_paths=(target_path,),
                ),
            )

    assert conn.fetchrow_calls == []


@pytest.mark.asyncio
async def test_enqueue_persists_objective_and_metadata_as_safe_references() -> None:
    conn = FakeAsyncConnection(fetchrow_results=[_row(event_id=41)])
    store = AutonomousLabStateStore()

    await store.enqueue_run(
        conn,
        LabRunQueueItem(
            run_id="safe-reference-run",
            idempotency_key="safe-reference-run:v1",
            objective="Queue a generic operator paragraph that should not persist verbatim.",
            receipt=_receipt(),
            target_paths=("apps/backend-rag/backend/services/autonomous_lab/state_store.py",),
            metadata={
                "lane": "ops",
                "details": "This generic note should become only a deterministic reference.",
            },
        ),
    )

    args = conn.fetchrow_calls[0][1]
    assert str(args[2]).startswith("evidence_fingerprint:sha256:")
    assert "generic operator paragraph" not in str(args)
    assert '"lane": "ops"' in str(args[5])
    assert "generic note" not in str(args[5])
    assert "evidence_fingerprint:sha256:" in str(args[5])


@pytest.mark.asyncio
async def test_enqueue_rejects_raw_metadata_keys() -> None:
    store = AutonomousLabStateStore()
    conn = FakeAsyncConnection(fetchrow_results=[_row()])

    with pytest.raises(ValueError, match="raw-content metadata key"):
        await store.enqueue_run(
            conn,
            LabRunQueueItem(
                run_id="unsafe-note-metadata",
                idempotency_key="unsafe-note-metadata:v1",
                objective="Build Lab runtime",
                receipt=_receipt(),
                metadata={"note": "Even harmless prose belongs in a receipt reference, not metadata."},
            ),
        )

    assert conn.fetchrow_calls == []


@pytest.mark.asyncio
async def test_append_event_uses_canonical_run_id_over_payload_run_id() -> None:
    conn = FakeAsyncConnection(fetchrow_results=[{"event_id": 99}])
    store = AutonomousLabStateStore()

    event_id = await store.append_event(
        conn,
        run_id="canonical-run",
        event_type=LabEventType.CANDIDATE_READY,
        payload={"run_id": "spoofed-run", "summary": "safe"},
    )

    assert event_id == 99
    assert '"run_id": "canonical-run"' in conn.fetchrow_calls[0][1][2]
    assert "spoofed-run" not in conn.fetchrow_calls[0][1][2]


def test_machine_placement_policy_matches_air_pro_mini_contract() -> None:
    air = resolve_runtime_placement("Air-M5", "balizero")
    pro = resolve_runtime_placement("Nuzantara", "nuzantara")
    mini = resolve_runtime_placement("Mini-Pro2", "nuzantara")
    unknown = resolve_runtime_placement("other", "someone")

    assert air.can_enqueue is True
    assert air.can_claim_runs is False
    assert air.can_consume_outbox is False
    assert air.heavy_work_destination == "ssh pro"
    assert pro.can_claim_runs is True
    assert pro.can_consume_outbox is True
    assert mini.can_claim_runs is False
    assert mini.can_consume_outbox is True
    assert unknown.can_enqueue is False


def test_role_guards_are_fail_closed() -> None:
    assert assert_run_worker_allowed(LabMachineRole.PRO_RUNTIME) == LabMachineRole.PRO_RUNTIME
    assert (
        assert_outbox_consumer_allowed(LabMachineRole.MINI_SCHEDULER)
        == LabMachineRole.MINI_SCHEDULER
    )
    with pytest.raises(ValueError):
        assert_run_worker_allowed(LabMachineRole.MINI_SCHEDULER)
    with pytest.raises(ValueError):
        assert_outbox_consumer_allowed(LabMachineRole.AIR_COCKPIT)


def _execute_update_zero(conn: FakeAsyncConnection):
    async def execute(query: str, *args: Any) -> str:
        conn.execute_calls.append((query, args))
        return "UPDATE 0"

    return execute
