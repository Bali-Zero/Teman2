---
date: 2026-07-17
domain: visa
client_case: none — product research (Visa Oracle v2 rebuild)
sources: multi-LLM panel round 2 (lane: codex-gpt-5.6-sol-ultra)
status: round-2 raw lane output, faithfully preserved
---

[Air-M5]

# Visa Oracle Round-2 — Engine Concretization

Status: engineering specification, based on local checkout `main@5d90948c87`. Pro was unreachable, so remote synchronization, production DB state, and runtime flags were not verified.

The checkout currently builds with Python 3.11, not 3.12: [Dockerfile](/Users/balizero/nuzantara/apps/backend-rag/Dockerfile:18) and [pyproject.toml](/Users/balizero/nuzantara/apps/backend-rag/pyproject.toml:11). Keep the engine compatible with Python 3.11 until deployment is deliberately upgraded.

## 0. Binding architecture decisions

1. `backend/services/visa_engine/` is the only recommendation authority.
2. Qdrant and LLMs may explain a persisted decision; they never determine eligibility, candidates, rank, or price.
3. Pricing occurs only after eligibility through an exact `PricingKey`; commercial budget never excludes a legally supported product.
4. A candidate is emitted only when:

   - every required fact for that candidate is `KNOWN`;
   - every declared purpose is covered;
   - no hard exclusion is true;
   - no applicable review trigger is true;
   - no unresolved safety fact can invalidate the proof;
   - every supporting rule points to an active verified source.

5. The current v1 questionnaires cannot enter `ENFORCE`: they do not collect current status, overstay, sponsor, onshore channel, marriage, work-source, or investment facts. [MatchRequest](/Users/balizero/nuzantara/apps/backend-rag/backend/app/routers/visa_check.py:113) and [RecommendRequest](/Users/balizero/nuzantara/apps/backend-rag/backend/app/routers/visa_oracle.py:31) remain `SHADOW` until an additive canonical `facts` envelope is available.
6. `ENFORCE` never falls back to `match_tree.py`, `VisaOracleService`, Qdrant, or an older unsigned representation.
7. Rolling back means signing a new higher-sequence bundle containing previously approved rules. It never means re-enabling the unsafe legacy engine.
8. Existing 16-character result hashes remain valid. New hashes use 20 lowercase base36 characters, within the existing path limit.
9. New decisions are not dual-written with nationality, purpose, budget, or recommendations in cleartext to `visa_checks`.
10. Existing clock hashes must be backfilled with immutable checkpoint snapshots before the current clock implementation can be removed.

---

# 1. Module layout

```text
apps/backend-rag/backend/services/visa_engine/
├── __init__.py
├── enums.py
├── models.py
├── fact_registry.py
├── ast.py
├── bundle.py
├── compiler.py
├── evaluator.py
├── trace.py
├── pricing.py
├── catalog.py
├── clock.py
├── repository.py
├── crypto.py
├── consent.py
├── retention.py
├── flags.py
├── compat.py
├── service.py
├── schema_export.py
├── errors.py
└── schemas/
    ├── contract.schema.json
    ├── rule-pack.schema.json
    ├── rule.schema.json
    ├── visa-product-version.schema.json
    ├── applicant-facts.schema.json
    ├── decision.schema.json
    ├── price-quote.schema.json
    └── source-record.schema.json
```

Public API:

```python
# enums.py
class TruthValue(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"

class DecisionState(str, Enum):
    NEEDS_INPUT = "NEEDS_INPUT"
    SUPPORTED_CANDIDATES = "SUPPORTED_CANDIDATES"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    NO_SUPPORTED_PATH = "NO_SUPPORTED_PATH"
    TEMPORARILY_UNAVAILABLE = "TEMPORARILY_UNAVAILABLE"

class RuleStage(str, Enum):
    HARD_FILTER = "HARD_FILTER"
    ELIGIBILITY = "ELIGIBILITY"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    RANKING = "RANKING"

class EngineMode(str, Enum):
    OFF = "OFF"
    SHADOW = "SHADOW"
    ENFORCE = "ENFORCE"

class EngineSurface(str, Enum):
    CLOCK = "CLOCK"
    MATCH = "MATCH"
    RECOMMEND = "RECOMMEND"
    CATALOG = "CATALOG"
    CHAT_CONTEXT = "CHAT_CONTEXT"
    HANDOFF = "HANDOFF"


# models.py — frozen Pydantic v2 models, extra="forbid"
class RulePack(BaseModel): ...
class Rule(BaseModel): ...
class VisaProductVersion(BaseModel): ...
class ApplicantFacts(BaseModel): ...
class Decision(BaseModel): ...
class PriceQuote(BaseModel): ...
class SourceRecord(BaseModel): ...
class CandidateDecision(BaseModel): ...
class ConsentEvent(BaseModel): ...
class EvaluationContext(BaseModel): ...


# fact_registry.py
@dataclass(frozen=True)
class FactSpec:
    path: str
    value_type: type
    derived: bool
    dependencies: frozenset[str]
    commercial_only: bool

@dataclass(frozen=True)
class FactSnapshot:
    values: Mapping[str, KnownFact | UnknownFact]

class FactRegistry:
    def spec(self, path: str) -> FactSpec: ...
    def derive(
        self,
        facts: ApplicantFacts,
        *,
        effective_at: datetime,
    ) -> FactSnapshot: ...

def canonical_fact_payload(facts: ApplicantFacts) -> Mapping[str, JsonValue]: ...


# ast.py
class AllCondition(BaseModel): ...
class AnyCondition(BaseModel): ...
class NotCondition(BaseModel): ...
class KnownCondition(BaseModel): ...
class UnknownCondition(BaseModel): ...
class EqCondition(BaseModel): ...
class NeqCondition(BaseModel): ...
class LtCondition(BaseModel): ...
class LteCondition(BaseModel): ...
class GtCondition(BaseModel): ...
class GteCondition(BaseModel): ...
class InCondition(BaseModel): ...
class NotInCondition(BaseModel): ...
class BetweenCondition(BaseModel): ...
class IntersectsCondition(BaseModel): ...
class ContainsAllCondition(BaseModel): ...

Condition = Annotated[
    AllCondition | AnyCondition | NotCondition | KnownCondition |
    UnknownCondition | EqCondition | NeqCondition | LtCondition |
    LteCondition | GtCondition | GteCondition | InCondition |
    NotInCondition | BetweenCondition | IntersectsCondition |
    ContainsAllCondition,
    Field(discriminator="op"),
]

@dataclass(frozen=True)
class ConditionResult:
    truth: TruthValue
    referenced_facts: frozenset[str]
    unknown_facts: frozenset[str]

def evaluate_condition(
    condition: Condition,
    facts: FactSnapshot,
) -> ConditionResult: ...

def collect_fact_paths(condition: Condition) -> frozenset[str]: ...


# bundle.py
@dataclass(frozen=True)
class TrustedSigningKey:
    key_id: str
    public_key: Ed25519PublicKey
    valid_from: datetime
    valid_to: datetime | None
    revoked_at: datetime | None

class TrustStore(Protocol):
    def resolve(
        self,
        *,
        key_id: str,
        signed_at: datetime,
        environment: str,
    ) -> TrustedSigningKey: ...

@dataclass(frozen=True)
class VerifiedRulePack:
    pack: RulePack
    canonical_payload: bytes
    payload_sha256: bytes

def canonicalize_json(value: Mapping[str, JsonValue]) -> bytes: ...

def verify_rule_pack(
    raw_envelope: Mapping[str, JsonValue],
    *,
    trust_store: TrustStore,
    observed_at: datetime,
) -> VerifiedRulePack: ...


# compiler.py
@dataclass(frozen=True)
class CompiledRule: ...
@dataclass(frozen=True)
class CompiledProduct: ...
@dataclass(frozen=True)
class CompiledRulePack: ...

def compile_rule_pack(
    verified: VerifiedRulePack,
    *,
    fact_registry: FactRegistry,
) -> CompiledRulePack: ...


# evaluator.py
class ProductProofStatus(str, Enum):
    EXCLUDED = "EXCLUDED"
    REVIEW = "REVIEW"
    BLOCKED_UNKNOWN = "BLOCKED_UNKNOWN"
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"

@dataclass(frozen=True)
class ProductProof: ...
@dataclass(frozen=True)
class DecisionDraft: ...

def evaluate(
    pack: CompiledRulePack,
    facts: FactSnapshot,
    *,
    context: EvaluationContext,
) -> DecisionDraft: ...


# trace.py — full trace is encrypted/internal, never returned publicly
@dataclass(frozen=True)
class TraceNode: ...
@dataclass(frozen=True)
class EvaluationTrace: ...

class TraceBuilder:
    def add_condition_result(...) -> None: ...
    def build(self) -> EvaluationTrace: ...

def trace_sha256(trace: EvaluationTrace) -> str: ...


# pricing.py
@dataclass(frozen=True)
class PricingKey:
    category: str
    item_key: str

class PriceQuoteProvider(Protocol):
    async def quote_exact(
        self,
        *,
        product: VisaProductVersion,
        quoted_at: datetime,
    ) -> PriceQuote: ...

class PricingToolQuoteProvider:
    async def quote_exact(
        self,
        *,
        product: VisaProductVersion,
        quoted_at: datetime,
    ) -> PriceQuote: ...


# catalog.py
class VisaCatalogService:
    async def list_active(
        self,
        *,
        effective_at: datetime,
        observed_at: datetime,
    ) -> tuple[VisaProductVersion, ...]: ...

    async def get_by_code_or_alias(
        self,
        code: str,
        *,
        effective_at: datetime,
        observed_at: datetime,
    ) -> VisaProductVersion | None: ...


# clock.py
@dataclass(frozen=True)
class ClockCheckpoint: ...
@dataclass(frozen=True)
class ClockSnapshot: ...

def build_clock_snapshot(
    *,
    product: VisaProductVersion,
    entry_date: date,
    effective_at: datetime,
) -> ClockSnapshot: ...


# repository.py
class VisaEngineRepository(BaseRepository):
    async def load_active_rule_pack(
        self,
        *,
        environment: str,
        effective_at: datetime,
        observed_at: datetime,
    ) -> Mapping[str, JsonValue] | None: ...

    async def save_decision(
        self,
        *,
        draft: DecisionDraft,
        encrypted_payload: EncryptedPayload,
        quotes: Sequence[PriceQuote],
        processing_receipt: ConsentEvent | None,
        idempotency_key: bytes,
    ) -> Decision: ...

    async def get_decision(self, decision_id: UUID) -> Decision | None: ...
    async def get_public_result(self, public_id: str) -> PublicResult | None: ...
    async def save_clock_snapshot(...) -> ClockSnapshot: ...
    async def consume_session_exchange(
        self,
        token_digest: bytes,
        *,
        consumed_at: datetime,
    ) -> SessionCapability | None: ...


# crypto.py
@dataclass(frozen=True)
class EncryptedPayload:
    key_id: str
    nonce: bytes
    ciphertext: bytes
    aad: bytes
    ciphertext_sha256: bytes

class PayloadCipher(Protocol):
    def encrypt(self, plaintext: bytes, *, aad: bytes) -> EncryptedPayload: ...
    def decrypt(self, payload: EncryptedPayload) -> bytes: ...

class AesGcmPayloadCipher(PayloadCipher): ...

class Pseudonymizer:
    def hmac_fingerprint(self, payload: bytes) -> tuple[str, bytes]: ...


# consent.py
class ConsentService:
    async def record_event(
        self,
        *,
        receipt_type: str,
        action: str,
        purpose: str,
        legal_basis: str,
        policy_version: str,
        policy_text_sha256: str,
        locale: str,
        session_id: UUID,
        decision_id: UUID | None,
        idempotency_key: str,
    ) -> ConsentReceipt: ...

    async def withdraw(
        self,
        *,
        prior_receipt_id: UUID,
        idempotency_key: str,
    ) -> ConsentReceipt: ...


# retention.py
@dataclass(frozen=True)
class RetentionReport: ...

class VisaRetentionService:
    async def preview(self, *, now: datetime, limit: int) -> RetentionReport: ...
    async def purge(self, *, now: datetime, limit: int) -> RetentionReport: ...


# flags.py
class VisaEngineModeResolver:
    async def resolve(self, surface: EngineSurface) -> EngineMode: ...


# compat.py
def applicant_facts_from_match_v1(request: MatchRequest) -> ApplicantFacts: ...
def applicant_facts_from_recommend_v1(request: RecommendRequest) -> ApplicantFacts: ...
def to_legacy_match_response(decision: Decision) -> Mapping[str, JsonValue]: ...
def to_legacy_recommend_response(decision: Decision) -> Mapping[str, JsonValue]: ...
def to_legacy_visa_type(product: VisaProductVersion, quote: PriceQuote) -> dict[str, object]: ...


# service.py
class VisaDecisionService:
    async def decide(
        self,
        facts: ApplicantFacts,
        *,
        effective_at: datetime,
        observed_at: datetime | None = None,
        processing_receipt_id: UUID | None = None,
        quote_requested: bool = False,
    ) -> Decision: ...

    async def replay(
        self,
        decision_id: UUID,
        *,
        observed_at: datetime,
    ) -> Decision: ...


# schema_export.py
def export_schemas(output_dir: Path) -> None: ...


# errors.py
class VisaEngineError(Exception): ...
class RulePackUnavailableError(VisaEngineError): ...
class RulePackVerificationError(VisaEngineError): ...
class RulePackCompilationError(VisaEngineError): ...
class FactValidationError(VisaEngineError): ...
class PersistenceRequiredError(VisaEngineError): ...
```

Supporting scripts:

