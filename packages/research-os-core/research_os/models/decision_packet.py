"""Immutable DecisionPacket contract from frozen CONTRACTS.md section 7,
plus the shared reference/lineage sub-types the sibling operator-decision
kinds (TopicLock, CreativeLock, RequestedActionSpec -- sections 8.1-8.3)
import from here rather than each redefining the identical shape.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import OutcomeFamily
from research_os.hashing import object_hash
from research_os.primitives import (
    ActorRef,
    Classification,
    ExactObjectRef,
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
    """``{decision_packet_id, object_hash}`` -- the typed pointer every
    operator-decision kind in this producer family (TopicLock, CreativeLock
    via TopicLock, RequestedActionSpec) binds back to its originating packet.
    """

    decision_packet_id: UUID
    object_hash: Sha256Hex


class ClaimRef(FrozenCoreModel):
    claim_id: UUID
    object_hash: Sha256Hex


class EvidenceRef(FrozenCoreModel):
    evidence_id: UUID
    object_hash: Sha256Hex


class SourceDocumentRef(FrozenCoreModel):
    document_id: str = Field(min_length=1)
    document_version_id: str = Field(min_length=1)
    document_content_hash: Sha256Hex


class RequiredWorkflowLineage(FrozenCoreModel):
    """``lineage: {workflow_run_ref: {workflow_run_id, object_hash}, input_hashes: []}``.

    Sections 8.1, 8.2, and 8.3 all spell this exact two-field shape
    verbatim, with ``workflow_run_ref`` MANDATORY -- unlike
    ``primitives.Lineage``, whose ``workflow_run_ref`` is optional for kinds
    that may run outside a workflow. TopicLock, CreativeLock, and
    RequestedActionSpec import this type rather than each redefining it.
    """

    workflow_run_ref: WorkflowRunRef
    input_hashes: tuple[Sha256Hex, ...]


class DecisionPacketLineage(FrozenCoreModel):
    """Section 7's own lineage: the same mandatory ``workflow_run_ref`` as
    ``RequiredWorkflowLineage``, plus three fields no other kind in this
    slice carries (``code_version?``, ``model_version?``, ``prompt_version?``).
    """

    workflow_run_ref: WorkflowRunRef
    input_hashes: tuple[Sha256Hex, ...]
    code_version: str | None = None
    model_version: str | None = None
    prompt_version: str | None = None


class EvidenceSummary(FrozenCoreModel):
    """``evidence_summary: structured citation-bearing summary``.

    INTERPRETATION (spec silent on shape -- flagging per mandate, not
    presenting this as spec-derived): four words of prose give no key
    names, so this shape is invented. ``citations`` reuses the generic
    ``ExactObjectRef`` (rather than a new type) because a citation may point
    at either a ``Claim`` or an ``Evidence`` object, and only the generic
    primitive carries ``object_kind`` to disambiguate which.

    CONTESTED GROUND: an earlier revision also required ``citations`` to be
    non-empty, on the reasoning that a summary calling itself
    "citation-bearing" with zero citations contradicts its own name. That
    rule was removed -- it rejected a packet CONTRACTS.md Rule 9 (section 1)
    explicitly permits: "Missing evidence is not negative evidence. `unknown`,
    `inconclusive`, and `insufficient_evidence` are valid outcomes." A
    DecisionPacket with empty ``claim_refs`` and empty ``evidence_refs`` is
    already accepted by this model (neither field carries a ``min_length``);
    demanding non-empty ``citations`` here rejected exactly that packet one
    field later, for the same missing evidentiary support. Section 7 also
    ranks ``evidence_summary`` as subordinate to those reference lists --
    "explanatory and cannot substitute for those references" -- so making it
    the one mandatory citation carrier inverted that ordering. See
    ``fixtures/decision_packet/valid_no_evidentiary_support.json``.
    """

    text: str = Field(min_length=1)
    citations: tuple[ExactObjectRef, ...]


class NoveltyWindow(FrozenCoreModel):
    started_at: UtcDateTime
    ended_at: UtcDateTime

    @model_validator(mode="after")
    def validate_window(self) -> NoveltyWindow:
        if self.ended_at <= self.started_at:
            raise PydanticCustomError(
                "novelty_window_not_increasing",
                "ended_at must be strictly later than started_at",
            )
        return self


class Novelty(FrozenCoreModel):
    """``novelty: {score, basis, compared_window}``.

    INTERPRETATION: no numeric range is given anywhere in the frozen
    contracts for ANY ``*score`` field (this one, or ``Claim.confidence.score``
    on the sibling evidence-spine lane) -- no bound is invented here, unlike
    e.g. ``Sha256Hex``'s explicit wire-level regex. ``compared_window``
    borrows the ``{started_at, ended_at}`` idiom already established for
    ``OutcomeEvent.window`` / ``MetricResult.window`` in this same contract
    family, rather than inventing a new one.
    """

    score: float
    basis: str = Field(min_length=1)
    compared_window: NoveltyWindow


class RiskAnalysis(FrozenCoreModel):
    reasons: tuple[str, ...]
    unresolved_questions: tuple[str, ...]


class RecommendedAction(FrozenCoreModel):
    action_type: RegisteredName
    target_surface: Identifier
    owner_ref: ActorRef | None = None
    due_at: UtcDateTime | None = None
    expected_outcome: str | None = None


class DecisionPacket(FrozenCoreModel):
    decision_packet_id: UUID
    decision_packet_family_id: RegisteredName
    revision: int = Field(ge=1)
    supersedes_decision_packet_ref: DecisionPacketRef | None = None
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    title: str = Field(min_length=1)
    why_now: str = Field(min_length=1)
    outcome_family: OutcomeFamily
    claim_refs: tuple[ClaimRef, ...]
    evidence_refs: tuple[EvidenceRef, ...]
    source_document_refs: tuple[SourceDocumentRef, ...]
    evidence_summary: EvidenceSummary
    novelty: Novelty
    risk_analysis: RiskAnalysis
    recommended_action: RecommendedAction
    # INTERPRETATION: both fields are bare `[]` in section 7's prose -- no
    # inner key names at all, unlike every other list field in this kind
    # (compare risk_analysis.reasons, which is also bare `[]` but at least
    # sits inside a named parent with a self-descriptive key). Genuinely no
    # shape to extract. Modeled as free-form JSON objects, matching how
    # `ExtensionValue.payload` already holds unconstrained structured
    # content elsewhere in this codebase -- not presented as spec-derived.
    alternatives: tuple[dict[str, Any], ...]
    downstream_candidates: tuple[dict[str, Any], ...]
    classification: Classification
    recorded_at: UtcDateTime
    producer: Producer
    lineage: DecisionPacketLineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_decision_packet(self) -> DecisionPacket:
        # Section 7: "decision_packet_family_id maps to
        # ObjectSuccessorEdge.family_id. An edited packet is a new revision
        # that binds the exact current predecessor ... a queue decision
        # never mutates the packet." The single-object half of that
        # invariant -- revision 1 has nothing to supersede, every later
        # revision must name its exact predecessor -- mirrors the identical
        # pattern already proven on ActionItem's revision/supersedes pair
        # (section 13.1 sibling lane). The cross-object half (later
        # recorded_at, unique current member, same family_id) is
        # graph.select_current_member's job, exactly as successor_edge.py's
        # own FREEZE-CONFLICT comment defers it there.
        if self.revision == 1 and self.supersedes_decision_packet_ref is not None:
            raise PydanticCustomError(
                "initial_revision_cannot_supersede",
                "revision 1 of a family cannot carry supersedes_decision_packet_ref",
            )
        if self.revision > 1 and self.supersedes_decision_packet_ref is None:
            raise PydanticCustomError(
                "revision_missing_supersedes_ref",
                "revision > 1 must bind supersedes_decision_packet_ref to its exact predecessor",
            )
        if (
            self.supersedes_decision_packet_ref is not None
            and self.supersedes_decision_packet_ref.decision_packet_id == self.decision_packet_id
        ):
            raise PydanticCustomError(
                "supersedes_ref_is_self",
                "supersedes_decision_packet_ref cannot name this same decision_packet_id",
            )
        validate_extensions(self.extensions)
        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
