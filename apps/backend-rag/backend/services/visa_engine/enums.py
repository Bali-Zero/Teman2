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

from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType

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
    """The four rule stages (spec §5.3).

    HARD_FILTER: any TRUE excludes the product outright.
    ELIGIBILITY: SUPPORT rules whose ``covered_purposes`` union must cover
        every declared purpose (``COVER_ALL_DECLARED_PURPOSES``).
    HUMAN_REVIEW: any TRUE forces HUMAN_REVIEW_REQUIRED, no candidate emitted.
    RANKING: only runs on already-SUPPORTED products; integer score deltas.

    Declaration order above matches the spec's public API listing — it is
    NOT the semantic processing/evaluation order (PR3 correction: an earlier
    draft of this docstring claimed "evaluated in this strict order" for the
    declaration order itself, which contradicts spec §4.2's own
    ``evaluate_product`` algorithm — HARD_FILTER excludes first, then
    HUMAN_REVIEW is checked BEFORE ELIGIBILITY runs, then RANKING last, only
    over already-SUPPORTED products). For the true processing order use
    :data:`STAGE_ORDER` (or the :attr:`order` property below).
    """

    HARD_FILTER = "HARD_FILTER"
    ELIGIBILITY = "ELIGIBILITY"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    RANKING = "RANKING"

    @property
    def order(self) -> int:
        """Semantic processing order per spec §4.2 (``evaluate_product``)/
        §4.5 (trace ordering): ``HARD_FILTER`` runs first, then
        ``HUMAN_REVIEW``, then ``ELIGIBILITY``, then (globally, only on
        already-``SUPPORTED`` products) ``RANKING``. Deliberately NOT the
        same as declaration order or alphabetical ``.value`` order — sorting
        by ``.value`` would put ``ELIGIBILITY`` before ``HARD_FILTER``,
        which is wrong.
        """

        return STAGE_ORDER[self]


#: Semantic processing order for ``CompiledRulePack.rules_for()`` (PR3,
#: ``compiler.py``) — the actual runtime sequence per spec §4.2, not
#: ``RuleStage``'s declaration order (see that class's docstring for the
#: correction). Module-level (not a class body dict comprehension) so
#: ``RuleStage.order`` can reference it after the class is fully defined.
STAGE_ORDER: Mapping[RuleStage, int] = MappingProxyType(
    {
        RuleStage.HARD_FILTER: 0,
        RuleStage.HUMAN_REVIEW: 1,
        RuleStage.ELIGIBILITY: 2,
        RuleStage.RANKING: 3,
    }
)


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
    """The applicant's relationship to the family sponsor (``family.relation_to_sponsor``).

    ``STEPCHILD`` added 2026-08-23 (owner ruling, verbatim: "figliastro =
    figlio del coniuge, serve akta nikah + akta lahir"): E31D ("Family Visa —
    Stepchild of Foreigner in Legal Mixed Marriage") is a distinct product
    from CHILD (a couple's own biological/adopted child) and from SPOUSE, but
    every one of its three ELIGIBILITY rules could previously only test bare
    ``intent.purposes intersects ["FAMILY"]`` — the vocabulary had no way to
    say "stepchild" at all (`research/visa/2026-08-15-gold-family-refuter.md`,
    which reproduced this as fail-open product manufacture on sequence 7 and
    explicitly blocked a rule-only repair, demanding this vocabulary
    extension first). Grounded independently in Permenkumham 11/2024's
    Pasal 33 ayat (2) huruf h angka 4: "anak dari Orang Asing yang kawin
    secara sah dengan warga negara Indonesia" ("child OF A FOREIGNER who is
    legally married to an Indonesian citizen") — exactly the stepchild-of-a-
    lawful-mixed-marriage shape E31D names. The two evidence facts the owner
    named for this relation — the parents' marriage certificate and the
    child's birth certificate — are ``FactPath.FAMILY_STEPCHILD_MARRIAGE_
    CERTIFICATE_CONFIRMED`` / ``FAMILY_STEPCHILD_BIRTH_CERTIFICATE_CONFIRMED``
    below. This PR adds the vocabulary only; the rules that consume it
    (a real STEPCHILD/evidence-gated E31D ELIGIBILITY rule, replacing the
    three purpose-only ones) land in a separate, later PR.
    """

    SPOUSE = "SPOUSE"
    CHILD = "CHILD"
    PARENT = "PARENT"
    SIBLING = "SIBLING"
    DEPENDENT = "DEPENDENT"
    STEPCHILD = "STEPCHILD"
    OTHER = "OTHER"


