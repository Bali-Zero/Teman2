"""Manual curator gate for Autonomous Lab evaluator reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.services.autonomous_lab.evaluator import EvaluationVerdict, LabEvaluationReport
from backend.services.autonomous_lab.runtime_contracts import CuratorDecision

CURATOR_CONTRACT_VERSION = "autonomous-lab-v1-curator"


@dataclass(frozen=True)
class CuratorAction:
    """One operator action exposed by the curator gate."""

    decision: CuratorDecision
    label: str
    description: str

    def to_receipt(self) -> dict[str, str]:
        return {
            "decision": self.decision.value,
            "label": self.label,
            "description": self.description,
        }


@dataclass(frozen=True)
class CuratorDecisionRecord:
    """Receipt-safe curator recommendation; promotion remains manual."""

    version: str
    decision_id: str
    report_id: str
    decision: CuratorDecision
    promotion_allowed: bool
    operator_required: bool
    next_action: str
    reason_reference: str
    allowed_actions: tuple[CuratorAction, ...]

    def to_receipt(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "decision_id": self.decision_id,
            "report_id": self.report_id,
            "decision": self.decision.value,
            "promotion_allowed": self.promotion_allowed,
            "operator_required": self.operator_required,
            "next_action": self.next_action,
            "reason_reference": self.reason_reference,
            "allowed_actions": [action.to_receipt() for action in self.allowed_actions],
        }


class AutonomousLabCurator:
    """Convert tribunal reports into explicit manual-gate recommendations."""

    def propose(self, report: LabEvaluationReport) -> CuratorDecisionRecord:
        """Return the next curator decision recommendation."""
        decision, next_action, reason = _decision_for_report(report)
        return CuratorDecisionRecord(
            version=CURATOR_CONTRACT_VERSION,
            decision_id=f"{report.report_id}-curator",
            report_id=report.report_id,
            decision=decision,
            promotion_allowed=False,
            operator_required=True,
            next_action=next_action,
            reason_reference=reason,
            allowed_actions=default_curator_actions(),
        )


def default_curator_actions() -> tuple[CuratorAction, ...]:
    """Return the manual decisions supported by v1."""
    return (
        CuratorAction(
            CuratorDecision.APPROVE,
            "Approve",
            "allow a human-reviewed patch branch to continue toward normal PR workflow",
        ),
        CuratorAction(
            CuratorDecision.REQUEST_CHANGES,
            "Request changes",
            "send the candidate back to experiment with a bounded failure note",
        ),
        CuratorAction(
            CuratorDecision.REJECT,
            "Reject",
            "archive the candidate as unsuitable or unsafe",
        ),
        CuratorAction(
            CuratorDecision.CANCEL,
            "Cancel",
            "stop the run without learning-library promotion",
        ),
    )


def _decision_for_report(
    report: LabEvaluationReport,
) -> tuple[CuratorDecision, str, str]:
    if report.verdict is EvaluationVerdict.FAIL:
        return (
            CuratorDecision.REJECT,
            "archive failure taxonomy and do not generate patch",
            "evaluator_verdict:fail",
        )
    if report.verdict is EvaluationVerdict.NEEDS_REVIEW:
        return (
            CuratorDecision.REQUEST_CHANGES,
            "execute allowed sandbox checks or add missing evidence",
            "evaluator_verdict:needs_review",
        )
    return (
        CuratorDecision.APPROVE,
        "operator can move the reviewed candidate into normal PR workflow",
        "evaluator_verdict:pass_manual_gate_required",
    )


__all__ = [
    "CURATOR_CONTRACT_VERSION",
    "AutonomousLabCurator",
    "CuratorAction",
    "CuratorDecisionRecord",
    "default_curator_actions",
]
