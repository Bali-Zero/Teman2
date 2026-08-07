"""Typed public API contract for ``POST /api/visa-oracle/evaluate``.

The pure engine contracts in :mod:`models` intentionally contain no HTTP
envelope or UI projection.  This module is the single executable contract
for that boundary: a backward-compatible request extending
``ApplicantFacts`` with conservative review disclosures, plus the response
envelope rendered by the Visa Oracle frontend.

``disclosed_review_flags`` is deliberately *monotone*: the orchestration
layer may use it only to replace any legal outcome with
``HUMAN_REVIEW_REQUIRED``.  It is not RulePack input and can never add,
remove, rank, or support a visa candidate.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.services.visa_engine.enums import SourceAuthorityType, SourceStatus
from backend.services.visa_engine.models import (
    ApplicantFacts,
    Decision,
    ExtensionPolicy,
    ProductCode,
    ProductNames,
    ReasonCode,
    SourceLocator,
    StayPolicy,
)

_PUBLIC_SOURCE_HOSTS = frozenset(
    {
        "www.imigrasi.go.id",
        "evisa.imigrasi.go.id",
        "peraturan.bpk.go.id",
        "kemenimipas.go.id",
        "www.peraturan.go.id",
        "kanwilsultra.imigrasi.go.id",
        # Synthetic TEST-only policy fixture. It is never a legal primary
        # authority because its authority_type is BALI_ZERO_POLICY.
        "internal.balizero.dev",
    }
)

_PRIMARY_SOURCE_AUTHORITY_TYPES = frozenset(
    {
        SourceAuthorityType.PRIMARY_LAW,
        SourceAuthorityType.IMPLEMENTING_REGULATION,
        SourceAuthorityType.OFFICIAL_PORTAL,
        SourceAuthorityType.OFFICIAL_CIRCULAR,
    }
)

_PRIMARY_SOURCE_HOSTS = frozenset(
    {
        "www.imigrasi.go.id",
        "evisa.imigrasi.go.id",
        "peraturan.bpk.go.id",
        "kemenimipas.go.id",
        "www.peraturan.go.id",
    }
)


class DisclosedReviewFlag(str, Enum):
    """UI disclosures not representable by the signed RulePack vocabulary.

    These are abstention inputs, never eligibility facts.  Keeping them in a
    separate closed enum prevents a free-text field from becoming an
    accidental legal-rule channel.
    """

    CRIMINAL_RECORD = "CRIMINAL_RECORD"
    HEALTH_CONCERN = "HEALTH_CONCERN"
    PRIOR_VISA_REFUSAL = "PRIOR_VISA_REFUSAL"
    NOT_CERTAIN = "NOT_CERTAIN"
    PEP_OR_SANCTIONS = "PEP_OR_SANCTIONS"
    SOURCE_OF_FUNDS_UNCLEAR = "SOURCE_OF_FUNDS_UNCLEAR"
    DIPLOMATIC_PASSPORT = "DIPLOMATIC_PASSPORT"
    AMBIGUOUS_SPONSOR = "AMBIGUOUS_SPONSOR"
    ACTIVITY_BOUNDARY = "ACTIVITY_BOUNDARY"
    MULTI_PURPOSE_TRIP = "MULTI_PURPOSE_TRIP"
    CONFLICTING_IMMIGRATION_STATUS = "CONFLICTING_IMMIGRATION_STATUS"


class VisaOracleEvaluateRequest(ApplicantFacts):
    """Canonical facts plus conservative, non-eligibility review flags.

    The extra field defaults to the empty tuple, so every existing
    ``ApplicantFacts`` request remains wire-compatible.
    """

    disclosed_review_flags: tuple[DisclosedReviewFlag, ...] = Field(
        default=(), max_length=len(DisclosedReviewFlag)
    )

    @field_validator("disclosed_review_flags")
    @classmethod
    def _canonical_review_flags(
        cls, value: tuple[DisclosedReviewFlag, ...]
    ) -> tuple[DisclosedReviewFlag, ...]:
        if len(set(value)) != len(value):
            raise ValueError("disclosed_review_flags must have unique items")
        return tuple(sorted(value, key=lambda flag: flag.value))

    def applicant_facts(self) -> ApplicantFacts:
        """Return the canonical applicant facts without deriving new knowledge.

        The public boundary must preserve every UNKNOWN exactly. Cross-fact
        contradictions may add a review flag, but absence from Indonesia is
        not evidence that a disclosed overstay value is zero.
        """

        return ApplicantFacts(
            schema_version=self.schema_version,
            assessment_id=self.assessment_id,
            collected_at=self.collected_at,
            facts=self.facts,
        )

    def effective_review_flags(self) -> tuple[DisclosedReviewFlag, ...]:
        """Return caller disclosures plus deterministic cross-fact conflicts."""

        flags = set(self.disclosed_review_flags)
        currently_in_indonesia = self.facts.immigration_currently_in_indonesia
        overstay_days = self.facts.immigration_overstay_days
        if (
            currently_in_indonesia.status == "KNOWN"
            and currently_in_indonesia.value is False
            and overstay_days.status == "KNOWN"
            and overstay_days.value > 0
        ):
            flags.add(DisclosedReviewFlag.CONFLICTING_IMMIGRATION_STATUS)
        return tuple(sorted(flags, key=lambda flag: flag.value))


class EvaluateResponseMode(str, Enum):
    CURATED = "CURATED"
    ENGINE = "ENGINE"


class SourceFreshnessStatus(str, Enum):
    """External re-verification state under an explicit freshness policy."""

    CURRENT = "CURRENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class SourceApplicabilityStatus(str, Enum):
    """Signed bitemporal/status applicability, distinct from freshness."""

    APPLICABLE = "APPLICABLE"
    NOT_YET_EFFECTIVE = "NOT_YET_EFFECTIVE"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("datetime must be timezone-aware UTC")
    return value


class SourceFreshnessDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: SourceFreshnessStatus
    reason_code: ReasonCode
    evaluated_at: datetime
    verified_at: datetime
    max_age_seconds: int | None = Field(default=None, ge=1, strict=True)

    @field_validator("evaluated_at", "verified_at")
    @classmethod
    def _check_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)


class SourceApplicabilityDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: SourceApplicabilityStatus
    effective_at: datetime
    observed_at: datetime

    @field_validator("effective_at", "observed_at")
    @classmethod
    def _check_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)


class SourceRecordDTO(BaseModel):
    """Resolved source projection required by the public outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_record_id: uuid.UUID
    source_key: str
    title: str
    publisher: str
    authority_type: SourceAuthorityType
    is_primary_authority: bool
    status: SourceStatus
    document_number: str | None
    canonical_url: str
    locators: tuple[SourceLocator, ...]
    legal_period_from: datetime
    legal_period_to: datetime | None
    recorded_period_from: datetime
    retrieved_at: datetime
    verified_at: datetime
    applicability: SourceApplicabilityDTO
    freshness: SourceFreshnessDTO

    @field_validator(
        "legal_period_from",
        "legal_period_to",
        "recorded_period_from",
        "retrieved_at",
        "verified_at",
    )
    @classmethod
    def _check_utc(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _require_utc(value)

    @field_validator("canonical_url")
    @classmethod
    def _check_public_source_url(cls, value: str) -> str:
        try:
            parsed = urlsplit(value)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("canonical_url must be an approved HTTPS source") from exc
        if not (
            parsed.scheme.lower() == "https"
            and parsed.hostname is not None
            and parsed.hostname.lower() in _PUBLIC_SOURCE_HOSTS
            and parsed.username is None
            and parsed.password is None
            and port is None
        ):
            raise ValueError("canonical_url must be an approved HTTPS source")
        return value

    @model_validator(mode="after")
    def _derive_primary_authority(self) -> SourceRecordDTO:
        """Prevent callers from promoting a non-primary source in the DTO.

        The projection flag is redundant by design for frontend ergonomics,
        so it must be exactly derivable from the closed authority vocabulary
        and pinned official host set. In particular, the TEST-only Bali Zero
        policy host can never authenticate an operational availability claim.
        """

        hostname = urlsplit(self.canonical_url).hostname
        expected = (
            self.authority_type in _PRIMARY_SOURCE_AUTHORITY_TYPES
            and hostname is not None
            and hostname.lower() in _PRIMARY_SOURCE_HOSTS
        )
        if self.is_primary_authority is not expected:
            raise ValueError("is_primary_authority must match authority type and official host")
        return self


class AvailabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class AvailabilityAssessmentDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: AvailabilityStatus
    reason_code: ReasonCode
    observed_at: datetime
    source_refs: tuple[uuid.UUID, ...] = Field(default=())

    @field_validator("observed_at")
    @classmethod
    def _check_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)

    @field_validator("source_refs")
    @classmethod
    def _unique_source_refs(cls, value: tuple[uuid.UUID, ...]) -> tuple[uuid.UUID, ...]:
        if len(set(value)) != len(value):
            raise ValueError("source_refs must have unique items")
        return value

    @model_validator(mode="after")
    def _require_evidence_for_claim(self) -> AvailabilityAssessmentDTO:
        if self.status is not AvailabilityStatus.UNKNOWN and not self.source_refs:
            raise ValueError("non-UNKNOWN availability requires source_refs")
        return self


