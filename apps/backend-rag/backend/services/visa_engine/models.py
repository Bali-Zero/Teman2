"""Frozen Pydantic v2 contracts for the Visa Oracle v2 rule engine.

Source: ``research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
concretization.md`` §1 (module layout, ``models.py``) and §2 (JSON Schema
2020-12 contract — every model below mirrors one ``$defs`` entry, field for
field, including the ``allOf``/``if``/``then`` conditionals that are cheap,
single-object, always-true structural rules).

PR1 scope (deliberately narrower than the spec's full ``models.py`` class
list, per the PR1 task brief): ``RulePack``, ``Rule``, the ``Condition`` AST
(re-exported from ``ast.py``), ``SourceRecord`` (the bitemporal metadata
object — ``legal_period``/``recorded_period``), and their structural
supporting types (``TimeRange``, ``RuleEffect`` variants, ``RulePackPayload``,
``ProtectedHeader``, ``VisaProductVersion``). ``VisaProductVersion`` is
included even though it is not in the PR1 brief's explicit model list,
because spec §2's ``RulePackPayload.products`` is a required, non-empty
array of exactly this type — a ``RulePack`` model that is "exactly per spec
§2's JSON Schema" cannot omit it.

Deferred to PR2+ (do not exist in this module): ``ApplicantFacts``,
``Decision``, ``PriceQuote``, ``CandidateDecision``/``Candidate``,
``ConsentEvent``, ``EvaluationContext``. None of PR1's modules (fact_registry,
ast, compiler, schema_export) need them — see each module's own docstring
for why. ``FactDefinition`` (named in the PR1 brief) is represented as
``fact_registry.FactSpec`` instead — see that module's docstring for the
resolved naming/placement ambiguity.

All models are frozen (``model_config = ConfigDict(frozen=True,
extra="forbid")``) — a RulePack, once parsed, is an immutable value; nothing
downstream may quietly attach an unexpected field.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.services.visa_engine.ast import Condition
from backend.services.visa_engine.enums import (
    ClockAnchor,
    EntryCount,
    Environment,
    OnUnknownAction,
    RuleEffectType,
    RuleScope,
    RuleStage,
    SourceAuthorityType,
    SourceLocatorKind,
    SourceStatus,
    SponsorType,
    StayPolicyKind,
    VisaProductCategory,
    VisaProductStatus,
    VisaPurpose,
)
from backend.services.visa_engine.fact_registry import FactPath

# ---------------------------------------------------------------------------
# Primitive $defs (spec §2) — reusable field types
# ---------------------------------------------------------------------------

#: ``$defs/Identifier``
IDENTIFIER_PATTERN = r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"
Identifier = Annotated[str, Field(pattern=IDENTIFIER_PATTERN, min_length=1, max_length=128)]

#: ``$defs/ReasonCode``
REASON_CODE_PATTERN = r"^[A-Z][A-Z0-9_]{0,127}$"
ReasonCode = Annotated[str, Field(pattern=REASON_CODE_PATTERN, min_length=1, max_length=128)]

#: ``$defs/ProductCode``
PRODUCT_CODE_PATTERN = r"^[A-Z][A-Z0-9-]{0,31}$"
ProductCode = Annotated[str, Field(pattern=PRODUCT_CODE_PATTERN, min_length=1, max_length=32)]

#: ``$defs/Sha256Hex``
SHA256_HEX_PATTERN = r"^[0-9a-f]{64}$"
Sha256Hex = Annotated[str, Field(pattern=SHA256_HEX_PATTERN, min_length=64, max_length=64)]

#: ``$defs/Ed25519Signature`` (base64url, no padding, 32-byte signature -> 86 chars)
SIGNATURE_PATTERN = r"^[A-Za-z0-9_-]{86}$"

_SEMVER_PATTERN = r"^[0-9]+\.[0-9]+\.[0-9]+$"


def _validate_utc(value: datetime) -> datetime:
    """``$defs/UtcDateTime`` requires ``format: date-time`` + ``pattern: "Z$"``
    — i.e. a timezone-aware instant whose canonical form ends in ``Z``.
    """
    if value.tzinfo is None:
        raise ValueError("UtcDateTime must be timezone-aware")
    if value.utcoffset() != timedelta(0):
        raise ValueError("UtcDateTime must carry a zero UTC offset")
    return value


def utc_isoformat(value: datetime) -> str:
    """Render a UTC ``datetime`` per ``$defs/UtcDateTime``'s ``pattern: "Z$"``.

    ``datetime.isoformat()`` renders UTC as ``+00:00``, not ``Z`` — used by
    ``schema_export.py``'s example payloads and available to any future
    serializer that needs the exact wire format.
    """
    text = value.astimezone(timezone.utc).isoformat()
    if text.endswith("+00:00"):
        text = text[: -len("+00:00")] + "Z"
    return text


#: ``$defs/UtcDateTime``. A plain ``datetime`` alias: UTC-ness (timezone-aware,
#: zero offset) is enforced per-model via a ``@field_validator`` calling
#: ``_validate_utc`` below, since Pydantic's ``Annotated`` metadata pipeline
#: has no clean way to attach a shared cross-field validator to a bare type
#: alias without a class to bind it to.
UtcDateTime = datetime


class TimeRange(BaseModel):
    """``$defs/TimeRange`` — an open-ended (``to: null`` = still open) interval."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    from_: UtcDateTime = Field(..., alias="from")
    to: UtcDateTime | None = None

    @field_validator("from_", "to")
    @classmethod
    def _check_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        return _validate_utc(v)


