from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone

from backend.services.autonomous_lab.planner import (
    AutonomousLabPlanner,
    LabRun,
    MaterialSourceType,
    ResearchMaterial,
)
from backend.services.autonomous_lab.reviewer import (
    AutonomousLabReviewer,
    LabReviewDecision,
)


def _material(
    *,
    text: str = "Repository evidence says the lab should use tests before promotion.",
    metadata: dict[str, str] | None = None,
) -> ResearchMaterial:
    return ResearchMaterial(
        material_id="m1",
        source_type=MaterialSourceType.OPERATOR_NOTE,
        source_uri="note://local/reviewer-test",
        title="Reviewer source",
        text=text,
        captured_at=datetime(2026, 6, 9, tzinfo=timezone.utc),
        metadata=metadata or {},
    )


def _safe_run(
    *,
    materials: list[ResearchMaterial] | None = None,
    target_paths: list[str] | None = None,
) -> LabRun:
    planner = AutonomousLabPlanner(worktree_lane="ops")
    return planner.draft_run(
        objective="review autonomous lab guardrails",
        materials=materials or [_material()],
        target_paths=target_paths
        or ["apps/backend-rag/backend/services/autonomous_lab/reviewer.py"],
        task_id="reviewer-test",
        created_at=datetime(2026, 6, 9, tzinfo=timezone.utc),
    )


def _review(run: LabRun) -> LabReviewDecision:
    return AutonomousLabReviewer().review(run)


def _rule_ids(decision: LabReviewDecision) -> set[str]:
    return {finding.rule_id for finding in decision.findings}


def test_safe_run_is_approved_without_findings() -> None:
    decision = _review(_safe_run())

    assert decision.approved is True
    assert decision.blocked is False
    assert decision.findings == ()
    assert decision.to_receipt()["blocker_count"] == 0


def test_deploy_command_is_blocked() -> None:
    run = _safe_run()
    plan = replace(run.simulation_plan, verification_commands=["fly deploy -a nuzantara-rag"])
    decision = _review(replace(run, simulation_plan=plan))

    assert decision.approved is False
    assert decision.blocked is True
    assert "deploy_command" in _rule_ids(decision)
    deploy_finding = next(
        finding for finding in decision.findings if finding.rule_id == "deploy_command"
    )
    assert deploy_finding.location == "simulation_plan.verification_commands[0]"


def test_unallowlisted_verification_command_is_blocked() -> None:
    run = _safe_run()
    plan = replace(run.simulation_plan, verification_commands=["python -c 'print(1)'"])
    decision = _review(replace(run, simulation_plan=plan))

    assert decision.approved is False
    assert decision.blocked is True
    assert "verification_command_not_allowlisted" in _rule_ids(decision)


def test_autonomous_lab_script_paths_are_allowed_exactly() -> None:
    decision = _review(_safe_run(target_paths=["scripts/autonomous_lab_run.py"]))

    assert decision.approved is True
    assert decision.blocked is False

    blocked = _review(_safe_run(target_paths=["scripts/unrelated_helper.py"]))

    assert blocked.approved is False
    assert "unsafe_target_path" in _rule_ids(blocked)


def test_autonomous_lab_ui_paths_are_allowed_narrowly() -> None:
    allowed = _review(
        _safe_run(
            target_paths=[
                "apps/admin-dashboard/app/autonomous-lab/page.tsx",
                "apps/admin-dashboard/lib/autonomous-lab.ts",
                "apps/admin-dashboard/components/Sidebar.tsx",
            ]
        )
    )

    assert allowed.approved is True
    assert allowed.blocked is False

    blocked = _review(_safe_run(target_paths=["apps/admin-dashboard/app/legal/page.tsx"]))

    assert blocked.approved is False
    assert "unsafe_target_path" in _rule_ids(blocked)


def test_planned_only_commands_outside_plan_are_scanned() -> None:
    run = _safe_run()
    receipt = run.to_receipt()
    receipt["planned_only_commands"] = ["git push origin main"]
    receipt["stage_results"] = [{"planned_only_commands": ["fly deploy -a prod"]}]

    decision = AutonomousLabReviewer().review(receipt)

    assert decision.blocked is True
    assert {"push_command", "deploy_command"} <= _rule_ids(decision)


def test_planned_only_non_mutating_commands_must_be_allowlisted() -> None:
    run = _safe_run()
    receipt = run.to_receipt()
    receipt["planned_only_commands"] = ["python scripts/unreviewed_helper.py"]

    decision = AutonomousLabReviewer().review(receipt)

    assert decision.blocked is True
    assert "command_not_allowlisted" in _rule_ids(decision)


