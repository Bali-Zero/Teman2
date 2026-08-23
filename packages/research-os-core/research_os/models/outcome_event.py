"""Immutable OutcomeEvent contract from frozen CONTRACTS.md section 16.

KNOWN GAP against section 3.2 (RevocationReceipt, already on main) --
reported, not silently resolved:

Section 3.2's ``RevocationReceipt`` invariants require that "every downstream
effect -- withdrawal, cache purge, reindex, notification, reroute, or other
propagation -- requires its own ActionItem/ActionIntent, unexpired
effect-specific ApprovalReceipt, immutable started ExecutionAttempt, typed
terminal OperationalReceipt, and OutcomeEvent." Section 13.5's
``OperationalReceipt`` registry even names the receipt type for this:
``revocation.propagation``. But section 16's ``OutcomeEvent.subject_refs``
has no ``revocation_receipt_ref`` field -- it only has
``operational_receipt_ref``, ``action_intent_ref``, and
``execution_attempt_ref``. An ``OutcomeEvent`` that reports a
``revocation.propagation`` result can bind the ``OperationalReceipt`` that
confirms propagation, but has no field to bind the exact ``RevocationReceipt``
hash the propagation was *for*. This model encodes section 16's
``subject_refs`` exactly as written (no invented ``revocation_receipt_ref``
field) rather than quietly patching the gap; Packet 04 needs to rule whether
this is an intentional indirection (the ``OperationalReceipt``'s own
``subject_refs`` already binds the revocation, per section 13.5) or a missing
field on this object.

Other judgment calls (spec silent, flagged for ratification):

- ``value: typed value`` has no shape at all in the prose -- not even a hint
  of a ``{type, value}`` tagged union vs. a raw scalar. Typed here as ``Any``
  (JSON-compatible by construction, since it is deserialized from JSON) with
  no further constraint. This is the least-determined shape in this file;
  do not read the ``Any`` typing as a spec-derived decision.
- ``classification.aggregation_level`` has no enum, no format, no example
  anywhere in the spec. Typed as a free non-empty string.
- ``quality.completeness`` has no declared type. Typed as an unconstrained
  ``float`` (no 0..1 bound) by analogy with ``StoryCluster.relation_score``'s
  "0..1" pattern elsewhere in CONTRACTS.md, but that bound is NOT stated for
  this field and is deliberately not enforced here.
- ``source_system`` is written with the same closed pipe-syntax as a
  section-3 registered enum (``GSC | GA4 | CRM | social | workflow |
  human_review | platform | product | compliance``) but, like
  ``ConductorHandoff.considered_options[].disposition``, has no matching row
  in the section-3 registry table. Encoded as a local closed ``Literal``,
  flagged for the same registry-completeness question.
- ``window`` (``started_at``/``ended_at``, both required) is given the same
  "ended strictly after started" ordering check the ``ValidTime`` primitive
  already enforces for the same class of field elsewhere in this package;
  it is not verbatim-stated for this section.
- ``cohort.size``/``cohort.minimum_required`` are constrained ``>= 0`` as a
  definitional non-negativity check (a cohort cannot have a negative
  membership count), not a business rule invented beyond the field's plain
  meaning.
- The "suppress or aggregate cohorts smaller than 10" rule (section 16
  invariants) is deliberately NOT enforced: it is scoped to "general-ledger
  CRM projections", and this object's closed ``source_system`` enum does not
  cleanly identify "is a general-ledger projection" (a ``CRM``-sourced
  observation is not necessarily a general-ledger projection of it). This is
  a repository/domain-policy check, not a single-object validator.
- The conditional "an event reporting a publication/action side effect binds
  the applicable exact content/artifact, ActionIntent, ExecutionAttempt, and
  OperationalReceipt" requirement is NOT enforced: distinguishing a
  "side-effect" OutcomeEvent from a "metric" or "deployed -> indexed_verified"
  OutcomeEvent depends on interpreting the open (non-closed-enum)
  ``outcome_type`` registry, which this package cannot pattern-match safely.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import AttributionStrength, RiskClass, Sensitivity
from research_os.hashing import object_hash
from research_os.primitives import (
    Extensions,
    FrozenCoreModel,
    Producer,
    RegisteredName,
    Retention,
    Sha256Hex,
    UtcDateTime,
    WorkflowRunRef,
    validate_extensions,
)

SourceSystem = Literal[
    "GSC",
    "GA4",
    "CRM",
    "social",
    "workflow",
    "human_review",
    "platform",
    "product",
    "compliance",
]


class DecisionPacketRef(FrozenCoreModel):
    decision_packet_id: UUID
    object_hash: Sha256Hex


class ContentObjectRef(FrozenCoreModel):
    content_object_id: UUID
    revision: int = Field(gt=0)
    object_hash: Sha256Hex


class ArtifactRevisionRef(FrozenCoreModel):
    artifact_revision_id: str = Field(min_length=1)
    artifact_sha256: Sha256Hex


class VerificationReceiptRef(FrozenCoreModel):
    verification_receipt_id: UUID
    object_hash: Sha256Hex


class ActionIntentRef(FrozenCoreModel):
    action_intent_id: UUID
    object_hash: Sha256Hex


class ExecutionAttemptRef(FrozenCoreModel):
    execution_attempt_id: UUID
    object_hash: Sha256Hex


class OperationalReceiptRef(FrozenCoreModel):
    operational_receipt_id: UUID
    object_hash: Sha256Hex


class ClaimRef(FrozenCoreModel):
    claim_id: UUID
    object_hash: Sha256Hex


class CampaignRef(FrozenCoreModel):
    campaign_id: str = Field(min_length=1)
    revision: int | None = Field(default=None, gt=0)
    object_hash: Sha256Hex


class SubjectRefs(FrozenCoreModel):
    decision_packet_ref: DecisionPacketRef | None = None
    content_object_ref: ContentObjectRef | None = None
    artifact_revision_ref: ArtifactRevisionRef | None = None
    verification_receipt_ref: VerificationReceiptRef | None = None
    action_intent_ref: ActionIntentRef | None = None
    execution_attempt_ref: ExecutionAttemptRef | None = None
    operational_receipt_ref: OperationalReceiptRef | None = None
    claim_refs: tuple[ClaimRef, ...]
    campaign_ref: CampaignRef | None = None
    workflow_run_ref: WorkflowRunRef | None = None


class MetricProfileRef(FrozenCoreModel):
    metric_profile_id: UUID
    object_hash: Sha256Hex


class MetricResultRef(FrozenCoreModel):
    metric_result_id: UUID
    object_hash: Sha256Hex


class OutcomeWindow(FrozenCoreModel):
    started_at: UtcDateTime
    ended_at: UtcDateTime

    @model_validator(mode="after")
    def validate_window(self) -> OutcomeWindow:
        if self.ended_at <= self.started_at:
            raise PydanticCustomError(
                "window_ended_at_not_later",
                "window.ended_at must be strictly later than window.started_at",
            )
        return self


class OutcomeQuality(FrozenCoreModel):
    attribution_strength: AttributionStrength
    completeness: float
    caveats: tuple[str, ...]
    collection_version: str = Field(min_length=1)


class OutcomeCohort(FrozenCoreModel):
    size: int | None = Field(default=None, ge=0)
    minimum_required: int | None = Field(default=None, ge=0)
    suppressed: bool


class OutcomeClassification(FrozenCoreModel):
    risk_class: RiskClass
    sensitivity: Sensitivity
    aggregation_level: str = Field(min_length=1)


class OutcomeEventLineage(FrozenCoreModel):
    workflow_run_ref: WorkflowRunRef | None = None
    input_hashes: tuple[Sha256Hex, ...]
    code_version: str | None = Field(default=None, min_length=1)
    model_version: str | None = Field(default=None, min_length=1)
    prompt_version: str | None = Field(default=None, min_length=1)


class OutcomeEventRef(FrozenCoreModel):
    outcome_event_id: UUID
    object_hash: Sha256Hex


# Section 16 joint-presence invariant, mirrored into JSON Schema (2026-08-23
# adversarial-review finding): metric_profile_ref and metric_result_ref must
# be jointly present-with-a-value or jointly absent/null. This is
# deliberately NOT a plain `dependentRequired` -- dependentRequired tests
# only KEY PRESENCE, and this contract uses presence-preserving null
# semantics (hashing.py's "option b": an absent key and a key explicitly set
# to JSON `null` are different wire documents, but the SAME validation state
# for THIS rule -- validate_event() below tests `is None`, which is True for
# both "absent" and "explicit null"). A document with both keys PRESENT but
# one explicitly `null` would slip past a bare `dependentRequired` while
# still being rejected by validate_event(); the two subschemas below test
# the VALUE (not `null`), not just key presence, and are combined
# bidirectionally (if A then B, and if B then A) to express "A iff B" --
# mirroring MetricResult's json_schema_extra precedent (metric_result.py).
_METRIC_PROFILE_REF_PRESENT_AND_NOT_NULL: dict[str, Any] = {
    "required": ["metric_profile_ref"],
    "properties": {"metric_profile_ref": {"not": {"type": "null"}}},
}
_METRIC_RESULT_REF_PRESENT_AND_NOT_NULL: dict[str, Any] = {
    "required": ["metric_result_ref"],
    "properties": {"metric_result_ref": {"not": {"type": "null"}}},
}


class OutcomeEvent(FrozenCoreModel):
    # Merges with (does not replace) FrozenCoreModel.model_config, per
    # pydantic's ConfigWrapper.for_model base-then-namespace update order --
    # extra="forbid" and frozen=True survive alongside json_schema_extra
    # (same pattern already shipped in metric_result.py, empirically
    # re-verified for this file: see PR discussion).
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": _METRIC_PROFILE_REF_PRESENT_AND_NOT_NULL,
                    "then": _METRIC_RESULT_REF_PRESENT_AND_NOT_NULL,
                },
                {
                    "if": _METRIC_RESULT_REF_PRESENT_AND_NOT_NULL,
                    "then": _METRIC_PROFILE_REF_PRESENT_AND_NOT_NULL,
                },
            ]
        }
    )

    outcome_event_id: UUID
    outcome_event_family_id: RegisteredName
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    supersedes_outcome_event_ref: OutcomeEventRef | None = None
    subject_refs: SubjectRefs
    metric_profile_ref: MetricProfileRef | None = None
    metric_result_ref: MetricResultRef | None = None
    outcome_type: RegisteredName
    value: Any
    window: OutcomeWindow
    source_system: SourceSystem
    quality: OutcomeQuality
    cohort: OutcomeCohort
    observed_at: UtcDateTime
    recorded_at: UtcDateTime
    classification: OutcomeClassification
    retention: Retention
    idempotency_key: str = Field(min_length=1)
    producer: Producer
    lineage: OutcomeEventLineage
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_event(self) -> OutcomeEvent:
        if (self.metric_profile_ref is None) != (self.metric_result_ref is None):
            raise PydanticCustomError(
                "metric_profile_and_result_not_jointly_present",
                "metric_profile_ref and metric_result_ref must be jointly present or jointly absent",
            )
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
