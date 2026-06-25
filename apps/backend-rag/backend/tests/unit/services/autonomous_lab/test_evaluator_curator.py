from __future__ import annotations

from backend.services.autonomous_lab.curator import AutonomousLabCurator
from backend.services.autonomous_lab.evaluator import (
    AutonomousLabEvaluator,
    EvaluationVerdict,
)
from backend.services.autonomous_lab.experiment_spec import build_experiment_spec
from backend.services.autonomous_lab.normalizer import normalize_and_dedupe_materials
from backend.services.autonomous_lab.planner import AutonomousLabPlanner
from backend.services.autonomous_lab.source_adapters import build_shadow_watchtower_tick


def test_evaluator_marks_shadow_run_pending_until_sandbox_results_exist() -> None:
    tick = build_shadow_watchtower_tick(objective="evaluate protected lab candidate")
    planner = AutonomousLabPlanner()
    run = planner.draft_run(
        objective="evaluate protected lab candidate",
        materials=tick.materials(),
        target_paths=["apps/backend-rag/backend/services/autonomous_lab/evaluator.py"],
        task_id="eval-test",
    )
    batch = normalize_and_dedupe_materials(materials=tick.materials(), planner=planner)
    spec = build_experiment_spec(run=run, candidate_summary="tribunal")

    report = AutonomousLabEvaluator().evaluate(spec=spec, normalized_batch=batch)
    decision = AutonomousLabCurator().propose(report)

    assert report.verdict is EvaluationVerdict.NEEDS_REVIEW
    assert report.failure_count == 0
    assert report.pending_count == 1
    assert report.promotion_eligible is False
    assert decision.decision.value == "request_changes"
    assert decision.promotion_allowed is False
