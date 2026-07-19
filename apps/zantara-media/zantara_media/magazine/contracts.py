"""Frozen Python mirrors of the Bali Zero Magazine TypeScript contracts."""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_validator,
)

_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_DECIMAL = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")
WireInt = Annotated[StrictInt, Field(le=9_007_199_254_740_991)]


def _wire_number(value: Any) -> Any:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("score must be a JSON number")
    return value


WireNumber = Annotated[float, BeforeValidator(_wire_number)]


class FrozenModel(BaseModel):
    """The common closed, immutable wire-model policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("*", mode="after")
    @classmethod
    def validate_wire_strings(cls, value: Any, info: Any) -> Any:
        if isinstance(value, str):
            return _trimmed(value, info.field_name)
        return value


def _trimmed(value: str, field: str) -> str:
    if not value or value.strip() != value:
        raise ValueError(f"{field} must be a non-empty trimmed string")
    return value


def _timestamp(value: str, field: str) -> str:
    _trimmed(value, field)
    if not _TIMESTAMP.fullmatch(value):
        raise ValueError(f"{field} must be a UTC RFC 3339 timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid timestamp") from exc
    return value


def _unique(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    for value in values:
        _trimmed(value, field)
    if len(set(values)) != len(values):
        raise ValueError(f"{field} contains duplicates")
    return values


def _sha256(value: str, field: str) -> str:
    if not _SHA256.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


class ClaimV1(FrozenModel):
    claim_id: str
    claim_kind: Literal["fact", "numeric", "analysis"]
    normalized_text: str
    numeric_value: str | None
    numeric_unit: str | None
    as_of: str | None
    evidence_ids: tuple[str, ...]
    breaking_gate: Literal["official-primary", "two-independent-root-sources"] | None

    @model_validator(mode="after")
    def validate_claim(self) -> ClaimV1:
        _trimmed(self.claim_id, "claim_id")
        _trimmed(self.normalized_text, "normalized_text")
        _unique(self.evidence_ids, "evidence_ids")
        if self.claim_kind == "numeric":
            if self.numeric_value is None or not _DECIMAL.fullmatch(self.numeric_value):
                raise ValueError("numeric_value must be a normalized decimal string")
        elif self.numeric_value is not None or self.numeric_unit is not None:
            raise ValueError("non-numeric claim cannot contain numeric fields")
        if self.claim_kind in {"fact", "numeric"} and not self.evidence_ids:
            raise ValueError("factual or numeric claim requires evidence")
        if self.as_of is not None and not _DATE.fullmatch(self.as_of):
            raise ValueError("as_of must be an ISO date")
        return self


class EvidenceRefV1(FrozenModel):
    evidence_id: str
    root_source_id: str
    canonical_url: str | None
    publisher: str
    document_citation: str | None
    published_at: str | None
    retrieved_at: str
    source_type: Literal["official", "journalism", "research", "dataset"]
    primary_document_status: Literal["verified", "not-primary", "unresolved"]
    root_resolution_status: Literal["resolved", "ambiguous", "unresolved"]
    independence_verdict: Literal["independent", "dependent", "ambiguous"]
    evidence_note: str | None
    upstream_root_source_ids: tuple[str, ...]
    syndication_group_fingerprint: str
    independence_ruleset_version: str
    independence_reason: str
    counts_toward_breaking: StrictBool

    @model_validator(mode="after")
    def validate_evidence(self) -> EvidenceRefV1:
        for field in (
            "evidence_id",
            "root_source_id",
            "publisher",
            "syndication_group_fingerprint",
            "independence_ruleset_version",
            "independence_reason",
        ):
            _trimmed(getattr(self, field), field)
        _timestamp(self.retrieved_at, "retrieved_at")
        if self.published_at is not None:
            _timestamp(self.published_at, "published_at")
        _unique(self.upstream_root_source_ids, "upstream_root_source_ids")
        if self.canonical_url is not None:
            parsed = urlsplit(self.canonical_url)
            if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
                raise ValueError("canonical_url must be a valid HTTPS URL")
        if self.primary_document_status == "verified" and self.source_type != "official":
            raise ValueError("primary_document_status verified requires an official source")
        if self.counts_toward_breaking and (
            self.root_resolution_status != "resolved"
            or self.independence_verdict != "independent"
        ):
            raise ValueError("counts_toward_breaking contradicts lineage verdict")
        return self


class ScoreComponentsV1(FrozenModel):
    editorial: WireNumber
    impact: WireNumber
    freshness: WireNumber
    evidence: WireNumber
    diversity: WireNumber

    @field_validator("editorial", "impact", "freshness", "evidence", "diversity")
    @classmethod
    def validate_score(cls, value: float) -> float:
        if isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("score must be a finite number between 0 and 1")
        return value


class StoryVersionV1(FrozenModel):
    story_id: str
    version: WireInt = Field(ge=1)
    expected_current_version: WireInt = Field(ge=0)
    slug: str
    language: str
    domain: Literal["immigration", "company", "tax", "property", "compliance", "general"]
    severity: Literal["low", "medium", "high", "critical"]
    lifecycle_state: Literal["developing", "verified", "amended", "superseded"]
    first_seen_at: str
    event_occurred_at: str | None
    updated_at: str
    title: str
    deck: str
    summary: str
    why_it_matters: str
    curiosity_text: str | None
    score_components: ScoreComponentsV1
    claims: tuple[ClaimV1, ...]
    evidence_refs: tuple[EvidenceRefV1, ...]
    contributing_system_ids: tuple[str, ...]
    coverage_state: Literal["full", "partial"]
    confidence: Literal["low", "medium", "high"]
    asset_digests: tuple[str, ...]
    adapter_version: str
    ruleset_version: str

    @model_validator(mode="after")
    def validate_story(self) -> StoryVersionV1:
        if self.version != self.expected_current_version + 1:
            raise ValueError("story version must equal expected_current_version + 1")
        for field in (
            "story_id",
            "slug",
            "language",
            "title",
            "deck",
            "summary",
            "why_it_matters",
            "adapter_version",
            "ruleset_version",
        ):
            _trimmed(getattr(self, field), field)
        _timestamp(self.first_seen_at, "first_seen_at")
        _timestamp(self.updated_at, "updated_at")
        if self.event_occurred_at is not None:
            _timestamp(self.event_occurred_at, "event_occurred_at")
        _unique(self.contributing_system_ids, "contributing_system_ids")
        for digest in self.asset_digests:
            _sha256(digest, "asset_digests")
        evidence_ids = [item.evidence_id for item in self.evidence_refs]
        claim_ids = [item.claim_id for item in self.claims]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("duplicate evidence_id")
        if len(set(claim_ids)) != len(claim_ids):
            raise ValueError("duplicate claim_id")
        evidence_set = set(evidence_ids)
        for claim in self.claims:
            unknown = set(claim.evidence_ids) - evidence_set
            if unknown:
                raise ValueError(f"unknown evidence_id {sorted(unknown)[0]}")
        return self


def _independent_root_count(items: list[EvidenceRefV1]) -> int:
    eligible = [
        item
        for item in items
        if item.counts_toward_breaking
        and item.root_resolution_status == "resolved"
        and item.independence_verdict == "independent"
    ]
    parent = list(range(len(eligible)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for left, left_item in enumerate(eligible):
        left_lineage = {left_item.root_source_id, *left_item.upstream_root_source_ids}
        for right in range(left + 1, len(eligible)):
            right_item = eligible[right]
            right_lineage = {right_item.root_source_id, *right_item.upstream_root_source_ids}
            if (
                left_item.syndication_group_fingerprint
                == right_item.syndication_group_fingerprint
                or left_lineage & right_lineage
            ):
                left_root, right_root = find(left), find(right)
                if left_root != right_root:
                    parent[right_root] = left_root
    return len({find(index) for index in range(len(eligible))})


def validate_breaking_story(story: StoryVersionV1) -> None:
    if story.severity not in {"high", "critical"}:
        raise ValueError("Breaking story severity must be high or critical")
    by_id = {item.evidence_id: item for item in story.evidence_refs}
    for claim in story.claims:
        if claim.claim_kind == "analysis":
            continue
        if claim.breaking_gate is None:
            raise ValueError(f"claim {claim.claim_id} requires a valid Breaking gate")
        supporting = [by_id[item] for item in claim.evidence_ids]
        if claim.breaking_gate == "official-primary":
            valid = any(
                item.source_type == "official"
                and item.primary_document_status == "verified"
                and item.root_resolution_status == "resolved"
                and item.independence_verdict == "independent"
                and item.counts_toward_breaking
                and (item.canonical_url is not None or item.document_citation is not None)
                for item in supporting
            )
            if not valid:
                raise ValueError(f"claim {claim.claim_id} lacks a resolvable official primary document")
        elif _independent_root_count(supporting) < 2:
            raise ValueError(f"claim {claim.claim_id} requires two independent resolved root sources")


class StoryPacketV1(FrozenModel):
    schema_version: Literal["story.v1"]
    packet_id: str
    publication_target: Literal["breaking"]
    expected_breaking_revision: WireInt = Field(ge=0)
    publication_state: Literal["building"]
    verified_at: str
    story: StoryVersionV1

    @model_validator(mode="after")
    def validate_packet(self) -> StoryPacketV1:
        _trimmed(self.packet_id, "packet_id")
        _timestamp(self.verified_at, "verified_at")
        validate_breaking_story(self.story)
        return self


class EditionPlacementV1(FrozenModel):
    story_id: str
    version: WireInt = Field(ge=1)
    section: Literal["immigration", "company", "tax", "property", "compliance", "general"]
    order: WireInt = Field(ge=1)
    lead: StrictBool


class EditionPacketV1(FrozenModel):
    schema_version: Literal["edition.v1"]
    packet_id: str
    editor_version: str
    ruleset_version: str
    edition_date: str
    edition_revision: WireInt = Field(ge=1)
    expected_current_revision: WireInt = Field(ge=0)
    expected_breaking_revision: WireInt = Field(ge=0)
    edition_kind: Literal["standard", "quiet"]
    publication_state: Literal["building"]
    coverage_state: Literal["complete", "partial"]
    readiness_cutoff: str
    verified_at: str
    collector_run_ids: tuple[str, ...]
    stories: tuple[StoryVersionV1, ...]
    placements: tuple[EditionPlacementV1, ...]
    breaking_story_ids: tuple[str, ...]
    referenced_claim_ids: tuple[str, ...]
    referenced_evidence_ids: tuple[str, ...]
    asset_digests: tuple[str, ...]
    coverage_gaps: tuple[str, ...]
    reader_notices: tuple[str, ...]

    @model_validator(mode="after")
    def validate_edition(self) -> EditionPacketV1:
        if self.edition_revision != self.expected_current_revision + 1:
            raise ValueError("edition_revision must equal expected_current_revision + 1")
        if not _DATE.fullmatch(self.edition_date):
            raise ValueError("edition_date must be an ISO date")
        _timestamp(self.readiness_cutoff, "readiness_cutoff")
        _timestamp(self.verified_at, "verified_at")
        story_ids = [item.story_id for item in self.stories]
        if len(set(story_ids)) != len(story_ids):
            raise ValueError("edition packet contains duplicate story_id")
        story_keys = {(item.story_id, item.version) for item in self.stories}
        lead_count = sum(item.lead for item in self.placements)
        if self.edition_kind == "standard" and lead_count != 1:
            raise ValueError("standard edition must declare exactly one lead")
        if self.edition_kind == "quiet" and lead_count:
            raise ValueError("quiet edition must not declare a lead")
        for placement in self.placements:
            if (placement.story_id, placement.version) not in story_keys:
                raise ValueError("edition placement references unknown story version")
        by_story = {item.story_id: item for item in self.stories}
        for story_id in _unique(self.breaking_story_ids, "breaking_story_ids"):
            if story_id not in by_story:
                raise ValueError(f"Breaking list references unknown story {story_id}")
            validate_breaking_story(by_story[story_id])
        expected_claims = {claim.claim_id for story in self.stories for claim in story.claims}
        expected_evidence = {
            evidence.evidence_id for story in self.stories for evidence in story.evidence_refs
        }
        expected_assets = {digest for story in self.stories for digest in story.asset_digests}
        checks: tuple[tuple[str, tuple[str, ...], set[str]], ...] = (
            ("referenced_claim_ids", self.referenced_claim_ids, expected_claims),
            ("referenced_evidence_ids", self.referenced_evidence_ids, expected_evidence),
            ("asset_digests", self.asset_digests, expected_assets),
        )
        for field, declared, actual in checks:
            if len(declared) != len(actual) or set(declared) != actual:
                raise ValueError(f"{field} must exactly match embedded story references")
        for field in ("collector_run_ids", "coverage_gaps", "reader_notices"):
            _unique(getattr(self, field), field)
        return self


class CollectorRunProjectionV1(FrozenModel):
    schema_version: Literal["collector-run.v1"]
    run_id: str
    system_id: str
    collector_id: str
    started_at: str
    completed_at: str
    status: Literal["healthy", "delayed", "degraded", "unavailable", "unknown"]
    freshness: Literal["fresh", "delayed", "archived"]
    items_seen: WireInt = Field(ge=0)
    items_eligible: WireInt = Field(ge=0)
    source_count: WireInt = Field(ge=0)
    unreachable_source_count: WireInt = Field(ge=0)
    watermark: str
    verified_at: str

    @model_validator(mode="after")
    def validate_run(self) -> CollectorRunProjectionV1:
        started = _timestamp(self.started_at, "started_at")
        completed = _timestamp(self.completed_at, "completed_at")
        _timestamp(self.verified_at, "verified_at")
        if datetime.fromisoformat(completed.replace("Z", "+00:00")) < datetime.fromisoformat(
            started.replace("Z", "+00:00")
        ):
            raise ValueError("completed_at precedes started_at")
        if self.items_eligible > self.items_seen:
            raise ValueError("items_eligible exceeds items_seen")
        if self.unreachable_source_count > self.source_count:
            raise ValueError("unreachable_source_count exceeds source_count")
        return self


class AssetProvenanceV2(FrozenModel):
    """Sanitized provenance supplied before source-derived fields are known."""

    packet_id: str
    asset_id: str
    captured_at: str
    alt_text: str
    source: str
    source_url: str | None
    rights_basis: Literal["internal-owned", "licensed", "public-domain", "official-use", "generated"]
    rights_status: Literal["approved"]
    usage_status: Literal["approved"]
    dlp_status: Literal["passed"]
    sanitization_status: Literal["passed"]
    perceptual_dedup_status: Literal["unique", "intentional-reuse"]

    @model_validator(mode="after")
    def validate_provenance(self) -> AssetProvenanceV2:
        _timestamp(self.captured_at, "captured_at")
        if self.source_url is not None:
            parsed = urlsplit(self.source_url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username
                or parsed.password
                or parsed.fragment
            ):
                raise ValueError("source_url must be a public HTTP URL")
        return self


class AssetUploadMetadataV2(AssetProvenanceV2):
    schema_version: Literal["asset-upload.v2"]
    source_sha256: str
    source_byte_count: WireInt = Field(ge=1, le=12 * 1024 * 1024)
    source_mime_type: Literal["image/jpeg", "image/png", "image/webp"]
    source_width: WireInt = Field(ge=1, le=8192)
    source_height: WireInt = Field(ge=1, le=8192)

    @model_validator(mode="after")
    def validate_asset(self) -> AssetUploadMetadataV2:
        _sha256(self.source_sha256, "source_sha256")
        _timestamp(self.captured_at, "captured_at")
        if self.source_width * self.source_height > 40_000_000:
            raise ValueError("asset decoded pixel count exceeds limit")
        if self.source_url is not None:
            parsed = urlsplit(self.source_url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username
                or parsed.password
                or parsed.fragment
            ):
                raise ValueError("source_url must be a public HTTP URL")
        return self


class AssetUploadResponseV2(FrozenModel):
    """Canonical publication digest returned by the AssetUploadV2 endpoint."""

    ok: StrictBool | None = None
    status: Literal["created", "replay"] | None = None
    asset_id: str | None = None
    source_sha256: str
    canonical_sha256: str
    canonical_mime_type: Literal["image/png"]
    canonical_byte_count: WireInt | None = Field(default=None, ge=1)
    width: WireInt | None = Field(default=None, ge=1)
    height: WireInt | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_response(self) -> AssetUploadResponseV2:
        _sha256(self.source_sha256, "source_sha256")
        _sha256(self.canonical_sha256, "canonical_sha256")
        return self


def json_mapping(model: BaseModel) -> dict[str, Any]:
    """Return a JSON-mode dictionary without weakening model closure."""

    return model.model_dump(mode="json")
