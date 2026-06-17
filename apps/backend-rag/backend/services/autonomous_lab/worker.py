"""Worker lifecycle for the Autonomous Lab runtime."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from backend.services.autonomous_lab.receipt_safety import receipt_safe_evidence
from backend.services.autonomous_lab.runtime_contracts import (
    LabArtifactKind,
    LabCheckpoint,
    LabGateState,
    LabStageName,
    LabStageStatus,
    build_lab_checkpoint,
)
from backend.services.autonomous_lab.sandbox_policy import (
    SandboxPolicy,
    default_sandbox_policy,
)
from backend.services.autonomous_lab.stages import (
    LabStageNode,
    StageResult,
    default_stage_nodes,
)
from backend.services.autonomous_lab.state_store import (
    AsyncConnection,
    AutonomousLabStateStore,
    LabEventType,
    LabRunRecord,
    LabRuntimePlacement,
    current_runtime_placement,
)

WORKER_CONTRACT_VERSION = "autonomous-lab-v1-worker-skeleton"


class LabWorkerCheckpointStatus(str, Enum):
    """Durable worker checkpoint state."""

    CHECKPOINTED = "checkpointed"
    PLANNED = "planned"
    PAUSED = "paused"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class LabWorkerCheckpoint:
    """One dry-run checkpoint emitted by the worker skeleton."""

    order: int
    stage: LabStageName
    status: LabWorkerCheckpointStatus
    gate_state: LabGateState
    artifact: LabArtifactKind
    summary: str
    executed: bool = False
    external_calls: int = 0

    def to_receipt(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "stage": self.stage.value,
            "status": self.status.value,
            "gate_state": self.gate_state.value,
            "artifact": self.artifact.value,
            "summary": self.summary,
            "executed": self.executed,
            "external_calls": self.external_calls,
        }


@dataclass(frozen=True)
class LabWorkerDryRun:
    """Receipt-safe preview of a worker lifecycle with no command execution."""

    version: str
    run_id: str
    objective_reference: str
    created_at: datetime
    placement: LabRuntimePlacement
    sandbox_policy: SandboxPolicy
    checkpoints: tuple[LabWorkerCheckpoint, ...]
    paused_at_stage: LabStageName
    execution_allowed: bool
    manual_promotion_required: bool

    @property
    def blocked(self) -> bool:
        return any(
            checkpoint.status == LabWorkerCheckpointStatus.BLOCKED
            for checkpoint in self.checkpoints
        )

    def to_receipt(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "objective_reference": self.objective_reference,
            "created_at": self.created_at.isoformat(),
            "placement": self.placement.to_receipt(),
            "sandbox_policy": self.sandbox_policy.to_receipt(),
            "checkpoints": [
                checkpoint.to_receipt() for checkpoint in self.checkpoints
            ],
            "paused_at_stage": self.paused_at_stage.value,
            "execution_allowed": self.execution_allowed,
            "manual_promotion_required": self.manual_promotion_required,
            "blocked": self.blocked,
        }


class AutonomousLabWorker:
    """Worker skeleton that emits checkpoint receipts but never executes work."""

    def __init__(
        self,
        *,
        placement: LabRuntimePlacement | None = None,
        sandbox_policy: SandboxPolicy | None = None,
        state_store: AutonomousLabStateStore | None = None,
        stage_nodes: Sequence[LabStageNode] | None = None,
    ) -> None:
        self.placement = placement or current_runtime_placement()
        self.sandbox_policy = sandbox_policy or default_sandbox_policy()
        self.state_store = state_store or AutonomousLabStateStore()
        self.stage_nodes = tuple(stage_nodes or default_stage_nodes())

    async def tick(
        self,
        conn: AsyncConnection,
        *,
        worker_id: str,
    ) -> LabWorkerTickResult:
        """Claim and advance one queued run until completion, failure, or pause."""
        record = await self.state_store.claim_next_run(conn, worker_id=worker_id)
        if record is None:
            return LabWorkerTickResult.idle(worker_id=worker_id)

        checkpoints: list[LabCheckpoint] = []
        try:
            await self.state_store.heartbeat_run(
                conn,
                run_id=record.run_id,
                worker_id=worker_id,
            )
            context: dict[str, Any] = {}
            for node in _nodes_after_resume(self.stage_nodes, record):
                result = await node.run(record, context)
                checkpoint = _checkpoint_from_stage_result(record.run_id, result)
                checkpoints.append(checkpoint)
                await self.state_store.append_event(
                    conn,
                    run_id=record.run_id,
                    event_type=LabEventType.RUN_CHECKPOINTED,
                    payload={"checkpoint": checkpoint.to_receipt()},
                )
                context[result.stage.value] = checkpoint.fingerprint
                if result.status is LabStageStatus.PAUSED:
                    await self.state_store.mark_run_paused(
                        conn,
                        run_id=record.run_id,
                        worker_id=worker_id,
                        stage=result.stage.value,
                        checkpoint=checkpoint.to_receipt(),
                    )
                    return LabWorkerTickResult.paused(
                        worker_id=worker_id,
                        record=record,
                        checkpoints=tuple(checkpoints),
                        paused_at_stage=result.stage,
                    )

            await self.state_store.mark_run_succeeded(
                conn,
                run_id=record.run_id,
                worker_id=worker_id,
                summary={"checkpoint_count": len(checkpoints)},
            )
            return LabWorkerTickResult.succeeded(
                worker_id=worker_id,
                record=record,
                checkpoints=tuple(checkpoints),
            )
        except Exception as exc:
            error_reference = receipt_safe_evidence(str(exc), force_fingerprint=True)
            await self.state_store.mark_run_failed(
                conn,
                run_id=record.run_id,
                worker_id=worker_id,
                error=str(exc),
            )
            return LabWorkerTickResult.failed(
                worker_id=worker_id,
                record=record,
                checkpoints=tuple(checkpoints),
                error_reference=error_reference,
            )

    def dry_run(
        self,
        *,
        run_id: str = "lab-control-room-preview",
        objective_reference: str = "objective_fingerprint:preview",
        created_at: datetime | None = None,
    ) -> LabWorkerDryRun:
        """Return a deterministic lifecycle preview without side effects."""
        checkpoints = (
            LabWorkerCheckpoint(
                1,
                LabStageName.WATCH,
                LabWorkerCheckpointStatus.CHECKPOINTED,
                LabGateState.PENDING,
                LabArtifactKind.FRONTIER_SIGNAL,
                "watch signal envelope accepted for planning",
            ),
            LabWorkerCheckpoint(
                2,
                LabStageName.INTAKE,
                LabWorkerCheckpointStatus.CHECKPOINTED,
                LabGateState.PASSED,
                LabArtifactKind.RESEARCH_MATERIAL,
                "materials normalized into receipt-safe fingerprints",
            ),
            LabWorkerCheckpoint(
                3,
                LabStageName.COMPOSE,
                LabWorkerCheckpointStatus.CHECKPOINTED,
                LabGateState.PASSED,
                LabArtifactKind.LAB_RUN,
                "LabRun receipt drafted with verification plan",
            ),
            LabWorkerCheckpoint(
                4,
                LabStageName.EXPERIMENT,
                LabWorkerCheckpointStatus.PLANNED,
                LabGateState.PENDING,
                LabArtifactKind.SANDBOX_RUN_RESULT,
                "sandbox runner waits for explicit policy-bound execution",
            ),
            LabWorkerCheckpoint(
                5,
                LabStageName.CURATE,
                LabWorkerCheckpointStatus.PAUSED,
                LabGateState.MANUAL,
                LabArtifactKind.CURATOR_DECISION,
                "operator decision required before promotion",
            ),
        )
        return LabWorkerDryRun(
            version=WORKER_CONTRACT_VERSION,
            run_id=run_id,
            objective_reference=objective_reference,
            created_at=created_at or datetime.now(tz=timezone.utc),
            placement=self.placement,
            sandbox_policy=self.sandbox_policy,
            checkpoints=checkpoints,
            paused_at_stage=LabStageName.CURATE,
            execution_allowed=False,
            manual_promotion_required=True,
        )


@dataclass(frozen=True)
class LabWorkerTickResult:
    """Receipt-safe result for one worker tick."""

    worker_id: str
    status: LabStageStatus
    run_id: str | None
    checkpoints: tuple[LabCheckpoint, ...]
    paused_at_stage: LabStageName | None = None
    error_reference: str | None = None

    @classmethod
    def idle(cls, *, worker_id: str) -> LabWorkerTickResult:
        return cls(
            worker_id=worker_id,
            status=LabStageStatus.SKIPPED,
            run_id=None,
            checkpoints=(),
        )

    @classmethod
    def paused(
        cls,
        *,
        worker_id: str,
        record: LabRunRecord,
        checkpoints: tuple[LabCheckpoint, ...],
        paused_at_stage: LabStageName,
    ) -> LabWorkerTickResult:
        return cls(
            worker_id=worker_id,
            status=LabStageStatus.PAUSED,
            run_id=record.run_id,
            checkpoints=checkpoints,
            paused_at_stage=paused_at_stage,
        )

    @classmethod
    def succeeded(
        cls,
        *,
        worker_id: str,
        record: LabRunRecord,
        checkpoints: tuple[LabCheckpoint, ...],
    ) -> LabWorkerTickResult:
        return cls(
            worker_id=worker_id,
            status=LabStageStatus.SUCCEEDED,
            run_id=record.run_id,
            checkpoints=checkpoints,
        )

    @classmethod
    def failed(
        cls,
        *,
        worker_id: str,
        record: LabRunRecord,
        checkpoints: tuple[LabCheckpoint, ...],
        error_reference: str,
    ) -> LabWorkerTickResult:
        return cls(
            worker_id=worker_id,
            status=LabStageStatus.FAILED,
            run_id=record.run_id,
            checkpoints=checkpoints,
            error_reference=error_reference,
        )

    def to_receipt(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "status": self.status.value,
            "run_id": self.run_id,
            "checkpoint_count": len(self.checkpoints),
            "checkpoints": [checkpoint.to_receipt() for checkpoint in self.checkpoints],
            "paused_at_stage": (
                self.paused_at_stage.value if self.paused_at_stage is not None else None
            ),
            "error_reference": self.error_reference,
        }


def _checkpoint_from_stage_result(run_id: str, result: StageResult) -> LabCheckpoint:
    return build_lab_checkpoint(
        run_id=run_id,
        stage=result.stage,
        status=result.status,
        payload={
            "summary": result.summary,
            "artifact_kind": result.artifact_kind.value,
            **dict(result.payload),
        },
    )


def _nodes_after_resume(
    stage_nodes: Sequence[LabStageNode],
    record: LabRunRecord,
) -> tuple[LabStageNode, ...]:
    last_stage = str(record.metadata.get("last_checkpoint_stage", "")).strip()
    if not last_stage:
        return tuple(stage_nodes)
    for index, node in enumerate(stage_nodes):
        if node.name.value == last_stage:
            return tuple(stage_nodes[index + 1 :])
    raise ValueError("unknown autonomous lab resume checkpoint stage")


__all__ = [
    "WORKER_CONTRACT_VERSION",
    "AutonomousLabWorker",
    "LabWorkerCheckpoint",
    "LabWorkerCheckpointStatus",
    "LabWorkerDryRun",
    "LabWorkerTickResult",
]