```text
apps/backend-rag/backend/scripts/visa_engine/
├── compile_pack.py
├── sign_pack.py       # offline only; private key never present in FastAPI
├── activate_pack.py
├── backfill_clock_snapshots.py
└── purge_retention.py
```

---

# 2. JSON Schema 2020-12 contract

Use one compound schema plus seven entrypoint schemas. Draft 2020-12 supports compound schema documents and `$defs`. [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12)

The runtime must use `Draft202012Validator(..., format_checker=FormatChecker())`; `format` alone is advisory.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.balizero.com/visa-engine/contract.schema.json",
  "$defs": {
    "Uuid": {
      "type": "string",
      "format": "uuid"
    },
    "Sha256Hex": {
      "type": "string",
      "pattern": "^[0-9a-f]{64}$"
    },
    "UtcDateTime": {
      "type": "string",
      "format": "date-time",
      "pattern": "Z$"
    },
    "Identifier": {
      "type": "string",
      "pattern": "^[A-Za-z][A-Za-z0-9_.:-]{0,127}$"
    },
    "ReasonCode": {
      "type": "string",
      "pattern": "^[A-Z][A-Z0-9_]{0,127}$"
    },
    "ProductCode": {
      "type": "string",
      "pattern": "^[A-Z][A-Z0-9-]{0,31}$"
    },
    "TimeRange": {
      "type": "object",
      "additionalProperties": false,
      "required": ["from", "to"],
      "properties": {
        "from": { "$ref": "#/$defs/UtcDateTime" },
        "to": {
          "oneOf": [
            { "$ref": "#/$defs/UtcDateTime" },
            { "type": "null" }
          ]
        }
      }
    },
    "UnknownFact": {
      "type": "object",
      "additionalProperties": false,
      "required": ["status", "reason"],
      "properties": {
        "status": { "const": "UNKNOWN" },
        "reason": {
          "enum": [
            "NOT_ASKED",
            "NOT_PROVIDED",
            "UNVERIFIED",
            "CONFLICTING",
            "NOT_APPLICABLE"
          ]
        }
      }
    },
    "KnownBoolean": {
      "type": "object",
      "additionalProperties": false,
      "required": ["status", "value"],
      "properties": {
        "status": { "const": "KNOWN" },
        "value": { "type": "boolean" }
      }
    },
    "KnownDate": {
      "type": "object",
      "additionalProperties": false,
      "required": ["status", "value"],
      "properties": {
        "status": { "const": "KNOWN" },
        "value": { "type": "string", "format": "date" }
      }
    },
    "KnownString": {
      "type": "object",
      "additionalProperties": false,
      "required": ["status", "value"],
      "properties": {
        "status": { "const": "KNOWN" },
        "value": {
          "type": "string",
          "minLength": 1,
          "maxLength": 64
        }
      }
    },
    "KnownNonNegativeInteger": {
      "type": "object",
      "additionalProperties": false,
      "required": ["status", "value"],
      "properties": {
        "status": { "const": "KNOWN" },
        "value": {
          "type": "integer",
          "minimum": 0,
          "maximum": 9007199254740991
        }
      }
    },
    "KnownMoney": {
      "type": "object",
      "additionalProperties": false,
      "required": ["status", "value"],
      "properties": {
        "status": { "const": "KNOWN" },
        "value": {
          "type": "integer",
          "minimum": 0,
          "maximum": 9007199254740991
        }
      }
    },
    "KnownCountryCode": {
      "type": "object",
      "additionalProperties": false,
      "required": ["status", "value"],
      "properties": {
        "status": { "const": "KNOWN" },
        "value": {
          "type": "string",
          "pattern": "^[A-Z]{2}$"
        }
      }
    },
    "KnownCountrySet": {
      "type": "object",
      "additionalProperties": false,
      "required": ["status", "value"],
      "properties": {
        "status": { "const": "KNOWN" },
        "value": {
          "type": "array",
          "minItems": 1,
          "maxItems": 4,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "pattern": "^[A-Z]{2}$"
          }
        }
      }
    },
    "KnownPurposeSet": {
      "type": "object",
      "additionalProperties": false,
      "required": ["status", "value"],
      "properties": {
        "status": { "const": "KNOWN" },
        "value": {
          "type": "array",
          "minItems": 1,
          "maxItems": 8,
          "uniqueItems": true,
          "items": {
            "enum": [
              "TOURISM",
              "BUSINESS_MEETINGS",
              "INVESTMENT",
              "EMPLOYMENT",
              "REMOTE_WORK",
              "FAMILY",
              "STUDY",
              "RETIREMENT",
              "SECOND_HOME",
              "TRANSIT",
              "MEDICAL",
              "OTHER"
            ]
          }
        }
      }
    },
    "KnownViolationSet": {
      "type": "object",
      "additionalProperties": false,
      "required": ["status", "value"],
      "properties": {
        "status": { "const": "KNOWN" },
        "value": {
          "type": "array",
          "maxItems": 8,
          "uniqueItems": true,
          "items": {
            "enum": [
              "OVERSTAY",
              "DEPORTATION",
              "BLACKLIST",
              "IMMIGRATION_INVESTIGATION",
              "OTHER"
            ]
          }
        }
      }
    },
    "MaritalStatusFact": {
      "oneOf": [
        { "$ref": "#/$defs/UnknownFact" },
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["status", "value"],
          "properties": {
            "status": { "const": "KNOWN" },
            "value": {
              "enum": ["SINGLE", "MARRIED", "DIVORCED", "WIDOWED", "OTHER"]
            }
          }
        }
      ]
    },
    "EntryPatternFact": {
      "oneOf": [
        { "$ref": "#/$defs/UnknownFact" },
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["status", "value"],
          "properties": {
            "status": { "const": "KNOWN" },
            "value": { "enum": ["SINGLE", "MULTIPLE"] }
          }
        }
      ]
    },
    "ApplicationChannelFact": {
      "oneOf": [
        { "$ref": "#/$defs/UnknownFact" },
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["status", "value"],
          "properties": {
            "status": { "const": "KNOWN" },
            "value": {
              "enum": ["OFFSHORE", "ONSHORE_CONVERSION", "STATUS_BRIDGING"]
            }
          }
        }
      ]
    },
    "RelationFact": {
      "oneOf": [
        { "$ref": "#/$defs/UnknownFact" },
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["status", "value"],
          "properties": {
            "status": { "const": "KNOWN" },
            "value": {
              "enum": ["SPOUSE", "CHILD", "PARENT", "DEPENDENT", "OTHER"]
            }
          }
        }
      ]
    },
    "ProposedRoleFact": {
      "oneOf": [
        { "$ref": "#/$defs/UnknownFact" },
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["status", "value"],
          "properties": {
            "status": { "const": "KNOWN" },
            "value": {
              "enum": [
                "SHAREHOLDER_DIRECTOR",
                "SHAREHOLDER_COMMISSIONER",
                "EMPLOYEE",
                "NO_OPERATIONAL_ROLE",
                "OTHER"
              ]
            }
          }
        }
      ]
    },
    "StudyLevelFact": {
      "oneOf": [
        { "$ref": "#/$defs/UnknownFact" },
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["status", "value"],
          "properties": {
            "status": { "const": "KNOWN" },
            "value": {
              "enum": [
                "PRIMARY",
                "SECONDARY",
                "VOCATIONAL",
                "UNDERGRADUATE",
                "POSTGRADUATE",
                "RESEARCH",
                "OTHER"
              ]
            }
          }
        }
      ]
    },
    "BooleanFact": {
      "oneOf": [
        { "$ref": "#/$defs/UnknownFact" },
        { "$ref": "#/$defs/KnownBoolean" }
      ]
    },
    "DateFact": {
      "oneOf": [
        { "$ref": "#/$defs/UnknownFact" },
        { "$ref": "#/$defs/KnownDate" }
      ]
    },
    "StringFact": {
      "oneOf": [
        { "$ref": "#/$defs/UnknownFact" },
        { "$ref": "#/$defs/KnownString" }
      ]
    },
    "CountryCodeFact": {
      "oneOf": [
        { "$ref": "#/$defs/UnknownFact" },
        { "$ref": "#/$defs/KnownCountryCode" }
      ]
    },
    "CountrySetFact": {
      "oneOf": [
        { "$ref": "#/$defs/UnknownFact" },
        { "$ref": "#/$defs/KnownCountrySet" }
      ]
    },
    "NonNegativeIntegerFact": {
      "oneOf": [
        { "$ref": "#/$defs/UnknownFact" },
        { "$ref": "#/$defs/KnownNonNegativeInteger" }
      ]
    },
    "MoneyFact": {
      "oneOf": [
        { "$ref": "#/$defs/UnknownFact" },
        { "$ref": "#/$defs/KnownMoney" }
      ]
    },
    "PurposeSetFact": {
      "oneOf": [
        { "$ref": "#/$defs/UnknownFact" },
        { "$ref": "#/$defs/KnownPurposeSet" }
      ]
    },
    "ViolationSetFact": {
      "oneOf": [
        { "$ref": "#/$defs/UnknownFact" },
        { "$ref": "#/$defs/KnownViolationSet" }
      ]
    },
    "ApplicantFactPath": {
      "enum": [
        "person.birth_date",
        "person.nationalities",
        "person.marital_status",
        "immigration.currently_in_indonesia",
        "immigration.current_status_code",
        "immigration.current_status_expiry",
        "immigration.last_entry_date",
        "immigration.overstay_days",
        "immigration.violation_history",
        "intent.purposes",
        "intent.stay_days",
        "intent.desired_entry_date",
        "intent.entry_pattern",
        "intent.requested_product_code",
        "work.employer_country_code",
        "work.employer_is_indonesian_entity",
        "work.serves_indonesian_clients",
        "work.indonesia_source_compensation",
        "work.indonesian_work_sponsor_confirmed",
        "investment.pt_pma_committed",
        "investment.investment_capital_idr",
        "investment.paid_up_capital_idr",
        "investment.proposed_role",
        "family.relation_to_sponsor",
        "family.sponsor_nationalities",
        "family.sponsor_status_code",
        "family.marriage_registered",
        "family.sponsor_confirmed",
        "study.level",
        "study.admission_confirmed",
        "study.sponsor_confirmed",
        "process.application_channel",
        "process.wants_onshore_conversion",
        "commercial.service_fee_budget_idr",
        "commercial.wants_quote"
      ]
    },
    "FactPath": {
      "oneOf": [
        { "$ref": "#/$defs/ApplicantFactPath" },
        {
          "enum": [
            "derived.age_years",
            "derived.is_minor",
            "derived.has_indonesian_citizenship"
          ]
        }
      ]
    },
    "ApplicantFacts": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "schema_version",
        "assessment_id",
        "collected_at",
        "facts"
      ],
      "properties": {
        "schema_version": { "const": "1.0.0" },
        "assessment_id": { "$ref": "#/$defs/Uuid" },
        "collected_at": { "$ref": "#/$defs/UtcDateTime" },
        "facts": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "person.birth_date",
            "person.nationalities",
            "person.marital_status",
            "immigration.currently_in_indonesia",
            "immigration.current_status_code",
            "immigration.current_status_expiry",
            "immigration.last_entry_date",
            "immigration.overstay_days",
            "immigration.violation_history",
            "intent.purposes",
            "intent.stay_days",
            "intent.desired_entry_date",
            "intent.entry_pattern",
            "intent.requested_product_code",
            "work.employer_country_code",
            "work.employer_is_indonesian_entity",
            "work.serves_indonesian_clients",
            "work.indonesia_source_compensation",
            "work.indonesian_work_sponsor_confirmed",
            "investment.pt_pma_committed",
            "investment.investment_capital_idr",
            "investment.paid_up_capital_idr",
            "investment.proposed_role",
            "family.relation_to_sponsor",
            "family.sponsor_nationalities",
            "family.sponsor_status_code",
            "family.marriage_registered",
            "family.sponsor_confirmed",
            "study.level",
            "study.admission_confirmed",
            "study.sponsor_confirmed",
            "process.application_channel",
            "process.wants_onshore_conversion",
            "commercial.service_fee_budget_idr",
            "commercial.wants_quote"
          ],
          "properties": {
            "person.birth_date": { "$ref": "#/$defs/DateFact" },
            "person.nationalities": { "$ref": "#/$defs/CountrySetFact" },
            "person.marital_status": { "$ref": "#/$defs/MaritalStatusFact" },
            "immigration.currently_in_indonesia": { "$ref": "#/$defs/BooleanFact" },
            "immigration.current_status_code": { "$ref": "#/$defs/StringFact" },
            "immigration.current_status_expiry": { "$ref": "#/$defs/DateFact" },
            "immigration.last_entry_date": { "$ref": "#/$defs/DateFact" },
            "immigration.overstay_days": { "$ref": "#/$defs/NonNegativeIntegerFact" },
            "immigration.violation_history": { "$ref": "#/$defs/ViolationSetFact" },
            "intent.purposes": { "$ref": "#/$defs/PurposeSetFact" },
            "intent.stay_days": { "$ref": "#/$defs/NonNegativeIntegerFact" },
            "intent.desired_entry_date": { "$ref": "#/$defs/DateFact" },
            "intent.entry_pattern": { "$ref": "#/$defs/EntryPatternFact" },
            "intent.requested_product_code": { "$ref": "#/$defs/StringFact" },
            "work.employer_country_code": { "$ref": "#/$defs/CountryCodeFact" },
            "work.employer_is_indonesian_entity": { "$ref": "#/$defs/BooleanFact" },
            "work.serves_indonesian_clients": { "$ref": "#/$defs/BooleanFact" },
            "work.indonesia_source_compensation": { "$ref": "#/$defs/BooleanFact" },
            "work.indonesian_work_sponsor_confirmed": { "$ref": "#/$defs/BooleanFact" },
            "investment.pt_pma_committed": { "$ref": "#/$defs/BooleanFact" },
            "investment.investment_capital_idr": { "$ref": "#/$defs/MoneyFact" },
            "investment.paid_up_capital_idr": { "$ref": "#/$defs/MoneyFact" },
            "investment.proposed_role": { "$ref": "#/$defs/ProposedRoleFact" },
            "family.relation_to_sponsor": { "$ref": "#/$defs/RelationFact" },
            "family.sponsor_nationalities": { "$ref": "#/$defs/CountrySetFact" },
            "family.sponsor_status_code": { "$ref": "#/$defs/StringFact" },
            "family.marriage_registered": { "$ref": "#/$defs/BooleanFact" },
            "family.sponsor_confirmed": { "$ref": "#/$defs/BooleanFact" },
            "study.level": { "$ref": "#/$defs/StudyLevelFact" },
            "study.admission_confirmed": { "$ref": "#/$defs/BooleanFact" },
            "study.sponsor_confirmed": { "$ref": "#/$defs/BooleanFact" },
            "process.application_channel": { "$ref": "#/$defs/ApplicationChannelFact" },
            "process.wants_onshore_conversion": { "$ref": "#/$defs/BooleanFact" },
            "commercial.service_fee_budget_idr": { "$ref": "#/$defs/MoneyFact" },
            "commercial.wants_quote": { "$ref": "#/$defs/BooleanFact" }
          }
        }
      }
    },
    "Scalar": {
      "oneOf": [
        { "type": "boolean" },
        {
          "type": "integer",
          "minimum": -9007199254740991,
          "maximum": 9007199254740991
        },
        {
          "type": "string",
          "minLength": 1,
          "maxLength": 128
        }
      ]
    },
    "AllCondition": {
      "type": "object",
      "additionalProperties": false,
      "unevaluatedProperties": false,
      "required": ["op", "args"],
      "properties": {
        "op": { "const": "all" },
        "args": {
          "type": "array",
          "minItems": 1,
          "maxItems": 64,
          "items": { "$ref": "#/$defs/Condition" }
        }
      }
    },
    "AnyCondition": {
      "type": "object",
      "additionalProperties": false,
      "unevaluatedProperties": false,
      "required": ["op", "args"],
      "properties": {
        "op": { "const": "any" },
        "args": {
          "type": "array",
          "minItems": 1,
          "maxItems": 64,
          "items": { "$ref": "#/$defs/Condition" }
        }
      }
    },
    "NotCondition": {
      "type": "object",
      "additionalProperties": false,
      "unevaluatedProperties": false,
      "required": ["op", "arg"],
      "properties": {
        "op": { "const": "not" },
        "arg": { "$ref": "#/$defs/Condition" }
      }
    },
    "PresenceCondition": {
      "type": "object",
      "additionalProperties": false,
      "unevaluatedProperties": false,
      "required": ["op", "fact"],
      "properties": {
        "op": { "enum": ["known", "unknown"] },
        "fact": { "$ref": "#/$defs/FactPath" }
      }
    },
    "EqCondition": {
      "type": "object",
      "additionalProperties": false,
      "required": ["op", "fact", "value"],
      "properties": {
        "op": { "const": "eq" },
        "fact": { "$ref": "#/$defs/FactPath" },
        "value": { "$ref": "#/$defs/Scalar" }
      }
    },
    "NeqCondition": {
      "type": "object",
      "additionalProperties": false,
      "required": ["op", "fact", "value"],
      "properties": {
        "op": { "const": "neq" },
        "fact": { "$ref": "#/$defs/FactPath" },
        "value": { "$ref": "#/$defs/Scalar" }
      }
    },
    "LtCondition": {
      "type": "object",
      "additionalProperties": false,
      "required": ["op", "fact", "value"],
      "properties": {
        "op": { "const": "lt" },
        "fact": { "$ref": "#/$defs/FactPath" },
        "value": { "$ref": "#/$defs/Scalar" }
      }
    },
    "LteCondition": {
      "type": "object",
      "additionalProperties": false,
      "required": ["op", "fact", "value"],
      "properties": {
        "op": { "const": "lte" },
        "fact": { "$ref": "#/$defs/FactPath" },
        "value": { "$ref": "#/$defs/Scalar" }
      }
    },
    "GtCondition": {
      "type": "object",
      "additionalProperties": false,
      "required": ["op", "fact", "value"],
      "properties": {
        "op": { "const": "gt" },
        "fact": { "$ref": "#/$defs/FactPath" },
        "value": { "$ref": "#/$defs/Scalar" }
      }
    },
    "GteCondition": {
      "type": "object",
      "additionalProperties": false,
      "required": ["op", "fact", "value"],
      "properties": {
        "op": { "const": "gte" },
        "fact": { "$ref": "#/$defs/FactPath" },
        "value": { "$ref": "#/$defs/Scalar" }
      }
    },
    "InCondition": {
      "type": "object",
      "additionalProperties": false,
      "required": ["op", "fact", "values"],
      "properties": {
        "op": { "const": "in" },
        "fact": { "$ref": "#/$defs/FactPath" },
        "values": {
          "type": "array",
          "minItems": 1,
          "maxItems": 256,
          "uniqueItems": true,
          "items": { "$ref": "#/$defs/Scalar" }
        }
      }
    },
    "NotInCondition": {
      "type": "object",
      "additionalProperties": false,
      "required": ["op", "fact", "values"],
      "properties": {
        "op": { "const": "not_in" },
        "fact": { "$ref": "#/$defs/FactPath" },
        "values": {
          "type": "array",
          "minItems": 1,
          "maxItems": 256,
          "uniqueItems": true,
          "items": { "$ref": "#/$defs/Scalar" }
        }
      }
    },
    "BetweenCondition": {
      "type": "object",
      "additionalProperties": false,
      "required": ["op", "fact", "lower", "upper"],
      "properties": {
        "op": { "const": "between" },
        "fact": { "$ref": "#/$defs/FactPath" },
        "lower": { "$ref": "#/$defs/Scalar" },
        "upper": { "$ref": "#/$defs/Scalar" }
      }
    },
    "IntersectsCondition": {
      "type": "object",
      "additionalProperties": false,
      "required": ["op", "fact", "values"],
      "properties": {
        "op": { "const": "intersects" },
        "fact": { "$ref": "#/$defs/FactPath" },
        "values": {
          "type": "array",
          "minItems": 1,
          "maxItems": 256,
          "uniqueItems": true,
          "items": { "$ref": "#/$defs/Scalar" }
        }
      }
    },
    "ContainsAllCondition": {
      "type": "object",
      "additionalProperties": false,
      "required": ["op", "fact", "values"],
      "properties": {
        "op": { "const": "contains_all" },
        "fact": { "$ref": "#/$defs/FactPath" },
        "values": {
          "type": "array",
          "minItems": 1,
          "maxItems": 256,
          "uniqueItems": true,
          "items": { "$ref": "#/$defs/Scalar" }
        }
      }
    },
    "Condition": {
      "oneOf": [
        { "$ref": "#/$defs/AllCondition" },
        { "$ref": "#/$defs/AnyCondition" },
        { "$ref": "#/$defs/NotCondition" },
        { "$ref": "#/$defs/PresenceCondition" },
        { "$ref": "#/$defs/EqCondition" },
        { "$ref": "#/$defs/NeqCondition" },
        { "$ref": "#/$defs/LtCondition" },
        { "$ref": "#/$defs/LteCondition" },
        { "$ref": "#/$defs/GtCondition" },
        { "$ref": "#/$defs/GteCondition" },
        { "$ref": "#/$defs/InCondition" },
        { "$ref": "#/$defs/NotInCondition" },
        { "$ref": "#/$defs/BetweenCondition" },
        { "$ref": "#/$defs/IntersectsCondition" },
        { "$ref": "#/$defs/ContainsAllCondition" }
      ]
    },
    "RuleEffect": {
      "oneOf": [
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["type", "reason_code"],
          "properties": {
            "type": { "const": "EXCLUDE" },
            "reason_code": { "$ref": "#/$defs/ReasonCode" }
          }
        },
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["type", "reason_code", "covered_purposes"],
          "properties": {
            "type": { "const": "SUPPORT" },
            "reason_code": { "$ref": "#/$defs/ReasonCode" },
            "covered_purposes": {
              "type": "array",
              "minItems": 1,
              "uniqueItems": true,
              "items": {
                "enum": [
                  "TOURISM",
                  "BUSINESS_MEETINGS",
                  "INVESTMENT",
                  "EMPLOYMENT",
                  "REMOTE_WORK",
                  "FAMILY",
                  "STUDY",
                  "RETIREMENT",
                  "SECOND_HOME",
                  "TRANSIT",
                  "MEDICAL",
                  "OTHER"
                ]
              }
            }
          }
        },
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["type", "reason_code"],
          "properties": {
            "type": { "const": "REQUIRE_REVIEW" },
            "reason_code": { "$ref": "#/$defs/ReasonCode" }
          }
        },
        {
          "type": "object",
          "additionalProperties": false,
          "required": ["type", "reason_code", "points"],
          "properties": {
            "type": { "const": "ADD_SCORE" },
            "reason_code": { "$ref": "#/$defs/ReasonCode" },
            "points": {
              "type": "integer",
              "minimum": -10000,
              "maximum": 10000
            }
          }
        }
      ]
    },
    "Rule": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "rule_id",
        "stage",
        "scope",
        "priority",
        "valid_period",
        "when",
        "effect",
        "on_unknown",
        "required_facts",
        "source_refs",
        "explanation_key",
        "safety_critical"
      ],
      "properties": {
        "rule_id": { "$ref": "#/$defs/Identifier" },
        "stage": {
          "enum": [
            "HARD_FILTER",
            "ELIGIBILITY",
            "HUMAN_REVIEW",
            "RANKING"
          ]
        },
        "scope": { "enum": ["GLOBAL", "PRODUCTS"] },
        "product_version_ids": {
          "type": "array",
          "minItems": 1,
          "maxItems": 256,
          "uniqueItems": true,
          "items": { "$ref": "#/$defs/Uuid" }
        },
        "priority": {
          "type": "integer",
          "minimum": 0,
          "maximum": 100000
        },
        "valid_period": { "$ref": "#/$defs/TimeRange" },
        "when": { "$ref": "#/$defs/Condition" },
        "effect": { "$ref": "#/$defs/RuleEffect" },
        "on_unknown": {
          "enum": ["NEEDS_INPUT", "HUMAN_REVIEW", "NO_EFFECT"]
        },
        "required_facts": {
          "type": "array",
          "maxItems": 128,
          "uniqueItems": true,
          "items": { "$ref": "#/$defs/FactPath" }
        },
        "source_refs": {
          "type": "array",
          "minItems": 1,
          "maxItems": 32,
          "uniqueItems": true,
          "items": { "$ref": "#/$defs/Uuid" }
        },
        "explanation_key": { "$ref": "#/$defs/Identifier" },
        "safety_critical": { "type": "boolean" }
      },
      "allOf": [
        {
          "if": { "properties": { "scope": { "const": "GLOBAL" } } },
          "then": { "not": { "required": ["product_version_ids"] } },
          "else": { "required": ["product_version_ids"] }
        },
        {
          "if": { "properties": { "stage": { "const": "HARD_FILTER" } } },
          "then": {
            "properties": {
              "effect": {
                "properties": { "type": { "const": "EXCLUDE" } }
              }
            }
          }
        },
        {
          "if": { "properties": { "stage": { "const": "ELIGIBILITY" } } },
          "then": {
            "properties": {
              "effect": {
                "properties": { "type": { "const": "SUPPORT" } }
              }
            }
          }
        },
        {
          "if": { "properties": { "stage": { "const": "HUMAN_REVIEW" } } },
          "then": {
            "properties": {
              "effect": {
                "properties": { "type": { "const": "REQUIRE_REVIEW" } }
              }
            }
          }
        },
        {
          "if": { "properties": { "stage": { "const": "RANKING" } } },
          "then": {
            "properties": {
              "effect": {
                "properties": { "type": { "const": "ADD_SCORE" } }
              }
            }
          }
        }
      ]
    },
    "SourceRecord": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "source_record_id",
        "source_key",
        "version",
        "authority_type",
        "status",
        "jurisdiction",
        "title",
        "publisher",
        "canonical_url",
        "language",
        "document_number",
        "locators",
        "content_sha256",
        "legal_period",
        "recorded_period",
        "retrieved_at",
        "verified_at",
        "verified_by",
        "supersedes_source_record_id"
      ],
      "properties": {
        "source_record_id": { "$ref": "#/$defs/Uuid" },
        "source_key": { "$ref": "#/$defs/Identifier" },
        "version": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "authority_type": {
          "enum": [
            "PRIMARY_LAW",
            "IMPLEMENTING_REGULATION",
            "OFFICIAL_PORTAL",
            "OFFICIAL_CIRCULAR",
            "BALI_ZERO_POLICY",
            "PRICING_CATALOG"
          ]
        },
        "status": {
          "enum": ["VERIFIED", "SUPERSEDED", "REVOKED", "UNAVAILABLE"]
        },
        "jurisdiction": { "const": "ID" },
        "title": {
          "type": "string",
          "minLength": 1,
          "maxLength": 512
        },
        "publisher": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "canonical_url": {
          "type": "string",
          "format": "uri",
          "maxLength": 2048
        },
        "language": {
          "type": "string",
          "pattern": "^[a-z]{2}(-[A-Z]{2})?$"
        },
        "document_number": {
          "oneOf": [
            { "type": "string", "maxLength": 256 },
            { "type": "null" }
          ]
        },
        "locators": {
          "type": "array",
          "maxItems": 64,
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["kind", "value"],
            "properties": {
              "kind": {
                "enum": ["ARTICLE", "SECTION", "PAGE", "PARAGRAPH", "ANCHOR"]
              },
              "value": {
                "type": "string",
                "minLength": 1,
                "maxLength": 256
              }
            }
          }
        },
        "content_sha256": { "$ref": "#/$defs/Sha256Hex" },
        "legal_period": { "$ref": "#/$defs/TimeRange" },
        "recorded_period": { "$ref": "#/$defs/TimeRange" },
        "retrieved_at": { "$ref": "#/$defs/UtcDateTime" },
        "verified_at": { "$ref": "#/$defs/UtcDateTime" },
        "verified_by": { "$ref": "#/$defs/Identifier" },
        "supersedes_source_record_id": {
          "oneOf": [
            { "$ref": "#/$defs/Uuid" },
            { "type": "null" }
          ]
        }
      }
    },
    "PricingKey": {
      "type": "object",
      "additionalProperties": false,
      "required": ["category", "item_key"],
      "properties": {
        "category": {
          "type": "string",
          "pattern": "^[a-z][a-z0-9_]{0,63}$"
        },
        "item_key": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        }
      }
    },
    "VisaProductVersion": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "product_version_id",
        "product_code",
        "legacy_codes",
        "legacy_slugs",
        "names",
        "category",
        "status",
        "valid_period",
        "covered_purposes",
        "prohibited_activities",
        "sponsor_types",
        "entry_policy",
        "stay_policy",
        "extension_policy",
        "clock_policy",
        "pricing_key",
        "source_refs",
        "public_catalog"
      ],
      "properties": {
        "product_version_id": { "$ref": "#/$defs/Uuid" },
        "product_code": { "$ref": "#/$defs/ProductCode" },
        "legacy_codes": {
          "type": "array",
          "uniqueItems": true,
          "items": { "$ref": "#/$defs/ProductCode" }
        },
        "legacy_slugs": {
          "type": "array",
          "uniqueItems": true,
          "items": {
            "type": "string",
            "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$"
          }
        },
        "names": {
          "type": "object",
          "additionalProperties": false,
          "required": ["id", "en"],
          "properties": {
            "id": { "type": "string", "minLength": 1, "maxLength": 256 },
            "en": { "type": "string", "minLength": 1, "maxLength": 256 }
          }
        },
        "category": {
          "enum": [
            "SHORT_STAY",
            "MULTIPLE_ENTRY",
            "LIMITED_STAY",
            "PERMANENT_STAY",
            "TRANSIT",
            "OTHER"
          ]
        },
        "status": { "enum": ["ACTIVE", "DEPRECATED", "OBSOLETE"] },
        "valid_period": { "$ref": "#/$defs/TimeRange" },
        "covered_purposes": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": {
            "enum": [
              "TOURISM",
              "BUSINESS_MEETINGS",
              "INVESTMENT",
              "EMPLOYMENT",
              "REMOTE_WORK",
              "FAMILY",
              "STUDY",
              "RETIREMENT",
              "SECOND_HOME",
              "TRANSIT",
              "MEDICAL",
              "OTHER"
            ]
          }
        },
        "prohibited_activities": {
          "type": "array",
          "uniqueItems": true,
          "items": { "$ref": "#/$defs/Identifier" }
        },
        "sponsor_types": {
          "type": "array",
          "uniqueItems": true,
          "items": {
            "enum": [
              "NONE",
              "INDIVIDUAL",
              "EMPLOYER",
              "EDUCATION",
              "INVESTMENT",
              "GOVERNMENT"
            ]
          }
        },
        "entry_policy": {
          "type": "object",
          "additionalProperties": false,
          "required": ["entry_count"],
          "properties": {
            "entry_count": { "enum": ["SINGLE", "MULTIPLE", "NOT_APPLICABLE"] }
          }
        },
        "stay_policy": {
          "type": "object",
          "additionalProperties": false,
          "required": ["kind", "minimum_days", "maximum_days"],
          "properties": {
            "kind": {
              "enum": ["FIXED_DAYS", "VARIABLE_BY_GRANT", "NOT_APPLICABLE"]
            },
            "minimum_days": {
              "oneOf": [
                { "type": "integer", "minimum": 0, "maximum": 36500 },
                { "type": "null" }
              ]
            },
            "maximum_days": {
              "oneOf": [
                { "type": "integer", "minimum": 0, "maximum": 36500 },
                { "type": "null" }
              ]
            }
          }
        },
        "extension_policy": {
          "type": "object",
          "additionalProperties": false,
          "required": ["allowed", "maximum_extensions", "days_per_extension"],
          "properties": {
            "allowed": { "type": "boolean" },
            "maximum_extensions": {
              "type": "integer",
              "minimum": 0,
              "maximum": 100
            },
            "days_per_extension": {
              "oneOf": [
                { "type": "integer", "minimum": 1, "maximum": 3650 },
                { "type": "null" }
              ]
            }
          }
        },
        "clock_policy": {
          "type": "object",
          "additionalProperties": false,
          "required": ["available", "anchor", "checkpoints"],
          "properties": {
            "available": { "type": "boolean" },
            "anchor": {
              "enum": ["ENTRY_DATE", "PERMIT_ISSUED_AT", "NOT_APPLICABLE"]
            },
            "checkpoints": {
              "type": "array",
              "maxItems": 64,
              "items": {
                "type": "object",
                "additionalProperties": false,
                "required": ["code", "offset_days", "title_key", "body_key"],
                "properties": {
                  "code": { "$ref": "#/$defs/Identifier" },
                  "offset_days": {
                    "type": "integer",
                    "minimum": -3650,
                    "maximum": 36500
                  },
                  "title_key": { "$ref": "#/$defs/Identifier" },
                  "body_key": { "$ref": "#/$defs/Identifier" }
                }
              }
            }
          }
        },
        "pricing_key": {
          "oneOf": [
            { "$ref": "#/$defs/PricingKey" },
            { "type": "null" }
          ]
        },
        "source_refs": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": { "$ref": "#/$defs/Uuid" }
        },
        "public_catalog": { "type": "boolean" }
      }
    },
    "RulePackPayload": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "rule_pack_id",
        "sequence",
        "version",
        "environment",
        "jurisdiction",
        "decision_domain",
        "engine_contract_version",
        "engine_min_version",
        "engine_max_version",
        "valid_period",
        "created_at",
        "created_by",
        "previous_payload_sha256",
        "rollback_of_payload_sha256",
        "hit_policy",
        "source_records",
        "products",
        "rules"
      ],
      "properties": {
        "rule_pack_id": { "$ref": "#/$defs/Uuid" },
        "sequence": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "version": {
          "type": "string",
          "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"
        },
        "environment": { "enum": ["TEST", "STAGING", "PRODUCTION"] },
        "jurisdiction": { "const": "ID" },
        "decision_domain": { "const": "IMMIGRATION_VISA" },
        "engine_contract_version": { "const": "1.0.0" },
        "engine_min_version": {
          "type": "string",
          "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"
        },
        "engine_max_version": {
          "type": "string",
          "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"
        },
        "valid_period": { "$ref": "#/$defs/TimeRange" },
        "created_at": { "$ref": "#/$defs/UtcDateTime" },
        "created_by": { "$ref": "#/$defs/Identifier" },
        "previous_payload_sha256": {
          "oneOf": [
            { "$ref": "#/$defs/Sha256Hex" },
            { "type": "null" }
          ]
        },
        "rollback_of_payload_sha256": {
          "oneOf": [
            { "$ref": "#/$defs/Sha256Hex" },
            { "type": "null" }
          ]
        },
        "hit_policy": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "hard_filter",
            "eligibility",
            "human_review",
            "ranking"
          ],
          "properties": {
            "hard_filter": { "const": "COLLECT_ALL" },
            "eligibility": { "const": "COVER_ALL_DECLARED_PURPOSES" },
            "human_review": { "const": "COLLECT_ALL" },
            "ranking": { "const": "SUM_TRUE_INTEGER_WEIGHTS" }
          }
        },
        "source_records": {
          "type": "array",
          "minItems": 1,
          "maxItems": 4096,
          "items": { "$ref": "#/$defs/SourceRecord" }
        },
        "products": {
          "type": "array",
          "minItems": 1,
          "maxItems": 256,
          "items": { "$ref": "#/$defs/VisaProductVersion" }
        },
        "rules": {
          "type": "array",
          "minItems": 1,
          "maxItems": 4096,
          "items": { "$ref": "#/$defs/Rule" }
        }
      },
      "allOf": [
        {
          "if": { "properties": { "sequence": { "const": 1 } } },
          "then": {
            "properties": {
              "previous_payload_sha256": { "type": "null" }
            }
          },
          "else": {
            "properties": {
              "previous_payload_sha256": { "$ref": "#/$defs/Sha256Hex" }
            }
          }
        }
      ]
    },
    "ProtectedHeader": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "domain",
        "alg",
        "kid",
        "signed_at",
        "schema_version",
        "environment"
      ],
      "properties": {
        "domain": { "const": "balizero.visa-rulepack.v1" },
        "alg": { "const": "Ed25519" },
        "kid": { "$ref": "#/$defs/Identifier" },
        "signed_at": { "$ref": "#/$defs/UtcDateTime" },
        "schema_version": { "const": "1.0.0" },
        "environment": { "enum": ["TEST", "STAGING", "PRODUCTION"] }
      }
    },
    "RulePack": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "canonicalization",
        "protected",
        "payload",
        "payload_sha256",
        "signature"
      ],
      "properties": {
        "canonicalization": { "const": "RFC8785" },
        "protected": { "$ref": "#/$defs/ProtectedHeader" },
        "payload": { "$ref": "#/$defs/RulePackPayload" },
        "payload_sha256": { "$ref": "#/$defs/Sha256Hex" },
        "signature": {
          "type": "string",
          "pattern": "^[A-Za-z0-9_-]{86}$"
        }
      }
    },
    "PriceQuote": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "quote_id",
        "product_version_id",
        "product_code",
        "status",
        "currency",
        "amount",
        "pricing_key",
        "catalog_version",
        "catalog_sha256",
        "row_sha256",
        "quoted_at",
        "valid_until",
        "reason_code"
      ],
      "properties": {
        "quote_id": { "$ref": "#/$defs/Uuid" },
        "product_version_id": { "$ref": "#/$defs/Uuid" },
        "product_code": { "$ref": "#/$defs/ProductCode" },
        "status": {
          "enum": ["AVAILABLE", "CONTACT_REQUIRED", "UNAVAILABLE"]
        },
        "currency": { "const": "IDR" },
        "amount": {
          "oneOf": [
            {
              "type": "integer",
              "minimum": 0,
              "maximum": 9007199254740991
            },
            { "type": "null" }
          ]
        },
        "pricing_key": { "$ref": "#/$defs/PricingKey" },
        "catalog_version": {
          "oneOf": [
            { "type": "string", "minLength": 1, "maxLength": 64 },
            { "type": "null" }
          ]
        },
        "catalog_sha256": {
          "oneOf": [
            { "$ref": "#/$defs/Sha256Hex" },
            { "type": "null" }
          ]
        },
        "row_sha256": {
          "oneOf": [
            { "$ref": "#/$defs/Sha256Hex" },
            { "type": "null" }
          ]
        },
        "quoted_at": { "$ref": "#/$defs/UtcDateTime" },
        "valid_until": {
          "oneOf": [
            { "$ref": "#/$defs/UtcDateTime" },
            { "type": "null" }
          ]
        },
        "reason_code": { "$ref": "#/$defs/ReasonCode" }
      },
      "allOf": [
        {
          "if": { "properties": { "status": { "const": "AVAILABLE" } } },
          "then": {
            "properties": {
              "amount": { "type": "integer", "minimum": 0 },
              "catalog_version": { "type": "string" },
              "catalog_sha256": { "$ref": "#/$defs/Sha256Hex" },
              "row_sha256": { "$ref": "#/$defs/Sha256Hex" }
            }
          },
          "else": {
            "properties": { "amount": { "type": "null" } }
          }
        }
      ]
    },
    "Reason": {
      "type": "object",
      "additionalProperties": false,
      "required": ["code", "rule_ids", "source_refs"],
      "properties": {
        "code": { "$ref": "#/$defs/ReasonCode" },
        "rule_ids": {
          "type": "array",
          "uniqueItems": true,
          "items": { "$ref": "#/$defs/Identifier" }
        },
        "source_refs": {
          "type": "array",
          "uniqueItems": true,
          "items": { "$ref": "#/$defs/Uuid" }
        }
      }
    },
    "Candidate": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "rank",
        "product_version_id",
        "product_code",
        "score",
        "covered_purposes",
        "support_rule_ids",
        "source_refs",
        "reason_codes"
      ],
      "properties": {
        "rank": { "type": "integer", "minimum": 1, "maximum": 256 },
        "product_version_id": { "$ref": "#/$defs/Uuid" },
        "product_code": { "$ref": "#/$defs/ProductCode" },
        "score": {
          "type": "integer",
          "minimum": -1000000,
          "maximum": 1000000
        },
        "covered_purposes": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": { "type": "string" }
        },
        "support_rule_ids": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": { "$ref": "#/$defs/Identifier" }
        },
        "source_refs": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": { "$ref": "#/$defs/Uuid" }
        },
        "reason_codes": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": { "$ref": "#/$defs/ReasonCode" }
        }
      }
    },
    "RulePackRef": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "rule_pack_id",
        "sequence",
        "version",
        "payload_sha256"
      ],
      "properties": {
        "rule_pack_id": { "$ref": "#/$defs/Uuid" },
        "sequence": {
          "type": "integer",
          "minimum": 1,
          "maximum": 9007199254740991
        },
        "version": { "type": "string" },
        "payload_sha256": { "$ref": "#/$defs/Sha256Hex" }
      }
    },
    "Fingerprint": {
      "type": "object",
      "additionalProperties": false,
      "required": ["algorithm", "key_id", "digest"],
      "properties": {
        "algorithm": { "const": "HMAC-SHA256" },
        "key_id": { "$ref": "#/$defs/Identifier" },
        "digest": { "$ref": "#/$defs/Sha256Hex" }
      }
    },
    "Decision": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "schema_version",
        "decision_id",
        "public_id",
        "state",
        "effective_at",
        "observed_at",
        "evaluated_at",
        "rule_pack",
        "facts_fingerprint",
        "candidates",
        "missing_facts",
        "review_reasons",
        "no_path_reasons",
        "outage",
        "quotes",
        "notices",
        "trace_sha256",
        "decision_integrity"
      ],
      "properties": {
        "schema_version": { "const": "1.0.0" },
        "decision_id": {
          "oneOf": [
            { "$ref": "#/$defs/Uuid" },
            { "type": "null" }
          ]
        },
        "public_id": {
          "oneOf": [
            {
              "type": "string",
              "pattern": "^[a-z0-9]{16,20}$"
            },
            { "type": "null" }
          ]
        },
        "state": {
          "enum": [
            "NEEDS_INPUT",
            "SUPPORTED_CANDIDATES",
            "HUMAN_REVIEW_REQUIRED",
            "NO_SUPPORTED_PATH",
            "TEMPORARILY_UNAVAILABLE"
          ]
        },
        "effective_at": { "$ref": "#/$defs/UtcDateTime" },
        "observed_at": { "$ref": "#/$defs/UtcDateTime" },
        "evaluated_at": { "$ref": "#/$defs/UtcDateTime" },
        "rule_pack": {
          "oneOf": [
            { "$ref": "#/$defs/RulePackRef" },
            { "type": "null" }
          ]
        },
        "facts_fingerprint": { "$ref": "#/$defs/Fingerprint" },
        "candidates": {
          "type": "array",
          "maxItems": 256,
          "items": { "$ref": "#/$defs/Candidate" }
        },
        "missing_facts": {
          "type": "array",
          "uniqueItems": true,
          "items": { "$ref": "#/$defs/ApplicantFactPath" }
        },
        "review_reasons": {
          "type": "array",
          "items": { "$ref": "#/$defs/Reason" }
        },
        "no_path_reasons": {
          "type": "array",
          "items": { "$ref": "#/$defs/Reason" }
        },
        "outage": {
          "oneOf": [
            {
              "type": "object",
              "additionalProperties": false,
              "required": ["code", "retryable"],
              "properties": {
                "code": { "$ref": "#/$defs/ReasonCode" },
                "retryable": { "type": "boolean" }
              }
            },
            { "type": "null" }
          ]
        },
        "quotes": {
          "type": "array",
          "items": { "$ref": "#/$defs/PriceQuote" }
        },
        "notices": {
          "type": "array",
          "items": { "$ref": "#/$defs/Reason" }
        },
        "trace_sha256": {
          "oneOf": [
            { "$ref": "#/$defs/Sha256Hex" },
            { "type": "null" }
          ]
        },
        "decision_integrity": {
          "oneOf": [
            { "$ref": "#/$defs/Fingerprint" },
            { "type": "null" }
          ]
        }
      },
      "allOf": [
        {
          "if": {
            "properties": {
              "state": { "const": "SUPPORTED_CANDIDATES" }
            }
          },
          "then": {
            "properties": {
              "decision_id": { "$ref": "#/$defs/Uuid" },
              "public_id": {
                "type": "string",
                "pattern": "^[a-z0-9]{16,20}$"
              },
              "rule_pack": { "$ref": "#/$defs/RulePackRef" },
              "candidates": { "minItems": 1 },
              "missing_facts": { "maxItems": 0 },
              "review_reasons": { "maxItems": 0 },
              "no_path_reasons": { "maxItems": 0 },
              "outage": { "type": "null" }
            }
          },
          "else": {
            "properties": {
              "candidates": { "maxItems": 0 },
              "quotes": { "maxItems": 0 }
            }
          }
        },
        {
          "if": {
            "properties": { "state": { "const": "NEEDS_INPUT" } }
          },
          "then": {
            "properties": {
              "decision_id": { "$ref": "#/$defs/Uuid" },
              "public_id": {
                "type": "string",
                "pattern": "^[a-z0-9]{16,20}$"
              },
              "rule_pack": { "$ref": "#/$defs/RulePackRef" },
              "missing_facts": { "minItems": 1 },
              "review_reasons": { "maxItems": 0 },
              "no_path_reasons": { "maxItems": 0 },
              "outage": { "type": "null" }
            }
          }
        },
        {
          "if": {
            "properties": {
              "state": { "const": "HUMAN_REVIEW_REQUIRED" }
            }
          },
          "then": {
            "properties": {
              "decision_id": { "$ref": "#/$defs/Uuid" },
              "public_id": {
                "type": "string",
                "pattern": "^[a-z0-9]{16,20}$"
              },
              "rule_pack": { "$ref": "#/$defs/RulePackRef" },
              "missing_facts": { "maxItems": 0 },
              "review_reasons": { "minItems": 1 },
              "no_path_reasons": { "maxItems": 0 },
              "outage": { "type": "null" }
            }
          }
        },
        {
          "if": {
            "properties": {
              "state": { "const": "NO_SUPPORTED_PATH" }
            }
          },
          "then": {
            "properties": {
              "decision_id": { "$ref": "#/$defs/Uuid" },
              "public_id": {
                "type": "string",
                "pattern": "^[a-z0-9]{16,20}$"
              },
              "rule_pack": { "$ref": "#/$defs/RulePackRef" },
              "missing_facts": { "maxItems": 0 },
              "review_reasons": { "maxItems": 0 },
              "no_path_reasons": { "minItems": 1 },
              "outage": { "type": "null" }
            }
          }
        },
        {
          "if": {
            "properties": {
              "state": { "const": "TEMPORARILY_UNAVAILABLE" }
            }
          },
          "then": {
            "properties": {
              "candidates": { "maxItems": 0 },
              "missing_facts": { "maxItems": 0 },
              "review_reasons": { "maxItems": 0 },
              "no_path_reasons": { "maxItems": 0 },
              "quotes": { "maxItems": 0 },
              "outage": { "type": "object" }
            }
          }
        }
      ]
    }
  }
}
```

Each entrypoint is a direct reference, for example:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.balizero.com/visa-engine/rule-pack.schema.json",
  "$ref": "contract.schema.json#/$defs/RulePack"
}
```

