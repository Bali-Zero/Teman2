"""Immutable CreativeLock contract from frozen CONTRACTS.md section 8.2."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import LockState, RiskClass, Sensitivity, max_risk, max_sensitivity
from research_os.hashing import object_hash
from research_os.models.decision_packet import RequiredWorkflowLineage
from research_os.models.topic_lock import TopicLockRef
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
    validate_extensions,
)


class CreativeLockRef(FrozenCoreModel):
    creative_lock_id: UUID
    object_hash: Sha256Hex


class ChannelIntent(FrozenCoreModel):
    """``channel_intent: [{surface, objective, cta}]`` -- named keys, so
    (unlike ``tone``/``narrative_arc``/``must_keep``/``must_avoid`` below)
    this one is a direct extraction, not an invention.
    """

    surface: Identifier
    objective: str = Field(min_length=1)
    cta: str = Field(min_length=1)


class AssetRef(FrozenCoreModel):
    asset_id: str = Field(min_length=1)
    content_hash: Sha256Hex


class ReferenceAsset(FrozenCoreModel):
    """``{asset_ref: {asset_id, content_hash}, purpose, rights_state, risk_class, sensitivity}``.

    INTERPRETATION: ``rights_state`` has no entry in section 3's closed enum
    registry -- unlike every other ``*_state``/``state`` field in this
    contract family (``LockState``, ``PublicationState``, ...), which IS
    listed there. Modeled as an open ``RegisteredName`` (the same
    open-vocabulary idiom as a ``reason_code``) rather than fabricating a
    closed ``Literal`` set the freeze never wrote down. If a closed
    vocabulary was intended, it is missing from section 3 and needs a
    freeze-change addition -- not an invented enum here.
    """

    asset_ref: AssetRef
    purpose: str = Field(min_length=1)
    rights_state: RegisteredName
    risk_class: RiskClass
    sensitivity: Sensitivity


class CreativeLock(FrozenCoreModel):
    creative_lock_id: UUID
    creative_lock_family_id: RegisteredName
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    topic_lock_ref: TopicLockRef
    promise: str = Field(min_length=1)
    # INTERPRETATION: "tone: structured register" and "narrative_arc:
    # structured beats" give zero key names -- invented as free-form JSON,
    # same treatment as DecisionPacket.alternatives. narrative_arc is a
    # tuple (plural "beats" implies a sequence of beat objects); tone is a
    # single object. Flagging for ratification, not spec-derived.
    tone: dict[str, Any]
    narrative_arc: tuple[dict[str, Any], ...]
    # INTERPRETATION: "[structured constraint]" names an item concept
    # ("constraint") but no keys -- same free-form treatment.
    must_keep: tuple[dict[str, Any], ...]
    must_avoid: tuple[dict[str, Any], ...]
    channel_intent: tuple[ChannelIntent, ...]
    reference_assets: tuple[ReferenceAsset, ...]
    classification: Classification
    lock_version: int = Field(ge=1)
    state: LockState
    supersedes_creative_lock_ref: CreativeLockRef | None = None
    recorded_at: UtcDateTime
    producer: Producer
    lineage: RequiredWorkflowLineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_creative_lock(self) -> CreativeLock:
        # Same family+revision coupling as TopicLock -- see that file's
        # comment for the "spec never spells this out for locks in so many
        # words" flag; it applies identically here.
        if self.lock_version == 1 and self.supersedes_creative_lock_ref is not None:
            raise PydanticCustomError(
                "initial_revision_cannot_supersede",
                "lock_version 1 of a family cannot carry supersedes_creative_lock_ref",
            )
        if self.lock_version > 1 and self.supersedes_creative_lock_ref is None:
            raise PydanticCustomError(
                "revision_missing_supersedes_ref",
                "lock_version > 1 must bind supersedes_creative_lock_ref to its exact predecessor",
            )
        if (
            self.supersedes_creative_lock_ref is not None
            and self.supersedes_creative_lock_ref.creative_lock_id == self.creative_lock_id
        ):
            raise PydanticCustomError(
                "supersedes_ref_is_self",
                "supersedes_creative_lock_ref cannot name this same creative_lock_id",
            )
        # Section 8, shared invariants: "A CreativeLock cannot weaken the
        # risk, sensitivity ... constraints inherited through its Topic
        # Lock. Its mandatory classification is the component-wise maximum
        # of the exact Topic Lock and every exact referenced asset." This
        # object carries only `topic_lock_ref` (a hash pointer, not the
        # Topic Lock's own classification), so the Topic-Lock half of that
        # maximum cannot be checked from a single CreativeLock fixture --
        # same class of cross-object concern as ObjectSuccessorEdge's
        # family checks living in graph.py rather than successor_edge.py's
        # model_validator (see that file's FREEZE-CONFLICT comment). What
        # IS checkable from this object alone: classification can never be
        # lower than any individual referenced asset's own classification.
        # A repository-level check must still verify the Topic-Lock half.
        for asset in self.reference_assets:
            if (
                max_risk(self.classification.risk_class, asset.risk_class)
                != self.classification.risk_class
            ):
                raise PydanticCustomError(
                    "classification_below_referenced_asset_risk",
                    "classification.risk_class cannot be lower than a referenced asset's risk_class",
                )
            if (
                max_sensitivity(self.classification.sensitivity, asset.sensitivity)
                != self.classification.sensitivity
            ):
                raise PydanticCustomError(
                    "classification_below_referenced_asset_sensitivity",
                    "classification.sensitivity cannot be lower than a referenced asset's sensitivity",
                )
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
