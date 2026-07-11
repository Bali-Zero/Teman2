from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.services.autonomous_lab.planner import (
    NOTEBOOKLM_OVERFLOW_THRESHOLD,
    AutonomousLabPlanner,
    GateSeverity,
    MaterialSourceType,
    ResearchMaterial,
    default_pipeline,
    default_research_notebooks,
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
        "watch",
        "intake",
        "normalize",
        "compose",
        "reconstruct",
        "experiment",
        "verify",
        "curate",
        "archive",
    ]


def test_default_research_notebooks_route_ai_coding_lab_memory() -> None:
    notebooks = default_research_notebooks()
    by_key = {notebook.key: notebook for notebook in notebooks}

    assert list(by_key) == [
        "frontier_radar",
        "agent_engineering_core",
        "ai_research_overflow",
    ]
    assert len({notebook.notebook_id for notebook in notebooks}) == len(notebooks)
    assert by_key["frontier_radar"].notebook_id == (
        "dc5d01cd-e99f-4c8f-aae4-75060b43d0de"
    )
    assert by_key["agent_engineering_core"].notebook_id == (
        "dff45303-4b51-45ad-8718-502d4f8a8e3f"
    )
    assert by_key["ai_research_overflow"].notebook_id == (
        "069f009c-ce74-42e5-b75c-e584aa18feb1"
    )
    assert by_key["frontier_radar"].observed_source_count >= NOTEBOOKLM_OVERFLOW_THRESHOLD
    assert by_key["frontier_radar"].near_source_limit is True
    assert "route new writes" in by_key["frontier_radar"].write_policy
    assert "multi-agent architecture" in by_key["agent_engineering_core"].query_contract
    assert "6d449787-04e3-430e-acbe-d6fc38d379a9" in (
        by_key["agent_engineering_core"].related_notebook_ids
    )


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
    assert "content_fingerprint" in receipt
    assert "sha256:" in receipt
    assert run.simulation_plan.worktree_command.endswith("--task-id autonomous-lab-v0")
    assert any(
        "pytest backend/tests/unit/services/autonomous_lab" in command
        for command in run.simulation_plan.verification_commands
    )
    assert [notebook.key for notebook in run.research_notebooks] == [
        "frontier_radar",
        "agent_engineering_core",
        "ai_research_overflow",
    ]
    assert "dff45303-4b51-45ad-8718-502d4f8a8e3f" in receipt
    assert run.has_blockers() is False


def test_frontier_watch_tags_ai_and_software_signals() -> None:
    planner = AutonomousLabPlanner(worktree_lane="ops")
    run = planner.draft_run(
        objective="turn AI and software research into a Nuzantara experiment",
        materials=[
            _material(
                text=(
                    "A new LLM agent benchmark and SDK release suggest a framework "
                    "change that should be simulated before production adoption."
                )
            ),
        ],
        target_paths=["apps/backend-rag/backend/services/autonomous_lab/planner.py"],
        task_id="frontier-watch",
        created_at=datetime(2026, 6, 16, tzinfo=timezone.utc),
    )

    tags = set(run.materials[0].tags)
    assert {"ai_frontier", "software_frontier", "simulation"} <= tags
    assert run.pipeline[0].stage == "watch"
    assert run.pipeline[0].component == "ai_software_watchtower"
    assert any(gate.name == "frontier_watch_is_bounded" for gate in run.safety_gates)
    assert any(
        gate.name == "notebooklm_research_route_declared"
        and "frontier_radar" in gate.detail
        and "ai_research_overflow" in gate.detail
        for gate in run.safety_gates
    )


def test_receipt_sanitizes_objective_and_sensitive_source_uri() -> None:
    raw_objective = "Investigate RAW_OBJECTIVE_SHOULD_NOT_APPEAR with token=abcdef1234567890"
    signed_source_uri = "https://drive.example/file?id=abc&token=abcdef1234567890"
    planner = AutonomousLabPlanner(worktree_lane="ops")
    run = planner.draft_run(
        objective=raw_objective,
        materials=[
            ResearchMaterial(
                material_id="m1",
                source_type=MaterialSourceType.DRIVE_METADATA,
                source_uri=signed_source_uri,
                title="Sensitive provenance",
                text="Derived facts only for the Lab planner.",
                captured_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
                metadata={},
            )
        ],
        target_paths=["apps/backend-rag/backend/services/autonomous_lab/planner.py"],
        task_id="sanitized-receipt",
        created_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
    )

    receipt = json.dumps(run.to_receipt(), sort_keys=True)

    assert "RAW_OBJECTIVE_SHOULD_NOT_APPEAR" not in receipt
    assert "abcdef1234567890" not in receipt
    assert "objective_fingerprint:sha256:" in receipt
    assert "drive_metadata:source_fingerprint:sha256:" in receipt


