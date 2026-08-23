"""Shared strict primitives from frozen CONTRACTS.md section 3."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    WithJsonSchema,
    model_validator,
)
from pydantic_core import PydanticCustomError

from research_os.enums import RiskClass, Sensitivity
from research_os.hashing import SHA256_HEX_PATTERN
from research_os.version import SemanticVersion

_REVERSE_DNS_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+"
    r"[a-z](?:[a-z0-9-]*[a-z0-9])?$"
)
_REGISTERED_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9][a-z0-9_-]*)+$")
_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_-]*(?:[.-][a-z0-9_-]+)*$")
_UTC_OFFSET_PATTERN = r"(?:Z|\+00:00)$"

# Frozen union of the canonical field vocabulary in CONTRACTS.md for
# research-os/v1.0.0. Extensions may add domain data, but cannot smuggle a
# core field or the explicitly forbidden revocation reversal verb at any depth.
V1_RESERVED_EXTENSION_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "action_intent_id",
        "action_intent_ref",
        "action_item_family_id",
        "action_item_id",
        "action_item_ref",
        "action_type",
        "actor_or_executor",
        "actor_ref",
        "after_hash",
        "alternatives",
        "angle",
        "approval_receipt_id",
        "approval_receipt_ref",
        "arguments_hash",
        "arguments_ref",
        "artifact_refs",
        "assets",
        "assistant_producer",
        "attempt_number",
        "audience",
        "audio",
        "authority",
        "authority_required",
        "authorized_effects",
        "availability",
        "baseline",
        "before_hash",
        "bindings",
        "campaign_id",
        "canonical_event_ref",
        "channel_intent",
        "channel_plan",
        "checks",
        "claim_family_id",
        "claim_id",
        "claim_refs",
        "classification",
        "close_reason",
        "cohort",
        "conductor_handoff_family_id",
        "conductor_handoff_id",
        "confidence",
        "considered_options",
        "content_object_family_id",
        "content_object_id",
        "content_object_ref",
        "context",
        "contract_version",
        "cost",
        "created_at",
        "creative_lock_family_id",
        "creative_lock_id",
        "creative_lock_ref",
        "criteria_version",
        "current_intent_ref",
        "decision",
        "decision_packet_family_id",
        "decision_packet_id",
        "decision_packet_ref",
        "decision_packet_refs",
        "decision_rule",
        "decision_rule_evaluation",
        "denominator",
        "document_content_hash",
        "document_id",
        "document_version_id",
        "downstream_candidates",
        "effects",
        "ended_at",
        "estimator",
        "evaluation_data",
        "event_id",
        "event_type",
        "evidence_family_id",
        "evidence_id",
        "evidence_refs",
        "evidence_summary",
        "execution_attempt_id",
        "execution_attempt_ref",
        "executor",
        "expected_outcome_types",
        "expires_at",
        "extensions",
        "family_id",
        "gate_disposition",
        "guardrail_results",
        "guardrails",
        "handoff_summary",
        "idempotency_key",
        "identity",
        "independent_source_groups",
        "input_revision_hash",
        "inputs",
        "issued_at",
        "limits",
        "lineage",
        "lock_version",
        "measurement",
        "media_manifest_id",
        "media_type",
        "members",
        "metric_name",
        "metric_profile_id",
        "metric_profile_ref",
        "metric_result_family_id",
        "metric_result_id",
        "metric_result_ref",
        "minimum_sample",
        "missing_data_policy",
        "must_avoid",
        "must_keep",
        "must_resolve_before_use",
        "narrative_arc",
        "novelty",
        "numerator",
        "object_hash",
        "object_kind",
        "object_successor_edge_id",
        "observed_at",
        "operational_receipt_family_id",
        "operational_receipt_id",
        "operator_actor_ref",
        "operator_inputs",
        "origin_decision_packet_ref",
        "outcome_code",
        "outcome_event_family_id",
        "outcome_event_id",
        "outcome_family",
        "outcome_type",
        "output_object",
        "owner_ref",
        "payload_ref",
        "permitted_use",
        "platform_specs",
        "policy",
        "predecessor_ref",
        "predecessor_refs",
        "priority",
        "producer",
        "promise",
        "propagation_scope",
        "provenance",
        "publication_state",
        "quality",
        "question",
        "queue_state",
        "rationale_code",
        "reason_code",
        "reason_codes",
        "receipt_type",
        "recommended_action",
        "reconciliation",
        "recorded_at",
        "reference_assets",
        "remediation",
        "requested_action_spec_id",
        "requested_action_spec_ref",
        "requested_action_spec_refs",
        "required_propagation_targets",
        "residual_risk",
        "result_state",
        "retention",
        "review",
        "review_state",
        "reviewer",
        "reviewer_ref",
        "revision",
        "revocation_receipt_id",
        "risk_analysis",
        "risk_class",
        "risk_reclassification_receipt_id",
        "run_revision",
        "sample",
        "sanitization_receipt_id",
        "scope",
        "sensitivity",
        "session_ref",
        "sla",
        "source",
        "source_document_refs",
        "source_event_ref",
        "source_object",
        "source_objects",
        "source_observation_refs",
        "source_refs",
        "source_span",
        "source_system",
        "source_tier",
        "source_versions",
        "stance",
        "started_at",
        "state",
        "statement",
        "status",
        "steps",
        "story_cluster_family_id",
        "story_cluster_id",
        "subgroups",
        "subject",
        "subject_refs",
        "successor_ref",
        "suggested_due_at",
        "suggested_owner_ref",
        "supersedes_action_item_ref",
        "supersedes_claim_ref",
        "supersedes_conductor_handoff_ref",
        "supersedes_content_object_ref",
        "supersedes_creative_lock_ref",
        "supersedes_decision_packet_ref",
        "supersedes_evidence_ref",
        "supersedes_metric_result_ref",
        "supersedes_operational_receipt_ref",
        "supersedes_outcome_event_ref",
        "supersedes_topic_lock_ref",
        "supersedes_verification_receipt_ref",
        "supersedes_workflow_run_ref",
        "supersession_ref",
        "target",
        "target_objects",
        "target_ref",
        "temporal_scope",
        "tenant",
        "terminal_outcome",
        "time",
        "timeline_or_slides",
        "times",
        "title",
        "tone",
        "topic",
        "topic_lock_family_id",
        "topic_lock_id",
        "topic_lock_ref",
        "transformations",
        "unit",
        "unrevoke",
        "unresolved_questions",
        "validity",
        "value",
        "verdict",
        "verification_receipt_family_id",
        "verification_receipt_id",
        "verification_receipt_refs",
        "verification_state",
        "verification_type",
        "verifier",
        "why_now",
        "window",
        "workflow",
        "workflow_run_family_id",
        "workflow_run_id",
        "workflow_run_ref",
    }
)


class FrozenCoreModel(BaseModel):
    """Base configuration for immutable, closed canonical objects."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PydanticCustomError(
            "timestamp_timezone_missing", "timestamp must be timezone-aware UTC"
        )
    if value.utcoffset() != timedelta(0):
        raise PydanticCustomError("timestamp_not_utc", "timestamp must be UTC")
    return value


