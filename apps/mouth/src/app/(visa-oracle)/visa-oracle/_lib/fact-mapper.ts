/**
 * Pure interview-to-engine adapter. The wire contract is imported from the
 * generated OpenAPI operation; this module owns only the explicit mapping from
 * language-neutral UI answer keys to that contract.
 */
import { canonicalCountryCodes } from "./countries";
import { parseIsoDateUtc, type CategoryKey, type OracleFacts } from "./tree";
import type {
  VisaOracleApplicantFacts,
  VisaOracleDisclosedReviewFlag,
  VisaOracleEvaluateRequest,
  VisaOracleRequestCategory,
  VisaOracleUnknownReason,
} from "./visa-oracle-contract";

export const SCHEMA_VERSION: VisaOracleEvaluateRequest["schema_version"] =
  "1.0.0";

export type ApplicantFactsDataWire = VisaOracleApplicantFacts;
export type ApplicantFactsWire = VisaOracleEvaluateRequest;
export type DisclosedReviewFlagWire = VisaOracleDisclosedReviewFlag;
export type UnknownReasonWire = VisaOracleUnknownReason;

/** Retained as a small test/helper type; the actual envelope is OpenAPI-derived. */
export type FactValue<T> =
  | { status: "KNOWN"; value: T }
  | { status: "UNKNOWN"; reason: UnknownReasonWire };

type KnownValue<Path extends keyof ApplicantFactsDataWire> = Extract<
  ApplicantFactsDataWire[Path],
  { status: "KNOWN" }
>["value"];

type Purpose = KnownValue<"intent.purposes">[number];
type Violation = KnownValue<"immigration.violation_history">[number];
type EntryPattern = KnownValue<"intent.entry_pattern">;
type ApplicationChannel = KnownValue<"process.application_channel">;
type MaritalStatus = KnownValue<"person.marital_status">;
type ProposedRole = KnownValue<"investment.proposed_role">;
type FamilyRelation = KnownValue<"family.relation_to_sponsor">;
type StudyLevel = KnownValue<"study.level">;
type SponsorTypeValue = KnownValue<"sponsor.type">;

const NOT_ASKED: UnknownReasonWire = "NOT_ASKED";
const UNVERIFIED: UnknownReasonWire = "UNVERIFIED";
const NOT_PROVIDED: UnknownReasonWire = "NOT_PROVIDED";
const NOT_APPLICABLE: UnknownReasonWire = "NOT_APPLICABLE";
const CONFLICTING: UnknownReasonWire = "CONFLICTING";

function known<T>(value: T): { status: "KNOWN"; value: T } {
  return { status: "KNOWN", value };
}

function unknownFact(reason: UnknownReasonWire): {
  status: "UNKNOWN";
  reason: UnknownReasonWire;
} {
  return { status: "UNKNOWN", reason };
}

function booleanFact(value: string | undefined): FactValue<boolean> {
  if (value === "yes") return known(true);
  if (value === "no") return known(false);
  if (value === "unsure") return unknownFact(UNVERIFIED);
  return value === undefined
    ? unknownFact(NOT_ASKED)
    : unknownFact(NOT_PROVIDED);
}

function dateFact(value: string | undefined): FactValue<string> {
  if (value === undefined) return unknownFact(NOT_ASKED);
  if (value === "unsure") return unknownFact(UNVERIFIED);
  return parseIsoDateUtc(value) === null
    ? unknownFact(NOT_PROVIDED)
    : known(value);
}

function integerFact(
  value: string | undefined,
  minimum: number,
  maximum: number,
): FactValue<number> {
  if (value === undefined) return unknownFact(NOT_ASKED);
  if (value === "unsure") return unknownFact(UNVERIFIED);
  if (!/^(0|[1-9]\d*)$/.test(value)) return unknownFact(NOT_PROVIDED);
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= minimum && parsed <= maximum
    ? known(parsed)
    : unknownFact(NOT_PROVIDED);
}

function enumFact<T extends string>(
  value: string | undefined,
  accepted: readonly T[],
): FactValue<T> {
  if (value === undefined) return unknownFact(NOT_ASKED);
  if (value === "unsure") return unknownFact(UNVERIFIED);
  return (accepted as readonly string[]).includes(value)
    ? known(value as T)
    : unknownFact(NOT_PROVIDED);
}

