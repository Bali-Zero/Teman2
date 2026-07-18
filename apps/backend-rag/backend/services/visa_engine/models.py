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

PR1 hardening round (codex correctness findings 1-3, orchestrator-arbitrated
scope expansion): also included are ``ApplicantFacts``, ``Decision``,
``Candidate`` (aliased as ``CandidateDecision`` — spec §1's module-layout
snippet names the class ``CandidateDecision`` while spec §2's JSON Schema
$def is named ``Candidate``; this file follows §2's authoritative name and
re-exports the §1 name as an alias, the same resolution pattern already used
for ``FactDefinition``/``FactSpec`` below), ``PriceQuote``, ``Reason``,
``RulePackRef``, ``Fingerprint``, and the ``*Fact``/``Known*``/``UnknownFact``
value-shape hierarchy ``ApplicantFacts.facts`` is built from. These are all
*pure data* (no evaluation/derivation logic — ``FactRegistry.derive()``,
``evaluate_condition``, and the evaluator's ``FactSnapshot`` remain PR3
scope, see ``fact_registry.py``'s and ``ast.py``'s docstrings) so they carry
no risk of PR1 quietly growing evaluator semantics.

Deferred to PR2+ (do not exist in this module): ``ConsentEvent``,
``EvaluationContext``. Neither is referenced by any PR1 module.
``FactDefinition`` (named in the PR1 brief) is represented as
``fact_registry.FactSpec`` instead — see that module's docstring for the
resolved naming/placement ambiguity.

