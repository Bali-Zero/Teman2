from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from backend.services.autonomous_lab.runtime_contracts import (
    LabArtifactKind,
    LabStageName,
    LabStageStatus,
)
from backend.services.autonomous_lab.stages import LabStageRiskClass, NoopLabStageNode
from backend.services.autonomous_lab.state_store import (
    AutonomousLabStateStore,
    LabMachineRole,
    LabRunRecord,
    resolve_runtime_placement,
)
from backend.services.autonomous_lab.worker import AutonomousLabWorker


class FakeAsyncConnection:
    def __init__(self, *, fetchrow_results: list[Any] | None = None) -> None:
        self.fetchrow_results = fetchrow_results or []
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, query: str, *args: Any) -> Any:
        self.fetchrow_calls.append((query, args))
        if not self.fetchrow_results:
            return None
        return self.fetchrow_results.pop(0)

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        raise AssertionError(f"worker tick should not fetch outbox rows: {query}")

    async def execute(self, query: str, *args: Any) -> str:
        self.execute_calls.append((query, args))
        return "UPDATE 1"


class FailingStageNode:
    name = LabStageName.WATCH
    input_data_class = "LabRunRecord"
    output_data_class = "FrontierSignal"
    risk_class = LabStageRiskClass.LOW
    artifact_kind = LabArtifactKind.FRONTIER_SIGNAL

    async def run(self, _run: LabRunRecord, _context: dict[str, Any]) -> Any:
        raise RuntimeError("token=abcdef1234567890 RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR")


def _row(**overrides: Any) -> dict[str, Any]:
    row = {
        "run_id": "worker-runtime-test",
        "idempotency_key": "worker-runtime-test:v1",
        "status": "running",
        "objective": "objective_fingerprint:sha256:1234-5678",
        "receipt": {"run_id": "worker-runtime-test", "blocked": False},
        "target_paths": ["apps/backend-rag/backend/services/autonomous_lab/worker.py"],
        "metadata": {},
        "priority": 10,
        "attempts": 1,
        "max_attempts": 3,
        "inserted": True,
    }
    row.update(overrides)
    return row


def _event_rows(count: int, *, start: int = 10) -> list[dict[str, int]]:
    return [{"event_id": start + index} for index in range(count)]


def _pro_store() -> AutonomousLabStateStore:
    with patch(
        "backend.services.autonomous_lab.state_store.current_runtime_placement",
        return_value=resolve_runtime_placement("Nuzantara", "nuzantara"),
    ):
        return AutonomousLabStateStore()


def _air_store() -> AutonomousLabStateStore:
    with patch(
        "backend.services.autonomous_lab.state_store.current_runtime_placement",
        return_value=resolve_runtime_placement("Air-M5", "balizero"),
    ):
        return AutonomousLabStateStore()


@pytest.mark.asyncio
async def test_worker_tick_claims_run_checkpoints_and_pauses_at_curate() -> None:
    conn = FakeAsyncConnection(
        fetchrow_results=[
            _row(),
            *_event_rows(8),
            {"updated_count": 1, "event_id": 99},
        ]
    )
    worker = AutonomousLabWorker(state_store=_pro_store())

    result = await worker.tick(conn, worker_id="lab-worker-pro-1")

    assert result.status is LabStageStatus.PAUSED
    assert result.run_id == "worker-runtime-test"
    assert result.paused_at_stage is LabStageName.CURATE
    assert [checkpoint.stage for checkpoint in result.checkpoints] == [
        LabStageName.WATCH,
        LabStageName.INTAKE,
        LabStageName.NORMALIZE,
        LabStageName.COMPOSE,
        LabStageName.RECONSTRUCT,
        LabStageName.EXPERIMENT,
        LabStageName.VERIFY,
        LabStageName.CURATE,
    ]
    assert "FOR UPDATE SKIP LOCKED" in conn.fetchrow_calls[0][0]
    assert conn.fetchrow_calls[0][1] == (
        "lab-worker-pro-1",
        LabMachineRole.PRO_RUNTIME.value,
    )
    assert len(conn.execute_calls) == 1
    assert "heartbeat_at = NOW()" in conn.execute_calls[0][0]

    checkpoint_events = [
        args
        for _sql, args in conn.fetchrow_calls
        if len(args) >= 2 and args[1] == "run_checkpointed"
    ]
    assert len(checkpoint_events) == 8
    assert "'run_paused'" in conn.fetchrow_calls[-1][0]