/**
 * A SINGLE country code — the wire type `KnownCountryCode`, whose `value` is a
 * bare string, not a one-element array.
 *
 * Kept separate from `countryCodesFact` on purpose. The two shapes look alike
 * and are not: `person.nationalities` / `family.sponsor_nationalities` are
 * `KnownCountrySet`, while `work.employer_country_code` is `KnownCountryCode`.
 * Sending the set shape for the singular field made the API reject the whole
 * request (422 `string_type`), which the interview surfaced as a "Client
 * safety hold" — so every remote-work interview that answered the employer's
 * country died before it ever reached the engine.
 */
function countryCodeFact(value: string | undefined): FactValue<string> {
  if (value === undefined) return unknownFact(NOT_ASKED);
  if (value === "unsure") return unknownFact(UNVERIFIED);
  const codes = value.split(",");
  if (codes.length !== 1) return unknownFact(NOT_PROVIDED);
  return canonicalCountryCodes(codes, false) === value
    ? known(codes[0])
    : unknownFact(NOT_PROVIDED);
}

function countryCodesFact(
  value: string | undefined,
  multiple: boolean,
): FactValue<string[]> {
  if (value === undefined) return unknownFact(NOT_ASKED);
  if (value === "unsure") return unknownFact(UNVERIFIED);
  const codes = value.split(",");
  const canonical = canonicalCountryCodes(codes, multiple);
  if (
    canonical !== value ||
    codes.length === 0 ||
    (!multiple && codes.length !== 1) ||
    (multiple && codes.length > 4)
  ) {
    return unknownFact(NOT_PROVIDED);
  }
  return known(codes);
}

function pairedBooleanFact(
  left: string | undefined,
  right: string | undefined,
): FactValue<boolean> {
  if (left !== undefined && right !== undefined && left !== right) {
    return unknownFact(CONFLICTING);
  }
  return booleanFact(left ?? right);
}

const ENTRY_PATTERNS = [
  "SINGLE",
  "MULTIPLE",
] as const satisfies readonly EntryPattern[];
const APPLICATION_CHANNELS = [
  "OFFSHORE",
  "ONSHORE_CONVERSION",
  "STATUS_BRIDGING",
] as const satisfies readonly ApplicationChannel[];
const MARITAL_STATUSES = [
  "SINGLE",
  "MARRIED",
  "DIVORCED",
  "WIDOWED",
  "OTHER",
] as const satisfies readonly MaritalStatus[];
const PROPOSED_ROLES = [
  "SHAREHOLDER_DIRECTOR",
  "SHAREHOLDER_COMMISSIONER",
  "EMPLOYEE",
  "NO_OPERATIONAL_ROLE",
  "OTHER",
] as const satisfies readonly ProposedRole[];
const FAMILY_RELATIONS = [
  "SPOUSE",
  "CHILD",
  "PARENT",
  "SIBLING",
  "DEPENDENT",
  // STEPCHILD added 2026-08-23 (owner ruling — E31D vocabulary extension,
  // `research/visa/2026-08-15-gold-family-refuter.md`).
  "STEPCHILD",
  "OTHER",
] as const satisfies readonly FamilyRelation[];
const STUDY_LEVELS = [
  "PRIMARY",
  "SECONDARY",
  "VOCATIONAL",
  "UNDERGRADUATE",
  "POSTGRADUATE",
  "RESEARCH",
  "OTHER",
] as const satisfies readonly StudyLevel[];
const CURRENT_STATUS_CODES = [
  "A1",
  "C1",
  "C2",
  "C6",
  "ITK_FROM_BVK",
  "ITK_FROM_VISIT_C",
  "ITK_FROM_VISIT_D",
  "ITK_PERALIHAN",
] as const;
// 29 real product codes, verbatim from `rulepack-prod-007.source.json`
// (`products[].product_code`, filtered to `E`-prefix). Only reachable via
// `stay_permit_code` (tree.ts), gated behind `holds_stay_permit === "yes"`
// — see `mapCurrentStatusCode` below. Not the same list as
// `CURRENT_STATUS_CODES` above: that one is the non-E ITK/visit-class
// catalogue, this one is the ITAS/ITAP catalogue backing
// `derived.has_active_stay_permit`'s positive branch (fact_registry.py's
// `^E\d+[A-Z]?$` heuristic).
const STAY_PERMIT_CODES = [
  "E23",
  "E23U",
  "E23V",
  "E28A",
  "E28B",
  "E28C",
  "E28D",
  "E28F",
  "E30",
  "E30A",
  "E30B",
  "E30E",
  "E30F",
  "E31A",
  "E31B",
  "E31C",
  "E31D",
  "E31E",
  "E31F",
  "E31G",
  "E31H",
  "E31J",
  "E33",
  "E33A",
  "E33B",
  "E33C",
  "E33E",
  "E33F",
  "E33G",
] as const;
const SPONSOR_TYPES = [
  "NONE",
  "INDIVIDUAL",
  "EMPLOYER",
  "EDUCATION",
  "INVESTMENT",
  "GOVERNMENT",
] as const satisfies readonly SponsorTypeValue[];