Equivalent entrypoints:

| File | `$ref` |
|---|---|
| `rule.schema.json` | `contract.schema.json#/$defs/Rule` |
| `visa-product-version.schema.json` | `contract.schema.json#/$defs/VisaProductVersion` |
| `applicant-facts.schema.json` | `contract.schema.json#/$defs/ApplicantFacts` |
| `decision.schema.json` | `contract.schema.json#/$defs/Decision` |
| `price-quote.schema.json` | `contract.schema.json#/$defs/PriceQuote` |
| `source-record.schema.json` | `contract.schema.json#/$defs/SourceRecord` |

Compiler-only invariants, because JSON Schema cannot express them safely:

- Fact-path-specific literal types.
- UTC normalization and Unicode NFC.
- Unique rule/product/source IDs.
- Source-reference and product-reference integrity.
- `required_facts == collect_fact_paths(when)`.
- No `commercial.*` fact in hard-filter, eligibility, or review rules.
- `ADD_SCORE` may use only commercial/preference facts.
- Eligibility rules cannot derive positive support solely from `known`, `unknown`, or absence tests.
- `requested_purposes ⊆ covered_purposes`.
- Maximum AST depth 12, condition nodes 256, rules 4096, products 256.
- Stage/effect compatibility.
- Header environment equals payload environment.
- Quotes reference only emitted candidate versions.
- All numbers are integers within JavaScript-safe range; floats are rejected.