@pytest.mark.asyncio
async def test_air_m5_worker_tick_cannot_claim_runs() -> None:
    conn = FakeAsyncConnection(fetchrow_results=[_row()])
    worker = AutonomousLabWorker(
        placement=resolve_runtime_placement("Air-M5", "balizero"),
        state_store=_air_store(),
    )

    with pytest.raises(ValueError, match="Pro runtime"):
        await worker.tick(conn, worker_id="air-worker")

    assert conn.fetchrow_calls == []
    assert conn.execute_calls == []


@pytest.mark.asyncio
async def test_worker_tick_failure_persists_only_error_reference() -> None:
    conn = FakeAsyncConnection(
        fetchrow_results=[
            _row(),
            {"updated_count": 1, "event_id": 44},
        ]
    )
    worker = AutonomousLabWorker(
        state_store=_pro_store(),
        stage_nodes=(FailingStageNode(),),
    )

    result = await worker.tick(conn, worker_id="lab-worker-pro-1")

    assert result.status is LabStageStatus.FAILED
    assert result.error_reference is not None
    assert result.error_reference.startswith("evidence_fingerprint:sha256:")
    persisted_args = str(conn.fetchrow_calls[-1][1])
    assert "abcdef1234567890" not in persisted_args
    assert "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR" not in persisted_args
    assert "'run_failed'" in conn.fetchrow_calls[-1][0]


@pytest.mark.asyncio
async def test_worker_tick_resumes_after_last_checkpoint_stage() -> None:
    conn = FakeAsyncConnection(
        fetchrow_results=[
            _row(metadata={"last_checkpoint_stage": "normalize"}),
            *_event_rows(5),
            {"updated_count": 1, "event_id": 100},
        ]
    )
    worker = AutonomousLabWorker(state_store=_pro_store())

    result = await worker.tick(conn, worker_id="lab-worker-pro-1")

    assert result.status is LabStageStatus.PAUSED
    assert [checkpoint.stage for checkpoint in result.checkpoints] == [
        LabStageName.COMPOSE,
        LabStageName.RECONSTRUCT,
        LabStageName.EXPERIMENT,
        LabStageName.VERIFY,
        LabStageName.CURATE,
    ]


@pytest.mark.asyncio
async def test_worker_tick_fails_closed_on_unknown_resume_stage() -> None:
    conn = FakeAsyncConnection(
        fetchrow_results=[
            _row(metadata={"last_checkpoint_stage": "unknown-stage"}),
            {"updated_count": 1, "event_id": 101},
        ]
    )
    worker = AutonomousLabWorker(state_store=_pro_store())

    result = await worker.tick(conn, worker_id="lab-worker-pro-1")

    assert result.status is LabStageStatus.FAILED
    assert result.checkpoints == ()
    assert result.error_reference is not None
    assert result.error_reference.startswith("evidence_fingerprint:sha256:")
    assert "'run_failed'" in conn.fetchrow_calls[-1][0]
    assert "unknown-stage" not in str(conn.fetchrow_calls[-1][1])


@pytest.mark.asyncio
async def test_worker_tick_succeeds_when_no_stage_pauses() -> None:
    conn = FakeAsyncConnection(
        fetchrow_results=[
            _row(),
            {"event_id": 101},
            {"updated_count": 1, "event_id": 102},
        ]
    )
    stage_node = NoopLabStageNode(
        LabStageName.WATCH,
        "LabRunRecord",
        "FrontierSignal",
        LabStageRiskClass.LOW,
        LabArtifactKind.FRONTIER_SIGNAL,
        "single no-op stage succeeds without side effects",
    )
    worker = AutonomousLabWorker(
        state_store=_pro_store(),
        stage_nodes=(stage_node,),
    )

    result = await worker.tick(conn, worker_id="lab-worker-pro-1")

    assert result.status is LabStageStatus.SUCCEEDED
    assert result.run_id == "worker-runtime-test"
    assert [checkpoint.stage for checkpoint in result.checkpoints] == [LabStageName.WATCH]
    assert "'run_succeeded'" in conn.fetchrow_calls[-1][0]
