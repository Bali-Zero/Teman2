"""Immutable TopicLock contract from frozen CONTRACTS.md section 8.1."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import LockState
from research_os.hashing import object_hash
from research_os.models.decision_packet import (
    ClaimRef,
    DecisionPacketRef,
    RequiredWorkflowLineage,
)
from research_os.primitives import (
    Classification,
    Extensions,
    FrozenCoreModel,
    Producer,
    RegisteredName,
    Retention,
    Sha256Hex,
    UtcDateTime,
    validate_extensions,
)


class TopicLockRef(FrozenCoreModel):
    """``{topic_lock_id, object_hash}`` -- also the pointer CreativeLock
    (section 8.2) binds back to its exact selected Topic Lock revision.
    """

    topic_lock_id: UUID
    object_hash: Sha256Hex


class SourceRef(FrozenCoreModel):
    """``source_refs: [{source_id, version_id, content_hash}]``.

    Deliberately NOT the generic ``ExactObjectRef`` or DecisionPacket's
    ``SourceDocumentRef``: section 8.1 names distinct keys
    (``source_id``/``version_id``/``content_hash``) from section 7's
    ``source_document_refs`` (``document_id``/``document_version_id``/
    ``document_content_hash``) -- a different wire shape, preserved exactly
    rather than collapsed into one "source ref" type the freeze never wrote.
    """

    source_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    content_hash: Sha256Hex


class TopicLock(FrozenCoreModel):
    topic_lock_id: UUID
    topic_lock_family_id: RegisteredName
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    decision_packet_ref: DecisionPacketRef
    topic: str = Field(min_length=1)
    angle: str = Field(min_length=1)
    # INTERPRETATION: "audience: structured audience" is two words of
    # prose with zero key names anywhere else in the frozen contracts --
    # not extracted, invented as a free-form JSON object (same treatment
    # as DecisionPacket.alternatives/downstream_candidates). Flagging for
    # ratification, not presenting as spec-derived.
    audience: dict[str, Any]
    why_now: str = Field(min_length=1)
    claim_refs: tuple[ClaimRef, ...]
    source_refs: tuple[SourceRef, ...]
    # INTERPRETATION: "must_resolve_before_use: []" names no item shape,
    # but its own key is self-descriptive the same way
    # RiskAnalysis.unresolved_questions is -- modeled as free text for the
    # same reason, lower-confidence judgment call than audience/tone/etc.
    must_resolve_before_use: tuple[str, ...]
    classification: Classification
    lock_version: int = Field(ge=1)
    state: LockState
    supersedes_topic_lock_ref: TopicLockRef | None = None
    recorded_at: UtcDateTime
    producer: Producer
    lineage: RequiredWorkflowLineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_topic_lock(self) -> TopicLock:
        # Section 8, shared invariants: "Each lock-family field maps to
        # ObjectSuccessorEdge.family_id. A revised lock binds the exact
        # current predecessor ... forks or stale predecessors quarantine
        # the family." The prose never spells out "lock_version==1 <=> no
        # supersedes ref" in so many words the way section 7/13.1 do for
        # `revision` -- this applies the same recurring family+revision
        # coupling by analogy (established explicitly for DecisionPacket,
        # ActionItem, ContentObject, WorkflowRun, MetricResult elsewhere in
        # this same freeze) rather than by direct textual instruction here.
        # FLAGGING FOR RATIFICATION: strong-but-inferred, not spec-literal.
        if self.lock_version == 1 and self.supersedes_topic_lock_ref is not None:
            raise PydanticCustomError(
                "initial_revision_cannot_supersede",
                "lock_version 1 of a family cannot carry supersedes_topic_lock_ref",
            )
        if self.lock_version > 1 and self.supersedes_topic_lock_ref is None:
            raise PydanticCustomError(
                "revision_missing_supersedes_ref",
                "lock_version > 1 must bind supersedes_topic_lock_ref to its exact predecessor",
            )
        if (
            self.supersedes_topic_lock_ref is not None
            and self.supersedes_topic_lock_ref.topic_lock_id == self.topic_lock_id
        ):
            raise PydanticCustomError(
                "supersedes_ref_is_self",
                "supersedes_topic_lock_ref cannot name this same topic_lock_id",
            )
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