# ---------------------------------------------------------------------------
# SourceRecord — the bitemporal metadata object (spec §2 ``SourceRecord``)
# ---------------------------------------------------------------------------


class SourceLocator(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: SourceLocatorKind
    value: Annotated[str, Field(min_length=1, max_length=256)]


class SourceRecord(BaseModel):
    """A single verified regulatory/pricing source, bitemporally tracked.

    ``legal_period`` = when the cited rule was legally true; ``recorded_period``
    = when Visa Oracle's system knew it (spec §5.4's bitemporal model — the
    two clocks tracked independently, never conflated).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_record_id: uuid.UUID
    source_key: Identifier
    version: Annotated[int, Field(ge=1, le=9_007_199_254_740_991)]
    authority_type: SourceAuthorityType
    status: SourceStatus
    jurisdiction: Literal["ID"] = "ID"
    title: Annotated[str, Field(min_length=1, max_length=512)]
    publisher: Annotated[str, Field(min_length=1, max_length=256)]
    canonical_url: Annotated[str, Field(max_length=2048)]
    language: Annotated[str, Field(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")]
    document_number: Annotated[str, Field(max_length=256)] | None = None
    locators: tuple[SourceLocator, ...] = Field(default_factory=tuple, max_length=64)
    content_sha256: Sha256Hex
    legal_period: TimeRange
    recorded_period: TimeRange
    retrieved_at: UtcDateTime
    verified_at: UtcDateTime
    verified_by: Identifier
    supersedes_source_record_id: uuid.UUID | None = None

    @field_validator("retrieved_at", "verified_at")
    @classmethod
    def _check_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v)


# ---------------------------------------------------------------------------
# VisaProductVersion (spec §2) — required nested type of RulePackPayload.products
# ---------------------------------------------------------------------------


class PricingKey(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    category: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    item_key: Annotated[str, Field(min_length=1, max_length=256)]


class ProductNames(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Annotated[str, Field(min_length=1, max_length=256)]
    en: Annotated[str, Field(min_length=1, max_length=256)]


class EntryPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entry_count: EntryCount


class StayPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: StayPolicyKind
    minimum_days: Annotated[int, Field(ge=0, le=36_500)] | None = None
    maximum_days: Annotated[int, Field(ge=0, le=36_500)] | None = None


class ExtensionPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool
    maximum_extensions: Annotated[int, Field(ge=0, le=100)]
    days_per_extension: Annotated[int, Field(ge=1, le=3650)] | None = None


class ClockCheckpointSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: Identifier
    offset_days: Annotated[int, Field(ge=-3650, le=36_500)]
    title_key: Identifier
    body_key: Identifier


class ClockPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    available: bool
    anchor: ClockAnchor
    checkpoints: tuple[ClockCheckpointSpec, ...] = Field(default_factory=tuple, max_length=64)


class VisaProductVersion(BaseModel):
    """``$defs/VisaProductVersion`` (spec §2). Included in PR1 because
    ``RulePackPayload.products`` requires it — see module docstring.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_version_id: uuid.UUID
    product_code: ProductCode
    legacy_codes: tuple[ProductCode, ...] = Field(default_factory=tuple)
    legacy_slugs: tuple[Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")], ...] = Field(
        default_factory=tuple
    )
    names: ProductNames
    category: VisaProductCategory
    status: VisaProductStatus
    valid_period: TimeRange
    covered_purposes: tuple[VisaPurpose, ...] = Field(..., min_length=1)
    prohibited_activities: tuple[Identifier, ...] = Field(default_factory=tuple)
    sponsor_types: tuple[SponsorType, ...] = Field(default_factory=tuple)
    entry_policy: EntryPolicy
    stay_policy: StayPolicy
    extension_policy: ExtensionPolicy
    clock_policy: ClockPolicy
    pricing_key: PricingKey | None = None
    source_refs: tuple[uuid.UUID, ...] = Field(..., min_length=1)
    public_catalog: bool

    @field_validator("legacy_codes", "legacy_slugs", "covered_purposes", "source_refs")
    @classmethod
    def _check_unique(cls, v: tuple) -> tuple:
        if len(set(v)) != len(v):
            raise ValueError("array must have unique items")
        return v


# ---------------------------------------------------------------------------
# RuleEffect (spec §2 ``RuleEffect``) — discriminated on ``type``
# ---------------------------------------------------------------------------


class EffectExclude(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["EXCLUDE"] = "EXCLUDE"
    reason_code: ReasonCode


class EffectSupport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["SUPPORT"] = "SUPPORT"
    reason_code: ReasonCode
    covered_purposes: tuple[VisaPurpose, ...] = Field(..., min_length=1)

    @field_validator("covered_purposes")
    @classmethod
    def _check_unique(cls, v: tuple[VisaPurpose, ...]) -> tuple[VisaPurpose, ...]:
        if len(set(v)) != len(v):
            raise ValueError("covered_purposes must have unique items")
        return v


class EffectRequireReview(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["REQUIRE_REVIEW"] = "REQUIRE_REVIEW"
    reason_code: ReasonCode


class EffectAddScore(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["ADD_SCORE"] = "ADD_SCORE"
    reason_code: ReasonCode
    points: Annotated[int, Field(ge=-10_000, le=10_000)]


RuleEffect = Annotated[
    EffectExclude | EffectSupport | EffectRequireReview | EffectAddScore,
    Field(discriminator="type"),
]

#: Maps each RuleStage to the one RuleEffectType it must carry (spec §2 Rule allOf).
STAGE_EFFECT_TYPE: dict[RuleStage, RuleEffectType] = {
    RuleStage.HARD_FILTER: RuleEffectType.EXCLUDE,
    RuleStage.ELIGIBILITY: RuleEffectType.SUPPORT,
    RuleStage.HUMAN_REVIEW: RuleEffectType.REQUIRE_REVIEW,
    RuleStage.RANKING: RuleEffectType.ADD_SCORE,
}


# ---------------------------------------------------------------------------
# Rule (spec §2 ``Rule``)
# ---------------------------------------------------------------------------


class Rule(BaseModel):
    """``$defs/Rule`` (spec §2), including its two ``allOf``/``if``/``then``
    conditionals as ``model_validator``s: (1) ``scope: GLOBAL`` forbids
    ``product_version_ids``, ``scope: PRODUCTS`` requires it; (2) each stage
    requires its matching effect type (spec's ``STAGE_EFFECT_TYPE`` mapping
    above). Both are cheap, single-object, always-true rules stated directly
    in the JSON Schema, so they belong at the model layer.

    Deliberately NOT enforced here (see ``ast.py``'s ``validate_ast_limits``
    docstring): AST depth/node-count limits. The spec buckets those under
    "compiler-only invariants" — ``compiler.py`` is the sole enforcement
    point, so a Rule with an oversized condition tree *can* be constructed
    (matching how a raw pack loads before compilation) and is instead
    reported as a collected ``CompilationError``, never a raised exception.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: Identifier
    stage: RuleStage
    scope: RuleScope
    product_version_ids: tuple[uuid.UUID, ...] | None = Field(
        default=None, min_length=1, max_length=256
    )
    priority: Annotated[int, Field(ge=0, le=100_000)]
    valid_period: TimeRange
    when: Condition
    effect: RuleEffect
    on_unknown: OnUnknownAction
    required_facts: tuple[FactPath, ...] = Field(default_factory=tuple, max_length=128)
    source_refs: tuple[uuid.UUID, ...] = Field(..., min_length=1, max_length=32)
    explanation_key: Identifier
    safety_critical: bool

    @field_validator("product_version_ids", "source_refs")
    @classmethod
    def _check_unique_uuids(cls, v: tuple[uuid.UUID, ...] | None) -> tuple[uuid.UUID, ...] | None:
        if v is not None and len(set(v)) != len(v):
            raise ValueError("array must have unique items")
        return v

    @field_validator("required_facts")
    @classmethod
    def _check_unique_facts(cls, v: tuple[FactPath, ...]) -> tuple[FactPath, ...]:
        if len(set(v)) != len(v):
            raise ValueError("required_facts must have unique items")
        return v

    @model_validator(mode="after")
    def _check_scope_products(self) -> Rule:
        if self.scope is RuleScope.GLOBAL and self.product_version_ids is not None:
            raise ValueError("GLOBAL-scope rule must not declare product_version_ids")
        if self.scope is RuleScope.PRODUCTS and not self.product_version_ids:
            raise ValueError("PRODUCTS-scope rule requires a non-empty product_version_ids")
        return self

    @model_validator(mode="after")
    def _check_stage_effect(self) -> Rule:
        expected = STAGE_EFFECT_TYPE[self.stage]
        actual = RuleEffectType(self.effect.type)
        if actual is not expected:
            raise ValueError(
                f"stage {self.stage.value} requires effect type {expected.value}, "
                f"got {actual.value}"
            )
        return self


# ---------------------------------------------------------------------------
# HitPolicy declaration (spec §2 ``RulePackPayload.hit_policy`` — all consts)
# ---------------------------------------------------------------------------


class HitPolicyDeclaration(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    hard_filter: Literal["COLLECT_ALL"] = "COLLECT_ALL"
    eligibility: Literal["COVER_ALL_DECLARED_PURPOSES"] = "COVER_ALL_DECLARED_PURPOSES"
    human_review: Literal["COLLECT_ALL"] = "COLLECT_ALL"
    ranking: Literal["SUM_TRUE_INTEGER_WEIGHTS"] = "SUM_TRUE_INTEGER_WEIGHTS"


# ---------------------------------------------------------------------------
# RulePackPayload + ProtectedHeader + RulePack envelope (spec §2)
# ---------------------------------------------------------------------------


class RulePackPayload(BaseModel):
    """``$defs/RulePackPayload`` (spec §2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_pack_id: uuid.UUID
    sequence: Annotated[int, Field(ge=1, le=9_007_199_254_740_991)]
    version: Annotated[str, Field(pattern=_SEMVER_PATTERN)]
    environment: Environment
    jurisdiction: Literal["ID"] = "ID"
    decision_domain: Literal["IMMIGRATION_VISA"] = "IMMIGRATION_VISA"
    engine_contract_version: Literal["1.0.0"] = "1.0.0"
    engine_min_version: Annotated[str, Field(pattern=_SEMVER_PATTERN)]
    engine_max_version: Annotated[str, Field(pattern=_SEMVER_PATTERN)]
    valid_period: TimeRange
    created_at: UtcDateTime
    created_by: Identifier
    previous_payload_sha256: Sha256Hex | None
    rollback_of_payload_sha256: Sha256Hex | None
    hit_policy: HitPolicyDeclaration
    source_records: tuple[SourceRecord, ...] = Field(..., min_length=1, max_length=4096)
    products: tuple[VisaProductVersion, ...] = Field(..., min_length=1, max_length=256)
    rules: tuple[Rule, ...] = Field(..., min_length=1, max_length=4096)

    @field_validator("created_at")
    @classmethod
    def _check_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v)

    @model_validator(mode="after")
    def _check_sequence_chain(self) -> RulePackPayload:
        if self.sequence == 1 and self.previous_payload_sha256 is not None:
            raise ValueError("sequence 1 must have previous_payload_sha256 = null")
        if self.sequence != 1 and self.previous_payload_sha256 is None:
            raise ValueError("sequence > 1 requires a non-null previous_payload_sha256")
        return self

    @field_validator("source_records")
    @classmethod
    def _check_unique_source_ids(cls, v: tuple[SourceRecord, ...]) -> tuple[SourceRecord, ...]:
        ids = [record.source_record_id for record in v]
        if len(set(ids)) != len(ids):
            raise ValueError("source_records must have unique source_record_id")
        return v

    @field_validator("products")
    @classmethod
    def _check_unique_product_ids(
        cls, v: tuple[VisaProductVersion, ...]
    ) -> tuple[VisaProductVersion, ...]:
        ids = [product.product_version_id for product in v]
        if len(set(ids)) != len(ids):
            raise ValueError("products must have unique product_version_id")
        return v

    @field_validator("rules")
    @classmethod
    def _check_unique_rule_ids(cls, v: tuple[Rule, ...]) -> tuple[Rule, ...]:
        ids = [rule.rule_id for rule in v]
        if len(set(ids)) != len(ids):
            raise ValueError("rules must have unique rule_id")
        return v


class ProtectedHeader(BaseModel):
    """``$defs/ProtectedHeader`` (spec §2, §3 signing envelope)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    domain: Literal["balizero.visa-rulepack.v1"] = "balizero.visa-rulepack.v1"
    alg: Literal["Ed25519"] = "Ed25519"
    kid: Identifier
    signed_at: UtcDateTime
    schema_version: Literal["1.0.0"] = "1.0.0"
    environment: Environment

    @field_validator("signed_at")
    @classmethod
    def _check_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v)


class RulePack(BaseModel):
    """``$defs/RulePack`` (spec §2) — the signed envelope.

    PR1 does not verify the signature (that is ``bundle.py``, PR2 scope):
    this model only guarantees the envelope is well-typed. ``compiler.py``
    takes a plain ``RulePack`` for the same reason (see that module's
    docstring) rather than the spec's ``VerifiedRulePack`` (a PR2 concept).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    canonicalization: Literal["RFC8785"] = "RFC8785"
    protected: ProtectedHeader
    payload: RulePackPayload
    payload_sha256: Sha256Hex
    signature: Annotated[str, Field(pattern=SIGNATURE_PATTERN)]

    @model_validator(mode="after")
    def _check_header_environment(self) -> RulePack:
        if self.protected.environment is not self.payload.environment:
            raise ValueError(
                "protected.environment "
                f"({self.protected.environment.value}) must equal "
                f"payload.environment ({self.payload.environment.value})"
            )
        return self