class SponsorPermitBasis(str, Enum):
    """What activity BASIS the sponsor's own stay permit (ITAS/ITAP) was
    granted under — added 2026-08-23 so a rule can express Permenkumham
    11/2024's Pasal 33 ayat (7) exclusion (verbatim, re-extracted from the
    primary PDF ``data/source_documents/t0_regulations/
    permenkumham_11_2024_perubahan_visa.pdf``, item 10):

        "Visa tinggal terbatas sebagaimana dimaksud pada ayat (2) huruf h
        angka 2, angka 5, angka 8, dan angka 9 tidak dapat diajukan untuk
        penyatuan kepada pemegang Izin Tinggal Penyatuan Keluarga."

    Those four angka are exactly the four family-reunification products
    whose sponsor must already hold an ITAS/ITAP — E31B (spouse of ITAS/ITAP
    holder), E31E (minor child of ITAS/ITAP-holder parent), E31H (parent of
    ITAS/ITAP-holder child) and E31J (minor sibling of ITAS/ITAP holder). The
    law forbids chaining one of those four onto a sponsor whose OWN permit
    was itself granted under huruf h (penyatuan keluarga / family
    reunification) — no daisy-chaining family-reunification permits across
    generations. ``family.sponsor_status_code`` (a free-form product-code
    STRING, no ``allowed_values``) can express whether the sponsor's permit
    is merely *valid*; it cannot express *what it is for*, which is the gap
    this fact closes.

    The value domain is transcribed directly from Pasal 33 ayat (2) huruf
    a-l — the complete, exhaustive list of limited-stay-visa activity
    categories in the regulation, not a guessed binary. ``FAMILY_REUNIFICATION``
    (huruf h) is the one basis ayat (7) excludes; every other member is a
    real, distinct huruf. ``OTHER`` is the closed-vocabulary escape hatch for
    a sponsor permit that predates this classification or does not cleanly
    map to a single huruf — it is deliberately NOT the same value as
    ``FAMILY_REUNIFICATION`` and must never be used as a proxy for it.
    """

    EXPERT = "EXPERT"  # huruf a: tenaga ahli
    WORKER = "WORKER"  # huruf b: pekerja
    MARITIME_CREW = "MARITIME_CREW"  # huruf c: kapal/instalasi lepas pantai
    CLERGY = "CLERGY"  # huruf d: rohaniwan
    FOREIGN_INVESTMENT = "FOREIGN_INVESTMENT"  # huruf e: penanaman modal asing
    SCIENTIFIC_RESEARCH = "SCIENTIFIC_RESEARCH"  # huruf f: penelitian ilmiah
    EDUCATION = "EDUCATION"  # huruf g: mengikuti pendidikan
    FAMILY_REUNIFICATION = "FAMILY_REUNIFICATION"  # huruf h: penyatuan keluarga
    REPATRIATION = "REPATRIATION"  # huruf i: repatriasi
    SECOND_HOME = "SECOND_HOME"  # huruf j: rumah kedua
    MEDICAL_TREATMENT = "MEDICAL_TREATMENT"  # huruf k: menjalani pengobatan
    WORKING_HOLIDAY = "WORKING_HOLIDAY"  # huruf l: kemudahan bekerja sambil berlibur
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
    """The sponsor CATEGORY a product record declares (``sponsor_types``,
    ``models.VisaProductVersion``) and an applicant answers (``sponsor.type``,
    ``FactPath.SPONSOR_TYPE``). Reused as the same closed vocabulary on both
    sides deliberately (``contract.schema.json``'s own description: "a rule
    can then compare the applicant's answer against the product's own
    ``sponsor_types`` without a mapping table in between").

    Per-value semantics were undocumented before the W3 sponsor-rules
    factbase (``research/visa/2026-08-11-w3-sponsor-rules-factbase.md``)
    found that gap load-bearing: two ambiguous product-record mappings
    (E23V government-vs-employer, E28C individual-vs-none) were judgment
    calls with no written definition to appeal to. Citations below are
    Permenkumham 22/2023 (jo. 11/2024) unless noted.

    NONE: self-filed — no external/statutory Penjamin is identified; the
        applicant furnishes ``Jaminan Keimigrasian`` (an immigration
        guarantee) instead of a third party's sponsorship attestation.
        "No Penjamin" and "Jaminan Keimigrasian" are not interchangeable
        terms — do not conflate them when citing this value. Verbatim,
        explicit basis: Pasal 58(1) huruf b, "tanpa Penjamin" (E33B). Also
        the resolved mapping for E28C (seq-7, superseding the prior
        ``INDIVIDUAL``/self-sponsor encoding), Pasal 39(1) / 40(1):
        "diajukan oleh Orang Asing" (never "...atau Penjamin"), huruf b
        requires "bukti Jaminan Keimigrasian", never "bukti penjaminan dari
        Penjamin" — a structural absence rather than an explicit "tanpa
        Penjamin" clause, weaker evidence than E33B's but pointing the same
        direction (factbase §3).
    INDIVIDUAL: a natural person stands as Penjamin (e.g. a family sponsor,
        or an individual employer). Distinct from NONE (no Penjamin exists)
        and from EMPLOYER (the Penjamin is a corporate entity). Has no
        currently-verified Pasal-level citation of its own in the six
        products the factbase covers; do not treat its use elsewhere in this
        pack as implying one.
    EMPLOYER: the Penjamin is a company/corporate entity — the ordinary work
        route (E23 and siblings), tested today via
        ``work.employer_is_indonesian_entity`` rather than this fact.
    EDUCATION: the Penjamin is an educational institution (STUDY-purpose
        routes).
    INVESTMENT: the sponsor is the applicant's own investment vehicle/venture
        (e.g. the E28A PT PMA pathway) — the applicant is economically their
        own guarantor through the investment, distinct from GOVERNMENT and
        EMPLOYER.
    GOVERNMENT: the Penjamin is a central-government instansi. Verbatim,
        explicit basis in two products: Pasal 57(1) huruf b, "bukti
        penjaminan dari Penjamin, yang merupakan pemerintah pusat" (E33A);
        Pasal 59(1) huruf b, "bukti penjaminan dari penjamin dari instansi
        pemerintah pusat" (E33C). Confirming the value here does not by
        itself license a SUPPORT/ELIGIBILITY rule keyed on it alone — see
        the factbase and ``research/visa/2026-08-11-seq7-sponsor-semantics
        -and-the-gate-that-does-not-exist.md`` for why E33A/E33C have no
        eligibility gate this fact can safely be conjoined with today.
    """

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
# FactPath — the closed 49-path fact vocabulary (45 applicant + 4 derived; spec §2 ``FactPath``)
# ---------------------------------------------------------------------------


