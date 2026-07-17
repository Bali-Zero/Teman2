"""Closed vocabularies for the Visa Oracle v2 rule engine.

Every enum here is a *closed, audited vocabulary by design* (spec §5.2): a
RulePack never carries a Python/JS/regex/LLM predicate, only these fixed
tokens. Source: ``research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
concretization.md`` §1 (module layout, ``enums.py``) and §2 (JSON Schema
2020-12 contract, ``$defs``).

PR1 scope note: this module holds every closed vocabulary the PR1 package
needs (models.py, ast.py, fact_registry.py, compiler.py). A few groups exist
in the spec's JSON Schema but are not literal Python ``class ... (Enum)``
declarations in §1's ``enums.py`` snippet (e.g. ``VisaPurpose``,
``SourceAuthorityType``, the per-fact value enums). They are added here
rather than duplicated across modules, keeping "closed vocabulary" ownership
in one place as instructed.
"""

from __future__ import annotations

from enum import Enum

# ---------------------------------------------------------------------------
# Core engine vocabularies (spec §1 enums.py, verbatim)
# ---------------------------------------------------------------------------


class TruthValue(str, Enum):
    """Tri-state Kleene logic value a condition evaluates to (spec §4.1).

    PR1 does not evaluate conditions (that is PR3's ``evaluator.py``), but
    every downstream consumer needs this vocabulary to exist and be closed.
    """

    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


class DecisionState(str, Enum):
    """The exactly-one-of-five global states a Decision resolves to (spec §5.3).

    Precedence (highest first): TEMPORARILY_UNAVAILABLE (unavailable pack
    fails closed) > HUMAN_REVIEW_REQUIRED > SUPPORTED_CANDIDATES >
    NEEDS_INPUT > NO_SUPPORTED_PATH.
    """

    NEEDS_INPUT = "NEEDS_INPUT"
    SUPPORTED_CANDIDATES = "SUPPORTED_CANDIDATES"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    NO_SUPPORTED_PATH = "NO_SUPPORTED_PATH"
    TEMPORARILY_UNAVAILABLE = "TEMPORARILY_UNAVAILABLE"


class RuleStage(str, Enum):
    """The four rule stages, evaluated in this strict order (spec §5.3).

    HARD_FILTER: any TRUE excludes the product outright.
    ELIGIBILITY: SUPPORT rules whose ``covered_purposes`` union must cover
        every declared purpose (``COVER_ALL_DECLARED_PURPOSES``).
    HUMAN_REVIEW: any TRUE forces HUMAN_REVIEW_REQUIRED, no candidate emitted.
    RANKING: only runs on already-SUPPORTED products; integer score deltas.
    """

    HARD_FILTER = "HARD_FILTER"
    ELIGIBILITY = "ELIGIBILITY"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    RANKING = "RANKING"


class EngineMode(str, Enum):
    """Per-surface rollout mode (spec §1 ``enums.py``). PR1 declares this
    closed vocabulary only — ``VisaEngineModeResolver.resolve()`` (spec §1)
    is the PR2+ evaluator-config concern that actually reads it; nothing in
    PR1 wires a Pydantic field to this enum yet.
    """

    OFF = "OFF"
    SHADOW = "SHADOW"
    ENFORCE = "ENFORCE"


class EngineSurface(str, Enum):
    """Every call-site the engine can be gated per (spec §1 ``enums.py``).
    Same PR1-declares-only note as ``EngineMode`` above.
    """

    CLOCK = "CLOCK"
    MATCH = "MATCH"
    RECOMMEND = "RECOMMEND"
    CATALOG = "CATALOG"
    CHAT_CONTEXT = "CHAT_CONTEXT"
    HANDOFF = "HANDOFF"


class HitPolicy(str, Enum):
    """Per-stage aggregation policy (spec §2 ``RulePackPayload.hit_policy``).

    Every RulePack declares all four as fixed consts (JSON Schema ``const``
    per field) — this is not a per-rule choice, it is the one fixed
    engine-wide policy stated in the payload for auditability.
    """

    COLLECT_ALL = "COLLECT_ALL"
    COVER_ALL_DECLARED_PURPOSES = "COVER_ALL_DECLARED_PURPOSES"
    SUM_TRUE_INTEGER_WEIGHTS = "SUM_TRUE_INTEGER_WEIGHTS"


