"""Stage-node contracts for the Autonomous Lab worker lifecycle."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from backend.services.autonomous_lab.command_policy import contains_blocked_command_verb
from backend.services.autonomous_lab.runtime_contracts import (
    LabArtifactKind,
    LabStageName,
    LabStageStatus,
)
from backend.services.autonomous_lab.state_store import LabRunRecord


class LabStageRiskClass(str, Enum):
    """Risk class declared by a stage before it can run."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MANUAL = "manual"


@dataclass(frozen=True)
class StageResult:
    """Receipt-safe stage transition emitted by a stage node."""

    stage: LabStageName
    status: LabStageStatus
    artifact_kind: LabArtifactKind
    summary: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.stage, LabStageName):
            raise ValueError("stage result must use canonical LabStageName")
        if not isinstance(self.status, LabStageStatus):
            raise ValueError("stage result must use canonical LabStageStatus")
        if contains_blocked_command_verb(self.summary) or _payload_contains_blocked_verb(
            self.payload
        ):
            raise ValueError("stage result contains blocked command verb")


class LabStageNode(Protocol):
    """Executable stage interface used by the durable worker."""

    name: LabStageName
    input_data_class: str
    output_data_class: str
    risk_class: LabStageRiskClass

    async def run(
        self,
        run: LabRunRecord,
        context: Mapping[str, Any],
    ) -> StageResult:
        """Execute one stage transition and return a receipt-safe result."""


@dataclass(frozen=True)
class NoopLabStageNode:
    """No-side-effect stage node used until real adapters are wired."""

    name: LabStageName
    input_data_class: str
    output_data_class: str
    risk_class: LabStageRiskClass
    artifact_kind: LabArtifactKind
    summary: str
    pause: bool = False

    async def run(
        self,
        run: LabRunRecord,
        context: Mapping[str, Any],
    ) -> StageResult:
        """Emit a deterministic stage result without external side effects."""
        status = LabStageStatus.PAUSED if self.pause else LabStageStatus.SUCCEEDED
        return StageResult(
            stage=self.name,
            status=status,
            artifact_kind=self.artifact_kind,
            summary=self.summary,
            payload={
                "run_id": run.run_id,
                "input_data_class": self.input_data_class,
                "output_data_class": self.output_data_class,
                "risk_class": self.risk_class.value,
                "previous_stage_count": len(context),
            },
        )


def default_stage_nodes() -> tuple[LabStageNode, ...]:
    """Return the v1 no-op lifecycle, pausing at the curator gate."""
    return (
        NoopLabStageNode(
            LabStageName.WATCH,
            "LabRunRecord",
            "FrontierSignal",
            LabStageRiskClass.LOW,
            LabArtifactKind.FRONTIER_SIGNAL,
            "watch envelope accepted without fetching external sources",
        ),
        NoopLabStageNode(
            LabStageName.INTAKE,
            "FrontierSignal",
            "ResearchMaterial",
            LabStageRiskClass.LOW,
            LabArtifactKind.RESEARCH_MATERIAL,
            "material references normalized as receipt-safe fingerprints",
        ),
        NoopLabStageNode(
            LabStageName.NORMALIZE,
            "ResearchMaterial",
            "NormalizedMaterial",
            LabStageRiskClass.LOW,
            LabArtifactKind.RESEARCH_MATERIAL,
            "normalized material stays metadata-only",
        ),
        NoopLabStageNode(
            LabStageName.COMPOSE,
            "NormalizedMaterial",
            "LabRun",
            LabStageRiskClass.MEDIUM,
            LabArtifactKind.LAB_RUN,
            "hypothesis and verification envelope composed",
        ),
        NoopLabStageNode(
            LabStageName.RECONSTRUCT,
            "LabRun",
            "ProdLikeContextManifest",
            LabStageRiskClass.MEDIUM,
            LabArtifactKind.LAB_CHECKPOINT,
            "prod-like context manifest declared with synthetic fixtures only",
        ),
        NoopLabStageNode(
            LabStageName.EXPERIMENT,
            "ProdLikeContextManifest",
            "SandboxRunRequest",
            LabStageRiskClass.HIGH,
            LabArtifactKind.SANDBOX_RUN_RESULT,
            "sandbox request prepared; no command executed by no-op node",
        ),
        NoopLabStageNode(
            LabStageName.VERIFY,
            "SandboxRunResult",
            "EvaluationReport",
            LabStageRiskClass.HIGH,
            LabArtifactKind.EVALUATION_REPORT,
            "verification plan requires empirical runner before promotion",
        ),
        NoopLabStageNode(
            LabStageName.CURATE,
            "EvaluationReport",
            "CuratorDecision",
            LabStageRiskClass.MANUAL,
            LabArtifactKind.CURATOR_DECISION,
            "operator decision required before any promotion",
            pause=True,
        ),
    )


def _payload_contains_blocked_verb(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_payload_contains_blocked_verb(child) for child in value.values())
    if isinstance(value, list | tuple):
        return any(_payload_contains_blocked_verb(child) for child in value)
    if isinstance(value, str):
        return contains_blocked_command_verb(value)
    return False


__all__ = [
    "LabStageNode",
    "LabStageRiskClass",
    "NoopLabStageNode",
    "StageResult",
    "default_stage_nodes",
]