UtcDateTime = Annotated[
    datetime,
    AfterValidator(_utc_datetime),
    WithJsonSchema(
        {
            "format": "date-time",
            "pattern": _UTC_OFFSET_PATTERN,
            "type": "string",
        }
    ),
]
Sha256Hex = Annotated[str, Field(pattern=SHA256_HEX_PATTERN)]
RegisteredName = Annotated[str, Field(pattern=_REGISTERED_NAME_RE.pattern)]
Identifier = Annotated[str, Field(pattern=_IDENTIFIER_RE.pattern)]


class ExactObjectRef(FrozenCoreModel):
    object_kind: Identifier
    object_id: str = Field(min_length=1)
    object_hash: Sha256Hex


class ActorRef(FrozenCoreModel):
    scheme: Literal["hmac-sha256"]
    key_version: str = Field(min_length=1)
    purpose: Literal[
        "approval", "verification", "queue_decision", "assignment", "execution", "audit"
    ]
    pseudonym: Sha256Hex


class Retention(FrozenCoreModel):
    retention_class: Literal["public_record", "operational", "audit", "restricted"]
    retain_until: UtcDateTime | None = None
    legal_hold: bool
    rights_expires_at: UtcDateTime | None = None


class Producer(FrozenCoreModel):
    name: Identifier
    version: str = Field(min_length=1)


class WorkflowRunRef(FrozenCoreModel):
    workflow_run_id: UUID
    object_hash: Sha256Hex


class Lineage(FrozenCoreModel):
    workflow_run_ref: WorkflowRunRef | None = None
    input_hashes: tuple[Sha256Hex, ...]


class Classification(FrozenCoreModel):
    risk_class: RiskClass
    sensitivity: Sensitivity


class ValidTime(FrozenCoreModel):
    valid_from: UtcDateTime
    valid_to: UtcDateTime | None

    @model_validator(mode="after")
    def validate_half_open_interval(self) -> ValidTime:
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise PydanticCustomError(
                "valid_time_not_increasing",
                "valid_to must be strictly later than valid_from",
            )
        return self


class ExtensionValue(FrozenCoreModel):
    extension_version: str
    payload: dict[str, Any]

    @model_validator(mode="after")
    def validate_semantic_version(self) -> ExtensionValue:
        try:
            SemanticVersion.parse(self.extension_version)
        except ValueError as exc:
            raise PydanticCustomError(
                "extension_version_not_semver",
                "extension_version must be semantic version",
            ) from exc
        return self


Extensions = dict[str, ExtensionValue]


def validate_extensions(
    extensions: Mapping[str, ExtensionValue] | None,
) -> Mapping[str, ExtensionValue] | None:
    """Enforce namespaces and recursively jail the frozen core vocabulary."""

    if extensions is None:
        return None
    for namespace, extension in extensions.items():
        if _REVERSE_DNS_RE.fullmatch(namespace) is None:
            raise ValueError(f"extension namespace must be reverse-DNS: {namespace!r}")
        shadowed: set[str] = set()
        pending: list[Any] = [extension.payload]
        while pending:
            value = pending.pop()
            if isinstance(value, dict):
                shadowed.update(V1_RESERVED_EXTENSION_FIELD_NAMES.intersection(value))
                pending.extend(value.values())
            elif isinstance(value, (list, tuple)):
                pending.extend(value)
        if shadowed:
            raise ValueError(f"extension payload cannot introduce a core field: {sorted(shadowed)}")
    return extensions
