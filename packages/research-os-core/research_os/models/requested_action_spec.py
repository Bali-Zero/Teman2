"""Immutable RequestedActionSpec contract from frozen CONTRACTS.md section 8.3.

Unlike TopicLock and CreativeLock, section 8.3's own prose is explicit that
this kind "carries no queue state, approval state, execution state, or
receipt ID" -- and, unlike every other family+revision kind in this producer
family, section 8.3 defines no ``*_family_id``, ``revision``/``lock_version``,
or ``supersedes_*_ref`` field, and the shared "Each lock-family field maps to
ObjectSuccessorEdge.family_id" bullet names only "each **lock**-family
field" -- TopicLock and CreativeLock, not this kind. No successor-family
fields are added here; doing so would invent a core field the freeze never
wrote (rule 1.11: "No packet may redefine a canonical object locally").
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import RiskClass, Sensitivity
from research_os.hashing import object_hash
from research_os.models.decision_packet import (
    DecisionPacketRef,
    RequiredWorkflowLineage,
)
from research_os.primitives import (
    ActorRef,
    ExactObjectRef,
    Extensions,
    FrozenCoreModel,
    Identifier,
    Producer,
    RegisteredName,
    Retention,
    Sha256Hex,
    UtcDateTime,
    validate_extensions,
)


class Target(FrozenCoreModel):
    """``target: {system, object_ref, surface?}``. ``object_ref`` reuses the
    generic ``ExactObjectRef`` -- section 8.3 names it identically to how
    ``PropagationTarget.object_ref`` already uses that same primitive.
    """

    system: Identifier
    object_ref: ExactObjectRef
    surface: Identifier | None = None


class AuthorityRequired(FrozenCoreModel):
    role: Identifier
    scope: str = Field(min_length=1)
    expires_after_seconds: int = Field(gt=0)


class RequestedActionSpec(FrozenCoreModel):
    requested_action_spec_id: UUID
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    decision_packet_ref: DecisionPacketRef
    action_type: RegisteredName
    target: Target
    # INTERPRETATION: "arguments_ref: protected or public durable
    # reference" names no sub-keys at all, unlike `target`/`channel_intent`
    # (CreativeLock) which DO. Modeled as an opaque non-empty locator
    # string rather than inventing a discriminated protected|public union
    # -- deliberately avoiding the exact mistake a sibling lane made
    # elsewhere (a discriminated union whose guard was proven on only one
    # arm). Flagging for ratification rather than presenting a guessed
    # union as spec-derived.
    arguments_ref: str = Field(min_length=1)
    arguments_hash: Sha256Hex
    input_revision_hash: Sha256Hex
    risk_class: RiskClass
    sensitivity: Sensitivity
    authority_required: AuthorityRequired
    expected_outcome_types: tuple[RegisteredName, ...]
    suggested_owner_ref: ActorRef | None = None
    suggested_due_at: UtcDateTime | None = None
    recorded_at: UtcDateTime
    producer: Producer
    lineage: RequiredWorkflowLineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_requested_action_spec(self) -> RequestedActionSpec:
        # Section 8.3's real invariants (materialization into ActionItem +
        # ActionIntent via the Packet 04 primitive, Packet 12's exclusive
        # runtime role, Packet 01's five-effect containment exception) are
        # all about downstream consumption of this object by OTHER kinds --
        # none are expressible as a single-object check here, matching
        # precedent (successor_edge.py, revocation_receipt.py, and the
        # sibling ActionIntent/ExecutionAttempt kinds all restrict their
        # own model_validator to field-level + hash checks for the same
        # reason).
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
