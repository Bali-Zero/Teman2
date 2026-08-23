"""Immutable Claim contract from frozen CONTRACTS.md section 6.

Purpose (verbatim): "smallest consequential proposition that can be
checked, timed, contradicted, expired, or superseded. NAGA owns the
canonical ledger; NEXUS may hold restricted projections linked by ID."

Interpretation notes (fields section 6 names but does not type further):

- ``statement.subject_ref``/``object_ref_or_value``: every other ``_ref``
  field in the frozen spec is an exact object reference, so
  ``subject_ref`` reuses ``ExactObjectRef``; ``object_ref_or_value`` is
  the explicit union the field name states (a reference OR a literal
  scalar).
- ``statement.predicate``: no descriptor is given, but it plays the same
  controlled-vocabulary role as ``reason_code``/``event_type``
  ("registered namespaced string" elsewhere), so it reuses
  ``RegisteredName``.
- ``statement.unit``/``currency``/``modality``, ``scope.jurisdiction``/
  ``audience``: no closed set given; modeled as non-empty strings.
- ``scope.domain``: a categorical single-or-namespaced token, reuses
  ``Identifier`` (same reading as ``IntelEvent.classification.domain``).
- ``confidence.method``: categorical token, reuses ``Identifier``.
  ``confidence.calibrated_on``: the ``_on``/``_at`` suffix family in this
  spec (``recorded_at``, ``verified_at``, ``reviewed_at``, ...) is always
  a timestamp, so this is modeled as ``UtcDateTime`` rather than a
  dataset reference.
- ``review.rationale_code``: namespaced code, reuses ``RegisteredName``
  (same family as ``reason_code``).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import ClaimStatus, EvidenceStance, ReviewState
from research_os.hashing import object_hash
from research_os.primitives import (
    ActorRef,
    Classification,
    ExactObjectRef,
    Extensions,
    FrozenCoreModel,
    Identifier,
    RegisteredName,
    Retention,
    Sha256Hex,
    UtcDateTime,
    validate_extensions,
)


class ClaimRef(FrozenCoreModel):
    """Exact reference to one immutable ``Claim`` revision: ``{claim_id, object_hash}``."""

    claim_id: UUID
    object_hash: Sha256Hex


class ClaimEvidenceRef(FrozenCoreModel):
    """``evidence_refs`` item: ``{evidence_id, object_hash, stance}``."""

    evidence_id: UUID
    object_hash: Sha256Hex
    stance: EvidenceStance


class ClaimStatement(FrozenCoreModel):
    """``statement: {subject_ref, predicate, object_ref_or_value, unit?, currency?, modality?}``."""

    subject_ref: ExactObjectRef
    predicate: RegisteredName
    object_ref_or_value: ExactObjectRef | str | float | bool
    unit: str | None = Field(default=None, min_length=1)
    currency: str | None = Field(default=None, min_length=1)
    modality: str | None = Field(default=None, min_length=1)


class ClaimScope(FrozenCoreModel):
    """``scope: {jurisdiction?, audience?, domain}``."""

    jurisdiction: str | None = Field(default=None, min_length=1)
    audience: str | None = Field(default=None, min_length=1)
    domain: Identifier


class ClaimTime(FrozenCoreModel):
    """``time: {valid_from?, valid_to?, recorded_at}``."""

    valid_from: UtcDateTime | None = None
    valid_to: UtcDateTime | None = None
    recorded_at: UtcDateTime

    @model_validator(mode="after")
    def validate_valid_time(self) -> ClaimTime:
        if (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_to <= self.valid_from
        ):
            raise PydanticCustomError(
                "valid_time_not_increasing",
                "valid_to must be strictly later than valid_from",
            )
        return self


class ClaimConfidence(FrozenCoreModel):
    """``confidence: {score, method, calibrated_on?}``."""

    score: float = Field(ge=0, le=1)
    method: Identifier
    calibrated_on: UtcDateTime | None = None


class ClaimReview(FrozenCoreModel):
    """``review: {state, reviewer_ref?, reviewed_at?, rationale_code?}``."""

    state: ReviewState
    reviewer_ref: ActorRef | None = None
    reviewed_at: UtcDateTime | None = None
    rationale_code: RegisteredName | None = None


class ClaimLineage(FrozenCoreModel):
    """``lineage: {run_id, extractor, model_version?, prompt_version?, input_claim_refs}``."""

    run_id: UUID
    extractor: Identifier
    model_version: str | None = Field(default=None, min_length=1)
    prompt_version: str | None = Field(default=None, min_length=1)
    input_claim_refs: tuple[ClaimRef, ...]


class Claim(FrozenCoreModel):
    claim_id: UUID
    claim_family_id: UUID
    supersedes_claim_ref: ClaimRef | None = None
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    statement: ClaimStatement
    scope: ClaimScope
    time: ClaimTime
    status: ClaimStatus
    evidence_refs: tuple[ClaimEvidenceRef, ...]
    confidence: ClaimConfidence
    classification: Classification
    review: ClaimReview
    lineage: ClaimLineage
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_claim(self) -> Claim:
        validate_extensions(self.extensions)

        if (
            self.supersedes_claim_ref is not None
            and self.supersedes_claim_ref.claim_id == self.claim_id
        ):
            raise PydanticCustomError(
                "claim_supersedes_self",
                "supersedes_claim_ref must not reference this claim's own claim_id",
            )

        # NOTE: several section-6 invariants are business rules over a
        # claim family or approval workflow, not a single standalone
        # object ("consequential numeric and regulatory claims require
        # evidence and explicit valid time before approval", "no red
        # claim enters a public ContentObject", "confidence ... cannot
        # override a contradiction or missing mandatory evidence") and are
        # therefore not enforced here.

        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
