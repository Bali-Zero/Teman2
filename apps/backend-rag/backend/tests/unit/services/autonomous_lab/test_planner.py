from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.services.autonomous_lab.planner import (
    AutonomousLabPlanner,
    GateSeverity,
    MaterialSourceType,
    ResearchMaterial,
    default_pipeline,
)


def _material(
    *,
    material_id: str = "m1",
    source_type: MaterialSourceType = MaterialSourceType.WEB,
    text: str = "A research note claims that prod-like simulation must run before promotion.",
    metadata: dict[str, str] | None = None,
) -> ResearchMaterial:
    return ResearchMaterial(
        material_id=material_id,
        source_type=source_type,
        source_uri=f"{source_type.value}://example/{material_id}",
        title="Lab source",
        text=text,
        captured_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
        metadata=metadata or {},
    )


def test_default_pipeline_covers_required_lab_stages() -> None:
    stages = [step.stage for step in default_pipeline()]
    assert stages == [
        "intake",
        "normalize",
        "compose",
        "reconstruct",
        "experiment",
        "verify",
        "promote",
    ]


def test_draft_run_is_source_agnostic_and_omits_raw_text_from_receipt() -> None:
    raw_secret_phrase = "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR"
    planner = AutonomousLabPlanner(worktree_lane="ops")
    run = planner.draft_run(
        objective="riprendere il laboratorio autonomo",
        materials=[
            _material(source_type=MaterialSourceType.WEB),
            _material(
                material_id="m2",
                source_type=MaterialSourceType.CHAT_METADATA,
                text=f"Sanitized chat metadata points to a CRM opportunity. {raw_secret_phrase}",
            ),
            _material(
                material_id="m3",
                source_type=MaterialSourceType.REPO,
                text="Repository evidence: pytest and git diff checks should gate experiments.",
            ),
        ],
        target_paths=[
            "apps/backend-rag/backend/services/autonomous_lab/planner.py",
            "research/operations/autonomous-lab/2026-05-31-technical-map.md",
        ],
        task_id="autonomous-lab-v0",
        created_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
    )

    receipt = json.dumps(run.to_receipt())
    assert {material.source_type for material in run.materials} == {
        MaterialSourceType.WEB,
        MaterialSourceType.CHAT_METADATA,
        MaterialSourceType.REPO,
    }
    assert raw_secret_phrase not in receipt
    assert "checksum_sha256" in receipt
    assert run.simulation_plan.worktree_command.endswith("--task-id autonomous-lab-v0")
    assert any(
        "pytest backend/tests/unit/services/autonomous_lab" in command
        for command in run.simulation_plan.verification_commands
    )
    assert run.has_blockers() is False


def test_workspace_write_request_is_a_blocker() -> None:
    planner = AutonomousLabPlanner()
    run = planner.draft_run(
        objective="test gate",
        materials=[
            _material(metadata={"requires_google_workspace_write": "true"}),
        ],
        target_paths=["research/operations/autonomous-lab/map.md"],
        task_id="workspace-block",
        created_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
    )

    gate = next(gate for gate in run.safety_gates if gate.name == "google_workspace_write_block")
    assert gate.passed is False
    assert gate.severity == GateSeverity.BLOCKER
    assert run.has_blockers() is True


def test_empty_materials_fail_material_gate() -> None:
    planner = AutonomousLabPlanner()
    run = planner.draft_run(
        objective="test empty",
        materials=[],
        target_paths=["research/operations/autonomous-lab/map.md"],
        task_id="empty-materials",
        created_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
    )

    gate = next(gate for gate in run.safety_gates if gate.name == "materials_present")
    assert gate.passed is False
    assert run.has_blockers() is True


def test_write_receipt_persists_json_without_raw_text(tmp_path: Path) -> None:
    planner = AutonomousLabPlanner()
    raw_phrase = "RAW_BODY_NOT_ALLOWED_IN_RECEIPT"
    run = planner.draft_run(
        objective="persist state",
        materials=[_material(text=f"Derived facts only. {raw_phrase}")],
        target_paths=["apps/backend-rag/backend/services/autonomous_lab/planner.py"],
        task_id="receipt-test",
        created_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
    )

    path = planner.write_receipt(run, tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path.name == "receipt-test.json"
    assert payload["run_id"] == "receipt-test"
    assert raw_phrase not in path.read_text(encoding="utf-8")
    assert payload["promotion_policy"] == "manual_operator_decision_only"