class CandidateAvailabilityDTO(BaseModel):
    """Three product concepts that must never be collapsed into one flag."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    legal_eligibility: Literal["SUPPORTED"]
    operational_availability: AvailabilityAssessmentDTO
    bali_zero_service_availability: AvailabilityAssessmentDTO


class PricingAvailabilityStatus(str, Enum):
    """Whether one exact, all-inclusive Bali Zero quote can be rendered."""

    AVAILABLE = "AVAILABLE"
    CONTACT_REQUIRED = "CONTACT_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class CandidatePricingDTO(BaseModel):
    """Pricing status kept separate from all three eligibility/availability axes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: PricingAvailabilityStatus
    reason_code: ReasonCode
    evaluated_at: datetime
    catalog_last_updated: date | None
    catalog_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    row_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @field_validator("evaluated_at")
    @classmethod
    def _check_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)

    @model_validator(mode="after")
    def _check_hash_chain(self) -> CandidatePricingDTO:
        if self.row_sha256 is not None and self.catalog_sha256 is None:
            raise ValueError("a pricing row hash requires its catalogue hash")
        if self.status is PricingAvailabilityStatus.AVAILABLE and (
            self.catalog_last_updated is None
            or self.catalog_sha256 is None
            or self.row_sha256 is None
        ):
            raise ValueError("AVAILABLE pricing requires complete catalogue provenance")
        return self