All models are frozen (``model_config = ConfigDict(frozen=True,
extra="forbid")``) — a RulePack, once parsed, is an immutable value; nothing
downstream may quietly attach an unexpected field.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.services.visa_engine.ast import Condition
from backend.services.visa_engine.enums import (
    APPLICANT_FACT_PATHS,
    ApplicationChannel,
    ClockAnchor,
    DecisionState,
    EntryCount,
    EntryPattern,
    Environment,
    MaritalStatus,
    OnUnknownAction,
    ProposedRole,
    RelationType,
    RuleEffectType,
    RuleScope,
    RuleStage,
    SourceAuthorityType,
    SourceLocatorKind,
    SourceStatus,
    SponsorType,
    StayPolicyKind,
    StudyLevel,
    UnknownReason,
    ViolationType,
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
    """``$defs/TimeRange`` — an open-ended (``to: null`` = still open) interval.

    ``to`` has no Python default (Codex finding 2): JSON Schema's
    ``required: ["from", "to"]`` means the *key* must be present even though
    its *value* may legally be ``null`` — a Python ``= None`` default would
    let ``TimeRange(from=...)`` silently omit the key, which for a field
    inside a signed payload changes what gets canonicalized/hashed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    from_: UtcDateTime = Field(..., alias="from")
    to: UtcDateTime | None

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
    version: Annotated[int, Field(ge=1, le=9_007_199_254_740_991, strict=True)]
    authority_type: SourceAuthorityType
    status: SourceStatus
    # No default (Codex finding 2): jurisdiction is a JSON Schema `const`,
    # which still means the *key* is required — see `TimeRange.to`'s
    # docstring for why a Python default is unsafe on a signed-payload field.
    jurisdiction: Literal["ID"]
    title: Annotated[str, Field(min_length=1, max_length=512)]
    publisher: Annotated[str, Field(min_length=1, max_length=256)]
    canonical_url: Annotated[str, Field(max_length=2048)]
    language: Annotated[str, Field(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")]
    document_number: Annotated[str, Field(max_length=256)] | None
    locators: tuple[SourceLocator, ...] = Field(..., max_length=64)
    content_sha256: Sha256Hex
    legal_period: TimeRange
    recorded_period: TimeRange
    retrieved_at: UtcDateTime
    verified_at: UtcDateTime
    verified_by: Identifier
    supersedes_source_record_id: uuid.UUID | None

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
    minimum_days: Annotated[int, Field(ge=0, le=36_500, strict=True)] | None
    maximum_days: Annotated[int, Field(ge=0, le=36_500, strict=True)] | None


class ExtensionPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool
    maximum_extensions: Annotated[int, Field(ge=0, le=100, strict=True)]
    days_per_extension: Annotated[int, Field(ge=1, le=3650, strict=True)] | None


class ClockCheckpointSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: Identifier
    offset_days: Annotated[int, Field(ge=-3650, le=36_500, strict=True)]
    title_key: Identifier
    body_key: Identifier


class ClockPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    available: bool
    anchor: ClockAnchor
    checkpoints: tuple[ClockCheckpointSpec, ...] = Field(..., max_length=64)


class VisaProductVersion(BaseModel):
    """``$defs/VisaProductVersion`` (spec §2). Included in PR1 because
    ``RulePackPayload.products`` requires it — see module docstring.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_version_id: uuid.UUID
    product_code: ProductCode
    # No `default_factory`/`= None` on any field below (Codex finding 2): a
    # RulePack's `products` array is inside the signed payload — see
    # `TimeRange.to`'s docstring for the general rationale.
    legacy_codes: tuple[ProductCode, ...] = Field(...)
    legacy_slugs: tuple[Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")], ...] = Field(
        ...
    )
    names: ProductNames
    category: VisaProductCategory
    status: VisaProductStatus
    valid_period: TimeRange
    covered_purposes: tuple[VisaPurpose, ...] = Field(..., min_length=1)
    prohibited_activities: tuple[Identifier, ...] = Field(...)
    sponsor_types: tuple[SponsorType, ...] = Field(...)
    entry_policy: EntryPolicy
    stay_policy: StayPolicy
    extension_policy: ExtensionPolicy
    clock_policy: ClockPolicy
    pricing_key: PricingKey | None
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

    # No default (Codex finding 2): `type` is the discriminator for the
    # `RuleEffect` union — same no-silent-default rationale as `ast.py`'s
    # `op` fields (see `AllCondition.op`'s docstring).
    type: Literal["EXCLUDE"]
    reason_code: ReasonCode


class EffectSupport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["SUPPORT"]
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

    type: Literal["REQUIRE_REVIEW"]
    reason_code: ReasonCode


class EffectAddScore(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    type: Literal["ADD_SCORE"]
    reason_code: ReasonCode
    points: Annotated[int, Field(ge=-10_000, le=10_000, strict=True)]


RuleEffect = Annotated[
    EffectExclude | EffectSupport | EffectRequireReview | EffectAddScore,
    Field(discriminator="type"),
]

#: Maps each RuleStage to the one RuleEffectType it must carry (spec §2 Rule
#: allOf). ``MappingProxyType``, not a plain ``dict`` (Codex finding 9): a
#: module-level mutable dict is a shared-global footgun — any caller with a
#: reference could mutate this engine-wide invariant table at runtime.
STAGE_EFFECT_TYPE: Mapping[RuleStage, RuleEffectType] = MappingProxyType(
    {
        RuleStage.HARD_FILTER: RuleEffectType.EXCLUDE,
        RuleStage.ELIGIBILITY: RuleEffectType.SUPPORT,
        RuleStage.HUMAN_REVIEW: RuleEffectType.REQUIRE_REVIEW,
        RuleStage.RANKING: RuleEffectType.ADD_SCORE,
    }
)


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
    priority: Annotated[int, Field(ge=0, le=100_000, strict=True)]
    valid_period: TimeRange
    when: Condition
    effect: RuleEffect
    on_unknown: OnUnknownAction
    # No `default_factory` (Codex finding 2): `required_facts` participates
    # in the `required_facts == collect_fact_paths(when)` compiler invariant
    # and is part of the signed payload — see `TimeRange.to`'s docstring.
    required_facts: tuple[FactPath, ...] = Field(..., max_length=128)
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
    """Every field is a JSON Schema ``const`` — but with no Python default
    (Codex finding 2, exact counterexample: ``HitPolicyDeclaration()`` with
    zero args was wrongly accepted). See ``TimeRange.to``'s docstring for
    the general "signed-payload field, no silent default" rationale.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    hard_filter: Literal["COLLECT_ALL"]
    eligibility: Literal["COVER_ALL_DECLARED_PURPOSES"]
    human_review: Literal["COLLECT_ALL"]
    ranking: Literal["SUM_TRUE_INTEGER_WEIGHTS"]


# ---------------------------------------------------------------------------
# RulePackPayload + ProtectedHeader + RulePack envelope (spec §2)
# ---------------------------------------------------------------------------


class RulePackPayload(BaseModel):
    """``$defs/RulePackPayload`` (spec §2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_pack_id: uuid.UUID
    sequence: Annotated[int, Field(ge=1, le=9_007_199_254_740_991, strict=True)]
    version: Annotated[str, Field(pattern=_SEMVER_PATTERN)]
    environment: Environment
    # No defaults on the three consts below (Codex finding 2) — see
    # `TimeRange.to`'s docstring.
    jurisdiction: Literal["ID"]
    decision_domain: Literal["IMMIGRATION_VISA"]
    engine_contract_version: Literal["1.0.0"]
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

    # No defaults (Codex finding 2, exact counterexample: "a header without
    # domain/alg/schema_version is accepted") — see `TimeRange.to`'s
    # docstring. These three consts are the strongest case of all: they are
    # literally what the signing scheme's `signed_bytes` binds to.
    domain: Literal["balizero.visa-rulepack.v1"]
    alg: Literal["Ed25519"]
    kid: Identifier
    signed_at: UtcDateTime
    schema_version: Literal["1.0.0"]
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

    # No default (Codex finding 2) — see `TimeRange.to`'s docstring.
    canonicalization: Literal["RFC8785"]
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


# ---------------------------------------------------------------------------
# Fact value shapes (spec §2 ``UnknownFact``/``Known*``/``*Fact``) — the
# building blocks of ``ApplicantFacts.facts``. Added in the PR1 hardening
# round (Codex findings 1-3, see module docstring). Every ``*Fact`` union is
# discriminated on ``status`` — no defaults, matching every other
# discriminator field in this package (``ast.py``'s ``op``, ``RuleEffect``'s
# ``type``).
# ---------------------------------------------------------------------------

#: ``$defs/KnownCountryCode``/``KnownCountrySet`` alpha-2 pattern.
COUNTRY_CODE_PATTERN = r"^[A-Z]{2}$"
CountryCode = Annotated[str, Field(pattern=COUNTRY_CODE_PATTERN)]

#: ``$defs/KnownDate`` — JSON Schema ``format: "date"`` (calendar date, no
#: time-of-day component — deliberately distinct from ``UtcDateTime``).
ISO_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
IsoDate = Annotated[str, Field(pattern=ISO_DATE_PATTERN)]

#: ``$defs/PublicDecisionId`` inline pattern (spec §2 ``Decision.public_id``).
PUBLIC_ID_PATTERN = r"^[a-z0-9]{16,20}$"


class UnknownFact(BaseModel):
    """``$defs/UnknownFact`` — a fact never collected/confirmed, with an
    explicit reason (spec §2; mirrors ``enums.UnknownReason``'s docstring:
    "no fact is ever just missing outside the type system").
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["UNKNOWN"]
    reason: UnknownReason


class KnownBoolean(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["KNOWN"]
    value: Annotated[bool, Field(strict=True)]


class KnownDate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["KNOWN"]
    value: IsoDate

    @field_validator("value")
    @classmethod
    def _check_calendar_date(cls, v: str) -> str:
        # Hotfix (2026-07-18, Gap E): `IsoDate`'s own `Field(pattern=...)`
        # only checks the `YYYY-MM-DD` *shape* — a shape-valid but
        # calendar-impossible date (month 13, day 45, Feb 30, Feb 29 on a
        # non-leap year) round-tripped clean. `date.fromisoformat` is the
        # strict calendar-aware check (correctly handles leap years).
        try:
            date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(f"{v!r} is not a valid calendar date: {exc}") from exc
        return v


class KnownString(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["KNOWN"]
    value: Annotated[str, Field(min_length=1, max_length=64)]


class KnownNonNegativeInteger(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["KNOWN"]
    value: Annotated[int, Field(ge=0, le=9_007_199_254_740_991, strict=True)]


class KnownMoney(BaseModel):
    """Structurally identical to ``KnownNonNegativeInteger`` — kept as a
    distinct class because spec §2 declares ``KnownMoney`` as its own
    ``$def`` (semantically an IDR amount, not an arbitrary count).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["KNOWN"]
    value: Annotated[int, Field(ge=0, le=9_007_199_254_740_991, strict=True)]


class KnownCountryCode(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["KNOWN"]
    value: CountryCode


class KnownCountrySet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["KNOWN"]
    value: tuple[CountryCode, ...] = Field(..., min_length=1, max_length=4)

    @field_validator("value")
    @classmethod
    def _check_unique(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("value must have unique items")
        return v


class KnownPurposeSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["KNOWN"]
    value: tuple[VisaPurpose, ...] = Field(..., min_length=1, max_length=8)

    @field_validator("value")
    @classmethod
    def _check_unique(cls, v: tuple[VisaPurpose, ...]) -> tuple[VisaPurpose, ...]:
        if len(set(v)) != len(v):
            raise ValueError("value must have unique items")
        return v


class KnownViolationSet(BaseModel):
    """No ``min_length`` (spec §2, deliberately): ``value=[]`` is a
    meaningful KNOWN fact — "we asked, they have zero violations" — distinct
    from ``UnknownFact`` ("we don't know").
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["KNOWN"]
    value: tuple[ViolationType, ...] = Field(..., max_length=8)

    @field_validator("value")
    @classmethod
    def _check_unique(cls, v: tuple[ViolationType, ...]) -> tuple[ViolationType, ...]:
        if len(set(v)) != len(v):
            raise ValueError("value must have unique items")
        return v


class KnownMaritalStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["KNOWN"]
    value: MaritalStatus


class KnownEntryPattern(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["KNOWN"]
    value: EntryPattern


class KnownApplicationChannel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["KNOWN"]
    value: ApplicationChannel


class KnownRelation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["KNOWN"]
    value: RelationType


class KnownProposedRole(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["KNOWN"]
    value: ProposedRole


class KnownStudyLevel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["KNOWN"]
    value: StudyLevel


BooleanFact = Annotated[UnknownFact | KnownBoolean, Field(discriminator="status")]
DateFact = Annotated[UnknownFact | KnownDate, Field(discriminator="status")]
StringFact = Annotated[UnknownFact | KnownString, Field(discriminator="status")]
CountryCodeFact = Annotated[UnknownFact | KnownCountryCode, Field(discriminator="status")]
CountrySetFact = Annotated[UnknownFact | KnownCountrySet, Field(discriminator="status")]
NonNegativeIntegerFact = Annotated[
    UnknownFact | KnownNonNegativeInteger, Field(discriminator="status")
]
MoneyFact = Annotated[UnknownFact | KnownMoney, Field(discriminator="status")]
PurposeSetFact = Annotated[UnknownFact | KnownPurposeSet, Field(discriminator="status")]
ViolationSetFact = Annotated[UnknownFact | KnownViolationSet, Field(discriminator="status")]
MaritalStatusFact = Annotated[UnknownFact | KnownMaritalStatus, Field(discriminator="status")]
EntryPatternFact = Annotated[UnknownFact | KnownEntryPattern, Field(discriminator="status")]
ApplicationChannelFact = Annotated[
    UnknownFact | KnownApplicationChannel, Field(discriminator="status")
]
RelationFact = Annotated[UnknownFact | KnownRelation, Field(discriminator="status")]
ProposedRoleFact = Annotated[UnknownFact | KnownProposedRole, Field(discriminator="status")]
StudyLevelFact = Annotated[UnknownFact | KnownStudyLevel, Field(discriminator="status")]


# ---------------------------------------------------------------------------
# ApplicantFacts (spec §2) — the 35 applicant-collected fact paths, each
# typed per its own *Fact union above. Field names use Python-safe
# identifiers with the dotted wire name as the Pydantic alias (same pattern
# as ``TimeRange.from_``/``alias="from"``) since a dotted path cannot be a
# Python attribute name.
# ---------------------------------------------------------------------------


class ApplicantFactsData(BaseModel):
    """``ApplicantFacts.facts`` (spec §2) — ``additionalProperties: false``
    with all 35 keys required. Field order mirrors ``enums.FactPath``'s
    ``person.*``/``immigration.*``/``intent.*``/``work.*``/``investment.*``/
    ``family.*``/``study.*``/``process.*``/``commercial.*`` grouping.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    person_birth_date: Annotated[DateFact, Field(alias="person.birth_date")]
    person_nationalities: Annotated[CountrySetFact, Field(alias="person.nationalities")]
    person_marital_status: Annotated[MaritalStatusFact, Field(alias="person.marital_status")]
    immigration_currently_in_indonesia: Annotated[
        BooleanFact, Field(alias="immigration.currently_in_indonesia")
    ]
    immigration_current_status_code: Annotated[
        StringFact, Field(alias="immigration.current_status_code")
    ]
    immigration_current_status_expiry: Annotated[
        DateFact, Field(alias="immigration.current_status_expiry")
    ]
    immigration_last_entry_date: Annotated[DateFact, Field(alias="immigration.last_entry_date")]
    immigration_overstay_days: Annotated[
        NonNegativeIntegerFact, Field(alias="immigration.overstay_days")
    ]
    immigration_violation_history: Annotated[
        ViolationSetFact, Field(alias="immigration.violation_history")
    ]
    intent_purposes: Annotated[PurposeSetFact, Field(alias="intent.purposes")]
    intent_stay_days: Annotated[NonNegativeIntegerFact, Field(alias="intent.stay_days")]
    intent_desired_entry_date: Annotated[DateFact, Field(alias="intent.desired_entry_date")]
    intent_entry_pattern: Annotated[EntryPatternFact, Field(alias="intent.entry_pattern")]
    intent_requested_product_code: Annotated[
        StringFact, Field(alias="intent.requested_product_code")
    ]
    work_employer_country_code: Annotated[
        CountryCodeFact, Field(alias="work.employer_country_code")
    ]
    work_employer_is_indonesian_entity: Annotated[
        BooleanFact, Field(alias="work.employer_is_indonesian_entity")
    ]
    work_serves_indonesian_clients: Annotated[
        BooleanFact, Field(alias="work.serves_indonesian_clients")
    ]
    work_indonesia_source_compensation: Annotated[
        BooleanFact, Field(alias="work.indonesia_source_compensation")
    ]
    work_indonesian_work_sponsor_confirmed: Annotated[
        BooleanFact, Field(alias="work.indonesian_work_sponsor_confirmed")
    ]
    investment_pt_pma_committed: Annotated[BooleanFact, Field(alias="investment.pt_pma_committed")]
    investment_investment_capital_idr: Annotated[
        MoneyFact, Field(alias="investment.investment_capital_idr")
    ]
    investment_paid_up_capital_idr: Annotated[
        MoneyFact, Field(alias="investment.paid_up_capital_idr")
    ]
    investment_proposed_role: Annotated[ProposedRoleFact, Field(alias="investment.proposed_role")]
    family_relation_to_sponsor: Annotated[RelationFact, Field(alias="family.relation_to_sponsor")]
    family_sponsor_nationalities: Annotated[
        CountrySetFact, Field(alias="family.sponsor_nationalities")
    ]
    family_sponsor_status_code: Annotated[StringFact, Field(alias="family.sponsor_status_code")]
    family_marriage_registered: Annotated[BooleanFact, Field(alias="family.marriage_registered")]
    family_sponsor_confirmed: Annotated[BooleanFact, Field(alias="family.sponsor_confirmed")]
    study_level: Annotated[StudyLevelFact, Field(alias="study.level")]
    study_admission_confirmed: Annotated[BooleanFact, Field(alias="study.admission_confirmed")]
    study_sponsor_confirmed: Annotated[BooleanFact, Field(alias="study.sponsor_confirmed")]
    process_application_channel: Annotated[
        ApplicationChannelFact, Field(alias="process.application_channel")
    ]
    process_wants_onshore_conversion: Annotated[
        BooleanFact, Field(alias="process.wants_onshore_conversion")
    ]
    commercial_service_fee_budget_idr: Annotated[
        MoneyFact, Field(alias="commercial.service_fee_budget_idr")
    ]
    commercial_wants_quote: Annotated[BooleanFact, Field(alias="commercial.wants_quote")]


class ApplicantFacts(BaseModel):
    """``$defs/ApplicantFacts`` (spec §2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0.0"]
    assessment_id: uuid.UUID
    collected_at: UtcDateTime
    facts: ApplicantFactsData

    @field_validator("collected_at")
    @classmethod
    def _check_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v)


# ---------------------------------------------------------------------------
# Decision-side types (spec §2 ``PriceQuote``/``Reason``/``Candidate``/
# ``RulePackRef``/``Fingerprint``/``Decision``). Pure data — PR3's evaluator
# is what actually *produces* a ``Decision``; PR1 only guarantees the shape.
# ---------------------------------------------------------------------------


class PriceQuote(BaseModel):
    """``$defs/PriceQuote`` (spec §2), including its ``status``-conditional
    ``allOf`` (AVAILABLE requires non-null amount/catalog fields; otherwise
    amount must be null).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    quote_id: uuid.UUID
    product_version_id: uuid.UUID
    product_code: ProductCode
    status: Literal["AVAILABLE", "CONTACT_REQUIRED", "UNAVAILABLE"]
    currency: Literal["IDR"]
    amount: Annotated[int, Field(ge=0, le=9_007_199_254_740_991, strict=True)] | None
    pricing_key: PricingKey
    catalog_version: Annotated[str, Field(min_length=1, max_length=64)] | None
    catalog_sha256: Sha256Hex | None
    row_sha256: Sha256Hex | None
    quoted_at: UtcDateTime
    valid_until: UtcDateTime | None
    reason_code: ReasonCode

    @field_validator("quoted_at")
    @classmethod
    def _check_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v)

    @field_validator("valid_until")
    @classmethod
    def _check_utc_if_present(cls, v: datetime | None) -> datetime | None:
        return v if v is None else _validate_utc(v)

    @model_validator(mode="after")
    def _check_status_conditional(self) -> PriceQuote:
        if self.status == "AVAILABLE":
            missing = [
                name
                for name, value in (
                    ("amount", self.amount),
                    ("catalog_version", self.catalog_version),
                    ("catalog_sha256", self.catalog_sha256),
                    ("row_sha256", self.row_sha256),
                )
                if value is None
            ]
            if missing:
                raise ValueError(f"status=AVAILABLE requires non-null {missing}")
        elif self.amount is not None:
            raise ValueError(f"status={self.status} requires amount=null")
        return self


class Reason(BaseModel):
    """``$defs/Reason`` (spec §2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: ReasonCode
    rule_ids: tuple[Identifier, ...] = Field(...)
    source_refs: tuple[uuid.UUID, ...] = Field(...)

    @field_validator("rule_ids")
    @classmethod
    def _check_unique_rule_ids(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(v)) != len(v):
            raise ValueError("rule_ids must have unique items")
        return v

    @field_validator("source_refs")
    @classmethod
    def _check_unique_source_refs(cls, v: tuple[uuid.UUID, ...]) -> tuple[uuid.UUID, ...]:
        if len(set(v)) != len(v):
            raise ValueError("source_refs must have unique items")
        return v


class Candidate(BaseModel):
    """``$defs/Candidate`` (spec §2). ``covered_purposes`` is deliberately a
    bare ``str`` tuple, not ``tuple[VisaPurpose, ...]`` — spec §2's own
    ``items`` schema for this field is ``{"type": "string"}`` with no enum
    constraint (unlike every other ``covered_purposes`` field in this
    package), so this class follows the spec literally.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rank: Annotated[int, Field(ge=1, le=256, strict=True)]
    product_version_id: uuid.UUID
    product_code: ProductCode
    score: Annotated[int, Field(ge=-1_000_000, le=1_000_000, strict=True)]
    covered_purposes: tuple[str, ...] = Field(..., min_length=1)
    support_rule_ids: tuple[Identifier, ...] = Field(..., min_length=1)
    source_refs: tuple[uuid.UUID, ...] = Field(..., min_length=1)
    reason_codes: tuple[ReasonCode, ...] = Field(..., min_length=1)

    @field_validator("covered_purposes", "support_rule_ids", "source_refs", "reason_codes")
    @classmethod
    def _check_unique(cls, v: tuple) -> tuple:
        if len(set(v)) != len(v):
            raise ValueError("array must have unique items")
        return v


#: Spec §1's module-layout snippet names this class ``CandidateDecision``;
#: spec §2's JSON Schema $def is ``Candidate`` — see module docstring.
CandidateDecision = Candidate


class RulePackRef(BaseModel):
    """``$defs/RulePackRef`` (spec §2). ``version`` is a bare ``str`` per
    spec (no semver pattern applied here, unlike ``RulePackPayload.version``
    — a reference snapshot, not the payload itself).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_pack_id: uuid.UUID
    sequence: Annotated[int, Field(ge=1, le=9_007_199_254_740_991, strict=True)]
    version: str
    payload_sha256: Sha256Hex


class Fingerprint(BaseModel):
    """``$defs/Fingerprint`` (spec §2) — an HMAC-SHA256 integrity tag over a
    ``Decision`` or its facts, distinct from the Ed25519 RulePack signature.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    algorithm: Literal["HMAC-SHA256"]
    key_id: Identifier
    digest: Sha256Hex


class Outage(BaseModel):
    """``Decision.outage`` inline object (spec §2, not a separate top-level $def)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: ReasonCode
    retryable: bool


class Decision(BaseModel):
    """``$defs/Decision`` (spec §2), including its five ``state``-conditional
    ``allOf`` entries. PR1 only guarantees the shape is well-typed and the
    five state invariants hold; *producing* a real ``Decision`` (running the
    evaluator over an ``ApplicantFacts`` + compiled ``RulePack``) is PR3.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0.0"]
    decision_id: uuid.UUID | None
    public_id: Annotated[str, Field(pattern=PUBLIC_ID_PATTERN)] | None
    state: DecisionState
    effective_at: UtcDateTime
    observed_at: UtcDateTime
    evaluated_at: UtcDateTime
    rule_pack: RulePackRef | None
    facts_fingerprint: Fingerprint
    candidates: tuple[Candidate, ...] = Field(..., max_length=256)
    missing_facts: tuple[FactPath, ...] = Field(...)
    review_reasons: tuple[Reason, ...] = Field(...)
    no_path_reasons: tuple[Reason, ...] = Field(...)
    outage: Outage | None
    quotes: tuple[PriceQuote, ...] = Field(...)
    notices: tuple[Reason, ...] = Field(...)
    trace_sha256: Sha256Hex | None
    decision_integrity: Fingerprint | None

    @field_validator("effective_at", "observed_at", "evaluated_at")
    @classmethod
    def _check_utc(cls, v: datetime) -> datetime:
        return _validate_utc(v)

    @field_validator("missing_facts")
    @classmethod
    def _check_missing_facts(cls, v: tuple[FactPath, ...]) -> tuple[FactPath, ...]:
        if len(set(v)) != len(v):
            raise ValueError("missing_facts must have unique items")
        non_applicant = [path for path in v if path not in APPLICANT_FACT_PATHS]
        if non_applicant:
            raise ValueError(
                f"missing_facts must reference applicant-collected paths only, "
                f"got derived path(s): {non_applicant}"
            )
        return v

    @model_validator(mode="after")
    def _check_state_conditionals(self) -> Decision:
        state = self.state
        identity_required = state in (
            DecisionState.SUPPORTED_CANDIDATES,
            DecisionState.NEEDS_INPUT,
            DecisionState.HUMAN_REVIEW_REQUIRED,
            DecisionState.NO_SUPPORTED_PATH,
        )
        if identity_required and (
            self.decision_id is None or self.public_id is None or self.rule_pack is None
        ):
            raise ValueError(
                f"state={state.value} requires non-null decision_id/public_id/rule_pack"
            )
        if identity_required and self.outage is not None:
            raise ValueError(f"state={state.value} forbids a non-null outage")

        if state is DecisionState.SUPPORTED_CANDIDATES:
            if len(self.candidates) < 1:
                raise ValueError("state=SUPPORTED_CANDIDATES requires at least one candidate")
            if self.missing_facts or self.review_reasons or self.no_path_reasons:
                raise ValueError(
                    "state=SUPPORTED_CANDIDATES forbids missing_facts/review_reasons/"
                    "no_path_reasons"
                )
        else:
            if self.candidates or self.quotes:
                raise ValueError(f"state={state.value} forbids non-empty candidates/quotes")

        if state is DecisionState.NEEDS_INPUT:
            if not self.missing_facts:
                raise ValueError("state=NEEDS_INPUT requires at least one missing fact")
            if self.review_reasons or self.no_path_reasons:
                raise ValueError("state=NEEDS_INPUT forbids review_reasons/no_path_reasons")

        if state is DecisionState.HUMAN_REVIEW_REQUIRED:
            if self.missing_facts:
                raise ValueError("state=HUMAN_REVIEW_REQUIRED forbids missing_facts")
            if not self.review_reasons:
                raise ValueError("state=HUMAN_REVIEW_REQUIRED requires at least one review reason")
            if self.no_path_reasons:
                raise ValueError("state=HUMAN_REVIEW_REQUIRED forbids no_path_reasons")

        if state is DecisionState.NO_SUPPORTED_PATH:
            if self.missing_facts or self.review_reasons:
                raise ValueError("state=NO_SUPPORTED_PATH forbids missing_facts/review_reasons")
            if not self.no_path_reasons:
                raise ValueError("state=NO_SUPPORTED_PATH requires at least one no_path reason")

        if state is DecisionState.TEMPORARILY_UNAVAILABLE:
            if self.missing_facts or self.review_reasons or self.no_path_reasons:
                raise ValueError(
                    "state=TEMPORARILY_UNAVAILABLE forbids missing_facts/review_reasons/"
                    "no_path_reasons"
                )
            if self.outage is None:
                raise ValueError("state=TEMPORARILY_UNAVAILABLE requires a non-null outage")

        return self

    @model_validator(mode="after")
    def _check_quotes_reference_candidates(self) -> Decision:
        """PR1b port from design B (F6 — quote<->candidate integrity).

        Every ``PriceQuote`` in ``self.quotes`` must reference a real
        ``Candidate`` in ``self.candidates``: membership by
        ``product_version_id`` AND a matching ``product_code``. Without this,
        a quote could silently drift onto the wrong product (same
        ``product_version_id`` typo'd into a different candidate's slot, or a
        ``product_code`` that disagrees with the candidate it claims to
        price) and nothing downstream would ever notice — ``quotes`` and
        ``candidates`` are two independently-constructed arrays with no
        structural link enforced elsewhere.

        A no-op for every state other than ``SUPPORTED_CANDIDATES``:
        ``_check_state_conditionals`` above already forces
        ``quotes == ()`` for all of them, so this loop never iterates.
        """
        candidates_by_id = {c.product_version_id: c for c in self.candidates}
        for quote in self.quotes:
            candidate = candidates_by_id.get(quote.product_version_id)
            if candidate is None:
                raise ValueError(
                    f"quote {quote.quote_id} references product_version_id "
                    f"{quote.product_version_id} with no matching candidate"
                )
            if candidate.product_code != quote.product_code:
                raise ValueError(
                    f"quote {quote.quote_id} product_code {quote.product_code!r} does not "
                    f"match candidate product_code {candidate.product_code!r} for "
                    f"product_version_id {quote.product_version_id}"
                )
        return self