export const CATEGORY_TO_PURPOSE: Partial<Record<CategoryKey, Purpose>> = {
  tourism: "TOURISM",
  business: "BUSINESS_MEETINGS",
  work: "EMPLOYMENT",
  invest: "INVESTMENT",
  remote: "REMOTE_WORK",
  family: "FAMILY",
  retirement: "RETIREMENT",
  study: "STUDY",
  other: "OTHER",
  // Diaspora is intentionally represented only by request_category.
};

const CATEGORY_TO_REQUEST_CATEGORY: Readonly<
  Record<CategoryKey, VisaOracleRequestCategory>
> = {
  tourism: "long_tourism",
  business: "business",
  work: "work_employee",
  invest: "investor",
  remote: "work_remote",
  family: "family",
  retirement: "retirement",
  study: "student",
  diaspora: "diaspora",
  other: "other",
};

export function requestCategoryForFacts(
  facts: OracleFacts,
): VisaOracleRequestCategory | undefined {
  if (facts.category === undefined || facts.category === "unsure") {
    return undefined;
  }
  const category = facts.category as CategoryKey;
  return category && category in CATEGORY_TO_REQUEST_CATEGORY
    ? CATEGORY_TO_REQUEST_CATEGORY[category]
    : undefined;
}

export function mapCurrentlyInIndonesia(
  facts: OracleFacts,
): FactValue<boolean> {
  return booleanFact(facts.in_indonesia);
}

export function mapCurrentStatusExpiry(facts: OracleFacts): FactValue<string> {
  return dateFact(facts.permit_expiry);
}

export function mapPurposes(facts: OracleFacts): FactValue<Purpose[]> {
  if (facts.category === undefined) return unknownFact(NOT_ASKED);
  if (facts.category === "unsure") return unknownFact(UNVERIFIED);
  const category = facts.category as CategoryKey;
  const purpose = CATEGORY_TO_PURPOSE[category];
  return purpose === undefined ? unknownFact(NOT_APPLICABLE) : known([purpose]);
}

export function mapStayDays(facts: OracleFacts): FactValue<number> {
  return integerFact(facts.stay_days, 1, 36_500);
}

export function mapEmployerIsIndonesianEntity(
  facts: OracleFacts,
): FactValue<boolean> {
  return booleanFact(facts.work_payer);
}

export interface RemoteClientsDerived {
  servesIndonesianClients: FactValue<boolean>;
}

export function mapRemoteClientsDerived(
  facts: OracleFacts,
): RemoteClientsDerived {
  if (facts.remote_clients === "foreign") {
    return { servesIndonesianClients: known(false) };
  }
  if (
    facts.remote_clients === "indonesian" ||
    facts.remote_clients === "mixed"
  ) {
    return { servesIndonesianClients: known(true) };
  }
  return {
    servesIndonesianClients:
      facts.remote_clients === "unsure"
        ? unknownFact(UNVERIFIED)
        : facts.remote_clients === undefined
          ? unknownFact(NOT_ASKED)
          : unknownFact(NOT_PROVIDED),
  };
}

export function mapViolationHistory(
  facts: OracleFacts,
): FactValue<Violation[]> {
  if (facts.review_gate === undefined) return unknownFact(NOT_ASKED);
  const values = facts.review_gate.split(",").filter(Boolean);
  const unique = new Set(values);
  if (values.length === 0 || unique.size !== values.length) {
    return unknownFact(CONFLICTING);
  }
  if (unique.has("none")) {
    return unique.size === 1 ? known([]) : unknownFact(CONFLICTING);
  }
  const knownReviewItems = new Set([
    "criminal_record",
    "health_flag",
    "prior_refusal",
    "overstay",
    "blacklist",
    "immigration_investigation",
    "pep_or_sanctions",
    "source_of_funds_unclear",
    "diplomatic_passport",
    "ambiguous_sponsor",
    "activity_boundary",
    "not_certain",
  ]);
  if (values.some((value) => !knownReviewItems.has(value))) {
    return unknownFact(CONFLICTING);
  }

  const violations: Violation[] = [];
  if (unique.has("overstay")) violations.push("OVERSTAY");
  if (unique.has("blacklist")) violations.push("BLACKLIST");
  if (unique.has("immigration_investigation")) {
    violations.push("IMMIGRATION_INVESTIGATION");
  }
  return violations.length > 0 ? known(violations) : unknownFact(UNVERIFIED);
}

