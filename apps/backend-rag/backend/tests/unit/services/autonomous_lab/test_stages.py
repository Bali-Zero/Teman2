from __future__ import annotations

from typing import Any

import pytest

from backend.services.autonomous_lab.runtime_contracts import (
    LabArtifactKind,
    LabStageName,
    LabStageStatus,
)
from backend.services.autonomous_lab.stages import (
    LabStageRiskClass,
    NoopLabStageNode,
    StageResult,
    default_stage_nodes,
)
from backend.services.autonomous_lab.state_store import LabRunRecord, LabRunStatus


def _run_record(**overrides: Any) -> LabRunRecord:
    values = {
        "run_id": "stage-node-test",
        "idempotency_key": "stage-node-test:v1",
        "status": LabRunStatus.RUNNING,
        "objective": "objective_fingerprint:sha256:1234-5678",
        "receipt": {"run_id": "stage-node-test", "blocked": False},
        "target_paths": (),
        "metadata": {},
        "priority": 0,
        "attempts": 1,
        "max_attempts": 3,
        "inserted": True,
    }
    values.update(overrides)
    return LabRunRecord(**values)


def test_default_stage_nodes_follow_canonical_lifecycle_until_curate() -> None:
    nodes = default_stage_nodes()

    assert [node.name for node in nodes] == [
        LabStageName.WATCH,
        LabStageName.INTAKE,
        LabStageName.NORMALIZE,
        LabStageName.COMPOSE,
        LabStageName.RECONSTRUCT,
        LabStageName.EXPERIMENT,
        LabStageName.VERIFY,
        LabStageName.CURATE,
    ]
    assert nodes[-1].risk_class is LabStageRiskClass.MANUAL


@pytest.mark.asyncio
async def test_noop_stage_node_emits_receipt_safe_result() -> None:
    node = NoopLabStageNode(
        LabStageName.NORMALIZE,
        "ResearchMaterial",
        "NormalizedMaterial",
        LabStageRiskClass.LOW,
        LabArtifactKind.RESEARCH_MATERIAL,
        "normalized material stays metadata-only",
    )

    result = await node.run(_run_record(), {"watch": object()})

    assert result.stage is LabStageName.NORMALIZE
    assert result.status is LabStageStatus.SUCCEEDED
    assert result.payload["run_id"] == "stage-node-test"
    assert result.payload["previous_stage_count"] == 1


@pytest.mark.asyncio
async def test_manual_curate_node_pauses_worker() -> None:
    result = await default_stage_nodes()[-1].run(_run_record(), {})

    assert result.stage is LabStageName.CURATE
    assert result.status is LabStageStatus.PAUSED


def test_stage_result_rejects_blocked_command_verbs() -> None:
    with pytest.raises(ValueError, match="blocked command verb"):
        StageResult(
            stage=LabStageName.EXPERIMENT,
            status=LabStageStatus.SUCCEEDED,
            artifact_kind=LabArtifactKind.SANDBOX_RUN_RESULT,
            summary="ready to git push origin main",
            payload={},
        )

    with pytest.raises(ValueError, match="blocked command verb"):
        StageResult(
            stage=LabStageName.EXPERIMENT,
            status=LabStageStatus.SUCCEEDED,
            artifact_kind=LabArtifactKind.SANDBOX_RUN_RESULT,
            summary="safe summary",
            payload={"command": "fly deploy"},
        )
