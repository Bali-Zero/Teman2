from __future__ import annotations

from backend.services.autonomous_lab.experiment_spec import build_experiment_spec
from backend.services.autonomous_lab.planner import AutonomousLabPlanner
from backend.services.autonomous_lab.source_adapters import build_shadow_watchtower_tick


def test_experiment_spec_keeps_only_allowlisted_verification_commands() -> None:
    tick = build_shadow_watchtower_tick(objective="build lab evaluator")
    run = AutonomousLabPlanner().draft_run(
        objective="build lab evaluator",
        materials=tick.materials(),
        target_paths=[
            "apps/backend-rag/backend/services/autonomous_lab/evaluator.py",
            "apps/mouth/components/example.tsx",
        ],
        task_id="spec-test",
    )

    spec = build_experiment_spec(run=run, candidate_summary="evaluator")
    receipt = spec.to_receipt()

    assert receipt["accepted_command_count"] == 1
    assert receipt["rejected_command_count"] == 1
    assert receipt["manual_promotion_required"] is True
    assert "cd apps/mouth && npm run lint" not in receipt["verification_commands"]
    assert receipt["sandbox_policy"]["deploy_merge_push_allowed"] is False