const REVIEW_FLAG_MAP: Readonly<
  Partial<Record<string, DisclosedReviewFlagWire>>
> = {
  criminal_record: "CRIMINAL_RECORD",
  health_flag: "HEALTH_CONCERN",
  prior_refusal: "PRIOR_VISA_REFUSAL",
  not_certain: "NOT_CERTAIN",
  pep_or_sanctions: "PEP_OR_SANCTIONS",
  source_of_funds_unclear: "SOURCE_OF_FUNDS_UNCLEAR",
  diplomatic_passport: "DIPLOMATIC_PASSPORT",
  ambiguous_sponsor: "AMBIGUOUS_SPONSOR",
  activity_boundary: "ACTIVITY_BOUNDARY",
};

export function mapDisclosedReviewFlags(
  facts: OracleFacts,
): DisclosedReviewFlagWire[] {
  const flags = new Set<DisclosedReviewFlagWire>();
  for (const item of facts.review_gate?.split(",") ?? []) {
    const mapped = REVIEW_FLAG_MAP[item];
    if (mapped) flags.add(mapped);
  }
  if (Object.values(facts).includes("unsure")) flags.add("NOT_CERTAIN");
  if (facts.trip_scope === "multiple") flags.add("MULTI_PURPOSE_TRIP");
  // Human-context answers that cannot be represented by a signed FactPath
  // may only lower the result to review. They must never be silently ignored
  // while a broader generic purpose still produces a candidate.
  if (
    facts.category === "diaspora" ||
    facts.business_activity !== undefined ||
    facts.work_role !== undefined ||
    facts.tourism_duration !== undefined ||
    facts.remote_income !== undefined ||
    facts.diaspora_connection !== undefined ||
    facts.diaspora_documents !== undefined ||
    facts.other_purpose !== undefined ||
    facts.other_paid_activity !== undefined ||
    facts.retirement_basis === "property" ||
    (facts.investment_vehicle !== undefined &&
      facts.investment_vehicle !== "pt_pma") ||
    facts.retirement_basis === "family_sponsor" ||
    facts.retirement_basis === "undecided"
  ) {
    flags.add("ACTIVITY_BOUNDARY");
  }
  if (
    facts.family_sponsor_status_code !== undefined ||
    facts.family_sponsor_permit_basis !== undefined
  ) {
    flags.add("AMBIGUOUS_SPONSOR");
  }
  return [...flags].sort();
}

// Two source questions feed this ONE FactPath. The `holds_stay_permit` gate
// (tree.ts) makes them mutually exclusive in the tree — "yes" routes to the
// KITAS/KITAP transcription question (`stay_permit_code`, validated against
// the real E-code catalogue), "no" routes to the original 8-code visit-class
// question (`current_status_code`), unchanged — and `pruneFacts` (flow.ts)
// drops whichever one falls out of history on every EDIT, so at most one of
// the two raw fields is ever populated at a time. Branching on THAT
// (presence of the raw field actually answered) rather than on
// `holds_stay_permit`'s value keeps this mapper correct even when it's
// invoked in isolation — e.g. a test that answers `stay_permit_code` alone,
// without also setting `holds_stay_permit` — instead of silently resolving
// to NOT_ASKED because the gate field was never populated. Both branches go
// through `enumFact`, so an unrecognized or "unsure" value resolves UNKNOWN
// either way — never a guessed KNOWN.
function mapCurrentStatusCode(facts: OracleFacts): FactValue<string> {
  if (facts.stay_permit_code !== undefined) {
    return enumFact(facts.stay_permit_code, STAY_PERMIT_CODES);
  }
  return enumFact(facts.current_status_code, CURRENT_STATUS_CODES);
}

/**
 * `sponsor.type` is the ONE backend fact path that ships with a default
 * (`UNKNOWN`/`NOT_ASKED`, models.py `_SPONSOR_TYPE_ROLLOUT_DEFAULT`) rather
 * than being strictly required — but this mapper still emits it on every
 * call, unconditionally, same as every other key. A fact that was never
 * asked and a key that was never sent are not the same thing to the
 * engine: only an explicit UNKNOWN can ever produce a follow-up question,
 * an omitted key cannot. See fact-mapper.test.ts's "staged contract"
 * describe block for the acceptance criteria this replaced.
 */
