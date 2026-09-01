"""Immutable ConductorHandoff contract from frozen CONTRACTS.md section 15.

Judgment calls (spec silent, encoded conservatively, flagged for ratification
in the P04-D1 handoff report):

- ``considered_options[].disposition`` is written in CONTRACTS.md with the
  same closed pipe-syntax as every section-3 registered enum
  (``selected | rejected | deferred``), but no matching row exists in the
  section-3 closed enum registry table -- unlike ``approval_decision``
  (``select``/``reject``/``defer``, different word forms and a different
  field). It is encoded here as a local closed ``Literal`` rather than
  invented as a new central enum, and flagged for Packet 04 to decide
  whether it belongs in the registry.
- ``considered_options[].reason_code`` carries no "registered namespaced
  string" qualifier in this section's prose (unlike most other
  ``reason_code`` fields in CONTRACTS.md, which do), but is typed as
  ``RegisteredName`` here for consistency with how the two already-shipped
  sibling models (``ObjectSuccessorEdge``, ``RevocationReceipt``) treat the
  identically-named field -- a convention-following inference, not a
  verbatim statement for this occurrence.
- ``decision.rationale_codes`` and ``session_ref.protected_transcript_ref``
  have no shape shown beyond a bare ``[]`` / a bare optional field name.
  They are read as a tuple of non-empty strings and an opaque non-empty
  string reference, respectively -- flagged as underspecified.
- ``session_ref.scheme`` and ``session_ref.purpose`` are open strings, not
  reuses of ``primitives.ActorRef``'s ``scheme``/``purpose`` closed literals:
  a session-identification scheme and a session's purpose are a different
  concept from an HMAC actor pseudonym's scheme/purpose, and forcing the
  narrower closed set here would very plausibly reject valid session
  metadata the spec never constrains.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import HandoffOutcome, HandoffState, Sensitivity
from research_os.hashing import object_hash
from research_os.primitives import (
    ActorRef,
    Classification,
    Extensions,
    FrozenCoreModel,
    Identifier,
    Producer,
    RegisteredName,
    Retention,
    Sha256Hex,
    UtcDateTime,
    WorkflowRunRef,
    validate_extensions,
)


class SessionRef(FrozenCoreModel):
    scheme: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    opaque_id: str = Field(min_length=1)
    record_hash: Sha256Hex
    protected_transcript_ref: str | None = Field(default=None, min_length=1)


class AssistantProducer(FrozenCoreModel):
    provider: Identifier
    model: Identifier
    model_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)


class OperatorInput(FrozenCoreModel):
    input_id: str = Field(min_length=1)
    content_hash: Sha256Hex
    sensitivity: Sensitivity


class DecisionPacketRef(FrozenCoreModel):
    decision_packet_id: UUID
    object_hash: Sha256Hex


class VerificationReceiptRef(FrozenCoreModel):
    verification_receipt_id: UUID
    object_hash: Sha256Hex


class ConsideredOption(FrozenCoreModel):
    option_id: str = Field(min_length=1)
    disposition: Literal["selected", "rejected", "deferred"]
    reason_code: RegisteredName


class TopicLockRef(FrozenCoreModel):
    topic_lock_id: UUID
    object_hash: Sha256Hex


class CreativeLockRef(FrozenCoreModel):
    creative_lock_id: UUID
    object_hash: Sha256Hex


class RequestedActionSpecRef(FrozenCoreModel):
    requested_action_spec_id: UUID
    object_hash: Sha256Hex


class HandoffDecision(FrozenCoreModel):
    outcome: HandoffOutcome
    rationale_codes: tuple[str, ...]


class ConductorHandoffRef(FrozenCoreModel):
    conductor_handoff_id: UUID
    object_hash: Sha256Hex


class ConductorHandoff(FrozenCoreModel):
    conductor_handoff_id: UUID
    conductor_handoff_family_id: RegisteredName
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    session_ref: SessionRef
    operator_actor_ref: ActorRef
    assistant_producer: AssistantProducer
    operator_inputs: tuple[OperatorInput, ...]
    decision_packet_refs: tuple[DecisionPacketRef, ...]
    verification_receipt_refs: tuple[VerificationReceiptRef, ...]
    considered_options: tuple[ConsideredOption, ...]
    topic_lock_ref: TopicLockRef | None = None
    creative_lock_ref: CreativeLockRef | None = None
    requested_action_spec_refs: tuple[RequestedActionSpecRef, ...]
    decision: HandoffDecision
    unresolved_questions: tuple[str, ...]
    handoff_summary: str = Field(min_length=1)
    classification: Classification
    workflow_run_ref: WorkflowRunRef
    state: HandoffState
    supersedes_conductor_handoff_ref: ConductorHandoffRef | None = None
    created_at: UtcDateTime
    recorded_at: UtcDateTime
    expires_at: UtcDateTime | None = None
    producer: Producer
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_handoff(self) -> ConductorHandoff:
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