class UnknownReason(str, Enum):
    """Why a fact is UNKNOWN rather than silently absent (spec §2 ``UnknownFact``).

    No fact is ever "just missing" outside the type system — every UNKNOWN
    carries one of these reasons explicitly.
    """

    NOT_ASKED = "NOT_ASKED"
    NOT_PROVIDED = "NOT_PROVIDED"
    UNVERIFIED = "UNVERIFIED"
    CONFLICTING = "CONFLICTING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ConditionOperator(str, Enum):
    """The closed operator vocabulary for the condition AST (spec §1 ``ast.py``, §2 ``Condition``).

    Resolved ambiguity (documented in the PR1 report): spec §1's ``ast.py``
    class list enumerates 16 separate Pydantic classes (``KnownCondition``
    and ``UnknownCondition`` as two distinct classes), while spec §2's JSON
    Schema ``Condition`` ``oneOf`` merges them into one ``PresenceCondition``
    type whose ``op`` is ``enum: ["known", "unknown"]`` — 15 node TYPES,
    which is what the product-design doc's "15 operators" figure counts.
    This package follows §2 (the doc explicitly says "complete — implement
    it exactly"): ``ast.py`` defines 15 node model classes, with
    ``PresenceCondition`` carrying both ``KNOWN`` and ``UNKNOWN``. This enum
    itself still carries all 16 distinct operator string values, since
    ``known``/``unknown`` remain semantically distinct operators.
    """

    ALL = "all"
    ANY = "any"
    NOT = "not"
    KNOWN = "known"
    UNKNOWN = "unknown"
    EQ = "eq"
    NEQ = "neq"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    IN = "in"
    NOT_IN = "not_in"
    BETWEEN = "between"
    INTERSECTS = "intersects"
    CONTAINS_ALL = "contains_all"


# ---------------------------------------------------------------------------
# Rule structure vocabularies (spec §2 ``Rule``, ``RuleEffect``)
# ---------------------------------------------------------------------------


class RuleScope(str, Enum):
    """Whether a rule applies to every product (GLOBAL) or a declared subset (PRODUCTS)."""

    GLOBAL = "GLOBAL"
    PRODUCTS = "PRODUCTS"


class RuleEffectType(str, Enum):
    """The discriminator of ``RuleEffect`` (spec §2), one per ``RuleStage``."""

    EXCLUDE = "EXCLUDE"
    SUPPORT = "SUPPORT"
    REQUIRE_REVIEW = "REQUIRE_REVIEW"
    ADD_SCORE = "ADD_SCORE"


class OnUnknownAction(str, Enum):
    """What an UNKNOWN condition result does to the global decision (spec §2 ``Rule.on_unknown``)."""

    NEEDS_INPUT = "NEEDS_INPUT"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    NO_EFFECT = "NO_EFFECT"


# ---------------------------------------------------------------------------
# Domain enums shared by ``ApplicantFacts``, ``Rule.effect.covered_purposes``,
# and ``VisaProductVersion.covered_purposes`` (spec §2 ``KnownPurposeSet`` etc.)
# ---------------------------------------------------------------------------


class VisaPurpose(str, Enum):
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


class ViolationType(str, Enum):
    OVERSTAY = "OVERSTAY"
    DEPORTATION = "DEPORTATION"
    BLACKLIST = "BLACKLIST"
    IMMIGRATION_INVESTIGATION = "IMMIGRATION_INVESTIGATION"
    OTHER = "OTHER"


class MaritalStatus(str, Enum):
    SINGLE = "SINGLE"
    MARRIED = "MARRIED"
    DIVORCED = "DIVORCED"
    WIDOWED = "WIDOWED"
    OTHER = "OTHER"


class EntryPattern(str, Enum):
    SINGLE = "SINGLE"
    MULTIPLE = "MULTIPLE"


class ApplicationChannel(str, Enum):
    OFFSHORE = "OFFSHORE"
    ONSHORE_CONVERSION = "ONSHORE_CONVERSION"
    STATUS_BRIDGING = "STATUS_BRIDGING"


class RelationType(str, Enum):
    SPOUSE = "SPOUSE"
    CHILD = "CHILD"
    PARENT = "PARENT"
    DEPENDENT = "DEPENDENT"
    OTHER = "OTHER"


class ProposedRole(str, Enum):
    SHAREHOLDER_DIRECTOR = "SHAREHOLDER_DIRECTOR"
    SHAREHOLDER_COMMISSIONER = "SHAREHOLDER_COMMISSIONER"
    EMPLOYEE = "EMPLOYEE"
    NO_OPERATIONAL_ROLE = "NO_OPERATIONAL_ROLE"
    OTHER = "OTHER"


