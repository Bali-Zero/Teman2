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
  "deterministic layers run before semantic or model layers". Of that
  vocabulary, only ``semantic`` is plausibly the named "model" layer (
  ``human`` is a human, not a model or a deterministic algorithm, and the
  prose says nothing about where it sits), so the validator enforces
  exactly the two-class partial order the prose states -- no
  deterministic layer (``exact``/``normalized``/``near``) may appear
  after ``semantic`` in the sequence -- and leaves the relative order
  *within* the deterministic set, repeats, and ``human``'s position
  unconstrained, since the prose does not constrain them either. (This
  replaces an earlier, over-specified "each layer at most once, in one
  fixed total order" reading that also forbade harmless reorderings like
  ``[normalized, exact]`` -- corrected 2026 after adversarial review of
  PR #4610.)
- ``decision.thresholds_version``: no "semantic version" descriptor is
  given here (contrast ``extensions.*.extension_version``, which section
  2 explicitly calls semver), so it is modeled as an opaque non-empty
  string, not validated as semver.
- ``decision.reasons``: "reasons: [code]" reuses the namespaced-code
  reading applied to ``reason_code`` elsewhere, i.e. ``RegisteredName``.
- ``lineage.code_version``/``model_version``: opaque non-empty strings.
- The invariant "independent corroboration counts distinct
  source_group_id values, not member count" -- and the purpose clause
  "without mistaking syndication for corroboration" -- are read together
  as binding ``independent_source_groups`` to the *non-syndicated*
  members it summarizes: no duplicate entries, and every entry must be
  attested by at least one member whose ``relationship`` is NOT
  ``syndicated``. A ``source_group_id`` attested only by a syndicated
  member is exactly the mistake the purpose clause names, so it does not
  count (corrected 2026 after adversarial review of PR #4610 -- the
  original check counted syndicated members as attestation).
- Adversarial-review note (2026, PR #4610, corrected on a third pass): a
  second-pass draft of this fix forbade ``extensions`` outright whenever
  ``classification.sensitivity`` is ``client_pii``/``restricted_osint``.
  That check has been REMOVED -- CONTRACTS.md section 2 grants every
  core object namespaced ``extensions`` unconditionally, and no clause
  anywhere in the freeze conditions that grant on ``classification.
  sensitivity``, so the check was an implementer-chosen narrowing of a
  frozen contract, not a spec-derived one, with no matching JSON Schema
  constraint for a non-Python consumer. See the same note on
  ``research_os.models.intel_event.IntelEvent`` for the full reasoning,
  which applies unchanged here: this stays a DECLARED LIMIT -- nothing
  on this object detects PII/OSINT content hidden inside an
  ``extensions`` payload whose declared sensitivity is (correctly or
  not) something else -- rather than a guard.
- Three shapes section 11 is silent on are deliberately left
  unconstrained rather than guessed at: a revision with an empty
  ``predecessor_refs`` (no stated rule ties ``revision`` to predecessor
  chain length), duplicate entries in ``predecessor_refs`` (no
  uniqueness rule is stated, unlike ``independent_source_groups`` which
  section 11's prose does address), and a ``canonical_event_ref`` that
  does not also appear in ``members`` (section 11 does not require the
  canonical event to be its own member). These are declared gaps, not
  oversights -- flagged by PR #4610's adversarial review (LOW finding);
  future clarification of section 11 would need to come from a freeze
  amendment, not an implementer's guess.
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
_DETERMINISTIC_DECISION_LAYERS = frozenset({"exact", "normalized", "near"})
_MODEL_DECISION_LAYERS = frozenset({"semantic"})


class StoryClusterPredecessorRef(FrozenCoreModel):
    """``predecessor_refs`` item: ``{story_cluster_id, object_hash, operation}``."""

    story_cluster_id: UUID
    object_hash: Sha256Hex
    operation: Literal["merge", "split", "canonical_change"]


class StoryClusterMember(FrozenCoreModel):
    """``members`` item: ``{event_ref, relationship, source_group_id, relation_score}``."""

    event_ref: EventRef
    relationship: Literal[
        "exact", "near", "syndicated", "translation", "update", "same_event"
    ]
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
        model_layer_seen = False
        for layer in self.layers_run:
            if layer in _MODEL_DECISION_LAYERS:
                model_layer_seen = True
            elif layer in _DETERMINISTIC_DECISION_LAYERS and model_layer_seen:
                raise PydanticCustomError(
                    "decision_layers_not_deterministic_first",
                    "a deterministic layer (exact/normalized/near) must not "
                    "run after a semantic/model layer",
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

        if len(set(self.independent_source_groups)) != len(
            self.independent_source_groups
        ):
            raise PydanticCustomError(
                "independent_source_groups_not_distinct",
                "independent_source_groups must not contain duplicate values",
            )
        # Syndicated members do not count as independent corroboration --
        # that is the exact mistake section 11's purpose clause names
        # ("without mistaking syndication for corroboration").
        attested_groups = {
            member.source_group_id
            for member in self.members
            if member.relationship != "syndicated"
        }
        if any(
            group not in attested_groups for group in self.independent_source_groups
        ):
            raise PydanticCustomError(
                "independent_source_group_not_attested_by_member",
                "every independent_source_groups entry must match at least "
                "one non-syndicated member's source_group_id",
            )

        # NOTE: "ambiguous clusters go to review" and "no merge/split edge
        # is interpreted as authority" are workflow-level rules, not a
        # single standalone object's structural constraint, and are
        # therefore not enforced here. Likewise deliberately unconstrained
        # (declared, not oversights -- see module docstring): revision
        # vs. predecessor_refs consistency, duplicate predecessor_refs,
        # and canonical_event_ref not appearing in members.
        #
        # NOTE: this validator does NOT gate ``extensions`` on
        # ``classification.sensitivity`` -- see the module docstring's
        # "Adversarial-review note" for why that was tried and reverted,
        # and what the resulting declared limit is.

        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
