"""Frozen Pydantic v2 wire models for the Visa Engine v2 JSON Schema contract.

Every model here mirrors a ``$defs`` entry of
``schemas/contract.schema.json`` field-for-field: same required keys (a
"required"-listed field always has NO Python default — the key must be
explicitly present, even when its value may be ``null`` — the ONE exception
is ``Rule.product_version_ids``, genuinely optional per the schema's
``scope``-conditional ``allOf``), same ``uniqueItems``/length/pattern
constraints, same conditional (``if``/``then``/``else``) invariants
re-implemented as ``model_validator``s.

``ConsentEvent`` and ``EvaluationContext`` are the two exceptions: neither
has a JSON Schema entrypoint (§2 lists exactly 8 schema files, none named
consent-event/evaluation-context) — they are Python-only service models, so
their field sets are derived from the ``consent.py``/``evaluate()`` usage
shown in the spec rather than transcribed from a schema.

Pure module: no I/O.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    field_validator,
    model_serializer,
    model_validator,
)

from backend.services.visa_engine._types import ApplicantFactPath, FactPath, UnknownReason
from backend.services.visa_engine.ast import Condition
from backend.services.visa_engine.enums import DecisionState, RuleStage

_INT_MAX = 9_007_199_254_740_991


def _require_unique(values: tuple[Any, ...] | None) -> tuple[Any, ...] | None:
    """Shared ``uniqueItems: true`` enforcement for tuple fields.

    Runs as an "after" validator (Pydantic's default `field_validator` mode),
    i.e. ``values`` has already been coerced to the field's declared
    ``tuple[...]`` type (F9) by the time this runs — the check itself is
    type-agnostic (``len``/``set`` work identically on tuple or list)."""

    if values is None:
        return values
    if len(values) != len(set(values)):
        raise ValueError("items must be unique")
    return values


def _validate_utc_datetime(value: str) -> str:
    """Matches ``$defs.UtcDateTime``: ``format: date-time`` + ``pattern: "Z$"``."""

    if not value.endswith("Z"):
        raise ValueError(f"UTC date-time must end in 'Z': {value!r}")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"not a valid date-time: {value!r}") from exc
    return value


_URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
"""RFC 3986 ``scheme ":"`` production (§3.1): a letter, then any number of
letters/digits/``+``/``.``/``-``, then a literal colon."""

_URI_FORBIDDEN_CHARS_RE = re.compile(r"[\x00-\x20\x7f]")
"""Raw whitespace (space/tab/newline/CR/...) and C0/DEL control characters —
none of these may appear anywhere in an RFC 3986 URI; a percent-encoded
representation is required instead."""


def _validate_uri(value: str) -> str:
    """Matches ``format: uri`` (RFC 3986 absolute-URI) without pulling in a
    URL-normalizing type (which would break exact wire round-tripping).

    F10: only a ``scheme`` is required — NOT a ``netloc``. ``urn:isbn:...``
    and ``mailto:someone@example.com`` are valid absolute URIs with no
    authority component and must pass.

    R3: ``urlparse`` alone is too permissive — it happily accepts a scheme
    followed by raw whitespace (e.g. ``"urn:bad value"``), which is not a
    valid RFC 3986 URI at all (unencoded space/control characters are
    forbidden by the grammar; a real space must be percent-encoded as
    ``%20``). Validate the scheme prefix AND reject any raw whitespace/
    control character anywhere in the string."""

    if not _URI_SCHEME_RE.match(value):
        raise ValueError(f"not a valid absolute URI (missing RFC 3986 scheme): {value!r}")
    if _URI_FORBIDDEN_CHARS_RE.search(value):
        raise ValueError(
            f"not a valid absolute URI (contains raw whitespace/control characters): {value!r}"
        )
    return value


# --- Shared primitive/pattern types (match $defs exactly) ------------------

UtcDateTime = Annotated[str, AfterValidator(_validate_utc_datetime)]
Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_.:-]{0,127}$")]
ReasonCode = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{0,127}$")]
ProductCode = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9-]{0,31}$")]
UriStr = Annotated[str, AfterValidator(_validate_uri), Field(max_length=2048)]
SemVer = Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")]


class _StrictModel(BaseModel):
    """Base for every wire model: frozen, no unknown keys, alias-ONLY input.

    F7: ``populate_by_name`` is OFF — a field with a wire alias (e.g.
    ``TimeRange.from_`` aliased to ``"from"``, or every dotted-path key in
    ``ApplicantFactsData``) must be constructed using exactly the schema's
    wire key. Accepting the Python attribute name too would let a caller
    silently bypass the contract's actual field names."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=False)


class TimeRange(_StrictModel):
    """Matches ``$defs.TimeRange``."""

    from_: UtcDateTime = Field(alias="from")
    to: UtcDateTime | None


# --- Enums used inline by fact/effect/product shapes -----------------------


class PurposeEnum(str, Enum):
    TOURISM = "TOURISM"
    BUSINESS_MEETINGS = "BUSINESS_MEETINGS"
    INVESTMENT = "INVESTMENT"
    EMPLOYMENT = "EMPLOYMENT"
    REMOTE_WORK = "REMOTE_WORK"
    FAMILY = "FAMILY"
    STUDY = "STUDY"
    RETIREMENT = "RETIREMENT"
    SECOND_HOME = "SECOND_HOME"
    TRANSIT = "TRANSIT"
    MEDICAL = "MEDICAL"
    OTHER = "OTHER"


class ViolationEnum(str, Enum):
    OVERSTAY = "OVERSTAY"
    DEPORTATION = "DEPORTATION"
    BLACKLIST = "BLACKLIST"
    IMMIGRATION_INVESTIGATION = "IMMIGRATION_INVESTIGATION"
    OTHER = "OTHER"


class MaritalStatusEnum(str, Enum):
    SINGLE = "SINGLE"
    MARRIED = "MARRIED"
    DIVORCED = "DIVORCED"
    WIDOWED = "WIDOWED"
    OTHER = "OTHER"


class EntryPatternEnum(str, Enum):
    SINGLE = "SINGLE"
    MULTIPLE = "MULTIPLE"


class ApplicationChannelEnum(str, Enum):
    OFFSHORE = "OFFSHORE"
    ONSHORE_CONVERSION = "ONSHORE_CONVERSION"
    STATUS_BRIDGING = "STATUS_BRIDGING"


class RelationEnum(str, Enum):
    SPOUSE = "SPOUSE"
    CHILD = "CHILD"
    PARENT = "PARENT"
    DEPENDENT = "DEPENDENT"
    OTHER = "OTHER"


class ProposedRoleEnum(str, Enum):
    SHAREHOLDER_DIRECTOR = "SHAREHOLDER_DIRECTOR"
    SHAREHOLDER_COMMISSIONER = "SHAREHOLDER_COMMISSIONER"
    EMPLOYEE = "EMPLOYEE"
    NO_OPERATIONAL_ROLE = "NO_OPERATIONAL_ROLE"
    OTHER = "OTHER"


class StudyLevelEnum(str, Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    VOCATIONAL = "VOCATIONAL"
    UNDERGRADUATE = "UNDERGRADUATE"
    POSTGRADUATE = "POSTGRADUATE"
    RESEARCH = "RESEARCH"
    OTHER = "OTHER"


# --- ApplicantFacts: UNKNOWN{reason} / KNOWN{value} per fact path ----------


class UnknownFact(_StrictModel):
    """Matches ``$defs.UnknownFact`` exactly."""

    status: Literal["UNKNOWN"]
    reason: UnknownReason


class KnownBoolean(_StrictModel):
    status: Literal["KNOWN"]
    value: StrictBool


class KnownDate(_StrictModel):
    status: Literal["KNOWN"]
    value: date


class KnownString(_StrictModel):
    status: Literal["KNOWN"]
    value: Annotated[str, Field(min_length=1, max_length=64)]


class KnownNonNegativeInteger(_StrictModel):
    status: Literal["KNOWN"]
    value: Annotated[StrictInt, Field(ge=0, le=_INT_MAX)]


class KnownMoney(_StrictModel):
    status: Literal["KNOWN"]
    value: Annotated[StrictInt, Field(ge=0, le=_INT_MAX)]


class KnownCountryCode(_StrictModel):
    status: Literal["KNOWN"]
    value: Annotated[str, Field(pattern=r"^[A-Z]{2}$")]


class KnownCountrySet(_StrictModel):
    status: Literal["KNOWN"]
    value: Annotated[
        tuple[Annotated[str, Field(pattern=r"^[A-Z]{2}$")], ...],
        Field(min_length=1, max_length=4),
    ]

    _unique_value = field_validator("value")(_require_unique)


class KnownPurposeSet(_StrictModel):
    status: Literal["KNOWN"]
    value: Annotated[tuple[PurposeEnum, ...], Field(min_length=1, max_length=8)]

    _unique_value = field_validator("value")(_require_unique)


class KnownViolationSet(_StrictModel):
    status: Literal["KNOWN"]
    value: Annotated[tuple[ViolationEnum, ...], Field(max_length=8)]

    _unique_value = field_validator("value")(_require_unique)


class KnownMaritalStatus(_StrictModel):
    status: Literal["KNOWN"]
    value: MaritalStatusEnum


class KnownEntryPattern(_StrictModel):
    status: Literal["KNOWN"]
    value: EntryPatternEnum


class KnownApplicationChannel(_StrictModel):
    status: Literal["KNOWN"]
    value: ApplicationChannelEnum


class KnownRelation(_StrictModel):
    status: Literal["KNOWN"]
    value: RelationEnum


class KnownProposedRole(_StrictModel):
    status: Literal["KNOWN"]
    value: ProposedRoleEnum


class KnownStudyLevel(_StrictModel):
    status: Literal["KNOWN"]
    value: StudyLevelEnum


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


class ApplicantFactsData(_StrictModel):
    """The ``facts`` sub-object of ``ApplicantFacts`` — matches
    ``$defs.ApplicantFacts.properties.facts`` exactly: 35 dotted-path keys,
    ``additionalProperties: false``. Python attribute names are the dotted
    path with ``.`` -> ``_``; the wire alias is the exact dotted path."""

    person_birth_date: DateFact = Field(alias="person.birth_date")
    person_nationalities: CountrySetFact = Field(alias="person.nationalities")
    person_marital_status: MaritalStatusFact = Field(alias="person.marital_status")
    immigration_currently_in_indonesia: BooleanFact = Field(
        alias="immigration.currently_in_indonesia"
    )
    immigration_current_status_code: StringFact = Field(alias="immigration.current_status_code")
    immigration_current_status_expiry: DateFact = Field(alias="immigration.current_status_expiry")
    immigration_last_entry_date: DateFact = Field(alias="immigration.last_entry_date")
    immigration_overstay_days: NonNegativeIntegerFact = Field(alias="immigration.overstay_days")
    immigration_violation_history: ViolationSetFact = Field(alias="immigration.violation_history")
    intent_purposes: PurposeSetFact = Field(alias="intent.purposes")
    intent_stay_days: NonNegativeIntegerFact = Field(alias="intent.stay_days")
    intent_desired_entry_date: DateFact = Field(alias="intent.desired_entry_date")
    intent_entry_pattern: EntryPatternFact = Field(alias="intent.entry_pattern")
    intent_requested_product_code: StringFact = Field(alias="intent.requested_product_code")
    work_employer_country_code: CountryCodeFact = Field(alias="work.employer_country_code")
    work_employer_is_indonesian_entity: BooleanFact = Field(
        alias="work.employer_is_indonesian_entity"
    )
    work_serves_indonesian_clients: BooleanFact = Field(alias="work.serves_indonesian_clients")
    work_indonesia_source_compensation: BooleanFact = Field(
        alias="work.indonesia_source_compensation"
    )
    work_indonesian_work_sponsor_confirmed: BooleanFact = Field(
        alias="work.indonesian_work_sponsor_confirmed"
    )
    investment_pt_pma_committed: BooleanFact = Field(alias="investment.pt_pma_committed")
    investment_investment_capital_idr: MoneyFact = Field(alias="investment.investment_capital_idr")
    investment_paid_up_capital_idr: MoneyFact = Field(alias="investment.paid_up_capital_idr")
    investment_proposed_role: ProposedRoleFact = Field(alias="investment.proposed_role")
    family_relation_to_sponsor: RelationFact = Field(alias="family.relation_to_sponsor")
    family_sponsor_nationalities: CountrySetFact = Field(alias="family.sponsor_nationalities")
    family_sponsor_status_code: StringFact = Field(alias="family.sponsor_status_code")
    family_marriage_registered: BooleanFact = Field(alias="family.marriage_registered")
    family_sponsor_confirmed: BooleanFact = Field(alias="family.sponsor_confirmed")
    study_level: StudyLevelFact = Field(alias="study.level")
    study_admission_confirmed: BooleanFact = Field(alias="study.admission_confirmed")
    study_sponsor_confirmed: BooleanFact = Field(alias="study.sponsor_confirmed")
    process_application_channel: ApplicationChannelFact = Field(alias="process.application_channel")
    process_wants_onshore_conversion: BooleanFact = Field(alias="process.wants_onshore_conversion")
    commercial_service_fee_budget_idr: MoneyFact = Field(alias="commercial.service_fee_budget_idr")
    commercial_wants_quote: BooleanFact = Field(alias="commercial.wants_quote")


class ApplicantFacts(_StrictModel):
    """Matches ``$defs.ApplicantFacts``. Public API model #4."""

    schema_version: Literal["1.0.0"]
    assessment_id: UUID
    collected_at: UtcDateTime
    facts: ApplicantFactsData


# --- Rule + RuleEffect ------------------------------------------------------


class ExcludeEffect(_StrictModel):
    type: Literal["EXCLUDE"]
    reason_code: ReasonCode


class SupportEffect(_StrictModel):
    type: Literal["SUPPORT"]
    reason_code: ReasonCode
    covered_purposes: Annotated[tuple[PurposeEnum, ...], Field(min_length=1)]

    _unique_covered_purposes = field_validator("covered_purposes")(_require_unique)


class RequireReviewEffect(_StrictModel):
    type: Literal["REQUIRE_REVIEW"]
    reason_code: ReasonCode


class AddScoreEffect(_StrictModel):
    type: Literal["ADD_SCORE"]
    reason_code: ReasonCode
    points: Annotated[StrictInt, Field(ge=-10000, le=10000)]


RuleEffect = Annotated[
    ExcludeEffect | SupportEffect | RequireReviewEffect | AddScoreEffect,
    Field(discriminator="type"),
]

_STAGE_EFFECT_TYPE: dict[RuleStage, str] = {
    RuleStage.HARD_FILTER: "EXCLUDE",
    RuleStage.ELIGIBILITY: "SUPPORT",
    RuleStage.HUMAN_REVIEW: "REQUIRE_REVIEW",
    RuleStage.RANKING: "ADD_SCORE",
}


class Rule(_StrictModel):
    """Matches ``$defs.Rule``. Public API model #2.

    ``product_version_ids`` is the ONE field in the entire contract that is
    genuinely optional (only required when ``scope == "PRODUCTS"``) —
    everywhere else, a "required" JSON key has no Python default.
    """

    rule_id: Identifier
    stage: RuleStage
    scope: Literal["GLOBAL", "PRODUCTS"]
    product_version_ids: Annotated[tuple[UUID, ...], Field(min_length=1, max_length=256)] | None = (
        None
    )
    priority: Annotated[StrictInt, Field(ge=0, le=100000)]
    valid_period: TimeRange
    when: Condition
    effect: RuleEffect
    on_unknown: Literal["NEEDS_INPUT", "HUMAN_REVIEW", "NO_EFFECT"]
    required_facts: Annotated[tuple[FactPath, ...], Field(max_length=128)]
    source_refs: Annotated[tuple[UUID, ...], Field(min_length=1, max_length=32)]
    explanation_key: Identifier
    safety_critical: StrictBool

    _unique_product_version_ids = field_validator("product_version_ids")(_require_unique)
    _unique_required_facts = field_validator("required_facts")(_require_unique)
    _unique_source_refs = field_validator("source_refs")(_require_unique)

    @model_validator(mode="after")
    def _check_scope_and_stage(self) -> Rule:
        if self.scope == "GLOBAL":
            if self.product_version_ids is not None:
                raise ValueError("GLOBAL-scope rules must not set product_version_ids")
        elif not self.product_version_ids:
            raise ValueError("PRODUCTS-scope rules require a non-empty product_version_ids")

        expected = _STAGE_EFFECT_TYPE[self.stage]
        if self.effect.type != expected:
            raise ValueError(
                f"stage {self.stage.value} requires effect.type={expected!r}, "
                f"got {self.effect.type!r}"
            )
        return self

    @model_serializer(mode="wrap")
    def _serialize_omit_null_product_version_ids(self, handler: Any) -> dict[str, Any]:
        """The schema requires ``product_version_ids`` to be ABSENT (not
        ``null``) for ``GLOBAL``-scope rules (``"then": {"not": {"required":
        [...]}}``) — unlike every other nullable field in the contract, which
        must stay present-but-null. Drop the key only when it's ``None``."""

        data = handler(self)
        if data.get("product_version_ids") is None:
            data.pop("product_version_ids", None)
        return data


# --- SourceRecord ------------------------------------------------------------


class Locator(_StrictModel):
    kind: Literal["ARTICLE", "SECTION", "PAGE", "PARAGRAPH", "ANCHOR"]
    value: Annotated[str, Field(min_length=1, max_length=256)]


class SourceRecord(_StrictModel):
    """Matches ``$defs.SourceRecord``. Public API model #7."""

    source_record_id: UUID
    source_key: Identifier
    version: Annotated[StrictInt, Field(ge=1, le=_INT_MAX)]
    authority_type: Literal[
        "PRIMARY_LAW",
        "IMPLEMENTING_REGULATION",
        "OFFICIAL_PORTAL",
        "OFFICIAL_CIRCULAR",
        "BALI_ZERO_POLICY",
        "PRICING_CATALOG",
    ]
    status: Literal["VERIFIED", "SUPERSEDED", "REVOKED", "UNAVAILABLE"]
    jurisdiction: Literal["ID"]
    title: Annotated[str, Field(min_length=1, max_length=512)]
    publisher: Annotated[str, Field(min_length=1, max_length=256)]
    canonical_url: UriStr
    language: Annotated[str, Field(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")]
    document_number: Annotated[str, Field(max_length=256)] | None
    locators: Annotated[tuple[Locator, ...], Field(max_length=64)]
    content_sha256: Sha256Hex
    legal_period: TimeRange
    recorded_period: TimeRange
    retrieved_at: UtcDateTime
    verified_at: UtcDateTime
    verified_by: Identifier
    supersedes_source_record_id: UUID | None


# --- VisaProductVersion ------------------------------------------------------


class PricingKey(_StrictModel):
    category: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
    item_key: Annotated[str, Field(min_length=1, max_length=256)]


class ProductNames(_StrictModel):
    id: Annotated[str, Field(min_length=1, max_length=256)]
    en: Annotated[str, Field(min_length=1, max_length=256)]


class EntryPolicy(_StrictModel):
    entry_count: Literal["SINGLE", "MULTIPLE", "NOT_APPLICABLE"]


class StayPolicy(_StrictModel):
    kind: Literal["FIXED_DAYS", "VARIABLE_BY_GRANT", "NOT_APPLICABLE"]
    minimum_days: Annotated[StrictInt, Field(ge=0, le=36500)] | None
    maximum_days: Annotated[StrictInt, Field(ge=0, le=36500)] | None


class ExtensionPolicy(_StrictModel):
    allowed: StrictBool
    maximum_extensions: Annotated[StrictInt, Field(ge=0, le=100)]
    days_per_extension: Annotated[StrictInt, Field(ge=1, le=3650)] | None


class ClockCheckpointSpec(_StrictModel):
    code: Identifier
    offset_days: Annotated[StrictInt, Field(ge=-3650, le=36500)]
    title_key: Identifier
    body_key: Identifier


class ClockPolicy(_StrictModel):
    available: StrictBool
    anchor: Literal["ENTRY_DATE", "PERMIT_ISSUED_AT", "NOT_APPLICABLE"]
    checkpoints: Annotated[tuple[ClockCheckpointSpec, ...], Field(max_length=64)]


class VisaProductVersion(_StrictModel):
    """Matches ``$defs.VisaProductVersion``. Public API model #3."""

    product_version_id: UUID
    product_code: ProductCode
    legacy_codes: tuple[ProductCode, ...]
    legacy_slugs: tuple[Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")], ...]
    names: ProductNames
    category: Literal[
        "SHORT_STAY", "MULTIPLE_ENTRY", "LIMITED_STAY", "PERMANENT_STAY", "TRANSIT", "OTHER"
    ]
    status: Literal["ACTIVE", "DEPRECATED", "OBSOLETE"]
    valid_period: TimeRange
    covered_purposes: Annotated[tuple[PurposeEnum, ...], Field(min_length=1)]
    prohibited_activities: tuple[Identifier, ...]
    sponsor_types: tuple[
        Literal["NONE", "INDIVIDUAL", "EMPLOYER", "EDUCATION", "INVESTMENT", "GOVERNMENT"], ...
    ]
    entry_policy: EntryPolicy
    stay_policy: StayPolicy
    extension_policy: ExtensionPolicy
    clock_policy: ClockPolicy
    pricing_key: PricingKey | None
    source_refs: Annotated[tuple[UUID, ...], Field(min_length=1)]
    public_catalog: StrictBool

    _unique_legacy_codes = field_validator("legacy_codes")(_require_unique)
    _unique_legacy_slugs = field_validator("legacy_slugs")(_require_unique)
    _unique_covered_purposes = field_validator("covered_purposes")(_require_unique)
    _unique_prohibited_activities = field_validator("prohibited_activities")(_require_unique)
    _unique_sponsor_types = field_validator("sponsor_types")(_require_unique)
    _unique_source_refs = field_validator("source_refs")(_require_unique)


# --- RulePack (signed envelope) ---------------------------------------------


class HitPolicy(_StrictModel):
    hard_filter: Literal["COLLECT_ALL"]
    eligibility: Literal["COVER_ALL_DECLARED_PURPOSES"]
    human_review: Literal["COLLECT_ALL"]
    ranking: Literal["SUM_TRUE_INTEGER_WEIGHTS"]


class ProtectedHeader(_StrictModel):
    domain: Literal["balizero.visa-rulepack.v1"]
    alg: Literal["Ed25519"]
    kid: Identifier
    signed_at: UtcDateTime
    schema_version: Literal["1.0.0"]
    environment: Literal["TEST", "STAGING", "PRODUCTION"]


class RulePackPayload(_StrictModel):
    rule_pack_id: UUID
    sequence: Annotated[StrictInt, Field(ge=1, le=_INT_MAX)]
    version: SemVer
    environment: Literal["TEST", "STAGING", "PRODUCTION"]
    jurisdiction: Literal["ID"]
    decision_domain: Literal["IMMIGRATION_VISA"]
    engine_contract_version: Literal["1.0.0"]
    engine_min_version: SemVer
    engine_max_version: SemVer
    valid_period: TimeRange
    created_at: UtcDateTime
    created_by: Identifier
    previous_payload_sha256: Sha256Hex | None
    rollback_of_payload_sha256: Sha256Hex | None
    hit_policy: HitPolicy
    source_records: Annotated[tuple[SourceRecord, ...], Field(min_length=1, max_length=4096)]
    products: Annotated[tuple[VisaProductVersion, ...], Field(min_length=1, max_length=256)]
    rules: Annotated[tuple[Rule, ...], Field(min_length=1, max_length=4096)]

    @model_validator(mode="after")
    def _check_sequence_previous_hash(self) -> RulePackPayload:
        if self.sequence == 1:
            if self.previous_payload_sha256 is not None:
                raise ValueError("sequence=1 requires previous_payload_sha256=null")
        elif self.previous_payload_sha256 is None:
            raise ValueError("sequence>1 requires a non-null previous_payload_sha256")
        return self


class RulePack(_StrictModel):
    """The signed envelope. Matches ``$defs.RulePack``. Public API model #1."""

    canonicalization: Literal["RFC8785"]
    protected: ProtectedHeader
    payload: RulePackPayload
    payload_sha256: Sha256Hex
    signature: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{86}$")]


# --- PriceQuote ---------------------------------------------------------


class PriceQuote(_StrictModel):
    """Matches ``$defs.PriceQuote``. Public API model #6."""

    quote_id: UUID
    product_version_id: UUID
    product_code: ProductCode
    status: Literal["AVAILABLE", "CONTACT_REQUIRED", "UNAVAILABLE"]
    currency: Literal["IDR"]
    amount: Annotated[StrictInt, Field(ge=0, le=_INT_MAX)] | None
    pricing_key: PricingKey
    catalog_version: Annotated[str, Field(min_length=1, max_length=64)] | None
    catalog_sha256: Sha256Hex | None
    row_sha256: Sha256Hex | None
    quoted_at: UtcDateTime
    valid_until: UtcDateTime | None
    reason_code: ReasonCode

    @model_validator(mode="after")
    def _check_status_amount(self) -> PriceQuote:
        if self.status == "AVAILABLE":
            if self.amount is None:
                raise ValueError("AVAILABLE quote requires a non-null amount")
            if (
                self.catalog_version is None
                or self.catalog_sha256 is None
                or self.row_sha256 is None
            ):
                raise ValueError(
                    "AVAILABLE quote requires catalog_version/catalog_sha256/row_sha256"
                )
        elif self.amount is not None:
            raise ValueError("non-AVAILABLE quote must have amount=null")
        return self


# --- Decision -----------------------------------------------------------


class RulePackRef(_StrictModel):
    rule_pack_id: UUID
    sequence: Annotated[StrictInt, Field(ge=1, le=_INT_MAX)]
    version: str
    payload_sha256: Sha256Hex


class Fingerprint(_StrictModel):
    algorithm: Literal["HMAC-SHA256"]
    key_id: Identifier
    digest: Sha256Hex


class Reason(_StrictModel):
    code: ReasonCode
    rule_ids: tuple[Identifier, ...]
    source_refs: tuple[UUID, ...]

    _unique_rule_ids = field_validator("rule_ids")(_require_unique)
    _unique_source_refs = field_validator("source_refs")(_require_unique)


class Outage(_StrictModel):
    code: ReasonCode
    retryable: StrictBool


class CandidateDecision(_StrictModel):
    """Matches ``$defs.Candidate``. Public API model #8 (named ``CandidateDecision``
    in the Python API to avoid clashing with any future "raw candidate"
    concept in ``evaluator.py``)."""

    rank: Annotated[StrictInt, Field(ge=1, le=256)]
    product_version_id: UUID
    product_code: ProductCode
    score: Annotated[StrictInt, Field(ge=-1000000, le=1000000)]
    covered_purposes: Annotated[tuple[str, ...], Field(min_length=1)]
    support_rule_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    source_refs: Annotated[tuple[UUID, ...], Field(min_length=1)]
    reason_codes: Annotated[tuple[ReasonCode, ...], Field(min_length=1)]

    _unique_covered_purposes = field_validator("covered_purposes")(_require_unique)
    _unique_support_rule_ids = field_validator("support_rule_ids")(_require_unique)
    _unique_source_refs = field_validator("source_refs")(_require_unique)
    _unique_reason_codes = field_validator("reason_codes")(_require_unique)


class Decision(_StrictModel):
    """Matches ``$defs.Decision``. Public API model #5."""

    schema_version: Literal["1.0.0"]
    decision_id: UUID | None
    public_id: Annotated[str, Field(pattern=r"^[a-z0-9]{16,20}$")] | None
    state: DecisionState
    effective_at: UtcDateTime
    observed_at: UtcDateTime
    evaluated_at: UtcDateTime
    rule_pack: RulePackRef | None
    facts_fingerprint: Fingerprint
    candidates: Annotated[tuple[CandidateDecision, ...], Field(max_length=256)]
    missing_facts: tuple[ApplicantFactPath, ...]
    review_reasons: tuple[Reason, ...]
    no_path_reasons: tuple[Reason, ...]
    outage: Outage | None
    quotes: tuple[PriceQuote, ...]
    notices: tuple[Reason, ...]
    trace_sha256: Sha256Hex | None
    decision_integrity: Fingerprint | None

    _unique_missing_facts = field_validator("missing_facts")(_require_unique)

    @model_validator(mode="after")
    def _check_state_invariants(self) -> Decision:
        state = self.state

        if state != DecisionState.SUPPORTED_CANDIDATES:
            if self.candidates:
                raise ValueError(f"{state.value} must have empty candidates")
            if self.quotes:
                raise ValueError(f"{state.value} must have empty quotes")

        if state == DecisionState.SUPPORTED_CANDIDATES:
            self._require_persisted()
            if not self.candidates:
                raise ValueError("SUPPORTED_CANDIDATES requires at least one candidate")
            if self.missing_facts or self.review_reasons or self.no_path_reasons:
                raise ValueError(
                    "SUPPORTED_CANDIDATES must have empty "
                    "missing_facts/review_reasons/no_path_reasons"
                )
            if self.outage is not None:
                raise ValueError("SUPPORTED_CANDIDATES must have outage=null")

        elif state == DecisionState.NEEDS_INPUT:
            self._require_persisted()
            if not self.missing_facts:
                raise ValueError("NEEDS_INPUT requires at least one missing fact")
            if self.review_reasons or self.no_path_reasons:
                raise ValueError("NEEDS_INPUT must have empty review_reasons/no_path_reasons")
            if self.outage is not None:
                raise ValueError("NEEDS_INPUT must have outage=null")

        elif state == DecisionState.HUMAN_REVIEW_REQUIRED:
            self._require_persisted()
            if self.missing_facts:
                raise ValueError("HUMAN_REVIEW_REQUIRED must have empty missing_facts")
            if not self.review_reasons:
                raise ValueError("HUMAN_REVIEW_REQUIRED requires at least one review reason")
            if self.no_path_reasons:
                raise ValueError("HUMAN_REVIEW_REQUIRED must have empty no_path_reasons")
            if self.outage is not None:
                raise ValueError("HUMAN_REVIEW_REQUIRED must have outage=null")

        elif state == DecisionState.NO_SUPPORTED_PATH:
            self._require_persisted()
            if self.missing_facts or self.review_reasons:
                raise ValueError("NO_SUPPORTED_PATH must have empty missing_facts/review_reasons")
            if not self.no_path_reasons:
                raise ValueError("NO_SUPPORTED_PATH requires at least one no-path reason")
            if self.outage is not None:
                raise ValueError("NO_SUPPORTED_PATH must have outage=null")

        elif state == DecisionState.TEMPORARILY_UNAVAILABLE:
            if self.missing_facts or self.review_reasons or self.no_path_reasons:
                raise ValueError(
                    "TEMPORARILY_UNAVAILABLE must have empty "
                    "missing_facts/review_reasons/no_path_reasons"
                )
            if self.outage is None:
                raise ValueError("TEMPORARILY_UNAVAILABLE requires a non-null outage")

        self._check_quotes_reference_real_candidates()
        return self

    def _check_quotes_reference_real_candidates(self) -> None:
        """F6: a ``PriceQuote`` for a product the decision never actually
        offered (or one whose ``product_code`` doesn't match the candidate
        it claims to price) is a data-integrity bug — quoting is downstream
        of candidate selection, never independent of it."""

        candidates_by_id = {c.product_version_id: c.product_code for c in self.candidates}
        for quote in self.quotes:
            if quote.product_version_id not in candidates_by_id:
                raise ValueError(
                    f"quote {quote.quote_id} references product_version_id "
                    f"{quote.product_version_id}, which is not among this "
                    "decision's candidates"
                )
            expected_code = candidates_by_id[quote.product_version_id]
            if quote.product_code != expected_code:
                raise ValueError(
                    f"quote {quote.quote_id} has product_code {quote.product_code!r} "
                    f"but candidate {quote.product_version_id} has product_code "
                    f"{expected_code!r}"
                )

    def _require_persisted(self) -> None:
        if self.decision_id is None or self.public_id is None or self.rule_pack is None:
            raise ValueError(
                f"{self.state.value} requires non-null decision_id/public_id/rule_pack"
            )


# --- Python-only service models (no JSON Schema entrypoint) -----------------


class ConsentEvent(_StrictModel):
    """Public API model #9. No wire schema exists for this (§2 packages only
    8 entrypoints) — field set derived from ``ConsentService.record_event``/
    ``withdraw`` signatures in the spec (section 1, ``consent.py``, out of
    PR1 scope)."""

    consent_event_id: UUID
    receipt_type: Annotated[str, Field(min_length=1, max_length=128)]
    action: Annotated[str, Field(min_length=1, max_length=128)]
    purpose: Annotated[str, Field(min_length=1, max_length=128)]
    legal_basis: Annotated[str, Field(min_length=1, max_length=128)]
    policy_version: Annotated[str, Field(min_length=1, max_length=64)]
    policy_text_sha256: Sha256Hex
    locale: Annotated[str, Field(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")]
    session_id: UUID
    decision_id: UUID | None
    occurred_at: UtcDateTime
    idempotency_key: Annotated[str, Field(min_length=1, max_length=256)]
    prior_event_id: UUID | None = None


class EvaluationContext(_StrictModel):
    """Public API model #10. No wire schema exists for this. Deliberately
    omits a ``trace`` field (``TraceBuilder`` lives in ``trace.py``, out of
    PR1 scope) — extend when ``trace.py`` lands."""

    effective_at: UtcDateTime
    observed_at: UtcDateTime
    environment: Literal["TEST", "STAGING", "PRODUCTION"]
    request_id: UUID | None = None
