"""Immutable Evidence contract from frozen CONTRACTS.md section 5.

Purpose (verbatim): "an addressable source unit supporting or contradicting
a claim."

Interpretation notes (fields section 5 names but does not type further):

- ``document_id``: section 5 calls it "stable identity of the
  source-document family" -- deliberately without the word "namespaced"
  that ``family_id`` fields get elsewhere -- so it is modeled as an
  opaque non-empty string, not ``RegisteredName``.
- ``document_version_id``: "immutable source revision identity" -- an
  opaque non-empty string (not itself declared ``sha256`` in section 5,
  unlike ``document_content_hash``).
- ``source_tier``: section 5 calls this "registered enum value", which is
  NOT one of the closed enums in section 3's registry table -- it reuses
  the open, namespaced-registry ``RegisteredName`` primitive, the same
  reading applied to ``event_type``/``reason_code`` elsewhere.
- ``source_span.{start,end,page}``: modeled as non-negative integer
  offsets; ``quote_hash``: a content hash, so ``sha256`` per section 2.
- ``provenance.extractor``: a categorical producer-like token, modeled as
  ``Identifier`` (matching ``Producer.name``'s treatment elsewhere).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from research_os.enums import EvidenceStance, ReviewState, RiskClass, Sensitivity
from research_os.hashing import object_hash
from research_os.models.intel_event import EventRef
from research_os.primitives import (
    Extensions,
    FrozenCoreModel,
    Identifier,
    RegisteredName,
    Retention,
    Sha256Hex,
    UtcDateTime,
    validate_extensions,
)


class EvidenceRef(FrozenCoreModel):
    """Exact reference to one immutable ``Evidence`` revision: ``{evidence_id, object_hash}``."""

    evidence_id: UUID
    object_hash: Sha256Hex


class SourceSpan(FrozenCoreModel):
    """``source_span: {locator, start?, end?, page?, section?, quote_hash}``."""

    locator: str = Field(min_length=1)
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    page: int | None = Field(default=None, ge=0)
    section: str | None = Field(default=None, min_length=1)
    quote_hash: Sha256Hex

    @model_validator(mode="after")
    def validate_span_bounds(self) -> SourceSpan:
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise PydanticCustomError(
                "source_span_end_not_after_start",
                "source_span.end must be strictly greater than source_span.start",
            )
        return self


class EvidenceTimes(FrozenCoreModel):
    """``times: {published_at?, observed_at, valid_from?, valid_to?, recorded_at}``."""

    published_at: UtcDateTime | None = None
    observed_at: UtcDateTime
    valid_from: UtcDateTime | None = None
    valid_to: UtcDateTime | None = None
    recorded_at: UtcDateTime

    @model_validator(mode="after")
    def validate_valid_time(self) -> EvidenceTimes:
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


class Provenance(FrozenCoreModel):
    """``provenance: {extractor, extractor_version, run_id, extraction_input_hash}``."""

    extractor: Identifier
    extractor_version: str = Field(min_length=1)
    run_id: UUID
    extraction_input_hash: Sha256Hex


class EvidenceClassification(FrozenCoreModel):
    """``classification: {risk_class, sensitivity, rights}`` -- ``rights`` is required here."""

    risk_class: RiskClass
    sensitivity: Sensitivity
    rights: str = Field(min_length=1)


class Evidence(FrozenCoreModel):
    evidence_id: UUID
    evidence_family_id: RegisteredName
    supersedes_evidence_ref: EvidenceRef | None = None
    contract_version: Literal["research-os/v1.0.0"]
    tenant: Literal["bali-zero"]
    source_event_ref: EventRef
    document_id: str = Field(min_length=1)
    document_version_id: str = Field(min_length=1)
    document_content_hash: Sha256Hex
    source_span: SourceSpan
    source_tier: RegisteredName
    stance: EvidenceStance
    times: EvidenceTimes
    provenance: Provenance
    classification: EvidenceClassification
    review_state: ReviewState
    retention: Retention
    object_hash: Sha256Hex
    extensions: Extensions | None = None

    @model_validator(mode="after")
    def validate_evidence(self) -> Evidence:
        validate_extensions(self.extensions)

        if (
            self.supersedes_evidence_ref is not None
            and self.supersedes_evidence_ref.evidence_id == self.evidence_id
        ):
            raise PydanticCustomError(
                "evidence_supersedes_self",
                "supersedes_evidence_ref must not reference this evidence's own evidence_id",
            )

        # NOTE: cross-object family-graph invariants ("evidence_family_id
        # maps to ObjectSuccessorEdge.family_id", "forks or stale
        # predecessors quarantine the family") are enforced by
        # research_os.graph over a collection, not on one standalone object.

        expected = object_hash(self)
        if self.object_hash != expected:
            raise PydanticCustomError(
                "object_hash_mismatch",
                "object_hash does not match the canonical object",
            )
        return self
