"""Experiment specification contract for Autonomous Lab candidates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from backend.services.autonomous_lab.command_policy import is_allowed_verification_command
from backend.services.autonomous_lab.planner import LabRun
from backend.services.autonomous_lab.sandbox_policy import SandboxPolicy, default_sandbox_policy

EXPERIMENT_SPEC_VERSION = "autonomous-lab-v1-experiment-spec"


class ExperimentRisk(str, Enum):
    """Operator-visible risk class for a Lab experiment."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MANUAL_ONLY = "manual_only"


@dataclass(frozen=True)
class ExperimentAcceptanceMetric:
    """One measurable acceptance criterion."""

    name: str
    gate: str
    threshold: str
    required: bool = True

    def to_receipt(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "gate": self.gate,
            "threshold": self.threshold,
            "required": self.required,
        }


@dataclass(frozen=True)
class ExperimentSpec:
    """Executable-in-principle, policy-bounded experiment plan."""

    version: str
    spec_id: str
    run_id: str
    objective_reference: str
    candidate_summary: str
    target_paths: tuple[str, ...]
    verification_commands: tuple[str, ...]
    accepted_command_count: int
    rejected_command_count: int
    sandbox_policy: dict[str, Any]
    acceptance_metrics: tuple[ExperimentAcceptanceMetric, ...]
    risk: ExperimentRisk
    rollback_plan: str
    manual_promotion_required: bool = True

    def to_receipt(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "spec_id": self.spec_id,
            "run_id": self.run_id,
            "objective_reference": self.objective_reference,
            "candidate_summary": self.candidate_summary,
            "target_paths": list(self.target_paths),
            "verification_commands": list(self.verification_commands),
            "accepted_command_count": self.accepted_command_count,
            "rejected_command_count": self.rejected_command_count,
            "sandbox_policy": self.sandbox_policy,
            "acceptance_metrics": [
                metric.to_receipt() for metric in self.acceptance_metrics
            ],
            "risk": self.risk.value,
            "rollback_plan": self.rollback_plan,
            "manual_promotion_required": self.manual_promotion_required,
        }


def build_experiment_spec(
    *,
    run: LabRun,
    candidate_summary: str,
    sandbox_policy: SandboxPolicy | None = None,
) -> ExperimentSpec:
    """Build a fail-closed experiment spec from an existing LabRun draft."""
    policy = sandbox_policy or default_sandbox_policy()
    commands = tuple(run.simulation_plan.verification_commands)
    accepted_commands = tuple(command for command in commands if is_allowed_verification_command(command))
    rejected_count = len(commands) - len(accepted_commands)
    return ExperimentSpec(
        version=EXPERIMENT_SPEC_VERSION,
        spec_id=f"{run.run_id}-spec",
        run_id=run.run_id,
        objective_reference=run.objective,
        candidate_summary=candidate_summary,
        target_paths=tuple(run.simulation_plan.target_paths),
        verification_commands=accepted_commands,
        accepted_command_count=len(accepted_commands),
        rejected_command_count=rejected_count,
        sandbox_policy=policy.to_receipt(),
        acceptance_metrics=_acceptance_metrics(),
        risk=_risk_for_run(run=run, rejected_command_count=rejected_count),
        rollback_plan="discard worktree patch; keep receipt and failure taxonomy only",
        manual_promotion_required=True,
    )


def _acceptance_metrics() -> tuple[ExperimentAcceptanceMetric, ...]:
    return (
        ExperimentAcceptanceMetric(
            name="sandbox_policy",
            gate="no prod writes, no deploy, no raw persistence",
            threshold="all policy booleans remain false where dangerous",
        ),
        ExperimentAcceptanceMetric(
            name="verification",
            gate="allowlisted commands only",
            threshold="all executed commands return zero or produce reviewed failure report",
        ),
        ExperimentAcceptanceMetric(
            name="receipt_safety",
            gate="Law 2",
            threshold="no raw text, secrets, emails, or private paths in receipts",
        ),
        ExperimentAcceptanceMetric(
            name="operator_gate",
            gate="manual curator decision",
            threshold="promotion_allowed is false until explicit operator approval",
        ),
    )


def _risk_for_run(*, run: LabRun, rejected_command_count: int) -> ExperimentRisk:
    if run.has_blockers():
        return ExperimentRisk.HIGH
    if rejected_command_count > 0:
        return ExperimentRisk.MEDIUM
    if not run.simulation_plan.target_paths:
        return ExperimentRisk.MANUAL_ONLY
    return ExperimentRisk.LOW


__all__ = [
    "EXPERIMENT_SPEC_VERSION",
    "ExperimentAcceptanceMetric",
    "ExperimentRisk",
    "ExperimentSpec",
    "build_experiment_spec",
]
