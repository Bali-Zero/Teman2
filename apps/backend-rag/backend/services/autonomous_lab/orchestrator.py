"""Deterministic, side-effect-free orchestration for the autonomous lab."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from backend.services.autonomous_lab.operational_plan import (
    LabOperationalPlan,
    default_operational_plan,
)
from backend.services.autonomous_lab.planner import (
    AutonomousLabPlanner,
    GateSeverity,
    LabRun,
    ResearchMaterial,
)
from backend.services.autonomous_lab.receipt_safety import (
    contains_receipt_sensitive_value,
    receipt_safe_evidence,
    redacted_receipt_value,
)
from backend.services.autonomous_lab.reviewer import AutonomousLabReviewer


class FleetStageStatus(str, Enum):
    """Receipt-safe status for an in-process fleet stage."""

    COMPLETED = "completed"
    PLANNED = "planned"
    BLOCKED = "blocked"


class FindingSeverity(str, Enum):
    """Review severity emitted by bounded orchestration checks."""

    BLOCKER = "blocker"
    WARNING = "warning"
    INFO = "info"


@dataclass(frozen=True)
class OrchestrationBounds:
    """Hard local bounds for deterministic orchestration."""

    max_materials: int = 20
    max_target_paths: int = 40
    max_planned_commands: int = 12
    max_material_text_chars: int = 20_000
    max_total_material_text_chars: int = 100_000


@dataclass(frozen=True)
class AgentFleetMember:
    """One deterministic in-process role in the lab fleet."""

    order: int
    stage: str
    role: str
    responsibility: str

    def to_receipt(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "stage": self.stage,
            "role": self.role,
            "responsibility": self.responsibility,
        }


@dataclass(frozen=True)
class FleetStageResult:
    """Receipt-safe result emitted by one fleet role."""

    order: int
    stage: str
    role: str
    status: FleetStageStatus
    summary: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    planned_only_commands: list[str] = field(default_factory=list)
    executed: bool = False
    external_calls: int = 0

    def to_receipt(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "stage": self.stage,
            "role": self.role,
            "status": self.status.value,
            "summary": self.summary,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "blockers": self.blockers,
            "planned_only_commands": self.planned_only_commands,
            "executed": self.executed,
            "external_calls": self.external_calls,
        }


@dataclass(frozen=True)
class ReviewFinding:
    """Receipt-safe reviewer output."""

    code: str
    severity: FindingSeverity
    detail: str

    def to_receipt(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ExecutionPolicy:
    """Explicit proof that orchestration did not run side-effecting work."""

    shell_execution_allowed: bool = False
    external_calls_allowed: bool = False
    deploy_allowed: bool = False
    merge_allowed: bool = False
    shell_commands_executed: tuple[str, ...] = ()
    deploys_triggered: tuple[str, ...] = ()
    merges_triggered: tuple[str, ...] = ()
    external_calls_made: tuple[str, ...] = ()

    def to_receipt(self) -> dict[str, Any]:
        return {
            "shell_execution_allowed": self.shell_execution_allowed,
            "external_calls_allowed": self.external_calls_allowed,
            "deploy_allowed": self.deploy_allowed,
            "merge_allowed": self.merge_allowed,
            "shell_commands_executed": list(self.shell_commands_executed),
            "deploys_triggered": list(self.deploys_triggered),
            "merges_triggered": list(self.merges_triggered),
            "external_calls_made": list(self.external_calls_made),
        }


@dataclass(frozen=True)
class LabOrchestrationResult:
    """Receipt-safe output of a bounded autonomous lab fleet run."""

    run: LabRun
    fleet: tuple[AgentFleetMember, ...]
    stages: list[FleetStageResult]
    review_findings: list[ReviewFinding]
    execution_policy: ExecutionPolicy
    operational_plan: LabOperationalPlan = field(default_factory=default_operational_plan)

    @property
    def planned_only_commands(self) -> list[str]:
        return [
            self.run.simulation_plan.worktree_command,
            *self.run.simulation_plan.verification_commands,
        ]

    @property
    def failed_blockers(self) -> list[str]:
        gate_blockers = [
            gate.name
            for gate in self.run.safety_gates
            if gate.severity == GateSeverity.BLOCKER and not gate.passed
        ]
        finding_blockers = [
            finding.code
            for finding in self.review_findings
            if finding.severity == FindingSeverity.BLOCKER
        ]
        return [*gate_blockers, *finding_blockers]

    @property
    def blocked(self) -> bool:
        return bool(self.failed_blockers)

    def to_receipt(self) -> dict[str, Any]:
        payload = {
            "run": self.run.to_receipt(),
            "agent_fleet": [member.to_receipt() for member in self.fleet],
            "stage_results": [stage.to_receipt() for stage in self.stages],
            "review_findings": [finding.to_receipt() for finding in self.review_findings],
            "execution_policy": self.execution_policy.to_receipt(),
            "operational_plan": self.operational_plan.to_receipt(),
            "planned_only_commands": self.planned_only_commands,
            "failed_blockers": self.failed_blockers,
            "blocked": self.blocked,
            "receipt_safe": True,
        }
        return _redact_receipt_unsafe_values(payload)


DEFAULT_AGENT_FLEET: tuple[AgentFleetMember, ...] = (
    AgentFleetMember(
        1,
        "intake",
        "intake_normalizer",
        "derive receipt-safe material summaries and fingerprints",
    ),
    AgentFleetMember(
        2,
        "compose",
        "hypothesis_composer",
        "compose deterministic hypotheses from normalized evidence",
    ),
    AgentFleetMember(
        3,
        "context",
        "context_builder",
        "build an isolated prod-like simulation plan without executing it",
    ),
    AgentFleetMember(
        4,
        "review",
        "reviewer",
        "propagate blockers and reject unsafe planned commands",
    ),
    AgentFleetMember(
        5,
        "verify",
        "verification_planner",
        "surface verification commands as planned-only receipts",
    ),
)


class AutonomousLabOrchestrator:
    """Run a bounded deterministic in-process agent fleet for lab drafts."""

    def __init__(
        self,
        *,
        planner: AutonomousLabPlanner | None = None,
        fleet: tuple[AgentFleetMember, ...] = DEFAULT_AGENT_FLEET,
        bounds: OrchestrationBounds | None = None,
    ) -> None:
        self._planner = planner or AutonomousLabPlanner()
        self._fleet = fleet
        self._bounds = bounds or OrchestrationBounds()
        self._reviewer = AutonomousLabReviewer()

    def orchestrate(
        self,
        *,
        objective: str,
        materials: list[ResearchMaterial],
        target_paths: list[str],
        task_id: str,
        created_at: datetime | None = None,
    ) -> LabOrchestrationResult:
        """Draft and review a lab run without executing commands or external calls."""
        preflight_findings = self._preflight_input_bounds(
            materials=materials,
            target_paths=target_paths,
        )
        if preflight_findings:
            raise ValueError("; ".join(finding.detail for finding in preflight_findings))
        run = self._planner.draft_run(
            objective=objective,
            materials=materials,
            target_paths=target_paths,
            task_id=task_id,
            created_at=created_at,
        )
        review_findings = self._review(run=run, material_count=len(materials))
        stages = self._run_fleet(run=run, review_findings=review_findings)
        return LabOrchestrationResult(
            run=run,
            fleet=self._fleet,
            stages=stages,
            review_findings=review_findings,
            execution_policy=ExecutionPolicy(),
        )

    def _preflight_input_bounds(
        self,
        *,
        materials: list[ResearchMaterial],
        target_paths: list[str],
    ) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        if len(materials) > self._bounds.max_materials:
            findings.append(
                ReviewFinding(
                    "material_bound_exceeded",
                    FindingSeverity.BLOCKER,
                    f"material count {len(materials)} exceeds {self._bounds.max_materials}",
                )
            )
        if len(target_paths) > self._bounds.max_target_paths:
            findings.append(
                ReviewFinding(
                    "target_path_bound_exceeded",
                    FindingSeverity.BLOCKER,
                    f"target path count {len(target_paths)} exceeds {self._bounds.max_target_paths}",
                )
            )

        total_text_chars = 0
        for material in materials:
            material_text_chars = len(material.text)
            total_text_chars += material_text_chars
            if material_text_chars > self._bounds.max_material_text_chars:
                material_ref = receipt_safe_evidence(material.material_id)
                findings.append(
                    ReviewFinding(
                        "material_text_bound_exceeded",
                        FindingSeverity.BLOCKER,
                        (
                            f"material {material_ref} text length {material_text_chars} "
                            f"exceeds {self._bounds.max_material_text_chars}"
                        ),
                    )
                )
        if total_text_chars > self._bounds.max_total_material_text_chars:
            findings.append(
                ReviewFinding(
                    "total_material_text_bound_exceeded",
                    FindingSeverity.BLOCKER,
                    (
                        f"total material text length {total_text_chars} exceeds "
                        f"{self._bounds.max_total_material_text_chars}"
                    ),
                )
            )
        return findings

    def _run_fleet(
        self,
        *,
        run: LabRun,
        review_findings: list[ReviewFinding],
    ) -> list[FleetStageResult]:
        failed_blockers = [
            gate.name
            for gate in run.safety_gates
            if gate.severity == GateSeverity.BLOCKER and not gate.passed
        ]
        review_blockers = [
            finding.code
            for finding in review_findings
            if finding.severity == FindingSeverity.BLOCKER
        ]
        blocked = [*failed_blockers, *review_blockers]

        return [
            FleetStageResult(
                order=1,
                stage="intake",
                role="intake_normalizer",
                status=FleetStageStatus.BLOCKED
                if "materials_present" in failed_blockers
                else FleetStageStatus.COMPLETED,
                summary=f"normalized {len(run.materials)} material envelope(s)",
                inputs=[material.material_id for material in run.materials],
                outputs=[material.content_fingerprint for material in run.materials],
                blockers=["materials_present"] if "materials_present" in failed_blockers else [],
            ),
            FleetStageResult(
                order=2,
                stage="compose",
                role="hypothesis_composer",
                status=FleetStageStatus.COMPLETED,
                summary=f"composed {len(run.hypotheses)} deterministic hypothesis item(s)",
                inputs=[material.material_id for material in run.materials],
                outputs=[f"hypothesis:{index + 1}" for index, _ in enumerate(run.hypotheses)],
            ),
            FleetStageResult(
                order=3,
                stage="context",
                role="context_builder",
                status=FleetStageStatus.PLANNED,
                summary=(
                    f"planned isolated context for {len(run.simulation_plan.target_paths)} "
                    "target path(s)"
                ),
                inputs=run.simulation_plan.target_paths,
                outputs=list(run.simulation_plan.context_reconstruction),
                planned_only_commands=[run.simulation_plan.worktree_command],
            ),
            FleetStageResult(
                order=4,
                stage="review",
                role="reviewer",
                status=FleetStageStatus.BLOCKED if blocked else FleetStageStatus.COMPLETED,
                summary=f"reviewed {len(run.safety_gates)} planner gate(s)",
                inputs=[gate.name for gate in run.safety_gates],
                outputs=[finding.code for finding in review_findings],
                blockers=blocked,
            ),
            FleetStageResult(
                order=5,
                stage="verify",
                role="verification_planner",
                status=FleetStageStatus.BLOCKED if blocked else FleetStageStatus.PLANNED,
                summary=(
                    f"planned {len(run.simulation_plan.verification_commands)} "
                    "verification command(s) without execution"
                ),
                inputs=run.simulation_plan.target_paths,
                outputs=["planned_only_verification"],
                blockers=blocked,
                planned_only_commands=list(run.simulation_plan.verification_commands),
            ),
        ]

    def _review(self, *, run: LabRun, material_count: int) -> list[ReviewFinding]:
        findings: list[ReviewFinding] = []
        planned_commands = [
            run.simulation_plan.worktree_command,
            *run.simulation_plan.verification_commands,
        ]

        if material_count > self._bounds.max_materials:
            findings.append(
                ReviewFinding(
                    "material_bound_exceeded",
                    FindingSeverity.BLOCKER,
                    f"material count {material_count} exceeds {self._bounds.max_materials}",
                )
            )
        if len(run.simulation_plan.target_paths) > self._bounds.max_target_paths:
            findings.append(
                ReviewFinding(
                    "target_path_bound_exceeded",
                    FindingSeverity.BLOCKER,
                    (
                        f"target path count {len(run.simulation_plan.target_paths)} "
                        f"exceeds {self._bounds.max_target_paths}"
                    ),
                )
            )
        if len(planned_commands) > self._bounds.max_planned_commands:
            findings.append(
                ReviewFinding(
                    "planned_command_bound_exceeded",
                    FindingSeverity.BLOCKER,
                    (
                        f"planned command count {len(planned_commands)} "
                        f"exceeds {self._bounds.max_planned_commands}"
                    ),
                )
            )

        decision = self._reviewer.review(run)
        findings.extend(
            ReviewFinding(
                finding.rule_id,
                FindingSeverity(finding.severity.value),
                finding.message,
            )
            for finding in decision.findings
        )
        if not findings:
            findings.append(
                ReviewFinding(
                    "bounded_no_side_effects",
                    FindingSeverity.INFO,
                    "orchestrator returns planned-only commands and executes none",
                )
            )
        return findings


def _redact_receipt_unsafe_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact_receipt_unsafe_values(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_redact_receipt_unsafe_values(child) for child in value]
    if isinstance(value, str) and _is_receipt_unsafe_value(value):
        return _redacted_receipt_value(value)
    return value


def _is_receipt_unsafe_value(value: str) -> bool:
    return contains_receipt_sensitive_value(value)


def _redacted_receipt_value(value: str) -> str:
    return redacted_receipt_value(value)