---

# 3. Bundle signing and anti-rollback

Use RFC 8785 JSON Canonicalization rather than `json.dumps(sort_keys=True)`. [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html) defines the canonical representation. A reviewed Python implementation is available as [Trail of Bits `rfc8785.py`](https://github.com/trailofbits/rfc8785.py).

Add direct production dependencies:

```text
jsonschema==4.26.0
rfc8785==0.1.4
```

`cryptography==49.0.0` is already locked and supports Ed25519 verification. [Ed25519 API](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/)

Exact signing input:

```text
protected_bytes = JCS(protected_header)
payload_bytes   = JCS(payload)

signed_bytes =
    UTF8("balizero.visa-rulepack.v1")
    || 0x00
    || protected_bytes
    || 0x00
    || payload_bytes

payload_sha256 = SHA256(payload_bytes)
signature      = Ed25519.sign(private_key, signed_bytes)
```

Rules:

- Base64url without padding.
- Private signing key exists only in the offline signing environment.
- Runtime has a pinned public-key trust store; the pack cannot supply its own trusted key.
- Trust entries include validity and revocation dates.
- Activation rejects:

  - sequence lower than or equal to the current sequence;
  - `previous_payload_sha256` not matching the current production bundle;
  - environment/jurisdiction/domain mismatch;
  - incompatible engine version;
  - invalid/revoked key;
  - legal period mismatch between pack and activation.

- Emergency rollback copies a previously approved payload into a newly signed bundle with a higher sequence and `rollback_of_payload_sha256`.
- Cross-language RFC 8785 test vectors are mandatory.

---

# 4. Evaluator algorithm

## 4.1 Three-valued condition semantics

| Operator | Known fact | Unknown fact |
|---|---|---|
| `known` | `TRUE` | `FALSE` |
| `unknown` | `FALSE` | `TRUE` |
| `eq`, `neq`, comparisons | typed comparison | `UNKNOWN` |
| `in`, `not_in` | scalar membership | `UNKNOWN` |
| `between` | inclusive `[lower, upper]` | `UNKNOWN` |
| `intersects` | set intersection | `UNKNOWN` |
| `contains_all` | set superset | `UNKNOWN` |
| `not` | negated result | `UNKNOWN` remains `UNKNOWN` |
| `all` | `FALSE` if any false; otherwise `UNKNOWN` if any unknown; otherwise true | same |
| `any` | `TRUE` if any true; otherwise `UNKNOWN` if any unknown; otherwise false | same |

All logical children are evaluated even when the truth value is already known, so the trace is complete. Evaluation does not short-circuit.

Malformed applicant values return HTTP 422. Pack literal/type mismatches invalidate the pack and produce `TEMPORARILY_UNAVAILABLE`; they do not become `UNKNOWN`.

## 4.2 Product proof

```python
def evaluate_product(
    product: CompiledProduct,
    rules: Sequence[CompiledRule],
    facts: FactSnapshot,
    purposes: frozenset[str],
    trace: TraceBuilder,
) -> ProductProof:
    hard_results = evaluate_all_rules(
        stage=RuleStage.HARD_FILTER,
        product=product,
        rules=rules,
        facts=facts,
        trace=trace,
    )

    if any(result.truth is TRUE for result in hard_results):
        return ProductProof(EXCLUDED, exclusion_reasons(hard_results))

    hard_unknowns = safety_unknowns(hard_results)

    review_results = evaluate_all_rules(
        stage=RuleStage.HUMAN_REVIEW,
        product=product,
        rules=rules,
        facts=facts,
        trace=trace,
    )

    if any(result.truth is TRUE for result in review_results):
        return ProductProof(REVIEW, review_reasons(review_results))

    review_unknowns = safety_unknowns(review_results)

    support_results = evaluate_all_rules(
        stage=RuleStage.ELIGIBILITY,
        product=product,
        rules=rules,
        facts=facts,
        trace=trace,
    )

    true_support = [
        result for result in support_results
        if result.truth is TRUE
    ]
    covered = union(result.effect.covered_purposes for result in true_support)

    support_unknowns = [
        result for result in support_results
        if result.truth is UNKNOWN
        and result.on_unknown != "NO_EFFECT"
    ]

    if hard_unknowns or review_unknowns:
        return ProductProof(
            BLOCKED_UNKNOWN,
            missing_facts=underlying_applicant_facts(
                hard_unknowns + review_unknowns
            ),
        )

    if purposes.issubset(covered):
        return ProductProof(
            SUPPORTED,
            support_rules=true_support,
        )

    missing_purposes = purposes - covered
    if an_unknown_support_rule_could_cover(
        support_unknowns,
        missing_purposes,
    ):
        return ProductProof(
            BLOCKED_UNKNOWN,
            missing_facts=underlying_applicant_facts(support_unknowns),
        )

    return ProductProof(UNSUPPORTED, missing_purposes=missing_purposes)
```

## 4.3 Global state

```python
def evaluate(
    pack: CompiledRulePack,
    facts: FactSnapshot,
    *,
    context: EvaluationContext,
) -> DecisionDraft:
    products = stable_sort(
        pack.products,
        key=lambda product: (
            product.product_code,
            str(product.product_version_id),
        ),
    )

    global_review = evaluate_global_review_rules(pack, facts)
    if global_review.has_true_trigger:
        return human_review_decision(global_review)

    proofs = [
        evaluate_product(
            product=product,
            rules=pack.rules_for(product),
            facts=facts,
            purposes=facts.require_known_set("intent.purposes"),
            trace=context.trace,
        )
        for product in products
        if product.is_effective_at(context.effective_at)
        and product.status == "ACTIVE"
    ]

    supported = [proof for proof in proofs if proof.status is SUPPORTED]

    if supported:
        ranked = rank_supported_only(
            proofs=supported,
            facts=facts,
            rules=pack.ranking_rules,
        )
        return supported_candidates_decision(ranked)

    review = [proof for proof in proofs if proof.status is REVIEW]
    if review:
        return human_review_decision(review)

    blocked = [proof for proof in proofs if proof.status is BLOCKED_UNKNOWN]
    if blocked:
        return needs_input_decision(minimal_missing_fact_set(blocked))

    return no_supported_path_decision(proofs)
```

Global precedence:

1. `TEMPORARILY_UNAVAILABLE`: absent/unverifiable pack, compilation failure, persistence-required dependency failure.
2. `HUMAN_REVIEW_REQUIRED`: independently true applicable review trigger.
3. `SUPPORTED_CANDIDATES`: at least one complete proof and no unresolved fact can invalidate returned candidates.
4. `NEEDS_INPUT`: at least one viable path is blocked only by unknown facts.
5. `NO_SUPPORTED_PATH`: all applicable products are definitively excluded or unsupported.

Pricing failure does not change the legal state. It returns `PriceQuote(status="UNAVAILABLE")`.

## 4.4 Ranking

- Applied only to `SUPPORTED` products.
- Integer points only.
- Stable order:

```python
(-score, product_code, str(product_version_id))
```

- Ranking rules may use only `commercial.*` or other explicitly registered preference facts.
- Unknown ranking facts add zero points.
- Ranking cannot add, remove, resurrect, or suppress a candidate.
- Legal facts are forbidden in ranking rules.

## 4.5 Deterministic trace

Full trace ordering:

```text
(stage_order, priority, rule_id, product_version_id, signed_child_index)
```

The internal trace records:

- pack hash;
- rule ID and source references;
- product version ID;
- condition result;
- referenced fact paths;
- unknown reason codes;
- applied effect;
- product proof transition.

It does not record raw fact values.

```text
trace_sha256 =
SHA256(
  JCS({
    pack_sha256,
    effective_at,
    facts_hmac,
    ordered_nodes
  })
)
```

`decision_id`, `public_id`, database timestamps, quote IDs, and encryption nonces are excluded from deterministic evaluation hashes.

The public response exposes only `trace_sha256`, reason codes, supporting rule IDs, and source references. The full trace is encrypted with the facts payload.

---

# 5. Database schema

The active migration path is `apps/backend-rag/backend/db/migrations_v2/`, not the legacy Python migrations. [Migration documentation](/Users/balizero/nuzantara/apps/backend-rag/backend/migrations/MIGRATIONS.md:5)

The local next number is 245, but it must be reserved again after Pro synchronization. Use:

```text
<next>_visa_engine_core.sql
<next+1>_visa_engine_runtime_grants.sql
```

PostgreSQL range types and exclusion constraints support non-overlap enforcement. [PostgreSQL 17 range constraints](https://www.postgresql.org/docs/17/rangetypes.html)

Core DDL:

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE visa_rule_packs (
    id                      UUID PRIMARY KEY,
    environment             TEXT NOT NULL
        CHECK (environment IN ('TEST', 'STAGING', 'PRODUCTION')),
    jurisdiction            CHAR(2) NOT NULL DEFAULT 'ID'
        CHECK (jurisdiction = 'ID'),
    decision_domain         TEXT NOT NULL DEFAULT 'IMMIGRATION_VISA'
        CHECK (decision_domain = 'IMMIGRATION_VISA'),
    sequence                BIGINT NOT NULL CHECK (sequence > 0),
    pack_version            TEXT NOT NULL,
    engine_contract_version TEXT NOT NULL,
    engine_min_version      TEXT NOT NULL,
    engine_max_version      TEXT NOT NULL,
    legal_period            TSTZRANGE NOT NULL,
    protected_header        JSONB NOT NULL,
    payload                 JSONB NOT NULL,
    payload_sha256          BYTEA NOT NULL CHECK (octet_length(payload_sha256) = 32),
    previous_payload_sha256 BYTEA CHECK (
        previous_payload_sha256 IS NULL
        OR octet_length(previous_payload_sha256) = 32
    ),
    signature               BYTEA NOT NULL CHECK (octet_length(signature) = 64),
    signing_key_id          TEXT NOT NULL,
    signed_at               TIMESTAMPTZ NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        NOT isempty(legal_period)
        AND lower_inc(legal_period)
        AND NOT upper_inc(legal_period)
    ),
    UNIQUE (environment, jurisdiction, decision_domain, sequence),
    UNIQUE (payload_sha256)
);

CREATE TABLE visa_ruleset_activations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_pack_id    UUID NOT NULL REFERENCES visa_rule_packs(id),
    environment     TEXT NOT NULL,
    jurisdiction    CHAR(2) NOT NULL DEFAULT 'ID',
    decision_domain TEXT NOT NULL DEFAULT 'IMMIGRATION_VISA',
    legal_period    TSTZRANGE NOT NULL,
    system_period   TSTZRANGE NOT NULL DEFAULT tstzrange(now(), NULL, '[)'),
    activated_by    TEXT NOT NULL,
    activation_reason TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        NOT isempty(legal_period)
        AND lower_inc(legal_period)
        AND NOT upper_inc(legal_period)
    ),
    CHECK (
        NOT isempty(system_period)
        AND lower_inc(system_period)
        AND NOT upper_inc(system_period)
    ),
    EXCLUDE USING gist (
        environment WITH =,
        jurisdiction WITH =,
        decision_domain WITH =,
        legal_period WITH &&,
        system_period WITH &&
    )
);

