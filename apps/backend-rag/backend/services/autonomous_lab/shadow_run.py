"""End-to-end shadow run assembly for the Autonomous Lab control room."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.services.autonomous_lab.curator import (
    AutonomousLabCurator,
    CuratorDecisionRecord,
)
from backend.services.autonomous_lab.evaluator import (
    AutonomousLabEvaluator,
    LabEvaluationReport,
)
from backend.services.autonomous_lab.experiment_spec import (
    ExperimentSpec,
    build_experiment_spec,
)
from backend.services.autonomous_lab.normalizer import (
    NormalizedMaterialBatch,
    normalize_and_dedupe_materials,
)
from backend.services.autonomous_lab.planner import AutonomousLabPlanner, LabRun
from backend.services.autonomous_lab.receipt_safety import (
    receipt_safe_evidence,
    safe_sha256_fingerprint,
)
from backend.services.autonomous_lab.source_adapters import (
    WatchtowerTick,
    build_shadow_watchtower_tick,
)

SHADOW_RUN_CONTRACT_VERSION = "autonomous-lab-v1-shadow-run"
DEFAULT_SHADOW_OBJECTIVE = (
    "Autonomous Lab continuously studies AI research and software frontier, "
    "then proposes protected Nuzantara implementations."
)
DEFAULT_SHADOW_TARGET_PATHS = (
    "apps/backend-rag/backend/services/autonomous_lab",
    "apps/admin-dashboard/app/autonomous-lab",
)


@dataclass(frozen=True)
class LabTimelineEvent:
    """One visible shadow-run event for the control room."""

    order: int
    stage: str
    status: str
    summary: str
    artifact: str
    gate: str

    def to_receipt(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "stage": self.stage,
            "status": self.status,
            "summary": self.summary,
            "artifact": self.artifact,
            "gate": self.gate,
        }


@dataclass(frozen=True)
class LabCandidateProposal:
    """Research-to-code candidate generated from shadow materials."""

    candidate_id: str
    title: str
    implementation_area: str
    target_paths: tuple[str, ...]
    technique_tags: tuple[str, ...]
    source_signal_ids: tuple[str, ...]

    def to_receipt(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "title": receipt_safe_evidence(self.title, force_fingerprint=True),
            "implementation_area": self.implementation_area,
            "target_paths": list(self.target_paths),
            "technique_tags": list(self.technique_tags),
            "source_signal_ids": list(self.source_signal_ids),
        }


@dataclass(frozen=True)
class LabShadowRun:
    """Read-only proof that the Lab pipeline composes end to end."""

    version: str
    run_id: str
    created_at: datetime
    watch_tick: WatchtowerTick
    normalized_batch: NormalizedMaterialBatch
    run: LabRun
    candidate: LabCandidateProposal
    experiment_spec: ExperimentSpec
    evaluation_report: LabEvaluationReport
    curator_decision: CuratorDecisionRecord
    timeline: tuple[LabTimelineEvent, ...]
    execution_allowed: bool = False
    external_calls: int = 0

    def to_receipt(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "created_at": self.created_at.isoformat(),
            "watch_tick": self.watch_tick.to_receipt(),
            "normalized_batch": self.normalized_batch.to_receipt(),
            "run": self.run.to_receipt(),
            "candidate": self.candidate.to_receipt(),
            "experiment_spec": self.experiment_spec.to_receipt(),
            "evaluation_report": self.evaluation_report.to_receipt(),
            "curator_decision": self.curator_decision.to_receipt(),
            "timeline": [event.to_receipt() for event in self.timeline],
            "execution_allowed": self.execution_allowed,
            "external_calls": self.external_calls,
        }


def build_shadow_run(
    *,
    objective: str = DEFAULT_SHADOW_OBJECTIVE,
    target_paths: tuple[str, ...] = DEFAULT_SHADOW_TARGET_PATHS,
    task_id: str | None = None,
    created_at: datetime | None = None,
) -> LabShadowRun:
    """Build an end-to-end shadow run without side effects or network calls."""
    now = created_at or datetime.now(tz=timezone.utc)
    run_id = task_id or f"shadow-{safe_sha256_fingerprint(objective, 12)}"
    watch_tick = build_shadow_watchtower_tick(objective=objective, captured_at=now)
    materials = watch_tick.materials()
    planner = AutonomousLabPlanner(worktree_lane="ops")
    normalized_batch = normalize_and_dedupe_materials(
        materials=materials,
        planner=planner,
        created_at=now,
    )
    run = planner.draft_run(
        objective=objective,
        materials=materials,
        target_paths=list(target_paths),
        task_id=run_id,
        created_at=now,
    )
    candidate = _candidate_from_run(run=run, watch_tick=watch_tick)
    spec = build_experiment_spec(
        run=run,
        candidate_summary=candidate.implementation_area,
    )
    evaluation = AutonomousLabEvaluator().evaluate(
        spec=spec,
        normalized_batch=normalized_batch,
    )
    curator_decision = AutonomousLabCurator().propose(evaluation)
    return LabShadowRun(
        version=SHADOW_RUN_CONTRACT_VERSION,
        run_id=run_id,
        created_at=now,
        watch_tick=watch_tick,
        normalized_batch=normalized_batch,
        run=run,
        candidate=candidate,
        experiment_spec=spec,
        evaluation_report=evaluation,
        curator_decision=curator_decision,
        timeline=_timeline(
            watch_tick=watch_tick,
            batch=normalized_batch,
            run=run,
            spec=spec,
            evaluation=evaluation,
            curator_decision=curator_decision,
        ),
    )


def _candidate_from_run(*, run: LabRun, watch_tick: WatchtowerTick) -> LabCandidateProposal:
    tags = tuple(sorted({tag for material in run.materials for tag in material.tags}))
    areas = sorted({signal.implementation_area for signal in watch_tick.signals})
    implementation_area = " + ".join(areas[:3]) if areas else "autonomous-lab"
    return LabCandidateProposal(
        candidate_id=f"{run.run_id}-candidate",
        title=f"Protected implementation candidate for {implementation_area}",
        implementation_area=implementation_area,
        target_paths=tuple(run.simulation_plan.target_paths),
        technique_tags=tags,
        source_signal_ids=tuple(signal.signal_id for signal in watch_tick.signals),
    )


def _timeline(
    *,
    watch_tick: WatchtowerTick,
    batch: NormalizedMaterialBatch,
    run: LabRun,
    spec: ExperimentSpec,
    evaluation: LabEvaluationReport,
    curator_decision: CuratorDecisionRecord,
) -> tuple[LabTimelineEvent, ...]:
    return (
        LabTimelineEvent(
            1,
            "watch",
            "checkpointed",
            f"{len(watch_tick.signals)} frontier signal(s), external_calls=0",
            "WatchtowerTick",
            "freshness + novelty",
        ),
        LabTimelineEvent(
            2,
            "normalize",
            "checkpointed",
            f"{batch.cluster_count} cluster(s), duplicates={batch.duplicate_count}",
            "NormalizedMaterialBatch",
            "no raw receipt",
        ),
        LabTimelineEvent(
            3,
            "compose",
            "checkpointed",
            f"{len(run.hypotheses)} hypothesis item(s)",
            "LabRun",
            "evidence quorum",
        ),
        LabTimelineEvent(
            4,
            "experiment",
            "planned",
            f"{spec.accepted_command_count} allowed command(s), {spec.rejected_command_count} rejected",
            "ExperimentSpec",
            "sandbox policy",
        ),
        LabTimelineEvent(
            5,
            "verify",
            evaluation.verdict.value,
            f"failures={evaluation.failure_count}, pending={evaluation.pending_count}",
            "EvaluationReport",
            "tribunal",
        ),
        LabTimelineEvent(
            6,
            "curate",
            "manual",
            curator_decision.next_action,
            "CuratorDecision",
            "operator decision",
        ),
    )


__all__ = [
    "DEFAULT_SHADOW_OBJECTIVE",
    "DEFAULT_SHADOW_TARGET_PATHS",
    "SHADOW_RUN_CONTRACT_VERSION",
    "LabCandidateProposal",
    "LabShadowRun",
    "LabTimelineEvent",
    "build_shadow_run",
]
