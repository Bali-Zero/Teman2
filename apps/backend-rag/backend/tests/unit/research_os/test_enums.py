from __future__ import annotations

import pytest
from research_os.enums import (
    ApprovalDecision,
    ApprovalSubjectKind,
    AttributionStrength,
    AvailabilityState,
    ClaimStatus,
    EffectStatus,
    EvidenceStance,
    ExecutionAttemptState,
    ExecutionTerminalOutcome,
    GateDisposition,
    HandoffOutcome,
    HandoffState,
    LockState,
    MetricResultState,
    OutcomeFamily,
    PublicationState,
    QueueState,
    ReconciliationState,
    ReviewState,
    RiskClass,
    Sensitivity,
    VerificationState,
    VerificationVerdict,
    WorkflowState,
    max_risk,
    max_sensitivity,
)

EXPECTED_ENUM_VALUES = {
    RiskClass: ["green", "amber", "red"],
    Sensitivity: ["public", "internal", "confidential", "restricted_osint", "client_pii"],
    ReviewState: [
        "unreviewed",
        "machine_checked",
        "human_approved",
        "human_rejected",
        "superseded",
    ],
    PublicationState: [
        "generated",
        "staged",
        "human_approved",
        "publishing",
        "deployed",
        "indexed_verified",
    ],
    VerificationState: ["unverified", "verified", "stale"],
    AvailabilityState: ["active", "correction_required", "withdrawal_requested", "withdrawn"],
    EvidenceStance: ["supports", "contradicts", "contextualizes", "inconclusive"],
    ClaimStatus: ["supported", "contradicted", "inconclusive", "superseded", "expired"],
    WorkflowState: [
        "created",
        "running",
        "waiting_for_input",
        "blocked",
        "succeeded",
        "failed",
        "cancelled",
    ],
    QueueState: ["new", "triaged", "assigned", "awaiting_decision", "ready", "closed"],
    ApprovalSubjectKind: [
        "decision_packet",
        "topic_lock",
        "creative_lock",
        "media_script_lock",
        "media_shot_lock",
        "content_revision",
        "action_intent",
    ],
    ApprovalDecision: [
        "select",
        "approve",
        "reject",
        "request_changes",
        "request_evidence",
        "defer",
    ],
    ExecutionAttemptState: ["started"],
    ExecutionTerminalOutcome: ["succeeded", "failed", "cancelled", "unknown"],
    EffectStatus: ["confirmed", "not_observed", "failed", "unknown"],
    ReconciliationState: ["pending", "confirmed", "mismatch", "not_applicable"],
    VerificationVerdict: ["pass", "pass_with_limits", "fail", "insufficient_evidence"],
    AttributionStrength: ["direct", "deterministic", "modeled", "correlational", "unattributed"],
    MetricResultState: ["measured", "insufficient_evidence", "invalidated"],
    GateDisposition: ["pass", "fail", "insufficient_evidence", "not_applicable"],
    LockState: ["current", "stale", "superseded"],
    HandoffState: ["draft", "operator_confirmed", "stale", "superseded", "rejected"],
    HandoffOutcome: ["content", "action", "request_evidence", "defer", "reject"],
    OutcomeFamily: [
        "compliance_protection",
        "client_journey",
        "revenue_partnerships",
        "product_self_service",
        "decision_intelligence",
        "authority_demand",
        "team_enablement",
        "memory_learning",
        "platform_governance",
    ],
}


@pytest.mark.parametrize(("enum_type", "expected"), EXPECTED_ENUM_VALUES.items())
def test_frozen_enum_registry_is_verbatim(enum_type: object, expected: list[str]) -> None:
    assert [member.value for member in enum_type] == expected  # type: ignore[attr-defined]


def test_closed_enums_reject_unknown_values() -> None:
    with pytest.raises(ValueError):
        RiskClass("yellow")
    with pytest.raises(ValueError):
        Sensitivity("secret")


def test_classification_axes_compute_component_wise_maximum() -> None:
    assert max_risk(RiskClass.GREEN, RiskClass.RED, RiskClass.AMBER) is RiskClass.RED
    assert max_sensitivity(Sensitivity.PUBLIC, Sensitivity.CLIENT_PII) is Sensitivity.CLIENT_PII
