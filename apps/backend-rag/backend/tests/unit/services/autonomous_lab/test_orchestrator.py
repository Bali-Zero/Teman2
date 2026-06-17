from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch

from backend.services.autonomous_lab.orchestrator import (
    AutonomousLabOrchestrator,
    FleetStageStatus,
    LabOrchestrationResult,
    OrchestrationBounds,
)
from backend.services.autonomous_lab.planner import MaterialSourceType, ResearchMaterial


def _material(
    *,
    material_id: str = "m1",
    source_type: MaterialSourceType = MaterialSourceType.OPERATOR_NOTE,
    source_uri: str | None = None,
    title: str = "Bounded orchestration material",
    text: str = "A lab note says experiments need prod-like verification before promotion.",
    metadata: dict[str, str] | None = None,
) -> ResearchMaterial:
    return ResearchMaterial(
        material_id=material_id,
        source_type=source_type,
        source_uri=source_uri or f"{source_type.value}://example/{material_id}",
        title=title,
        text=text,
        captured_at=datetime(2026, 6, 9, tzinfo=timezone.utc),
        metadata=metadata or {},
    )


def _orchestrate(
    *,
    materials: list[ResearchMaterial] | None = None,
    target_paths: list[str] | None = None,
) -> LabOrchestrationResult:
    orchestrator = AutonomousLabOrchestrator()
    return orchestrator.orchestrate(
        objective="implement bounded autonomous lab orchestration",
        materials=materials if materials is not None else [_material()],
        target_paths=target_paths
        if target_paths is not None
        else [
            "apps/backend-rag/backend/services/autonomous_lab/orchestrator.py",
            "apps/backend-rag/backend/tests/unit/services/autonomous_lab/test_orchestrator.py",
        ],
        task_id="orchestrator-test",
        created_at=datetime(2026, 6, 9, tzinfo=timezone.utc),
    )


def test_orchestrator_runs_ordered_agent_fleet_stages() -> None:
    result = _orchestrate()

    assert [(stage.order, stage.stage, stage.role) for stage in result.stages] == [
        (1, "intake", "intake_normalizer"),
        (2, "compose", "hypothesis_composer"),
        (3, "context", "context_builder"),
        (4, "review", "reviewer"),
        (5, "verify", "verification_planner"),
    ]
    assert [member.role for member in result.fleet] == [
        "intake_normalizer",
        "hypothesis_composer",
        "context_builder",
        "reviewer",
        "verification_planner",
    ]
    assert result.blocked is False


def test_orchestration_receipt_declares_v1_control_plane_and_parallel_work() -> None:
    result = _orchestrate()
    operational_plan = result.to_receipt()["operational_plan"]

    assert operational_plan["version"] == "autonomous-lab-v1-control-plane"
    assert [piece["key"] for piece in operational_plan["governance_pieces"]] == [
        "P1",
        "P2",
        "P3",
        "P4",
        "P5",
        "P6",
        "P7",
        "P8",
        "P9",
    ]
    assert operational_plan["anchor_jobs"][0]["key"] == "lab_intake_sweeper"
    assert operational_plan["missing_component_keys"] == [
        "operational_queue",
        "events_outbox",
        "source_adapters",
        "composer",
        "prod_like_context_builder",
        "worktree_experiment_runner",
        "verification_runner",
        "curator_decision_gate",
        "scheduler_daemon",
        "dashboard_api",
    ]
    assert "scheduler_daemon" in operational_plan["blocked_component_keys"]
    assert {
        "source_adapters",
        "composer",
        "prod_like_context_builder",
        "worktree_experiment_runner",
        "verification_runner",
        "curator_decision_gate",
        "dashboard_api",
    } <= set(operational_plan["parallelizable_component_keys"])


