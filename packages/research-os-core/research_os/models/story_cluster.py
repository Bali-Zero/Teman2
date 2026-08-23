"""Immutable StoryCluster contract from frozen CONTRACTS.md section 11.

Purpose (verbatim): "preserve one evolving story without mistaking
syndication for corroboration."

Interpretation notes (fields section 11 names but does not type further):

- ``predecessor_refs[].operation``, ``members[].relationship``,
  ``decision.verdict``, ``decision.decided_by``: each is given as an
  explicit closed pipe-separated set inline in section 11's wire shape,
  but none of those sets appear in section 3's shared closed-enum
  registry table -- they are modeled as local ``Literal`` sets scoped to
  this kind, the same treatment ``contract_version``/``tenant`` get in
  the already-built kinds.
- ``decision.layers_run``: section 11 gives the fixed vocabulary
  ``[exact, normalized, near, semantic, human]`` and the prose invariant
  "deterministic layers run before semantic or model layers". This is
  modeled as a closed ``Literal`` per entry plus a validator requiring
  the tuple's ordinals to be strictly increasing against that fixed
  order -- i.e. each layer runs at most once and a deterministic layer
  (``exact``/``normalized``) never follows a later-stage layer.
- ``decision.thresholds_version``: no "semantic version" descriptor is
  given here (contrast ``extensions.*.extension_version``, which section
  2 explicitly calls semver), so it is modeled as an opaque non-empty
  string, not validated as semver.
- ``decision.reasons``: "reasons: [code]" reuses the namespaced-code
  reading applied to ``reason_code`` elsewhere, i.e. ``RegisteredName``.
- ``lineage.code_version``/``model_version``: opaque non-empty strings.
- The invariant "independent corroboration counts distinct
  source_group_id values, not member count" is read as binding
  ``independent_source_groups`` to the members it summarizes: no
  duplicate entries, and every entry must be attested by at least one
  member's ``source_group_id``.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.hashing import object_hash
from research_os.models.intel_event import EventRef
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

DecisionLayer = Literal["exact", "normalized", "near", "semantic", "human"]
_DECISION_LAYER_ORDER: dict[str, int] = {
    "exact": 0,
    "normalized": 1,
    "near": 2,
    "semantic": 3,
    "human": 4,
}


class StoryClusterPredecessorRef(FrozenCoreModel):
    """``predecessor_refs`` item: ``{story_cluster_id, object_hash, operation}``."""

    story_cluster_id: UUID
    object_hash: Sha256Hex
    operation: Literal["merge", "split", "canonical_change"]


class StoryClusterMember(FrozenCoreModel):
    """``members`` item: ``{event_ref, relationship, source_group_id, relation_score}``."""

    event_ref: EventRef
    relationship: Literal["exact", "near", "syndicated", "translation", "update", "same_event"]
    source_group_id: str = Field(min_length=1)
    relation_score: float = Field(ge=0, le=1)


class StoryClusterDecision(FrozenCoreModel):
    """``decision: {layers_run, thresholds_version, verdict, reasons, decided_by, decided_at}``."""

    layers_run: tuple[DecisionLayer, ...]
    thresholds_version: str = Field(min_length=1)
    verdict: Literal["merged", "split", "review"]
    reasons: tuple[RegisteredName, ...]
    decided_by: Literal["deterministic", "model", "human"]
    decided_at: UtcDateTime

    @model_validator(mode="after")
    def validate_layer_order(self) -> StoryClusterDecision:
        ordinals = [_DECISION_LAYER_ORDER[layer] for layer in self.layers_run]
        if ordinals != sorted(ordinals) or len(set(ordinals)) != len(ordinals):
            raise PydanticCustomError(
                "decision_layers_not_deterministic_first",
                "layers_run must run each layer at most once, in the fixed "
                "order exact < normalized < near < semantic < human, so "
                "deterministic layers always precede semantic/model layers",
            )
        return self


class StoryClusterLineage(FrozenCoreModel):
    """``lineage: {run_id, code_version, model_version?, input_hashes}``."""

    run_id: UUID
    code_version: str = Field(min_length=1)
    model_version: str | None = Field(default=None, min_length=1)
    input_hashes: tuple[Sha256Hex, ...]


class StoryCluster(FrozenCoreModel):
    story_cluster_id: UUID
    story_cluster_family_id: UUID
    revision: int = Field(gt=0)
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    predecessor_refs: tuple[StoryClusterPredecessorRef, ...]
    canonical_event_ref: EventRef
    members: tuple[StoryClusterMember, ...]
    independent_source_groups: tuple[str, ...]
    decision: StoryClusterDecision
    recorded_at: UtcDateTime
    classification: Classification
    producer: Producer
    lineage: StoryClusterLineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_story_cluster(self) -> StoryCluster:
        validate_extensions(self.extensions)

        if len(set(self.independent_source_groups)) != len(self.independent_source_groups):
            raise PydanticCustomError(
                "independent_source_groups_not_distinct",
                "independent_source_groups must not contain duplicate values",
            )
        member_groups = {member.source_group_id for member in self.members}
        if any(group not in member_groups for group in self.independent_source_groups):
            raise PydanticCustomError(
                "independent_source_group_not_attested_by_member",
                "every independent_source_groups entry must match at least "
                "one member's source_group_id",
            )

        # NOTE: "ambiguous clusters go to review" and "no merge/split edge
        # is interpreted as authority" are workflow-level rules, not a
        # single standalone object's structural constraint, and are
        # therefore not enforced here.

        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