CREATE TABLE visa_source_records (
    id                 UUID PRIMARY KEY,
    source_key         TEXT NOT NULL,
    source_version     BIGINT NOT NULL CHECK (source_version > 0),
    authority_type     TEXT NOT NULL CHECK (
        authority_type IN (
            'PRIMARY_LAW',
            'IMPLEMENTING_REGULATION',
            'OFFICIAL_PORTAL',
            'OFFICIAL_CIRCULAR',
            'BALI_ZERO_POLICY',
            'PRICING_CATALOG'
        )
    ),
    status             TEXT NOT NULL CHECK (
        status IN ('VERIFIED', 'SUPERSEDED', 'REVOKED', 'UNAVAILABLE')
    ),
    jurisdiction       CHAR(2) NOT NULL DEFAULT 'ID',
    title              TEXT NOT NULL,
    publisher          TEXT NOT NULL,
    canonical_url      TEXT NOT NULL,
    document_number    TEXT,
    locators           JSONB NOT NULL DEFAULT '[]'::jsonb,
    content_sha256     BYTEA NOT NULL CHECK (octet_length(content_sha256) = 32),
    legal_period       TSTZRANGE NOT NULL,
    system_period      TSTZRANGE NOT NULL DEFAULT tstzrange(now(), NULL, '[)'),
    retrieved_at       TIMESTAMPTZ NOT NULL,
    verified_at        TIMESTAMPTZ NOT NULL,
    verified_by        TEXT NOT NULL,
    supersedes_id      UUID REFERENCES visa_source_records(id),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_key, source_version),
    EXCLUDE USING gist (
        source_key WITH =,
        legal_period WITH &&,
        system_period WITH &&
    )
);