class FactPath(str, Enum):
    """Every fact path the engine may ever reference — 45 applicant-collected
    + 4 derived (spec §2 ``ApplicantFactPath`` + ``FactPath``, extended by the
    ``secondhome.*`` group for the E33 Second Home vertical, 2026-07-23, by
    ``sponsor.type`` for the sponsor-category question, 2026-08-10, by the
    two ``family.stepchild_*`` evidence facts, ``family.sponsor_permit_basis``
    and ``derived.has_active_stay_permit`` (2026-08-23, three owner rulings),
    and by ``immigration.renewal_paid`` (2026-08-24, F4 — see its own inline
    comment for the grounding).

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
    # immigration.renewal_paid — added 2026-08-24 (F4, owner ruling on a
    # renewal-in-process KITAS holder — verbatim: "chi ha un kitas scaduto e
    # il pagamento del rinnovo e' avvenuto prima della scadenza... resta sul
    # visa che ha esteso, non va su un altro", clarified further: "il rinno
    # si considera depositato se ce stato pagamento" — payment is what makes
    # a renewal "filed" at all, not a separate, weaker signal). Tri-state
    # boolean: KNOWN True only once the applicant confirms the renewal FEE
    # was paid — a lodged-but-unpaid submission does not count, and the
    # interview question wording must ask about payment explicitly for
    # exactly this reason (see ``apps/mouth``'s question copy). Consumed by
    # ``FactRegistry._derive_has_active_stay_permit`` as an early
    # short-circuit — see that method's docstring.
    IMMIGRATION_RENEWAL_PAID = "immigration.renewal_paid"
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
    # family.stepchild_* — evidence facts for RelationType.STEPCHILD
    # (2026-08-23 owner ruling, see that enum member's docstring for the full
    # citation trail). Modeled the same way as `family.marriage_registered`/
    # `family.sponsor_confirmed`: a boolean, PERSONAL-tier, "has this piece
    # of evidence been confirmed" fact — not a document upload, not a legal
    # conclusion, matching this codebase's existing `*_confirmed` idiom
    # (`work.indonesian_work_sponsor_confirmed`, `study.sponsor_confirmed`).
    # Two facts, not one, because the owner named two distinct documents:
    # "akta nikah" (the parents' marriage certificate — evidences the lawful
    # WNA-WNI mixed marriage E31D requires) and "akta lahir" (the child's
    # birth certificate — evidences the child's parentage). Vocabulary only:
    # no rule references either yet.
    FAMILY_STEPCHILD_MARRIAGE_CERTIFICATE_CONFIRMED = (
        "family.stepchild_marriage_certificate_confirmed"
    )
    FAMILY_STEPCHILD_BIRTH_CERTIFICATE_CONFIRMED = "family.stepchild_birth_certificate_confirmed"
    # family.sponsor_permit_basis — the sponsor's OWN stay-permit BASIS,
    # closed-enum (`enums.SponsorPermitBasis`), added 2026-08-23 so a rule can
    # express Permenkumham 11/2024 Pasal 33 ayat (7)'s no-chaining-family-
    # reunification-permits exclusion. See `SponsorPermitBasis`'s docstring
    # for the verbatim Pasal text and the four excluded products
    # (E31B/E31E/E31H/E31J). Deliberately distinct from
    # `FAMILY_SPONSOR_STATUS_CODE` (a free-form product-code STRING that can
    # only say the permit is *valid*, never *what it is for* — the exact
    # defect this fact exists to cure) and from `SPONSOR_TYPE` (WHO the
    # sponsor is — a person/employer/institution category — not what basis
    # THEIR OWN permit was granted under). Vocabulary only: no rule
    # references it yet.
    FAMILY_SPONSOR_PERMIT_BASIS = "family.sponsor_permit_basis"
    # study.*
    STUDY_LEVEL = "study.level"
    STUDY_ADMISSION_CONFIRMED = "study.admission_confirmed"
    STUDY_SPONSOR_CONFIRMED = "study.sponsor_confirmed"
    # sponsor.* — WHO the sponsor is, as a category. Deliberately NOT under
    # family.*: `family.sponsor_confirmed` and its siblings describe a family
    # relationship, while this is the sponsor CATEGORY and applies to
    # employment, study and investment routes just as much.
    #
    # Why it exists: every product record already declares `sponsor_types`
    # (models.py, `sponsor_types: tuple[SponsorType, ...]`) — but nothing
    # ever asked the applicant, so no rule could test it.
    #
    # CORRECTED 2026-08-11 (W3 sponsor-rules factbase,
    # research/visa/2026-08-11-w3-sponsor-rules-factbase.md): an earlier
    # version of this comment claimed the pack had "always known that E23V
    # wants a GOVERNMENT sponsor and E23U an INDIVIDUAL one" and that "the
    # future pack must add legally grounded rules before any product becomes
    # reachable" — both overclaimed. E23U/E23V have no dedicated Permenkumham
    # Pasal at all (confirmed by full-text search of 22/2023 and 11/2024);
    # their `sponsor_types` values in the pack are Bali Zero working
    # hypotheses, not statutory readings, and remain UNRESOLVED. For
    # E33A/E33B/E33C the sponsor category IS statutorily verbatim
    # (Pasal 57/58/59) — but sponsor.type alone does not supply a safe
    # eligibility gate for any of the three: E33A/E33C's substantive
    # requirement (a confirmed central-government invitation) has no fact
    # path and cannot be checked, and E33B's (certification/university/GPA/
    # cooperation-commitment) is the factbase's largest gap. An eligibility
    # rule keyed only on sponsor.type for these three is either dead code
    # (masked by the existing HUMAN_REVIEW rule whenever its own condition
    # holds) or a manufactured offer (SUPPORTED for purposes the review rule
    # does not police) — reproduced empirically against the real evaluator,
    # not just reasoned about; see the factbase and the seq-7 research note.
    # Measured 2026-08-10 against rulepack-prod-006, sponsor.type together
    # with the already-collected purpose would, IF a safe gate existed,
    # uniquely identify six of the eleven then-unreachable products: E23U,
    # E23V, E28C, E33A, E33B and E33C (five more still collide: E28B/E28D/
    # E28F and E30E/E30F). Unblocking any of them needs new, legally grounded
    # discriminator facts — not merely this one — so treat that count as a
    # ceiling on what sponsor.type alone could ever help with, not a
    # forecast of imminent reachability. Re-run the reachability sweep
    # against the then-current pack rather than treating either snapshot as
    # permanent.
    SPONSOR_TYPE = "sponsor.type"
    # secondhome.* — E33 Second Home vertical (bank-route scope, owner decision
    # 2026-07-23): the qualifying-basis facts the base E33 / E33E / E33F
    # eligibility rules test. ``bank_deposit_*`` is one deposit, evidenced as
    # a whole (amount + state-owned-bank (BUMN) placement + own-name holder);
    # split deposits are never modeled (owner decision: never offered).
    SECONDHOME_BANK_DEPOSIT_USD = "secondhome.bank_deposit_usd"
    SECONDHOME_BANK_DEPOSIT_AT_STATE_BANK = "secondhome.bank_deposit_at_state_bank"
    SECONDHOME_BANK_DEPOSIT_IN_OWN_NAME = "secondhome.bank_deposit_in_own_name"
    SECONDHOME_QUALIFYING_PROPERTY_VALUE_USD = "secondhome.qualifying_property_value_usd"
    SECONDHOME_PASSIVE_MONTHLY_INCOME_USD = "secondhome.passive_monthly_income_usd"
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
    # derived.has_active_stay_permit — added 2026-08-23 (owner ruling: an
    # applicant WITH an active KITAS is excluded from D12). Computed by
    # `FactRegistry.derive()` from `immigration.current_status_code` +
    # `immigration.current_status_expiry` + the evaluator's `effective_at`.
    # Tri-state by construction: UNKNOWN unless BOTH inputs are KNOWN and the
    # status code is one this registry can positively classify — see that
    # method's docstring for the closed classification and why an
    # unclassifiable code stays UNKNOWN rather than guessing FALSE (which
    # would wrongly ADMIT an applicant to D12).
    DERIVED_HAS_ACTIVE_STAY_PERMIT = "derived.has_active_stay_permit"


#: The 45 applicant-collected paths (everything except ``derived.*``).
APPLICANT_FACT_PATHS: frozenset[FactPath] = frozenset(
    path for path in FactPath if not path.value.startswith("derived.")
)

#: The 4 engine-computed paths, never collected from the applicant directly.
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