def test_command_patterns_block_global_options_and_flag_order() -> None:
    run = _safe_run()
    receipt = run.to_receipt()
    receipt["planned_only_commands"] = [
        "git -C . push origin main",
        "git -c user.name=lab merge main",
        "flyctl -a prod deploy",
        "rm -fr /tmp/autonomous-lab",
    ]

    decision = AutonomousLabReviewer().review(receipt)

    assert decision.blocked is True
    assert {
        "deploy_command",
        "merge_command",
        "push_command",
        "unsafe_command",
    } <= _rule_ids(decision)


def test_nested_run_planned_only_commands_are_scanned() -> None:
    run = _safe_run()
    receipt = {"run": run.to_receipt()}
    receipt["run"]["planned_only_commands"] = ["git -C . push origin main"]

    decision = AutonomousLabReviewer().review(receipt)

    assert decision.blocked is True
    finding = next(finding for finding in decision.findings if finding.rule_id == "push_command")
    assert finding.location == "run.planned_only_commands[0]"


def test_worktree_command_must_match_allowlist() -> None:
    run = _safe_run()
    plan = replace(run.simulation_plan, worktree_command="python -c 'print(1)'")
    decision = _review(replace(run, simulation_plan=plan))

    assert decision.blocked is True
    assert "worktree_command_not_allowlisted" in _rule_ids(decision)


def test_missing_worktree_command_is_blocked() -> None:
    run = _safe_run()
    receipt = run.to_receipt()
    receipt["simulation_plan"].pop("worktree_command")

    decision = AutonomousLabReviewer().review(receipt)

    assert decision.blocked is True
    assert "missing_worktree_command" in _rule_ids(decision)


def test_unsafe_absolute_and_traversal_paths_are_blocked() -> None:
    run = _safe_run()
    plan = replace(run.simulation_plan, target_paths=["/etc/passwd", "../outside.py"])
    decision = _review(replace(run, simulation_plan=plan))

    assert decision.blocked is True
    path_findings = [
        finding for finding in decision.findings if finding.rule_id == "unsafe_target_path"
    ]
    assert len(path_findings) == 2
    assert path_findings[0].evidence == "/etc/passwd"
    assert path_findings[1].evidence == "../outside.py"


def test_raw_phrase_leakage_is_blocked() -> None:
    raw_phrase = "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR"
    run = _safe_run(materials=[_material(text=f"Input contains {raw_phrase} but planner omits it.")])
    assert raw_phrase not in str(run.to_receipt())

    leaked_material = replace(run.materials[0], summary=f"Leaked phrase: {raw_phrase}")
    decision = _review(replace(run, materials=[leaked_material]))

    assert decision.blocked is True
    assert "raw_text_leakage" in _rule_ids(decision)


def test_raw_leakage_finding_evidence_is_receipt_safe() -> None:
    raw_phrase = "RAW_PRIVATE_SENTENCE_SHOULD_NOT_APPEAR"
    run = _safe_run()
    receipt = run.to_receipt()
    receipt["materials"][0]["summary"] = f"Leaked phrase: {raw_phrase}"

    decision = AutonomousLabReviewer().review(receipt)
    review_receipt = json.dumps(decision.to_receipt(), sort_keys=True)

    assert decision.blocked is True
    assert raw_phrase not in review_receipt
    assert "evidence_fingerprint:sha256:" in review_receipt


def test_failed_gate_finding_evidence_is_receipt_safe() -> None:
    raw_gate_name = "RAW_GATE_NAME_SHOULD_NOT_APPEAR"
    raw_gate_detail = "token=abc.def.ghi.jkl"
    run = _safe_run()
    receipt = run.to_receipt()
    receipt["safety_gates"][0] = {
        "name": raw_gate_name,
        "passed": False,
        "severity": "blocker",
        "detail": raw_gate_detail,
    }

    decision = AutonomousLabReviewer().review(receipt)
    review_receipt = json.dumps(decision.to_receipt(), sort_keys=True)

    assert decision.blocked is True
    assert raw_gate_name not in review_receipt
    assert raw_gate_detail not in review_receipt
    assert "evidence_fingerprint:sha256:" in review_receipt


def test_workspace_write_gate_is_blocked() -> None:
    run = _safe_run(materials=[_material(metadata={"requires_google_workspace_write": "true"})])
    decision = _review(run)

    assert decision.blocked is True
    assert "google_workspace_write_request" in _rule_ids(decision)


def test_missing_verification_blocks_when_targets_exist() -> None:
    run = _safe_run()
    plan = replace(run.simulation_plan, verification_commands=[])
    decision = _review(replace(run, simulation_plan=plan))

    assert decision.approved is False
    assert decision.blocked is True
    assert "missing_verification" in _rule_ids(decision)
    finding = next(
        finding for finding in decision.findings if finding.rule_id == "missing_verification"
    )
    assert finding.severity.value == "blocker"