CREATE TABLE visa_consent_receipts (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_type         TEXT NOT NULL CHECK (
        receipt_type IN ('NOTICE_ACKNOWLEDGEMENT', 'CONSENT')
    ),
    action               TEXT NOT NULL CHECK (
        action IN ('ACKNOWLEDGED', 'GRANTED', 'REFUSED', 'WITHDRAWN')
    ),
    purpose              TEXT NOT NULL CHECK (
        purpose IN (
            'ENGINE_EVALUATION',
            'ESSENTIAL_SESSION',
            'ANALYTICS',
            'PERSONALIZED_CHAT',
            'HUMAN_HANDOFF'
        )
    ),
    legal_basis          TEXT NOT NULL CHECK (
        legal_basis IN ('REQUESTED_SERVICE', 'CONSENT', 'LEGAL_OBLIGATION')
    ),
    policy_version       TEXT NOT NULL,
    policy_text_sha256   BYTEA NOT NULL CHECK (octet_length(policy_text_sha256) = 32),
    locale               TEXT NOT NULL,
    subject_hmac         BYTEA NOT NULL CHECK (octet_length(subject_hmac) = 32),
    subject_hmac_key_id  TEXT NOT NULL,
    session_id           UUID NOT NULL,
    decision_id          UUID,
    prior_receipt_id     UUID REFERENCES visa_consent_receipts(id),
    capture_channel      TEXT NOT NULL,
    idempotency_key      TEXT NOT NULL UNIQUE,
    receipt_sha256       BYTEA NOT NULL CHECK (octet_length(receipt_sha256) = 32),
    receipt_hmac         BYTEA NOT NULL CHECK (octet_length(receipt_hmac) = 32),
    receipt_hmac_key_id  TEXT NOT NULL,
    captured_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    retention_until      TIMESTAMPTZ NOT NULL,
    legal_hold           BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE visa_decisions (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state                    TEXT NOT NULL CHECK (
        state IN (
            'NEEDS_INPUT',
            'SUPPORTED_CANDIDATES',
            'HUMAN_REVIEW_REQUIRED',
            'NO_SUPPORTED_PATH',
            'TEMPORARILY_UNAVAILABLE'
        )
    ),
    rule_pack_id             UUID REFERENCES visa_rule_packs(id),
    rule_pack_sequence       BIGINT,
    rule_pack_sha256         BYTEA CHECK (
        rule_pack_sha256 IS NULL
        OR octet_length(rule_pack_sha256) = 32
    ),
    effective_at             TIMESTAMPTZ NOT NULL,
    observed_at              TIMESTAMPTZ NOT NULL,
    evaluated_at             TIMESTAMPTZ NOT NULL,
    facts_hmac               BYTEA NOT NULL CHECK (octet_length(facts_hmac) = 32),
    facts_hmac_key_id        TEXT NOT NULL,
    candidate_summary        JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(candidate_summary) = 'array'),
    missing_facts            TEXT[] NOT NULL DEFAULT '{}',
    review_reason_codes      TEXT[] NOT NULL DEFAULT '{}',
    no_path_reason_codes     TEXT[] NOT NULL DEFAULT '{}',
    notice_codes             TEXT[] NOT NULL DEFAULT '{}',
    trace_sha256             BYTEA CHECK (
        trace_sha256 IS NULL
        OR octet_length(trace_sha256) = 32
    ),
    decision_sha256          BYTEA NOT NULL CHECK (octet_length(decision_sha256) = 32),
    decision_hmac            BYTEA NOT NULL CHECK (octet_length(decision_hmac) = 32),
    decision_hmac_key_id     TEXT NOT NULL,
    processing_receipt_id    UUID REFERENCES visa_consent_receipts(id),
    idempotency_key          BYTEA NOT NULL UNIQUE,
    retention_until          TIMESTAMPTZ NOT NULL,
    legal_hold               BOOLEAN NOT NULL DEFAULT FALSE,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        state = 'TEMPORARILY_UNAVAILABLE'
        OR rule_pack_id IS NOT NULL
    )
);

ALTER TABLE visa_consent_receipts
    ADD CONSTRAINT fk_visa_consent_decision
    FOREIGN KEY (decision_id) REFERENCES visa_decisions(id);

