"""Evaluator tribunal for Autonomous Lab shadow experiments."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from backend.services.autonomous_lab.experiment_spec import ExperimentSpec
from backend.services.autonomous_lab.normalizer import NormalizedMaterialBatch
from backend.services.autonomous_lab.receipt_safety import contains_receipt_sensitive_value
from backend.services.autonomous_lab.sandbox_runner import SandboxCommandResult

EVALUATOR_CONTRACT_VERSION = "autonomous-lab-v1-evaluator"


class EvaluationVerdict(str, Enum):
    """Final tribunal verdict."""

    PASS = "pass"
    FAIL = "fail"
    NEEDS_REVIEW = "needs_review"


class EvaluationMetricStatus(str, Enum):
    """Status for one evaluator metric."""

    PASS = "pass"
    FAIL = "fail"
    PENDING = "pending"


@dataclass(frozen=True)
class EvaluationMetric:
    """One measured or pending criterion."""

    name: str
    status: EvaluationMetricStatus
    detail: str

    def to_receipt(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class LabEvaluationReport:
    """Receipt-safe evaluation output for the curator."""

    version: str
    report_id: str
    spec_id: str
    verdict: EvaluationVerdict
    metrics: tuple[EvaluationMetric, ...]
    promotion_eligible: bool
    manual_review_required: bool
    failure_count: int
    pending_count: int

    def to_receipt(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "report_id": self.report_id,
            "spec_id": self.spec_id,
            "verdict": self.verdict.value,
            "metrics": [metric.to_receipt() for metric in self.metrics],
            "promotion_eligible": self.promotion_eligible,
            "manual_review_required": self.manual_review_required,
            "failure_count": self.failure_count,
            "pending_count": self.pending_count,
        }


class AutonomousLabEvaluator:
    """Score a Lab spec against sandbox, execution, leakage, and novelty gates."""

    def evaluate(
        self,
        *,
        spec: ExperimentSpec,
        sandbox_results: tuple[SandboxCommandResult, ...] = (),
        normalized_batch: NormalizedMaterialBatch | None = None,
    ) -> LabEvaluationReport:
        """Return a compact tribunal report without running commands."""
        metrics = (
            _policy_metric(spec),
            _command_metric(spec),
            _sandbox_result_metric(sandbox_results),
            _receipt_safety_metric(spec, sandbox_results),
            _novelty_metric(normalized_batch),
        )
        failure_count = sum(
            metric.status is EvaluationMetricStatus.FAIL for metric in metrics
        )
        pending_count = sum(
            metric.status is EvaluationMetricStatus.PENDING for metric in metrics
        )
        if failure_count:
            verdict = EvaluationVerdict.FAIL
        elif pending_count:
            verdict = EvaluationVerdict.NEEDS_REVIEW
        else:
            verdict = EvaluationVerdict.PASS
        return LabEvaluationReport(
            version=EVALUATOR_CONTRACT_VERSION,
            report_id=f"{spec.spec_id}-eval",
            spec_id=spec.spec_id,
            verdict=verdict,
            metrics=metrics,
            promotion_eligible=verdict is EvaluationVerdict.PASS,
            manual_review_required=True,
            failure_count=failure_count,
            pending_count=pending_count,
        )


def _policy_metric(spec: ExperimentSpec) -> EvaluationMetric:
    policy = spec.sandbox_policy
    dangerous_allowed = any(
        bool(policy.get(key))
        for key in (
            "production_writes_allowed",
            "deploy_merge_push_allowed",
            "raw_data_persistence_allowed",
        )
    )
    if dangerous_allowed:
        return EvaluationMetric(
            "sandbox_policy",
            EvaluationMetricStatus.FAIL,
            "dangerous sandbox permission enabled",
        )
    return EvaluationMetric(
        "sandbox_policy",
        EvaluationMetricStatus.PASS,
        "prod writes, deploy, push, and raw persistence are blocked",
    )


def _command_metric(spec: ExperimentSpec) -> EvaluationMetric:
    if spec.rejected_command_count:
        return EvaluationMetric(
            "command_allowlist",
            EvaluationMetricStatus.FAIL,
            f"{spec.rejected_command_count} verification command(s) rejected",
        )
    if spec.accepted_command_count == 0:
        return EvaluationMetric(
            "command_allowlist",
            EvaluationMetricStatus.PENDING,
            "no executable verification command is available yet",
        )
    return EvaluationMetric(
        "command_allowlist",
        EvaluationMetricStatus.PASS,
        f"{spec.accepted_command_count} verification command(s) allowlisted",
    )


def _sandbox_result_metric(
    sandbox_results: tuple[SandboxCommandResult, ...],
) -> EvaluationMetric:
    if not sandbox_results:
        return EvaluationMetric(
            "sandbox_execution",
            EvaluationMetricStatus.PENDING,
            "shadow run has not executed commands",
        )
    if any((not result.allowed) or result.timed_out or result.returncode != 0 for result in sandbox_results):
        return EvaluationMetric(
            "sandbox_execution",
            EvaluationMetricStatus.FAIL,
            "one or more sandbox command results failed",
        )
    return EvaluationMetric(
        "sandbox_execution",
        EvaluationMetricStatus.PASS,
        "all sandbox command results passed",
    )


def _receipt_safety_metric(
    spec: ExperimentSpec,
    sandbox_results: tuple[SandboxCommandResult, ...],
) -> EvaluationMetric:
    payload = {
        "spec": spec.to_receipt(),
        "sandbox_results": [result.to_receipt() for result in sandbox_results],
    }
    if contains_receipt_sensitive_value(json.dumps(payload, sort_keys=True)):
        return EvaluationMetric(
            "receipt_safety",
            EvaluationMetricStatus.FAIL,
            "receipt payload contains sensitive-looking material",
        )
    return EvaluationMetric(
        "receipt_safety",
        EvaluationMetricStatus.PASS,
        "receipt payload is bounded and redacted",
    )


def _novelty_metric(batch: NormalizedMaterialBatch | None) -> EvaluationMetric:
    if batch is None or not batch.materials:
        return EvaluationMetric(
            "novelty",
            EvaluationMetricStatus.PENDING,
            "no normalized material batch supplied",
        )
    if batch.novelty_score < 0.5:
        return EvaluationMetric(
            "novelty",
            EvaluationMetricStatus.FAIL,
            "dedupe left too little unique signal",
        )
    return EvaluationMetric(
        "novelty",
        EvaluationMetricStatus.PASS,
        f"novelty_score={batch.novelty_score:.2f}",
    )


__all__ = [
    "EVALUATOR_CONTRACT_VERSION",
    "AutonomousLabEvaluator",
    "EvaluationMetric",
    "EvaluationMetricStatus",
    "EvaluationVerdict",
    "LabEvaluationReport",
]