export function mapSponsorType(
  facts: OracleFacts,
): FactValue<SponsorTypeValue> {
  return enumFact(facts.sponsor_category, SPONSOR_TYPES);
}

function mapFamilySponsorStatus(facts: OracleFacts): FactValue<string> {
  if (facts.family_sponsor_confirmed === "no") {
    return unknownFact(NOT_APPLICABLE);
  }
  if (facts.family_sponsor_confirmed === "unsure") {
    return unknownFact(UNVERIFIED);
  }
  if (facts.family_sponsor_confirmed !== "yes") {
    return facts.family_sponsor_status_code === undefined
      ? unknownFact(NOT_ASKED)
      : unknownFact(UNVERIFIED);
  }
  const value = facts.family_sponsor_status_code;
  if (value === undefined) return unknownFact(NOT_ASKED);
  // The UI accepts a human-entered status label. It is not backed by the
  // signed status-code catalogue, so even a syntactically plausible value
  // must never satisfy an engine rule that checks `op: known`.
  return unknownFact(UNVERIFIED);
}

/**
 * `family.sponsor_permit_basis` shipped in PR #4650 wired straight to
 * `enumFact()` — self-declaration resolving directly to `KNOWN`. That
 * missed the parallel to its sibling immediately above: the applicant/
 * sponsor is asked to classify the sponsor's OWN permit into one of 13
 * Pasal 33 ayat (2) huruf a-l legal categories, a taxonomy they are no
 * more likely to know precisely than a signed status code. Ruling 2's
 * whole purpose is Pasal 33 ayat (7), an EXCLUSIONARY gate — a wrong
 * self-declared category does not just fail to help, it can wrongly
 * exclude an eligible applicant. Mirrors `mapFamilySponsorStatus` exactly:
 * collected, flagged for human review (`AMBIGUOUS_SPONSOR`, below), never
 * trusted for `op: known`, until a document-verified source (e.g. an
 * OCR'd sponsor permit card cross-checked against the signed catalogue —
 * which does not exist yet for `sponsor_status_code` either) supplies one.
 */
function mapFamilySponsorPermitBasis(
  facts: OracleFacts,
): FactValue<KnownValue<"family.sponsor_permit_basis">> {
  if (facts.family_sponsor_confirmed === "no") {
    return unknownFact(NOT_APPLICABLE);
  }
  if (facts.family_sponsor_confirmed === "unsure") {
    return unknownFact(UNVERIFIED);
  }
  if (facts.family_sponsor_confirmed !== "yes") {
    return facts.family_sponsor_permit_basis === undefined
      ? unknownFact(NOT_ASKED)
      : unknownFact(UNVERIFIED);
  }
  const value = facts.family_sponsor_permit_basis;
  if (value === undefined) return unknownFact(NOT_ASKED);
  return unknownFact(UNVERIFIED);
}

function mapMarriageRegistered(facts: OracleFacts): FactValue<boolean> {
  if (facts.family_marriage_registered === "not_applicable") {
    return unknownFact(NOT_APPLICABLE);
  }
  return booleanFact(facts.family_marriage_registered);
}

export interface MapFactsOptions {
  assessmentId: string;
  /** One frozen clock shared by evaluation, dedupe and presentation. */
  collectedAt: Date;
}