def test_orchestration_receipt_omits_raw_material_text() -> None:
    raw_phrase = "RAW_MATERIAL_BODY_MUST_NOT_ESCAPE_ORCHESTRATOR_RECEIPT"
    result = _orchestrate(
        materials=[
            _material(
                text=(
                    "Sanitized metadata says the Lab needs deterministic orchestration. "
                    f"{raw_phrase}"
                )
            )
        ]
    )

    receipt_text = json.dumps(result.to_receipt(), sort_keys=True)

    assert raw_phrase not in receipt_text
    assert "content_fingerprint" in receipt_text
    assert "claim_fingerprint" in receipt_text
    assert all(stage.executed is False for stage in result.stages)
    assert all(stage.external_calls == 0 for stage in result.stages)


def test_orchestration_receipt_redacts_raw_and_secret_like_material_fields() -> None:
    raw_phrase = "RAW_STAGE_VALUE_SHOULD_NOT_APPEAR"
    secret_like_value = "token=abcdef1234567890"
    result = _orchestrate(materials=[_material(text="Derived body without raw marker.")])
    result.stages[0].inputs.append(raw_phrase)
    result.stages[1].outputs.append(secret_like_value)

    receipt_text = json.dumps(result.to_receipt(), sort_keys=True)

    assert raw_phrase not in receipt_text
    assert secret_like_value not in receipt_text
    assert "redacted_receipt_value:" in receipt_text
    assert result.blocked is False


def test_planner_blockers_propagate_to_review_and_receipt() -> None:
    result = _orchestrate(
        materials=[
            _material(metadata={"requires_google_workspace_write": "true"}),
        ]
    )

    reviewer_stage = next(stage for stage in result.stages if stage.role == "reviewer")
    verifier_stage = next(stage for stage in result.stages if stage.role == "verification_planner")
    receipt = result.to_receipt()

    assert result.blocked is True
    assert "google_workspace_write_block" in result.failed_blockers
    assert "google_workspace_write_request" in result.failed_blockers
    assert reviewer_stage.status == FleetStageStatus.BLOCKED
    assert verifier_stage.status == FleetStageStatus.BLOCKED
    assert "google_workspace_write_block" in reviewer_stage.blockers
    assert "google_workspace_write_block" in receipt["failed_blockers"]
    assert receipt["run"]["blocked"] is True


def test_orchestrator_never_executes_shell_deploy_merge_or_external_calls() -> None:
    with (
        patch("subprocess.run") as subprocess_run,
        patch("subprocess.Popen") as subprocess_popen,
        patch("os.system") as os_system,
        patch("urllib.request.urlopen") as urlopen,
        patch("socket.create_connection") as create_connection,
    ):
        result = _orchestrate()

    subprocess_run.assert_not_called()
    subprocess_popen.assert_not_called()
    os_system.assert_not_called()
    urlopen.assert_not_called()
    create_connection.assert_not_called()

    receipt = result.to_receipt()
    policy = receipt["execution_policy"]
    unsafe_markers = (
        "deploy",
        "git push",
        "git merge",
        "gh pr merge",
        "docker push",
        "kubectl apply",
    )

    assert policy["shell_execution_allowed"] is False
    assert policy["external_calls_allowed"] is False
    assert policy["deploy_allowed"] is False
    assert policy["merge_allowed"] is False
    assert policy["shell_commands_executed"] == []
    assert policy["deploys_triggered"] == []
    assert policy["merges_triggered"] == []
    assert policy["external_calls_made"] == []
    assert all(stage["executed"] is False for stage in receipt["stage_results"])
    assert all(stage["external_calls"] == 0 for stage in receipt["stage_results"])
    assert not any(
        marker in command.lower()
        for command in result.planned_only_commands
        for marker in unsafe_markers
    )


def test_orchestrator_rejects_oversized_material_before_receipt() -> None:
    orchestrator = AutonomousLabOrchestrator(
        bounds=OrchestrationBounds(max_material_text_chars=20)
    )

    try:
        orchestrator.orchestrate(
            objective="oversized material",
            materials=[_material(text="x" * 21)],
            target_paths=["apps/backend-rag/backend/services/autonomous_lab/orchestrator.py"],
            task_id="oversized-material",
            created_at=datetime(2026, 6, 9, tzinfo=timezone.utc),
        )
    except ValueError as exc:
        assert "text length 21 exceeds 20" in str(exc)
    else:
        raise AssertionError("oversized material should fail before orchestration")
