"""Frozen closed enum registry for Research OS v1.0.0."""

from __future__ import annotations

from enum import StrEnum
from typing import TypeVar


class RiskClass(StrEnum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


class Sensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED_OSINT = "restricted_osint"
    CLIENT_PII = "client_pii"


class ReviewState(StrEnum):
    UNREVIEWED = "unreviewed"
    MACHINE_CHECKED = "machine_checked"
    HUMAN_APPROVED = "human_approved"
    HUMAN_REJECTED = "human_rejected"
    SUPERSEDED = "superseded"


class PublicationState(StrEnum):
    GENERATED = "generated"
    STAGED = "staged"
    HUMAN_APPROVED = "human_approved"
    PUBLISHING = "publishing"
    DEPLOYED = "deployed"
    INDEXED_VERIFIED = "indexed_verified"


class VerificationState(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    STALE = "stale"


class AvailabilityState(StrEnum):
    ACTIVE = "active"
    CORRECTION_REQUIRED = "correction_required"
    WITHDRAWAL_REQUESTED = "withdrawal_requested"
    WITHDRAWN = "withdrawn"


class EvidenceStance(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXTUALIZES = "contextualizes"
    INCONCLUSIVE = "inconclusive"


class ClaimStatus(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INCONCLUSIVE = "inconclusive"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"


class WorkflowState(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_FOR_INPUT = "waiting_for_input"
    BLOCKED = "blocked"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QueueState(StrEnum):
    NEW = "new"
    TRIAGED = "triaged"
    ASSIGNED = "assigned"
    AWAITING_DECISION = "awaiting_decision"
    READY = "ready"
    CLOSED = "closed"


class ApprovalSubjectKind(StrEnum):
    DECISION_PACKET = "decision_packet"
    TOPIC_LOCK = "topic_lock"
    CREATIVE_LOCK = "creative_lock"
    MEDIA_SCRIPT_LOCK = "media_script_lock"
    MEDIA_SHOT_LOCK = "media_shot_lock"
    CONTENT_REVISION = "content_revision"
    ACTION_INTENT = "action_intent"


class ApprovalDecision(StrEnum):
    SELECT = "select"
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    REQUEST_EVIDENCE = "request_evidence"
    DEFER = "defer"


class ExecutionAttemptState(StrEnum):
    STARTED = "started"


class ExecutionTerminalOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class EffectStatus(StrEnum):
    CONFIRMED = "confirmed"
    NOT_OBSERVED = "not_observed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ReconciliationState(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    MISMATCH = "mismatch"
    NOT_APPLICABLE = "not_applicable"


class VerificationVerdict(StrEnum):
    PASS = "pass"
    PASS_WITH_LIMITS = "pass_with_limits"
    FAIL = "fail"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AttributionStrength(StrEnum):
    DIRECT = "direct"
    DETERMINISTIC = "deterministic"
    MODELED = "modeled"
    CORRELATIONAL = "correlational"
    UNATTRIBUTED = "unattributed"


class MetricResultState(StrEnum):
    MEASURED = "measured"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INVALIDATED = "invalidated"


class GateDisposition(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_APPLICABLE = "not_applicable"


class LockState(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    SUPERSEDED = "superseded"


class HandoffState(StrEnum):
    DRAFT = "draft"
    OPERATOR_CONFIRMED = "operator_confirmed"
    STALE = "stale"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class HandoffOutcome(StrEnum):
    CONTENT = "content"
    ACTION = "action"
    REQUEST_EVIDENCE = "request_evidence"
    DEFER = "defer"
    REJECT = "reject"


class OutcomeFamily(StrEnum):
    COMPLIANCE_PROTECTION = "compliance_protection"
    CLIENT_JOURNEY = "client_journey"
    REVENUE_PARTNERSHIPS = "revenue_partnerships"
    PRODUCT_SELF_SERVICE = "product_self_service"
    DECISION_INTELLIGENCE = "decision_intelligence"
    AUTHORITY_DEMAND = "authority_demand"
    TEAM_ENABLEMENT = "team_enablement"
    MEMORY_LEARNING = "memory_learning"
    PLATFORM_GOVERNANCE = "platform_governance"


_RISK_ORDER = {value: index for index, value in enumerate(RiskClass)}
_SENSITIVITY_ORDER = {value: index for index, value in enumerate(Sensitivity)}
_OrderedEnum = TypeVar("_OrderedEnum", RiskClass, Sensitivity)


def _maximum(values: tuple[_OrderedEnum, ...], order: dict[_OrderedEnum, int]) -> _OrderedEnum:
    if not values:
        raise ValueError("at least one classification value is required")
    return max(values, key=order.__getitem__)


def max_risk(*values: RiskClass) -> RiskClass:
    """Return the greatest risk class under green < amber < red."""

    return _maximum(values, _RISK_ORDER)


def max_sensitivity(*values: Sensitivity) -> Sensitivity:
    """Return the greatest sensitivity under the frozen five-level ordering."""

    return _maximum(values, _SENSITIVITY_ORDER)