export function mapOracleFactsToApplicantFacts(
  facts: OracleFacts,
  options: MapFactsOptions,
): ApplicantFactsWire {
  const remoteClients = mapRemoteClientsDerived(facts);
  const data: ApplicantFactsDataWire = {
    "person.birth_date": dateFact(facts.birth_date),
    "person.nationalities": countryCodesFact(facts.nationalities, true),
    "person.marital_status": enumFact(facts.marital_status, MARITAL_STATUSES),
    "immigration.currently_in_indonesia": mapCurrentlyInIndonesia(facts),
    "immigration.current_status_code": mapCurrentStatusCode(facts),
    "immigration.current_status_expiry": mapCurrentStatusExpiry(facts),
    "immigration.last_entry_date": unknownFact(NOT_ASKED),
    "immigration.overstay_days": integerFact(facts.overstay_days, 0, 36_500),
    "immigration.violation_history": mapViolationHistory(facts),
    "intent.purposes": mapPurposes(facts),
    "intent.stay_days": mapStayDays(facts),
    "intent.desired_entry_date": unknownFact(NOT_ASKED),
    "intent.entry_pattern": enumFact(facts.entry_pattern, ENTRY_PATTERNS),
    "intent.requested_product_code": unknownFact(NOT_ASKED),
    "work.employer_country_code": countryCodeFact(
      facts.remote_employer_country,
    ),
    "work.employer_is_indonesian_entity": mapEmployerIsIndonesianEntity(facts),
    "work.serves_indonesian_clients": remoteClients.servesIndonesianClients,
    "work.indonesia_source_compensation": pairedBooleanFact(
      facts.work_indonesia_compensation,
      facts.remote_compensation,
    ),
    "work.indonesian_work_sponsor_confirmed": booleanFact(
      facts.work_sponsor_confirmed,
    ),
    "investment.pt_pma_committed": pairedBooleanFact(
      facts.investment_pt_pma,
      facts.remote_pt_pma,
    ),
    "investment.investment_capital_idr": integerFact(
      facts.investment_capital_idr,
      0,
      Number.MAX_SAFE_INTEGER,
    ),
    "investment.paid_up_capital_idr": integerFact(
      facts.investment_paid_up_capital_idr,
      0,
      Number.MAX_SAFE_INTEGER,
    ),
    "investment.proposed_role": enumFact(facts.investment_role, PROPOSED_ROLES),
    "family.relation_to_sponsor": enumFact(
      facts.family_relation,
      FAMILY_RELATIONS,
    ),
    "family.sponsor_nationalities": countryCodesFact(
      facts.family_sponsor_nationalities,
      true,
    ),
    "family.sponsor_status_code": mapFamilySponsorStatus(facts),
    "family.marriage_registered": mapMarriageRegistered(facts),
    "family.stepchild_marriage_certificate_confirmed": booleanFact(
      facts.family_stepchild_marriage_certificate_confirmed,
    ),
    "family.stepchild_birth_certificate_confirmed": booleanFact(
      facts.family_stepchild_birth_certificate_confirmed,
    ),
    "family.sponsor_permit_basis": mapFamilySponsorPermitBasis(facts),
    "family.sponsor_confirmed": booleanFact(facts.family_sponsor_confirmed),
    "study.level": enumFact(facts.study_level, STUDY_LEVELS),
    "study.admission_confirmed": booleanFact(facts.study_admission_confirmed),
    "study.sponsor_confirmed": booleanFact(facts.study_sponsor_confirmed),
    "sponsor.type": mapSponsorType(facts),
    "secondhome.bank_deposit_usd": integerFact(
      facts.secondhome_deposit_usd,
      0,
      Number.MAX_SAFE_INTEGER,
    ),
    "secondhome.bank_deposit_at_state_bank": booleanFact(
      facts.secondhome_state_bank,
    ),
    "secondhome.bank_deposit_in_own_name": booleanFact(
      facts.secondhome_own_name,
    ),
    "secondhome.qualifying_property_value_usd": integerFact(
      facts.secondhome_property_value_usd,
      0,
      Number.MAX_SAFE_INTEGER,
    ),
    "secondhome.passive_monthly_income_usd": integerFact(
      facts.secondhome_passive_income_usd,
      0,
      Number.MAX_SAFE_INTEGER,
    ),
    "process.application_channel": enumFact(
      facts.application_channel,
      APPLICATION_CHANNELS,
    ),
    "process.wants_onshore_conversion": booleanFact(
      facts.wants_onshore_conversion,
    ),
    "commercial.service_fee_budget_idr": unknownFact(NOT_ASKED),
    "commercial.wants_quote": unknownFact(NOT_ASKED),
  };

  return {
    schema_version: SCHEMA_VERSION,
    assessment_id: options.assessmentId,
    collected_at: options.collectedAt.toISOString(),
    facts: data,
    disclosed_review_flags: mapDisclosedReviewFlags(facts),
  };
}

/** Stable, PII-bearing only in memory. Hash it before storage or telemetry. */
export function stableFactsKey(data: ApplicantFactsDataWire): string {
  return JSON.stringify(
    Object.keys(data)
      .sort()
      .map((key) => [key, data[key as keyof ApplicantFactsDataWire]]),
  );
}

export function stableEvaluationInputKey(request: ApplicantFactsWire): string {
  return JSON.stringify({
    schemaVersion: request.schema_version,
    facts: stableFactsKey(request.facts),
    disclosedReviewFlags: [...request.disclosed_review_flags].sort(),
  });
}