class CandidateStayPolicyDTO(BaseModel):
    """Legal stay/extension policy, never a processing-time estimate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stay: StayPolicy
    extension: ExtensionPolicy


class DocumentationStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNKNOWN = "UNKNOWN"


class CandidateDocumentationDTO(BaseModel):
    """Verified document content, with UNKNOWN distinct from a verified empty list."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: DocumentationStatus
    reason_code: ReasonCode
    observed_at: datetime
    requirements: tuple[ProductNames, ...]
    checklist: tuple[ProductNames, ...]

    @field_validator("observed_at")
    @classmethod
    def _check_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)

    @model_validator(mode="after")
    def _unknown_has_no_items(self) -> CandidateDocumentationDTO:
        if self.status is DocumentationStatus.UNKNOWN and (self.requirements or self.checklist):
            raise ValueError("UNKNOWN documentation cannot carry unverified items")
        return self


class ProcessingTimelineStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNKNOWN = "UNKNOWN"


class CandidateProcessingTimelineDTO(BaseModel):
    """Operational processing estimate anchored to a disclosed calendar date."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ProcessingTimelineStatus
    reason_code: ReasonCode
    observed_at: datetime
    anchor_date: date | None
    estimated_completion_from: date | None
    estimated_completion_to: date | None

    @field_validator("observed_at")
    @classmethod
    def _check_utc(cls, value: datetime) -> datetime:
        return _require_utc(value)

    @model_validator(mode="after")
    def _check_status_dates(self) -> CandidateProcessingTimelineDTO:
        dates = (
            self.anchor_date,
            self.estimated_completion_from,
            self.estimated_completion_to,
        )
        if self.status is ProcessingTimelineStatus.UNKNOWN:
            if any(value is not None for value in dates):
                raise ValueError("UNKNOWN processing timeline cannot carry dates")
            return self
        if any(value is None for value in dates):
            raise ValueError("AVAILABLE processing timeline requires all dates")
        assert self.anchor_date is not None
        assert self.estimated_completion_from is not None
        assert self.estimated_completion_to is not None
        if self.estimated_completion_from < self.anchor_date:
            raise ValueError("processing estimate cannot start before its anchor")
        if self.estimated_completion_to < self.estimated_completion_from:
            raise ValueError("processing estimate end cannot precede its start")
        return self


class CandidateDisplayDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    product_code: ProductCode
    product_version_id: uuid.UUID
    rank: int = Field(ge=1, le=256, strict=True)
    name: ProductNames
    tagline: ProductNames | None
    stay_policy: CandidateStayPolicyDTO
    documentation: CandidateDocumentationDTO
    processing_timeline: CandidateProcessingTimelineDTO
    availability: CandidateAvailabilityDTO
    pricing: CandidatePricingDTO


class VisaOracleDisplayDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    candidates: tuple[CandidateDisplayDTO, ...] = Field(max_length=256)


class VisaOracleEvaluateResponse(BaseModel):
    """Stable response envelope consumed by the frontend engine adapter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: EvaluateResponseMode
    decision: Decision
    sources: tuple[SourceRecordDTO, ...]
    display: VisaOracleDisplayDTO

    @model_validator(mode="after")
    def _check_projection_integrity(self) -> VisaOracleEvaluateResponse:
        decision_ids = tuple(candidate.product_version_id for candidate in self.decision.candidates)
        display_ids = tuple(candidate.product_version_id for candidate in self.display.candidates)
        if decision_ids != display_ids:
            raise ValueError("display candidates must exactly match decision candidate order")

        source_ids = tuple(source.source_record_id for source in self.sources)
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("sources must have unique source_record_id values")
        sources_by_id = {source.source_record_id: source for source in self.sources}

        referenced: set[uuid.UUID] = set()
        for candidate in self.decision.candidates:
            referenced.update(candidate.source_refs)
        for reason in (
            *self.decision.review_reasons,
            *self.decision.no_path_reasons,
            *self.decision.notices,
        ):
            referenced.update(reason.source_refs)
        for candidate in self.display.candidates:
            referenced.update(candidate.availability.operational_availability.source_refs)
            referenced.update(candidate.availability.bali_zero_service_availability.source_refs)
        if not referenced.issubset(set(source_ids)):
            raise ValueError("every decision and availability source_ref must resolve in sources")

        for source in self.sources:
            if source.freshness.verified_at != source.verified_at:
                raise ValueError("source freshness verified_at must match source verified_at")
            if source.freshness.evaluated_at != self.decision.observed_at:
                raise ValueError("source freshness evaluated_at must match decision observed_at")
            if (
                source.applicability.effective_at != self.decision.effective_at
                or source.applicability.observed_at != self.decision.observed_at
            ):
                raise ValueError("source applicability clocks must match the decision clocks")
            if source.recorded_period_from > self.decision.observed_at:
                raise ValueError("source cannot be recorded after the decision observed_at")
            if (
                source.recorded_period_from > source.retrieved_at
                or source.retrieved_at > source.verified_at
                or source.verified_at > self.decision.observed_at
            ):
                raise ValueError("source evidence clocks must not be in the future")
            if source.applicability.status is SourceApplicabilityStatus.APPLICABLE and not (
                source.legal_period_from <= self.decision.effective_at
                and (
                    source.legal_period_to is None
                    or self.decision.effective_at < source.legal_period_to
                )
            ):
                raise ValueError("APPLICABLE source legal period must contain effective_at")

        for candidate in self.display.candidates:
            assessments = (
                candidate.availability.operational_availability,
                candidate.availability.bali_zero_service_availability,
            )
            for assessment in assessments:
                if assessment.status is AvailabilityStatus.UNKNOWN:
                    continue
                for source_ref in assessment.source_refs:
                    source = sources_by_id[source_ref]
                    if (
                        source.status is not SourceStatus.VERIFIED
                        or not source.is_primary_authority
                        or source.applicability.status is not SourceApplicabilityStatus.APPLICABLE
                        or source.freshness.status is not SourceFreshnessStatus.CURRENT
                    ):
                        raise ValueError(
                            "availability claims require current, applicable primary sources"
                        )

        quotes_by_product = {quote.product_version_id: quote for quote in self.decision.quotes}
        if len(quotes_by_product) != len(self.decision.quotes):
            raise ValueError("decision quotes must have unique product_version_id values")
        for candidate in self.display.candidates:
            quote = quotes_by_product.get(candidate.product_version_id)
            if quote is None:
                if candidate.pricing.status not in (
                    PricingAvailabilityStatus.CONTACT_REQUIRED,
                    PricingAvailabilityStatus.UNKNOWN,
                ):
                    raise ValueError("a candidate without a quote cannot claim a price")
                continue
            if candidate.pricing.status.value != quote.status:
                raise ValueError("display pricing status must match the decision quote")
            if candidate.pricing.reason_code != quote.reason_code:
                raise ValueError("display pricing reason must match the decision quote")
        return self


class VisaOracleErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    detail: str


class VisaOracleValidationErrorItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    loc: tuple[str, ...]
    type: str
    msg: str


class VisaOracleValidationErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    detail: tuple[VisaOracleValidationErrorItem, ...]


__all__ = [
    "AvailabilityAssessmentDTO",
    "AvailabilityStatus",
    "CandidateAvailabilityDTO",
    "CandidateDisplayDTO",
    "CandidateDocumentationDTO",
    "CandidatePricingDTO",
    "CandidateProcessingTimelineDTO",
    "CandidateStayPolicyDTO",
    "DisclosedReviewFlag",
    "DocumentationStatus",
    "EvaluateResponseMode",
    "PricingAvailabilityStatus",
    "ProcessingTimelineStatus",
    "SourceApplicabilityDTO",
    "SourceApplicabilityStatus",
    "SourceFreshnessDTO",
    "SourceFreshnessStatus",
    "SourceRecordDTO",
    "VisaOracleDisplayDTO",
    "VisaOracleErrorResponse",
    "VisaOracleEvaluateRequest",
    "VisaOracleEvaluateResponse",
    "VisaOracleValidationErrorItem",
    "VisaOracleValidationErrorResponse",
]