class StudyLevel(str, Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    VOCATIONAL = "VOCATIONAL"
    UNDERGRADUATE = "UNDERGRADUATE"
    POSTGRADUATE = "POSTGRADUATE"
    RESEARCH = "RESEARCH"
    OTHER = "OTHER"


# ---------------------------------------------------------------------------
# VisaProductVersion vocabularies (spec §2)
# ---------------------------------------------------------------------------


class VisaProductCategory(str, Enum):
    SHORT_STAY = "SHORT_STAY"
    MULTIPLE_ENTRY = "MULTIPLE_ENTRY"
    LIMITED_STAY = "LIMITED_STAY"
    PERMANENT_STAY = "PERMANENT_STAY"
    TRANSIT = "TRANSIT"
    OTHER = "OTHER"


class VisaProductStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    OBSOLETE = "OBSOLETE"


class SponsorType(str, Enum):
    NONE = "NONE"
    INDIVIDUAL = "INDIVIDUAL"
    EMPLOYER = "EMPLOYER"
    EDUCATION = "EDUCATION"
    INVESTMENT = "INVESTMENT"
    GOVERNMENT = "GOVERNMENT"


class EntryCount(str, Enum):
    SINGLE = "SINGLE"
    MULTIPLE = "MULTIPLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class StayPolicyKind(str, Enum):
    FIXED_DAYS = "FIXED_DAYS"
    VARIABLE_BY_GRANT = "VARIABLE_BY_GRANT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ClockAnchor(str, Enum):
    ENTRY_DATE = "ENTRY_DATE"
    PERMIT_ISSUED_AT = "PERMIT_ISSUED_AT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


# ---------------------------------------------------------------------------
# SourceRecord vocabularies (spec §2)
# ---------------------------------------------------------------------------


class SourceAuthorityType(str, Enum):
    PRIMARY_LAW = "PRIMARY_LAW"
    IMPLEMENTING_REGULATION = "IMPLEMENTING_REGULATION"
    OFFICIAL_PORTAL = "OFFICIAL_PORTAL"
    OFFICIAL_CIRCULAR = "OFFICIAL_CIRCULAR"
    BALI_ZERO_POLICY = "BALI_ZERO_POLICY"
    PRICING_CATALOG = "PRICING_CATALOG"


class SourceStatus(str, Enum):
    VERIFIED = "VERIFIED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
    UNAVAILABLE = "UNAVAILABLE"


class SourceLocatorKind(str, Enum):
    ARTICLE = "ARTICLE"
    SECTION = "SECTION"
    PAGE = "PAGE"
    PARAGRAPH = "PARAGRAPH"
    ANCHOR = "ANCHOR"


class Environment(str, Enum):
    """RulePack target environment (spec §2 ``RulePackPayload.environment`` / ``ProtectedHeader.environment``)."""

    TEST = "TEST"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"


# ---------------------------------------------------------------------------
# FactPath — the closed 38-path fact vocabulary (35 applicant + 3 derived; spec §2 ``FactPath``)
# ---------------------------------------------------------------------------


class FactPath(str, Enum):
    """Every fact path the engine may ever reference — 35 applicant-collected
    + 3 derived (spec §2 ``ApplicantFactPath`` + ``FactPath``).

    Closed by design (spec §5.2): a Condition's ``fact`` field and a Rule's
    ``required_facts`` array are both typed against this enum, so a rule
    that references an unknown fact path is a Pydantic ``ValidationError``
    at parse time, not a runtime surprise. ``fact_registry.py`` layers typed
    metadata (value kind, PII class, commercial flag) on top of this same
    vocabulary — see that module's docstring for why both exist.
    """

    # person.*
    PERSON_BIRTH_DATE = "person.birth_date"
    PERSON_NATIONALITIES = "person.nationalities"
    PERSON_MARITAL_STATUS = "person.marital_status"
    # immigration.*
    IMMIGRATION_CURRENTLY_IN_INDONESIA = "immigration.currently_in_indonesia"
    IMMIGRATION_CURRENT_STATUS_CODE = "immigration.current_status_code"
    IMMIGRATION_CURRENT_STATUS_EXPIRY = "immigration.current_status_expiry"
    IMMIGRATION_LAST_ENTRY_DATE = "immigration.last_entry_date"
    IMMIGRATION_OVERSTAY_DAYS = "immigration.overstay_days"
    IMMIGRATION_VIOLATION_HISTORY = "immigration.violation_history"
    # intent.*
    INTENT_PURPOSES = "intent.purposes"
    INTENT_STAY_DAYS = "intent.stay_days"
    INTENT_DESIRED_ENTRY_DATE = "intent.desired_entry_date"
    INTENT_ENTRY_PATTERN = "intent.entry_pattern"
    INTENT_REQUESTED_PRODUCT_CODE = "intent.requested_product_code"
    # work.*
    WORK_EMPLOYER_COUNTRY_CODE = "work.employer_country_code"
    WORK_EMPLOYER_IS_INDONESIAN_ENTITY = "work.employer_is_indonesian_entity"
    WORK_SERVES_INDONESIAN_CLIENTS = "work.serves_indonesian_clients"
    WORK_INDONESIA_SOURCE_COMPENSATION = "work.indonesia_source_compensation"
    WORK_INDONESIAN_WORK_SPONSOR_CONFIRMED = "work.indonesian_work_sponsor_confirmed"
    # investment.*
    INVESTMENT_PT_PMA_COMMITTED = "investment.pt_pma_committed"
    INVESTMENT_INVESTMENT_CAPITAL_IDR = "investment.investment_capital_idr"
    INVESTMENT_PAID_UP_CAPITAL_IDR = "investment.paid_up_capital_idr"
    INVESTMENT_PROPOSED_ROLE = "investment.proposed_role"
    # family.*
    FAMILY_RELATION_TO_SPONSOR = "family.relation_to_sponsor"
    FAMILY_SPONSOR_NATIONALITIES = "family.sponsor_nationalities"
    FAMILY_SPONSOR_STATUS_CODE = "family.sponsor_status_code"
    FAMILY_MARRIAGE_REGISTERED = "family.marriage_registered"
    FAMILY_SPONSOR_CONFIRMED = "family.sponsor_confirmed"
    # study.*
    STUDY_LEVEL = "study.level"
    STUDY_ADMISSION_CONFIRMED = "study.admission_confirmed"
    STUDY_SPONSOR_CONFIRMED = "study.sponsor_confirmed"
    # process.*
    PROCESS_APPLICATION_CHANNEL = "process.application_channel"
    PROCESS_WANTS_ONSHORE_CONVERSION = "process.wants_onshore_conversion"
    # commercial.* — never usable in a legal-stage (HARD_FILTER/ELIGIBILITY/HUMAN_REVIEW) condition.
    COMMERCIAL_SERVICE_FEE_BUDGET_IDR = "commercial.service_fee_budget_idr"
    COMMERCIAL_WANTS_QUOTE = "commercial.wants_quote"
    # derived.* — computed by fact_registry.py, never collected directly.
    DERIVED_AGE_YEARS = "derived.age_years"
    DERIVED_IS_MINOR = "derived.is_minor"
    DERIVED_HAS_INDONESIAN_CITIZENSHIP = "derived.has_indonesian_citizenship"


#: The 35 applicant-collected paths (everything except ``derived.*``).
APPLICANT_FACT_PATHS: frozenset[FactPath] = frozenset(
    path for path in FactPath if not path.value.startswith("derived.")
)

#: The 3 engine-computed paths, never collected from the applicant directly.
DERIVED_FACT_PATHS: frozenset[FactPath] = frozenset(FactPath) - APPLICANT_FACT_PATHS

#: Facts that describe commercial willingness/budget, never legal eligibility.
#: Compiler invariant (spec §2, compiler-only): these may never appear in a
#: HARD_FILTER/ELIGIBILITY/HUMAN_REVIEW condition, and RANKING conditions may
#: reference *only* these (plus derived facts scored as preference, none exist
#: yet in PR1).
COMMERCIAL_FACT_PATHS: frozenset[FactPath] = frozenset(
    {FactPath.COMMERCIAL_SERVICE_FEE_BUDGET_IDR, FactPath.COMMERCIAL_WANTS_QUOTE}
)


# ---------------------------------------------------------------------------
# fact_registry.py-internal vocabularies
# ---------------------------------------------------------------------------


class FactValueKind(str, Enum):
    """The shape a fact's ``KNOWN`` value takes, used by the compiler to reject
    operator/fact-type mismatches (e.g. ``lt`` against a boolean fact, or
    ``eq`` against a set-valued fact) — spec §2 compiler-only invariant
    "fact-path-specific literal types".

    ``STRING`` also covers ISO-8601 dates: they sort correctly under lexical
    ``lt``/``lte``/``gt``/``gte``, so no separate ``DATE`` kind is needed for
    structural (non-evaluating) validation.
    """

    BOOLEAN = "BOOLEAN"
    INTEGER = "INTEGER"
    STRING = "STRING"
    STRING_SET = "STRING_SET"


class PiiClass(str, Enum):
    """UU PDP-aligned sensitivity tier for a fact (CLAUDE.md §14 PII boundary).

    Not present as a named enum in the spec text; added here because the PR1
    mandate explicitly asks ``fact_registry.py`` to carry "fact path -> type/
    allowed values/PII class". ``SENSITIVE`` mirrors CLAUDE.md's own framing
    of "criminal/health/biometric/financial data get heightened treatment" —
    the closest analogues in this domain are immigration violation/overstay
    history and investment capital amounts.
    """

    NONE = "NONE"
    PERSONAL = "PERSONAL"
    SENSITIVE = "SENSITIVE"