def test_receipt_sanitizes_public_source_uri_path_and_short_pii() -> None:
    raw_email = "client.name@example.com"
    raw_phone = "+62 812-3456-7890"
    source_uri = f"https://example.com/clients/{raw_email}/wa/{raw_phone}"
    planner = AutonomousLabPlanner(worktree_lane="ops")
    run = planner.draft_run(
        objective="test public URI safety",
        materials=[
            ResearchMaterial(
                material_id="m1",
                source_type=MaterialSourceType.WEB,
                source_uri=source_uri,
                title="Public URI with private path",
                text="Derived facts only for public URI safety.",
                captured_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
                metadata={},
            )
        ],
        target_paths=["apps/backend-rag/backend/services/autonomous_lab/planner.py"],
        task_id="public-uri-safety",
        created_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
    )

    receipt = json.dumps(run.to_receipt(), sort_keys=True)

    assert raw_email not in receipt
    assert raw_phone not in receipt
    assert "/clients/" not in receipt
    assert "https://example.com/source_fingerprint:sha256:" in receipt


def test_receipt_sanitizes_material_identifiers_and_titles() -> None:
    raw_material_id = "RAW_MATERIAL_ID_SHOULD_NOT_APPEAR"
    raw_title_marker = "RAW_TITLE_SHOULD_NOT_APPEAR"
    raw_title_token = "token=abc.def.ghi.jkl"
    private_source_uri = "note://local/material-safety"
    planner = AutonomousLabPlanner(worktree_lane="ops")
    run = planner.draft_run(
        objective="test material receipt safety",
        materials=[
            ResearchMaterial(
                material_id=raw_material_id,
                source_type=MaterialSourceType.OPERATOR_NOTE,
                source_uri=private_source_uri,
                title=f"Collected prompt {raw_title_marker} {raw_title_token}",
                text="Derived facts only for the planner receipt.",
                captured_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
                metadata={},
            )
        ],
        target_paths=["apps/backend-rag/backend/services/autonomous_lab/planner.py"],
        task_id="material-receipt-safety",
        created_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
    )

    receipt = json.dumps(run.to_receipt(), sort_keys=True)

    assert raw_material_id not in receipt
    assert raw_title_marker not in receipt
    assert raw_title_token not in receipt
    assert private_source_uri not in receipt
    assert "material_fingerprint:sha256:" in receipt
    assert "operator_note:source_fingerprint:sha256:" in receipt
    assert "title_fingerprint:sha256:" in receipt


def test_planner_rejects_unsafe_target_paths() -> None:
    planner = AutonomousLabPlanner(worktree_lane="ops")

    with pytest.raises(ValueError, match="path traversal"):
        planner.draft_run(
            objective="test unsafe path",
            materials=[_material()],
            target_paths=["../outside.py"],
            task_id="unsafe-path",
            created_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
        )

    with pytest.raises(ValueError, match="receipt-sensitive"):
        planner.draft_run(
            objective="test sensitive path",
            materials=[_material()],
            target_paths=[
                "apps/backend-rag/backend/services/autonomous_lab/token=abcdef1234567890.py"
            ],
            task_id="sensitive-path",
            created_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
        )


def test_planner_rejects_unsafe_command_arguments() -> None:
    with pytest.raises(ValueError, match="worktree_lane"):
        AutonomousLabPlanner(worktree_lane="ops;fly-deploy").draft_run(
            objective="test unsafe lane",
            materials=[_material()],
            target_paths=["apps/backend-rag/backend/services/autonomous_lab/planner.py"],
            task_id="safe-task",
            created_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
        )

    with pytest.raises(ValueError, match="task_id"):
        AutonomousLabPlanner(worktree_lane="ops").draft_run(
            objective="test unsafe task",
            materials=[_material()],
            target_paths=["apps/backend-rag/backend/services/autonomous_lab/planner.py"],
            task_id="bad;fly-deploy",
            created_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
        )


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
    assert (tmp_path / "events.jsonl").exists()


def test_write_receipt_uses_append_only_store(tmp_path: Path) -> None:
    planner = AutonomousLabPlanner()
    run = planner.draft_run(
        objective="persist state once",
        materials=[_material()],
        target_paths=["apps/backend-rag/backend/services/autonomous_lab/planner.py"],
        task_id="receipt-store-once",
        created_at=datetime(2026, 5, 31, tzinfo=timezone.utc),
    )

    planner.write_receipt(run, tmp_path)

    with pytest.raises(FileExistsError, match="receipt already exists"):
        planner.write_receipt(run, tmp_path)
