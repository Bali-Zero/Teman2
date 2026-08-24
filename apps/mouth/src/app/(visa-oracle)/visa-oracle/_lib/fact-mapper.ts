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
// V1/E28+E33 (2026-08-24/25, mandate docs/plans/2026-08-24-visa-oracle-live/
// MANDATE.md): the seven product codes any V1 UI question on this repo lets
// an applicant self-name (E28B/C/D/F, E33A/B/C — E28A never gates on this
// fact at all, it's the ordinary no-code path). NOT the complete set of
// values any rule in the pack checks against `intent.requested_product_code`:
// 13 rules total list this fact among their `required_facts` (verified live
// against rulepack-prod-013.source.json, team-lead PASS-grade review
// 2026-08-25) — the 7 named above (review.e28{b,c,d,f}.*-manual +
// review.e33{a,b,c}.*) plus review.e23{u,v}.requested-product (2, in removal
// under PR #4797) and el.bridging.* (4). Deliberately NOT closed-enum-typed
// on the wire (`intent.requested_product_code` is a free `KnownString`, 1-64
// chars) — this list only decides which of the four UI answers merged below
// maps to KNOWN vs UNKNOWN(NOT_PROVIDED); the "STANDARD" option (no specific
// code) and any other stray value fall through to NOT_PROVIDED via
// `enumFact`.
//
// E33A/E33B/E33C were added 2026-08-25 (team-lead ruling, correcting an
// earlier version of this comment that called them "not groundable" and
// excluded them entirely). That concern conflated two different axes:
// AUTOMATABILITY (nobody can auto-approve E33A/B/C on a self-declared
// answer — true, and still true: all three have zero SUPPORT/ELIGIBILITY
// rules, only a REQUIRE_REVIEW rule each) is NOT the same axis as
// REACHABILITY (can the question even be asked at all). A T3 product with
// zero SUPPORT rules still needs to be reachable so it routes to a human —
// "invisible" is a silent BLOCKED_UNKNOWN outcome, exactly the E28B/C/D/F
// failure this fact-mapper change originally fixed; HUMAN_REVIEW toward a
// person IS the T3 promise this mandate makes, even with an incomplete
// doctrine card.
//
// Unlike E28B/C/D/F (asked unconditionally in the "invest" branch), E33A/B/C
// are gated: `employment_product_code_govt` / `employment_product_code_none`
// / `investment_product_code_govt` (tree.ts) are inserted into the interview
// ONLY when `sponsor_category` matches the exact value(s) each product's own
// independent HARD_FILTER requires — GOVERNMENT for E33A
// (`hf.e33a.sponsor-not-government`), GOVERNMENT-or-NONE for E33B/E33C
// (`hf.e33{b,c}.sponsor-not-government-or-none`) — see flow.ts's
// "work"/"invest" branches. This is deliberately NARROWER than gating on
// purpose/category alone (an alternative this lane proposed and team-lead
// rejected 2026-08-25): EMPLOYMENT/INVESTMENT purpose is a much wider slice
// of traffic than the sponsor types that can ever pass these HARD_FILTERs,
// and every extra applicant offered a choice they cannot pass is one more
// person who could name it.
//
// DOCTRINE GAP (ledger, `.claude/skills/modus/PENDING-ARMS.md`, opened
// 2026-08-25): no NB-2 claim anywhere in this repo states what "central
// government invitation" (E33A/E33C) or the expertise-qualification
// standard (E33B) actually requires — issuing ministry, document type,
// validity period. The human reviewer who receives a REVIEW-routed E33A/B/C
// case today has nothing written down to check it against. This is a real
// gap that this V1 reachability fix does NOT close — see the ledger entry
// for the missing-arming-step and proof-of-armed condition, not a footnote
// buried in this comment.
const REQUESTED_PRODUCT_CODES = [
  "E28B",
  "E28C",
  "E28D",
  "E28F",
  "E33A",
  "E33B",
  "E33C",
] as const;
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
//
// A THIRD case (added 2026-08-24, P0 offshore-reachability fix): an
// OFFSHORE applicant (`in_indonesia === "no"`) who answers
// `holds_stay_permit === "no"` is never asked `current_status_code` at all
// — `flow.ts::computeNextNode`'s offshore branch converges straight to
// `overstay_days` instead, specifically to avoid paying a redundant
// question for a fact `holds_stay_permit`'s own answer already fully
// determines (measured funnel-cost review, PR #4727: asking it anyway
// would cost every offshore applicant of every product 3 questions to
// serve one product's rule). When neither raw field is populated but
// `holds_stay_permit` is explicitly "no", emit the synthesized
// `NO_STAY_PERMIT` sentinel directly (see `fact_registry.py`'s
// `_VISIT_CLASS_STATUS_CODES` docstring for why this is honest, not a
// guess) rather than falling through to NOT_ASKED. This branch can never
// fire for onshore: onshore always asks the real `current_status_code`
// question on "no" (unchanged), so that raw field is already populated by
// the time this mapper runs and the second branch above wins first.
function mapCurrentStatusCode(facts: OracleFacts): FactValue<string> {
  if (facts.stay_permit_code !== undefined) {
    return enumFact(facts.stay_permit_code, STAY_PERMIT_CODES);
  }
  if (facts.current_status_code !== undefined) {
    return enumFact(facts.current_status_code, CURRENT_STATUS_CODES);
  }
  if (facts.holds_stay_permit === "no") {
    return known("NO_STAY_PERMIT");
  }
  return unknownFact(NOT_ASKED);
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
    // V1 (2026-08-25, team-lead ruling — "the question follows the rule, not
    // precedes it"): `immigration.last_entry_date` has NO question in
    // tree.ts/flow.ts, deliberately, and stays `unknownFact(NOT_ASKED)`
    // unconditionally. Verified this turn against the REAL active pack
    // (`rulepack-prod-013.source.json`): ZERO rules reference this fact —
    // not one HARD_FILTER/ELIGIBILITY/HUMAN_REVIEW condition needs it today.
    // This is the EXACT INVERSE of the E28/E33 disease this same file's
    // `intent.requested_product_code` comment (below) documents fixing:
    // there, a rule existed and starved for a fact nothing could ever
    // supply; here, asking the question would supply a fact no rule
    // consumes. Both directions are defects, but this direction is the
    // worse one to get wrong going forward, because the data collected is
    // actually RETAINED (Legge 2 / UU PDP minimization: a fact that decides
    // nothing is a fact collected for no purpose, not merely a wasted
    // question) — see `SWITCHBOARD-2-RETENTION.md` (feature/visa-oracle)
    // for a live example of exactly this mistake already made once on the
    // legacy funnel. The rule: do NOT add a question for any of these four
    // facts (this one, `intent.desired_entry_date`,
    // `commercial.service_fee_budget_idr`, `commercial.wants_quote` below)
    // until a real rule in the signed pack actually needs it — at which
    // point the question ships in the SAME PR as the rule, never ahead of
    // it. `commercial.*`'s case is additionally a compiler INVARIANT, not
    // just an absent rule today — see that pair's own comment.
    "immigration.last_entry_date": unknownFact(NOT_ASKED),
    "immigration.overstay_days": integerFact(facts.overstay_days, 0, 36_500),
    "immigration.violation_history": mapViolationHistory(facts),
    // F4, 2026-08-24: the `renewal_paid` question now ships (tree.ts,
    // gated in flow.ts's `computeNextNode`/`shouldAskRenewalPaid` on an
    // already-collected `stay_permit_code` + `permit_expiry`). Same
    // `booleanFact` treatment as every other yes/no question — "never
    // asked" (the question was gated out) and "answered unsure" both
    // resolve to an explicit UNKNOWN (NOT_ASKED / UNVERIFIED respectively),
    // never a guessed `false`.
    //
    // V1 (2026-08-25, team-lead ledger pass): this fact IS consumed today —
    // `FactRegistry._derive_has_active_stay_permit` (fact_registry.py)
    // reads it as an early short-circuit — but that DERIVED fact
    // (`derived.has_active_stay_permit`) is itself referenced by ZERO
    // rules in the currently-signed active pack (verified live against
    // `rulepack-prod-013.source.json`; also confirmed in
    // `reachability_report.py`'s own "referenced by zero rules" list). The
    // consuming rule is the D12 ruling (owner ruling 2026-08-23: an
    // applicant WITH an active KITAS is excluded from D12) — landed in the
    // derivation layer, not yet in a signed pack. This question is
    // therefore correctly "asked in advance of its rule," NOT the
    // question-precedes-rule anti-pattern this file's `immigration.last_
    // entry_date` comment (above) warns against — it is a KNOWN, NAMED,
    // in-flight consumer, not an absent one. If D12's rule never lands in a
    // future signed pack, this becomes exactly that anti-pattern
    // retroactively; whoever next re-runs this sweep should re-check.
    "immigration.renewal_paid": booleanFact(facts.renewal_paid),
    "intent.purposes": mapPurposes(facts),
    "intent.stay_days": mapStayDays(facts),
    "intent.desired_entry_date": unknownFact(NOT_ASKED),
    "intent.entry_pattern": enumFact(facts.entry_pattern, ENTRY_PATTERNS),
    // V1/E28 (2026-08-24): the `investment_product_code` question now ships
    // (tree.ts, asked for every "invest" category applicant right after
    // `investment_vehicle` — flow.ts's `getCategoryQuestionIds`). Before
    // this, this field was unconditionally `unknownFact(NOT_ASKED)` and no
    // applicant could ever name E28B/E28C/E28D/E28F — the only 4 products
    // whose sole rule keys on this exact fact
    // (`review.e28{b,c,d,f}.*-manual`, each `REQUIRE_REVIEW` /
    // `on_unknown: NEEDS_INPUT`) — making all four invisible in production
    // (`NEEDS_INPUT` UNKNOWN routes to `BLOCKED_UNKNOWN`, which always loses
    // to a plausible investor's ordinary `SUPPORTED_CANDIDATES` via E28A).
    // Same `enumFact` treatment as every other closed-set choice question:
    // a named code -> KNOWN; "no specific code"/anything else -> UNKNOWN
    // NOT_PROVIDED (an ordinary E28A evaluation is unaffected either way);
    // never asked (question gated out, e.g. any non-"invest" category) ->
    // UNKNOWN NOT_ASKED, via `enumFact`'s own `value === undefined` branch.
    //
    // TEAM-LEAD VERIFICATION (2026-08-25, PASS grade on V1 unit 1): making
    // this fact askable is NOT a local change scoped to E28B/C/D/F — 13
    // rules in the signed pack list `intent.requested_product_code` among
    // their `required_facts` (extracted live from rulepack-prod-013, not
    // from memory): `review.e28{b,c,d,f}.*-manual` (these 4, REQUIRE_REVIEW
    // / NEEDS_INPUT) · `review.e33{a,b,c}.*` (3, REQUIRE_REVIEW /
    // NEEDS_INPUT) · `review.e23{u,v}.requested-product` (2, in removal
    // under PR #4797) · `el.bridging.{t3-window,overstay-shield,
    // source-status}` (3, SUPPORT / NO_EFFECT) ·
    // `el.bridging.destination-stated` (1, SUPPORT / NEEDS_INPUT). All 9
    // siblings were checked, not assumed innocent.
    //
    // `el.bridging.destination-stated`'s `when` is `intent.purposes
    // intersects [OTHER] AND intent.requested_product_code != "BRIDGING"` —
    // a NEQ against one sentinel value is satisfied by almost any other
    // value, the exact shape of #4797's defect mirrored (a rule that
    // doesn't actually test what it claims to). This fact reaching KNOWN
    // does NOT arm it, for a structural reason, not a coincidence:
    // `mapPurposes` (above) returns `known([purpose])` — always exactly ONE
    // purpose, a pure function of `facts.category` via `CATEGORY_TO_PURPOSE`
    // (flow.ts), a TOTAL, DISJOINT mapping (`invest` -> `INVESTMENT`,
    // `work` -> `EMPLOYMENT`, `other` -> `OTHER`, never any two at once).
    // All four UI questions merged below (`investment_product_code`,
    // `investment_product_code_govt`, `employment_product_code_govt`,
    // `employment_product_code_none`) are only ever inserted into the
    // question sequence when `category` is `"invest"` or `"work"`
    // (flow.ts's `getCategoryQuestionIds`, asserted by flow.test.ts for
    // every non-invest/non-work category). So this fact reaching KNOWN
    // implies category is "invest" or "work" implies `intent.purposes` is
    // `[INVESTMENT]` or `[EMPLOYMENT]` — never `[OTHER]`.
    // `el.bridging.destination-stated`'s own `purposes intersects [OTHER]`
    // half of its `when` can never be satisfied on any path where this
    // fact is KNOWN: the rule stays unreachable BY CONSTRUCTION, not by
    // luck of what values got asked. See the "implies NOT OTHER purpose"
    // innocence test in fact-mapper.test.ts — it goes red the day someone
    // asks any of these four questions outside the "invest"/"work"
    // branches.
    //
    // V1/E33 innocence test (team-lead ruling 2026-08-25): "an applicant
    // without a GOVERNMENT sponsor never produces a KNOWN
    // requested_product_code for E33[A|B|C]" — `employment_product_code_govt`
    // is inserted ONLY when `sponsor_category === "GOVERNMENT"`;
    // `employment_product_code_none`/`investment_product_code_govt` ONLY
    // when `sponsor_category` is `"GOVERNMENT"` or `"NONE"`. Every OTHER
    // `sponsor_category` value (`INDIVIDUAL`/`EMPLOYER`/`EDUCATION`/
    // `INVESTMENT`) never inserts any of the three E33-bearing questions,
    // so none of these three UI facts can ever be set for those applicants
    // — see the corresponding test in fact-mapper.test.ts.
    "intent.requested_product_code": enumFact(
      facts.investment_product_code ??
        facts.investment_product_code_govt ??
        facts.employment_product_code_govt ??
        facts.employment_product_code_none,
      REQUESTED_PRODUCT_CODES,
    ),
    // V1 (2026-08-25, team-lead ruling): the `remote_employer_country`
    // question was REMOVED — see `immigration.last_entry_date`'s comment
    // above for the general principle (zero rules in the signed pack
    // consume this fact, and no planned rule names it; the cure is
    // removing the question, not documenting it as unused).
    "work.employer_country_code": unknownFact(NOT_ASKED),
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
    // V1 (2026-08-25, team-lead ledger pass): both facts below are
    // referenced by ZERO rules in the currently-signed active pack
    // (verified live against `rulepack-prod-013.source.json`). Named,
    // in-flight consumer, not an absent one: STEPCHILD support shipped
    // 2026-08-23 (owner ruling, `E31D vocabulary extension` — see tree.ts's
    // "Stepchild route" comment above `family_stepchild_marriage_
    // certificate_confirmed`) specifically to feed E31D's rule authoring,
    // which had not yet landed in a signed pack as of this note. If E31D's
    // rule never lands in a future signed pack, this becomes the same
    // question-precedes-rule anti-pattern `immigration.last_entry_date`'s
    // comment (above) warns against; whoever next re-runs this sweep
    // should re-check.
    "family.stepchild_marriage_certificate_confirmed": booleanFact(
      facts.family_stepchild_marriage_certificate_confirmed,
    ),
    "family.stepchild_birth_certificate_confirmed": booleanFact(
      facts.family_stepchild_birth_certificate_confirmed,
    ),
    // V1 (2026-08-25, team-lead ledger pass): zero rules read this fact
    // today, and none ever can — `mapFamilySponsorPermitBasis` (above)
    // NEVER returns KNOWN, by design (self-declared 13-category legal
    // taxonomy, same trust problem as its sibling `mapFamilySponsorStatus`
    // — see that function's own docstring). Not a gap to fill or a
    // question to remove; already the correct, ruled disposition.
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
    // V1 (2026-08-25, team-lead ledger pass): this fact is read by ZERO
    // rules in the currently-signed active pack — but that is NOT the
    // "question precedes the rule" gap `immigration.last_entry_date`'s
    // comment above warns about. It is read by NO rule BY DESIGN: it is
    // the client-side MIRROR check against the rule
    // `hf.d12-onshore-conversion-excluded` (`safety_critical: true`),
    // which reads ONLY
    // `process.wants_onshore_conversion` — `flow.ts`'s
    // `channelConflictsWithOnshoreIntent` (flow.ts:416) detects a
    // self-contradictory `wants_onshore_conversion`/`application_channel`
    // pair and truncates the interview history at that frontier instead of
    // ever sending the contradictory pair to the engine (call sites
    // flow.ts:307 and flow.ts:785). This exists because of a real past bug
    // (see flow.ts's own comment above `ONSHORE_APPLICATION_CHANNELS`):
    // `false` on `wants_onshore_conversion` alone could disarm that
    // HARD_FILTER while `ONSHORE_CONVERSION` sat unread, recommending D12
    // to an applicant actually converting onshore. Do NOT remove this
    // question on a "zero rule consumers" reading — that reading is
    // correct but the wrong lens for THIS fact; removing it reopens the bug
    // `channelConflictsWithOnshoreIntent` closed.
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
