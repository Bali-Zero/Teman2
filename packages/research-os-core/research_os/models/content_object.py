"""Immutable ContentObject contract from frozen CONTRACTS.md section 9.

``ContentObject`` is "one editorial or product object from which
channel-specific derivatives are created." Each object is an immutable
revision; a correction or state change appends the next revision in the
same ``content_object_family_id`` and binds ``supersedes_content_object_ref``
(section 9: "``content_object_family_id`` maps to ``ObjectSuccessorEdge.
family_id``. Revision greater than one requires the exact current
predecessor and an atomic successor edge; revision forks or non-monotonic
``recorded_at`` quarantine the family.").

The lineage shape (``workflow_run_ref`` MANDATORY, plus optional
``code_version``/``model_version``/``prompt_version``) is spelled out
identically in sections 9 and 10, so ``ContentLineage`` is defined once
here and imported by ``media_manifest.py`` rather than redefined.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import AvailabilityState, PublicationState, VerificationState
from research_os.hashing import object_hash
from research_os.primitives import (
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


class DecisionPacketRef(FrozenCoreModel):
    """``{decision_packet_id, object_hash}``."""

    decision_packet_id: UUID
    object_hash: Sha256Hex


class TopicLockRef(FrozenCoreModel):
    """``{topic_lock_id, object_hash}``."""

    topic_lock_id: UUID
    object_hash: Sha256Hex


class CreativeLockRef(FrozenCoreModel):
    """``{creative_lock_id, object_hash}``."""

    creative_lock_id: UUID
    object_hash: Sha256Hex


class ClaimRef(FrozenCoreModel):
    """``{claim_id, object_hash}`` -- no ``stance``, unlike ``Claim.evidence_refs``
    (section 6). Section 9 spells this pair-only shape verbatim for
    ``ContentObject.claim_refs``.
    """

    claim_id: UUID
    object_hash: Sha256Hex


class EvidenceRef(FrozenCoreModel):
    """``{evidence_id, object_hash}``."""

    evidence_id: UUID
    object_hash: Sha256Hex


class SourceDocumentRef(FrozenCoreModel):
    document_id: str = Field(min_length=1)
    document_version_id: str = Field(min_length=1)
    document_content_hash: Sha256Hex


class ContentObjectRef(FrozenCoreModel):
    """``{content_object_id, revision, object_hash}`` -- unlike every other
    ``supersedes_*_ref`` in this contract family (``ActionItemRef``,
    ``DecisionPacketRef``, ...), section 9 explicitly bakes the
    predecessor's own ``revision`` into the exact reference rather than
    leaving it to be looked up. This same ref shape is what
    ``MediaManifest.content_object_ref`` (section 10) points at a
    ``ContentObject`` with, so it is defined here and imported there.
    """

    content_object_id: UUID
    revision: int = Field(ge=1)
    object_hash: Sha256Hex


class ContentLineage(FrozenCoreModel):
    """``lineage: {workflow_run_ref: {...}, input_hashes: [], code_version?,
    model_version?, prompt_version?}`` -- ``workflow_run_ref`` has no ``?``
    in either section 9 or section 10, so (unlike ``primitives.Lineage``,
    whose ``workflow_run_ref`` is optional for kinds that may run outside a
    workflow) it is mandatory here, mirroring the sibling operator-decision
    lane's identical ``DecisionPacketLineage`` shape for section 7.
    """

    workflow_run_ref: WorkflowRunRef
    input_hashes: tuple[Sha256Hex, ...]
    code_version: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None


class ChannelPlanEntry(FrozenCoreModel):
    """``channel_plan: [{surface, objective, cta, status}]``.

    INTERPRETATION: ``status`` has no entry in section 3's closed enum
    registry. Reusing the sibling top-level ``publication_state`` enum was
    considered and rejected: section 9 never says a per-channel status
    shares that vocabulary, and a channel might legitimately need a state
    (e.g. "paused", "rejected") ``PublicationState`` does not have.
    Modeled as an open ``RegisteredName`` -- the same open-vocabulary idiom
    used below for ``MediaAsset.rights``/``AudioMetadata.sync_result``/
    ``IdentityMetadata.verification_result`` -- rather than fabricating a
    closed ``Literal`` set the freeze never wrote down. A freeze-change
    addition to section 3 is the correct place for a closed vocabulary if
    one was intended.
    """

    surface: Identifier
    objective: str = Field(min_length=1)
    cta: str = Field(min_length=1)
    status: RegisteredName


class Availability(FrozenCoreModel):
    """``availability: {state, severity, reason_code?, requested_at?,
    required_by?, resolved_at?}``.

    ``severity`` is given as an explicit inline closed list
    (``low | medium | high | critical``) directly in section 9's wire
    shape -- unlike ``status`` above, this one is not silent, so it is a
    closed ``Literal`` rather than an open ``RegisteredName``.

    ``reason_code`` is spelled ``string?`` in section 9's prose --
    deliberately NOT "registered namespaced string", the wording every
    other ``reason_code`` field in this contract family uses (see
    ``ObjectSuccessorEdge.reason_code``, ``RevocationReceipt.reason_code``).
    Followed literally: a bare optional string, not ``RegisteredName``.
    """

    state: AvailabilityState
    severity: Literal["low", "medium", "high", "critical"]
    reason_code: str | None = None
    requested_at: UtcDateTime | None = None
    required_by: UtcDateTime | None = None
    resolved_at: UtcDateTime | None = None

    @model_validator(mode="after")
    def validate_availability_clock(self) -> Availability:
        # INTERPRETATION: section 9 gives no explicit ordering invariant
        # for these three optional timestamps, but an SLA deadline or a
        # resolution instant that precedes the request it responds to
        # describes a clock running backward -- mirrored on the sibling
        # decision-chain lane's identical ``Sla`` pattern (section 13.1:
        # "cannot precede opened_at"), anchored here on ``requested_at``
        # instead of ``opened_at``. Only checked when both sides of a pair
        # are present, so it fills a silent gap rather than requiring a
        # field section 9 marks optional.
        if self.requested_at is not None:
            if self.required_by is not None and self.required_by < self.requested_at:
                raise PydanticCustomError(
                    "availability_required_by_before_requested_at",
                    "required_by cannot precede requested_at",
                )
            if self.resolved_at is not None and self.resolved_at < self.requested_at:
                raise PydanticCustomError(
                    "availability_resolved_at_before_requested_at",
                    "resolved_at cannot precede requested_at",
                )
        return self


class ContentObject(FrozenCoreModel):
    # Section 9's revision<->supersedes_content_object_ref conditional
    # presence (enforced below in ``validate_content_object``) is expressible
    # as a JSON Schema if/then -- unlike hash-binding or cross-field-equality
    # invariants elsewhere in this contract family, both sides here are a
    # closed shape (``revision``'s own literal value vs. a field's mere
    # presence/absence), so the schema does not have to fall back to leaving
    # the gap open. ``ConfigDict`` merges with (does not replace)
    # ``FrozenCoreModel.model_config`` -- verified: pydantic's
    # ``ConfigWrapper.for_model`` builds the child's config by starting from
    # each base's ``model_config`` and then updating it key-by-key with the
    # subclass's own dict, so ``extra="forbid"``/``frozen=True`` are
    # unaffected by adding ``json_schema_extra`` here.
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {
                        "properties": {"revision": {"const": 1}},
                        "required": ["revision"],
                    },
                    "then": {"not": {"required": ["supersedes_content_object_ref"]}},
                },
                {
                    "if": {
                        "properties": {"revision": {"not": {"const": 1}}},
                        "required": ["revision"],
                    },
                    "then": {"required": ["supersedes_content_object_ref"]},
                },
            ]
        }
    )

    content_object_id: UUID
    content_object_family_id: RegisteredName
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    origin_decision_packet_ref: DecisionPacketRef
    revision: int = Field(ge=1)
    supersedes_content_object_ref: ContentObjectRef | None = None
    topic_lock_ref: TopicLockRef
    creative_lock_ref: CreativeLockRef
    claim_refs: tuple[ClaimRef, ...]
    evidence_refs: tuple[EvidenceRef, ...]
    source_document_refs: tuple[SourceDocumentRef, ...]
    classification: Classification
    channel_plan: tuple[ChannelPlanEntry, ...]
    publication_state: PublicationState
    verification_state: VerificationState
    availability: Availability
    campaign_id: str | None = None
    recorded_at: UtcDateTime
    producer: Producer
    lineage: ContentLineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_content_object(self) -> ContentObject:
        # Section 9: "Revision greater than one requires the exact current
        # predecessor" / an initial revision has nothing to supersede --
        # the identical single-object pattern already proven on
        # ActionItem/DecisionPacket's revision/supersedes pair (the
        # cross-object half -- fork, non-monotonic recorded_at, unique
        # current member -- is graph.select_current_member's job, exactly
        # as successor_edge.py's own FREEZE-CONFLICT comment defers it
        # there).
        if self.revision == 1 and self.supersedes_content_object_ref is not None:
            raise PydanticCustomError(
                "initial_revision_cannot_supersede",
                "revision 1 of a family cannot carry supersedes_content_object_ref",
            )
        if self.revision > 1 and self.supersedes_content_object_ref is None:
            raise PydanticCustomError(
                "revision_missing_supersedes_ref",
                "revision > 1 must bind supersedes_content_object_ref to its exact predecessor",
            )
        if self.supersedes_content_object_ref is not None:
            if self.supersedes_content_object_ref.content_object_id == self.content_object_id:
                raise PydanticCustomError(
                    "supersedes_ref_is_self",
                    "supersedes_content_object_ref cannot name this same content_object_id",
                )
            # INTERPRETATION: section 9 does not spell out that the
            # embedded predecessor revision number must be strictly less
            # than this object's own revision, but "revision" naming an
            # exact predecessor otherwise carries no ordering meaning at
            # all. This is a self-contained check over this object's own
            # two revision-shaped fields (no other object is
            # dereferenced) -- the same footing as ``ObjectSuccessorEdge``
            # checking ``predecessor_ref != successor_ref`` without
            # looking up either referenced object.
            if self.supersedes_content_object_ref.revision >= self.revision:
                raise PydanticCustomError(
                    "supersedes_ref_revision_not_less",
                    "supersedes_content_object_ref.revision must be less than revision",
                )
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