CREATE TABLE visa_decision_payloads (
    decision_id          UUID PRIMARY KEY REFERENCES visa_decisions(id),
    encryption_algorithm TEXT NOT NULL DEFAULT 'AES-256-GCM',
    encryption_key_id    TEXT NOT NULL,
    nonce                BYTEA NOT NULL CHECK (octet_length(nonce) = 12),
    ciphertext           BYTEA NOT NULL,
    aad                  BYTEA NOT NULL,
    ciphertext_sha256    BYTEA NOT NULL CHECK (octet_length(ciphertext_sha256) = 32),
    purge_after          TIMESTAMPTZ NOT NULL,
    legal_hold           BOOLEAN NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_visa_decision_payloads_purge
    ON visa_decision_payloads (purge_after)
    WHERE legal_hold = FALSE;

CREATE TABLE visa_price_quotes (
    id                 UUID PRIMARY KEY,
    decision_id        UUID NOT NULL REFERENCES visa_decisions(id),
    product_version_id UUID NOT NULL,
    product_code       TEXT NOT NULL,
    status             TEXT NOT NULL CHECK (
        status IN ('AVAILABLE', 'CONTACT_REQUIRED', 'UNAVAILABLE')
    ),
    currency           CHAR(3) NOT NULL DEFAULT 'IDR',
    amount             BIGINT,
    pricing_category   TEXT NOT NULL,
    pricing_item_key   TEXT NOT NULL,
    catalog_version    TEXT,
    catalog_sha256     BYTEA,
    row_sha256         BYTEA,
    quoted_at          TIMESTAMPTZ NOT NULL,
    valid_until        TIMESTAMPTZ,
    reason_code        TEXT NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (decision_id, product_version_id),
    CHECK (
        (status = 'AVAILABLE' AND amount IS NOT NULL)
        OR (status <> 'AVAILABLE' AND amount IS NULL)
    )
);

CREATE TABLE visa_clock_snapshots (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_version_id UUID,
    product_code       TEXT NOT NULL,
    rule_pack_id       UUID REFERENCES visa_rule_packs(id),
    algorithm_version  TEXT NOT NULL,
    entry_date         DATE NOT NULL,
    snapshot           JSONB NOT NULL CHECK (jsonb_typeof(snapshot) = 'object'),
    snapshot_sha256    BYTEA NOT NULL CHECK (octet_length(snapshot_sha256) = 32),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE visa_public_results (
    public_id          VARCHAR(20) PRIMARY KEY
        CHECK (public_id ~ '^[a-z0-9]{16,20}$'),
    kind               TEXT NOT NULL CHECK (kind IN ('MATCH', 'CLOCK')),
    decision_id        UUID REFERENCES visa_decisions(id),
    clock_snapshot_id  UUID REFERENCES visa_clock_snapshots(id),
    public_snapshot    JSONB NOT NULL CHECK (jsonb_typeof(public_snapshot) = 'object'),
    snapshot_sha256    BYTEA NOT NULL CHECK (octet_length(snapshot_sha256) = 32),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at         TIMESTAMPTZ,
    disabled_at        TIMESTAMPTZ,
    CHECK (
        (kind = 'MATCH' AND decision_id IS NOT NULL AND clock_snapshot_id IS NULL)
        OR
        (kind = 'CLOCK' AND decision_id IS NULL AND clock_snapshot_id IS NOT NULL)
    )
);

CREATE TABLE visa_session_exchanges (
    token_digest       BYTEA PRIMARY KEY CHECK (octet_length(token_digest) = 32),
    public_id          VARCHAR(20) NOT NULL REFERENCES visa_public_results(public_id),
    expires_at         TIMESTAMPTZ NOT NULL,
    consumed_at        TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_visa_session_exchanges_expiry
    ON visa_session_exchanges (expires_at)
    WHERE consumed_at IS NULL;

CREATE FUNCTION reject_visa_immutable_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER visa_rule_packs_immutable
BEFORE UPDATE OR DELETE ON visa_rule_packs
FOR EACH ROW EXECUTE FUNCTION reject_visa_immutable_mutation();

CREATE TRIGGER visa_decisions_immutable
BEFORE UPDATE OR DELETE ON visa_decisions
FOR EACH ROW EXECUTE FUNCTION reject_visa_immutable_mutation();

CREATE TRIGGER visa_quotes_immutable
BEFORE UPDATE OR DELETE ON visa_price_quotes
FOR EACH ROW EXECUTE FUNCTION reject_visa_immutable_mutation();

CREATE TRIGGER visa_consent_receipts_immutable
BEFORE UPDATE OR DELETE ON visa_consent_receipts
FOR EACH ROW EXECUTE FUNCTION reject_visa_immutable_mutation();

-- ROLLBACK
DROP TRIGGER IF EXISTS visa_consent_receipts_immutable ON visa_consent_receipts;
DROP TRIGGER IF EXISTS visa_quotes_immutable ON visa_price_quotes;
DROP TRIGGER IF EXISTS visa_decisions_immutable ON visa_decisions;
DROP TRIGGER IF EXISTS visa_rule_packs_immutable ON visa_rule_packs;
DROP FUNCTION IF EXISTS reject_visa_immutable_mutation();
DROP TABLE IF EXISTS visa_session_exchanges;
DROP TABLE IF EXISTS visa_public_results;
DROP TABLE IF EXISTS visa_clock_snapshots;
DROP TABLE IF EXISTS visa_price_quotes;
DROP TABLE IF EXISTS visa_decision_payloads;
DROP TABLE IF EXISTS visa_decisions;
DROP TABLE IF EXISTS visa_consent_receipts;
DROP TABLE IF EXISTS visa_source_records;
DROP TABLE IF EXISTS visa_ruleset_activations;
DROP TABLE IF EXISTS visa_rule_packs;
```

Do not drop `btree_gist` in rollback because it may be shared. Extension creation must be preflighted in staging; the migration role may lack permission.

Activation is a privileged stored function/transaction:

```text
activate_visa_rule_pack(pack_id, legal_period, actor, reason)
  1. pg_advisory_xact_lock(environment/jurisdiction/domain)
  2. SELECT current activation FOR UPDATE
  3. verify signature, sequence, previous hash, engine compatibility
  4. close current system_period at transaction timestamp
  5. insert new activation with system_period [now, infinity)
  6. commit
```

Runtime queries both time dimensions:

```sql
WHERE legal_period  @> $effective_at
  AND system_period @> $observed_at
```

Runtime grants:

- `SELECT`: packs, activations, sources.
- `INSERT`: decisions, encrypted payloads, quotes, receipts, public results, exchanges.
- No runtime `UPDATE` or `DELETE`.
- Activation role: controlled source/activation period closure only.
- Retention role: bounded delete from payload/session tables only.
- Signing role and private key: outside FastAPI and outside the production DB.

## Retention

Provisional values requiring Gate-0 legal/DPO approval:

| Data | Retention |
|---|---:|
| Signed packs/source versions | Indefinite |
| Minimized decision envelope and provenance | 24 months |
| Encrypted ApplicantFacts and full trace | 90 days |
| Anonymous chat content | 30 days |
| One-time session exchanges | 24 hours after expiry |
| Public result snapshot | 24 months, then HTTP 410 |
| Consent/withdrawal receipts | 5 years after last relevant event |
| Abuse-control network HMAC | 7 days |

The purge worker uses bounded `DELETE … FOR UPDATE SKIP LOCKED`, respects legal holds, emits metrics, and also deletes expired `visa_oracle_sessions`. An `expires_at` column alone is not retention enforcement.

Existing `visa_checks` rows are not deleted during the strangler migration.

---

# 6. Strangler migration

## 6.1 Flags

Per-surface flags:

```text
VISA_ENGINE_CLOCK_MODE
VISA_ENGINE_MATCH_MODE
VISA_ENGINE_RECOMMEND_MODE
VISA_ENGINE_CATALOG_MODE
VISA_ENGINE_CHAT_CONTEXT_MODE
VISA_ENGINE_HANDOFF_MODE
```

Values: `OFF | SHADOW | ENFORCE`.

Effective mode is the minimum of:

- call-time environment ceiling;
- DB-controlled rollout mode.

Missing or invalid configuration resolves to `OFF`, never `ENFORCE`.

`OFF` does not authorize unsupported legacy recommendations. Before Gate 1, v1 inputs must return a safe `NEEDS_INPUT` or review-only response.

## 6.2 Endpoint compatibility

| Endpoint | Final behavior |
|---|---|
| `POST /api/visa/check/start` | Path and response unchanged. |
| `POST /api/visa/clock` | Uses signed product clock policy. Unknown product: 422. No active pack: 503. Persists complete snapshot. |
| `GET /api/visa/clock/{hash}` | Returns persisted snapshot. Never recomputes and never emits a JWT. |
| `POST /api/visa/match` | Adds `contract_version` and optional canonical `facts`. V1 fields are adapted to explicit unknowns and normally produce `NEEDS_INPUT`. |
| `GET /api/visa/match/{hash}` | Returns persisted public snapshot. Never re-evaluates or refreshes price. |
| `POST /api/v1/visa-oracle/recommend` | Keeps `{success, visas, session_id}`; adds `state`, `decision_id`, `missing_facts`, `review_reasons`. `visas=[]` unless state is `SUPPORTED_CANDIDATES`. |
| `POST /api/v1/visa-oracle/chat` | Anonymous general Q&A remains possible. Personalized explanations require private capability and a persisted decision. Chat cannot create or upgrade candidates. |
| `POST /api/v1/visa-oracle/handoff` | Accepts `decision_id` plus explicit handoff receipt. Client-supplied recommendations, prices, and quiz facts are ignored and eventually removed. |
| `GET /api/v1/visa-oracle/visa-types` | Preserves `{success, visa_types, count}` and item fields `name`, `category`, `price`; data becomes visa-only and pack-backed. |
| `GET /api/v1/visa-oracle/visa-types/{code}` | Accepts canonical code and signed legacy name-slug aliases. |
| `/api/knowledge/visa/*` | Becomes content/read adapter; admin writes cannot alter engine rules or prices. Writes return 409 after authoring cutover. |

Current effective prefixes are verified in [visa_check.py](/Users/balizero/nuzantara/apps/backend-rag/backend/app/routers/visa_check.py:54), [visa_oracle.py](/Users/balizero/nuzantara/apps/backend-rag/backend/app/routers/visa_oracle.py:24), and [knowledge_visa.py](/Users/balizero/nuzantara/apps/backend-rag/backend/app/routers/knowledge_visa.py:29).

## 6.3 Public hash versus private capability

Current public GETs issue a new chat JWT to every hash holder. [Clock GET](/Users/balizero/nuzantara/apps/backend-rag/backend/app/routers/visa_check.py:284) and [Match GET](/Users/balizero/nuzantara/apps/backend-rag/backend/app/routers/visa_check.py:314)

Replacement:

1. Result creation returns a one-time `session_exchange_token`.
2. Frontend exchanges it before navigation.
3. Next sets a host-only, `HttpOnly`, `Secure`, `SameSite=Strict` Visa capability cookie.
4. Personalized chat and handoff move to same-origin `/api/v1/visa-oracle/*`.
5. Origin and CSRF checks are enforced.
6. Public GET never returns a token or cookie.
7. Old shared hashes remain readable but do not grant personalized chat.
8. Public DTO omits raw nationality, investment, family, status, and overstay facts.
9. Result pages send:

```text
Referrer-Policy: no-referrer
X-Robots-Tag: noindex, nofollow
Cache-Control: private, no-store
```

This requires changing the direct Fly client in [api.ts](/Users/balizero/nuzantara/apps/mouth/src/lib/visa-oracle/api.ts:10).

## 6.4 Clock history

Current clock GET reconstructs checkpoint copy using current code rather than persisted data. [visa_check.py](/Users/balizero/nuzantara/apps/backend-rag/backend/app/routers/visa_check.py:295)

Before deleting `clock.py`:

1. Freeze it as `legacy_clock_v1.py`.
2. Backfill every historical clock row into `visa_clock_snapshots`.
3. Store `algorithm_version="legacy-clock-v1"` and snapshot hash.
4. Compare old endpoint output against snapshot output.
5. Switch GET lookup to snapshot.
6. Delete the frozen implementation only after zero unresolved rows.

If a complete backfill is impossible, retain `legacy_clock_v1.py` indefinitely.

## 6.5 Frontend changes

- Mount the replacement consent controller in `apps/mouth/src/app/visa/layout.tsx`, so direct `/clock`, `/match`, and hash URLs cannot bypass it.
- Separate:

  - processing notice acknowledgement;
  - optional analytics consent;
  - personalized-chat consent;
  - human-handoff consent.

- Stop analytics before analytics consent.
- Do not store canonical visa facts in `localStorage`.
- Harden `AppWizard`:

  - `onComplete: (...) => Promise<void>`;
  - pending lock and double-submit prevention;
  - clear state only after successful persistence;
  - no sensitive default persistence;
  - correct completion/abandon telemetry.

Current `AppWizard` clears storage before the async request can succeed and accepts only synchronous completion. [AppWizard](/Users/balizero/nuzantara/packages/core/components/apps/AppWizard.tsx:26)

- Use backend `result_url`; do not reconstruct it.
- Preserve hash/query components in `visa.balizero.com` redirects.
- Remove calling-visa logic from the client as an authority; it may only render server-provided outcomes.
- Runtime-validate API responses rather than TypeScript-casting JSON.

## 6.6 Deprecation order

1. Add five-state responses and frontend handling.
2. Remove ABSTAIN→CAUTIOUS pretraining promotion.
3. Stop trusting handoff recommendations/prices/messages from the browser.
4. Add exact pricing operation; ambiguous mappings return unavailable.
5. Add canonical facts v2 form and same-origin capability exchange.
6. Deploy signed engine in `SHADOW`; compare proof properties, not agreement with unsafe legacy output.
7. Enforce clock and match for v2 inputs.
8. Enforce recommend, chat context, catalog, and handoff.
9. Backfill historical clock snapshots.
10. Disable writes to old knowledge/catalog paths.
11. Verify import graph is zero.
12. Delete legacy implementations.

---

# 7. Gold-case harness

## Test layout

```text
apps/backend-rag/backend/tests/services/visa_engine/
├── conftest.py
├── fixtures/
│   ├── rulepacks/
│   │   ├── gold-v1.json
│   │   ├── gold-v1.signature.json
│   │   └── test-public-key.pem
│   └── gold_cases.v1.json
├── test_schema_contracts.py
├── test_condition_ast.py
├── test_fact_registry.py
├── test_rulepack_compiler.py
├── test_bundle_verification.py
├── test_anti_rollback.py
├── test_bitemporal_selection.py
├── test_evaluator_gold.py
├── test_evaluator_determinism.py
├── test_exact_pricing.py
├── test_clock_snapshot.py
├── test_consent.py
├── test_retention.py
└── test_no_pii_serialization.py

apps/backend-rag/backend/tests/db/
├── test_migration_<next>_visa_engine_roundtrip.py
└── test_visa_engine_repository.py

apps/backend-rag/backend/tests/routers/
└── test_visa_engine_strangler.py
```

Every fixture contains the complete canonical `ApplicantFacts` object. No inheritance or hidden defaults are allowed. The abbreviated table below is for review only; the JSON fixture must materialize every other field as an explicit `UNKNOWN` with a reason.

Gold fixture constants are synthetic engine-test policy, not production Indonesian legal assertions:

```text
GOLD_EFFECTIVE_AT = 2026-07-17T00:00:00Z
GOLD_CALLING_COUNTRIES = ["AF"]
GOLD_INVESTOR_MIN_IDR = 10_000_000_000
```

## First 20 personas

| # | Concrete distinguishing facts | Expected state | Candidates / required reason |
|---:|---|---|---|
| 1 | Nationalities `KNOWN ["ID","IT"]`; adult; tourism; offshore | `NO_SUPPORTED_PATH` | `[]`; `APPLICANT_IS_INDONESIAN_CITIZEN` |
| 2 | Nationalities `UNKNOWN(CONFLICTING)`; all other tourism facts complete | `HUMAN_REVIEW_REQUIRED` | `[]`; `CITIZENSHIP_EVIDENCE_CONFLICT` |
| 3 | Nationalities `KNOWN ["AF"]`; adult; tourism; offshore | `HUMAN_REVIEW_REQUIRED` | `[]`; `CALLING_VISA_REVIEW` |
| 4 | In Indonesia `true`; current status `C1`; overstay days `3`; violation includes `OVERSTAY` | `HUMAN_REVIEW_REQUIRED` | `[]`; `ACTIVE_OVERSTAY` |
| 5 | Birth date `2012-01-01`; tourism; guardian/sponsor confirmed `false` | `HUMAN_REVIEW_REQUIRED` | `[]`; `MINOR_WITHOUT_CONFIRMED_GUARDIAN` |
| 6 | Birth date `2012-01-01`; purpose `FAMILY`; relation `CHILD`; sponsor status `E23`; sponsor confirmed `true` | `SUPPORTED_CANDIDATES` | `[E31]` |
| 7 | Adult; purpose `FAMILY`; relation `SPOUSE`; sponsor nationality `ID`; marriage registered `true`; sponsor confirmed `true`; offshore | `SUPPORTED_CANDIDATES` | `[E31]` |
| 8 | Same as #7, but marriage registered `UNKNOWN(UNVERIFIED)` | `NEEDS_INPUT` | `[]`; missing `family.marriage_registered` |
| 9 | In Indonesia; current status `C1`; requested `E28A`; channel `ONSHORE_CONVERSION`; investment facts at fixture minimum | `NO_SUPPORTED_PATH` | `[]`; `DIRECT_ONSHORE_CONVERSION_UNSUPPORTED` |
| 10 | Same investor facts; channel `STATUS_BRIDGING` | `HUMAN_REVIEW_REQUIRED` | `[]`; `STATUS_BRIDGING_REVIEW` |
| 11 | Purpose `REMOTE_WORK`; foreign employer; Indonesian entity `false`; Indonesian clients `false`; Indonesian-source compensation `false`; offshore | `SUPPORTED_CANDIDATES` | `[E33G]` |
| 12 | Same as #11, but serves Indonesian clients `true` | `HUMAN_REVIEW_REQUIRED` | `[]`; `LOCAL_MARKET_ACTIVITY_REVIEW` |
| 13 | Same as #11, but serves Indonesian clients `UNKNOWN(NOT_PROVIDED)` | `NEEDS_INPUT` | `[]`; missing `work.serves_indonesian_clients` |
| 14 | Purposes `["TOURISM","REMOTE_WORK"]`; safe remote-work facts as #11 | `SUPPORTED_CANDIDATES` | `[E33G]`; never `C1` |
| 15 | Purposes `["TOURISM","EMPLOYMENT"]`; Indonesian employer `true`; work sponsor confirmed `true` | `SUPPORTED_CANDIDATES` | `[E23]`; never `C1` |
| 16 | Purpose `INVESTMENT`; capital `9,999,999,999`; all other investment facts complete | `NO_SUPPORTED_PATH` | `[]`; `INVESTMENT_CAPITAL_BELOW_FIXTURE_MINIMUM` |
| 17 | Purpose `INVESTMENT`; capital at fixture minimum; PT PMA committed; valid role; service-fee budget `1` IDR | `SUPPORTED_CANDIDATES` | `[E28A]`; commercial budget does not filter |
| 18 | Requested code `B211A`; purposes `UNKNOWN(NOT_PROVIDED)`; stay 30 days | `NEEDS_INPUT` | `[]`; missing `intent.purposes`; notice `OBSOLETE_PRODUCT_CODE` |
| 19 | Requested code `B211A`; purpose `TOURISM`; stay 30 days; complete offshore facts | `SUPPORTED_CANDIDATES` | `[C1]`; notice `OBSOLETE_PRODUCT_CODE` |
| 20 | In Indonesia; wants onshore conversion `true`; current status and overstay both `UNKNOWN(NOT_PROVIDED)` | `NEEDS_INPUT` | `[]`; missing both status and overstay facts |

Every case asserts:

- exact state;
- exact candidate order;
- exact missing/review/no-path reason codes;
- pack sequence and hash;
- quote status;
- deterministic trace equality across repeated runs;
- no candidate for any review/unknown/no-path case.

Non-persona tests additionally cover:

- invalid signature;
- revoked key;
- broken hash chain;
- lower sequence rollback;
- active-pack gap;
- future-effective query with no pack;
- AST depth/node rejection;
- duplicate literal rejection;
- D2/D12 exact-pricing mismatch;
- price outage preserving legal state;
- facts HMAC stability;
- ciphertext tampering;
- migration apply/rollback;
- retention actually deleting expired payloads;
- legacy clock backfill parity.

---

# 8. Salvage map

## Backend

| Existing file | Verdict | Reason |
|---|---|---|
| [app/routers/visa_check.py](/Users/balizero/nuzantara/apps/backend-rag/backend/app/routers/visa_check.py:54) | ADAPT | Preserve `/api/visa/*`; replace execution and result security. |
| [app/routers/visa_oracle.py](/Users/balizero/nuzantara/apps/backend-rag/backend/app/routers/visa_oracle.py:470) | ADAPT | Preserve `/api/v1/visa-oracle/*`; engine becomes authority; chat explanation-only. |
| [app/routers/knowledge_visa.py](/Users/balizero/nuzantara/apps/backend-rag/backend/app/routers/knowledge_visa.py:84) | ADAPT, then read-only | Content API only; remove price/rule authority. |
| `services/visa_check/repository.py` | ADAPT | Rename to legacy repository; read old hashes only after cutover. |
| `services/visa_check/catalogue.py` | ADAPT, then DELETE | First move `VisaType` parsing and aliases into `compat.py`; persisted rows still depend on it. |
| `services/visa_check/clock.py` | FREEZE, BACKFILL, then DELETE | Historical GETs currently recompute checkpoints. |
| `services/visa_check/match_tree.py` | DELETE | Nationality ignored; commercial budget used as eligibility filter. |
| `services/visa_check/pricing_bridge.py` | DELETE | Fuzzy/substr matching can map D2 to D12. |
| `services/visa_check/__init__.py` | ADAPT | Export compatibility façade during strangler. |
| `services/visa_oracle/visa_oracle_service.py` | DELETE | Static scorer, nationality informational, catalog includes non-visa services. |
| `services/visa_oracle/__init__.py` | ADAPT | Export new façade until callers migrate. |
| `services/visa_unified/bridge.py` | ADAPT, then DELETE | Preserve module path temporarily; stop treating legacy results as “ground truth.” |
| `services/visa_unified/__init__.py` | DELETE after import graph zero | Obsolete once chat consumes persisted Decision directly. |
| `services/pricing/pricing_service.py` | KEEP + ADAPT | Retain commercial SSOT; add exact category/key lookup. |
| `services/rag/agentic/tools.py::PricingTool` | KEEP + ADAPT | Add typed `quote_exact`; fuzzy string tool cannot be engine boundary. |
| `migration_080a_visa_oracle_sessions.py` | KEEP HISTORICAL | Never delete applied migration history; forward-migrate retention. |
| `db/migrations_v2/124_visa_checks.sql` | KEEP HISTORICAL | Old hashes remain readable; stop creating full new rows. |
| `migrations/scripts/seed_visa_types_complete_2026.py` | DELETE FROM OPERATIONS | Static duplicated rule/price authority. |
| `migration_043_fix_visa_types_from_qdrant.py` | KEEP HISTORICAL | Retire from runbooks only. |
| `app/auth/public_endpoints.py` | ADAPT | Separate anonymous catalog/general chat from private personalized actions. |
| `middleware/rate_limiter.py` | ADAPT | Costly chat/handoff requires fail-closed Visa-specific limits. |
| Router registration | KEEP | Only dependency wiring changes. |
| Qdrant `visa_oracle` collection | KEEP, NON-AUTHORITATIVE | General sourced explanation/research only. |

## Frontend

| Existing file | Verdict | Reason |
|---|---|---|
| `app/visa/page.tsx` | ADAPT | Preserve URL; move consent to layout. |
| `app/visa/clock/page.tsx` | ADAPT | Use signed catalog/product code. |
| `app/visa/clock/[hash]/page.tsx` | ADAPT | Public snapshot only; no JWT/chat capability from GET. |
| `app/visa/match/page.tsx` | ADAPT | Collect canonical v2 safety facts. |
| `app/visa/match/[hash]/page.tsx` | ADAPT | Render all five states; no re-evaluation. |
| `app/visa/layout.tsx` | ADAPT | Mount consent controller and same-origin capability boundary. |
| `components/visa/ConsentBanner.tsx` | DELETE/REPLACE | “By continuing” acknowledgement is not purpose-specific consent. |
| `components/visa/VisaChat.tsx` | ADAPT | Same-origin calls; Decision explanation only. |
| `components/visa/ChatAccordion.tsx` | ADAPT | Cookie capability rather than bearer JWT prop. |
| `components/visa/HandoffWaLink.tsx` | ADAPT | Server-built handoff from persisted decision. |
| `components/visa/QuestionCounter.tsx` | KEEP | Presentation-only. |
| `components/visa/WhatsAppCTA.tsx` | ADAPT, then DELETE | Still imported by `VisaChat`; replace with core CTA before deletion. |
| `lib/visa-oracle/api.ts` | ADAPT | Remove direct Fly URL and bearer JWT. |
| `lib/visa-oracle/types.ts` | ADAPT | Add five-state discriminated response union. |
| `lib/visa-oracle/storage.ts` | ADAPT | No canonical personal facts in localStorage. |
| `lib/visa-oracle/nationalities.ts` | ADAPT | Country picker only; calling-visa authority removed. |
| `lib/visa-oracle/quiz-logic.ts` and test | DELETE | Unused duplicate decision logic. |
| `lib/api/knowledge/visa.types.ts` | DELETE if import graph remains zero | Orphan contract. |
| `packages/core/AppWizard` | ADAPT, then KEEP | Async completion, pending/error, safe persistence. |
| `packages/core/AppFrame` | ADAPT, then KEEP | Correct nested layout behavior. |
| `packages/core/AppBranchSelector` | ADAPT, then KEEP | Use Next navigation rather than full-page anchors. |
| `packages/core/useFunnelApp` | ADAPT, then KEEP | Consent-aware telemetry. |
| `AppShareBar`, `AppEmailOptIn`, `AppWhatsAppCTA` | KEEP + ADAPT | Reusable presentation; server-side data contracts change. |
| Workspace intelligence Visa Oracle | KEEP SEPARATE | Regulation-ingestion surface, not consumer engine. |
| Portal Visa and CRM `VisaCard` | KEEP SEPARATE | Operational lifecycle, not public recommendation engine. |

Files deleted outright only after Gate 4 and `rg` confirms zero imports:

```text
apps/backend-rag/backend/services/visa_check/match_tree.py
apps/backend-rag/backend/services/visa_check/pricing_bridge.py
apps/backend-rag/backend/services/visa_check/catalogue.py
apps/backend-rag/backend/services/visa_check/clock.py
apps/backend-rag/backend/services/visa_oracle/visa_oracle_service.py
apps/backend-rag/backend/services/visa_unified/bridge.py
apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py
apps/mouth/src/components/visa/ConsentBanner.tsx
apps/mouth/src/components/visa/WhatsAppCTA.tsx
apps/mouth/src/lib/visa-oracle/quiz-logic.ts
apps/mouth/src/lib/visa-oracle/quiz-logic.test.ts
apps/mouth/src/lib/api/knowledge/visa.types.ts
```

Historical migrations are never deleted.

---

# 9. PR sizing and gates

The exact Round-1 Gate 0–4 wording was not included in this prompt or checkout. The mapping below is an implementation mapping, not a redefinition; it must be reconciled against the adopted Round-1 text before work begins.

| PR | Increment | Estimate | Gate evidence |
|---:|---|---:|---|
| 0 | Safety freeze: additive five-state responses; remove ABSTAIN promotion; stop client-trusted prices/recommendations; frontend handles empty candidates | 3–4 days | Gate 0 |
| 1 | Pydantic contracts, JSON Schema export, AST, fact registry, compiler limits | 4–5 days | Gate 1 partial |
| 2 | RFC8785/Ed25519 verification, trust store, sequence/hash-chain anti-rollback, offline scripts | 3–4 days | Gate 1 |
| 3 | Pure evaluator, deterministic trace, first 20 gold cases, metamorphic tests | 5–7 days | Gate 1 complete |
| 4 | V2 SQL, bitemporal repository, encrypted payloads, consent receipts, apply/rollback tests | 5–7 days | Gate 2 foundation |
| 5 | Exact PricingTool operation, signed catalog, clock snapshots, historical clock backfill | 4–5 days | Gate 2 |
| 6 | Shadow adapters for match/recommend/catalog; proof metrics and source validation | 4–5 days | Gate 2 complete |
| 7 | Complete-facts frontend, AppWizard hardening, same-origin capability cookie, public result split | 5–7 days | Gate 3 prerequisite |
| 8 | Enforce match/clock, then recommend/chat/handoff; canary and rollback bundle | 5–7 days | Gate 3 |
| 9 | Retention worker, knowledge write shutdown, import-graph cleanup, legacy deletion | 3–5 days | Gate 4 |

Engineering total: approximately 41–56 engineer-days. Legal-source review and production RulePack authoring are separate critical-path work.

Gate blockers:

- Gate 0: retention/legal-basis approval; source authority policy; current unsafe paths frozen.
- Gate 1: all schemas valid; compiler rejects malformed packs; 20 gold cases pass; deterministic output; key rotation and anti-rollback tested.
- Gate 2: active signed source-backed pack; exact pricing provenance; bitemporal selection; migration roundtrip; shadow emits no unsupported candidates.
- Gate 3: complete-facts UI; private capability split; consent receipts; historical clock backfill; canary evidence that every candidate has a complete proof.
- Gate 4: retention worker observed deleting expired payloads; all surfaces `ENFORCE`; rollback uses a signed higher-sequence pack; `rg` shows zero imports of deleted modules; no legacy fallback remains.

No repository files were modified.
