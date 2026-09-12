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

/**
 * Every tile now has a purpose. Typed `Partial` deliberately, even though
 * it is total over `CategoryKey`: `facts.category` is a raw browser string
 * cast to `CategoryKey`, so the lookup below CAN miss at runtime and
 * `mapPurposes`'s `undefined` branch must stay reachable to the compiler.
 * `fact-mapper.test.ts` pins the totality instead of the type doing it.
 *
 * `second_home` emits `SECOND_HOME` ALONE and never alongside `RETIREMENT`
 * (owner ruling 3, 2026-09-06): the pack's
 * `hit_policy.eligibility = COVER_ALL_DECLARED_PURPOSES` drops E33 the
 * moment a second purpose is declared, so a joined purpose would be a
 * silent no-path. One tile, one purpose is what makes that safe here.
 *
 * `diaspora` maps to `FAMILY` (owner ruling 4, 2026-09-06). It previously
 * mapped to nothing at all, so `mapPurposes` returned
 * `UNKNOWN(NOT_APPLICABLE)` and every diaspora interview dead-ended on
 * `intent.purposes` — a fact the interview HAD collected. The products a
 * diaspora applicant actually reaches (E31C/E31F) are family-reunification
 * products, and `flow.ts` now serves the family question set on this tile.
 */
export const CATEGORY_TO_PURPOSE: Partial<Record<CategoryKey, Purpose>> = {
  tourism: "TOURISM",
  business: "BUSINESS_MEETINGS",
  work: "EMPLOYMENT",
  invest: "INVESTMENT",
  remote: "REMOTE_WORK",
  family: "FAMILY",
  retirement: "RETIREMENT",
  second_home: "SECOND_HOME",
  study: "STUDY",
  diaspora: "FAMILY",
  other: "OTHER",
};

/**
 * `request_category` is an OPTIONAL query parameter whose vocabulary is
 * owned by the backend operation, not by this file. `second_home` has no
 * member there yet, so the tile deliberately sends NO `request_category`
 * rather than borrowing `retirement`'s — a wrong label is worse than an
 * absent optional one, and the decision itself is driven by
 * `intent.purposes`, never by this parameter. Hence `Partial`.
 */
const CATEGORY_TO_REQUEST_CATEGORY: Readonly<
  Partial<Record<CategoryKey, VisaOracleRequestCategory>>
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
  // D3-1 (owner ruling SHWEB-20260911, PR-D3): an `invest` applicant whose
  // vehicle is a property purchase or a bank deposit is a Second Home
  // applicant, not an investor — `getCategoryQuestionIds` already serves the
  // Second Home question set for these two vehicles. SECOND_HOME ALONE,
  // never joined with INVESTMENT: `hit_policy.eligibility =
  // COVER_ALL_DECLARED_PURPOSES` drops E33 the moment a second purpose is
  // declared (owner ruling 3, 2026-09-06 — same reasoning as the
  // `second_home` tile's own entry above).
  if (
    category === "invest" &&
    (facts.investment_vehicle === "property" ||
      facts.investment_vehicle === "bank_deposit")
  ) {
    return known(["SECOND_HOME"]);
  }
  // D3-2 (owner ruling SHWEB-20260911, PR-D3): declared paid activity is
  // employment, not a generic OTHER purpose — `el.c1/c2/c6` all exclude paid
  // activity (UU 6/2011 Pasal 122) and only `el.e23-employment-support`
  // covers it. `no` and `unsure` fall through to OTHER unchanged: `no` is
  // the honest negative (C6 stays reachable) and `unsure` is a disclosed
  // uncertainty the NOT_CERTAIN flag already holds on.
  if (category === "other" && facts.other_paid_activity === "yes") {
    return known(["EMPLOYMENT"]);
  }
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

/**
 * ACTIVITY_BOUNDARY is a HOLD, not a label: any disclosed flag makes the
 * backend rewrite the decision to HUMAN_REVIEW_REQUIRED with `candidates=()`
 * (`evaluate_path.py::_apply_disclosed_review_flags`), and `models.py` forbids
 * a non-empty candidate list in any other state — so raising it DELETES a
 * product the signed pack had already proven. It may be raised only for an
 * answer the signed vocabulary cannot decide, never for the mere fact that a
 * question was answered.
 *
 * Keyed by question id (`tree.ts`), listing per question the answers the pack
 * decides on its own. Every OTHER answer holds, including an option added to
 * `tree.ts` later without revisiting this table — fail-closed on purpose. A
 * question absent from the table never raises this flag at all. Rationale per
 * row, and the rows deliberately NOT here (`work_role`, engine-inert per the
 * owner ruling of 2026-09-06 decision 6; `tourism_duration`/`remote_income`,
 * question ids that exist nowhere in `tree.ts`): research/visa/
 * 2026-09-06-visa-oracle-decisiveness-investigation.md §4 PR-4 and §6 R3.
 * `diaspora_connection`/`diaspora_documents` decided 2026-09-07: measured in
 * production with `disclosed_review_flags=[]`, all 15 corpus diaspora walks
 * resolved to `SUPPORTED_CANDIDATES` with real candidates (C1, plus
 * E31A/E31C/E31F/E31G per the declared link) — the pack already decides
 * `former_wni`/`descendant`/`family` and both document answers on its own, so
 * holding on their mere presence was discarding a proven answer, the same
 * defect this table exists to cure for the other questions. `dual` (Indonesian
 * dual citizenship) and `other` stay undecidable on purpose: `dual` is the
 * legally most sensitive diaspora status the owner named as a legitimate
 * human-review case, and no corpus walk exercises it — releasing it would
 * open a branch never tested on the point that matters most; `other` is
 * fail-closed by construction, it names no specific status the pack can
 * reason about.
 * Guilt, innocence and the per-walk census: `activity-boundary.test.ts`.
 */
export const ACTIVITY_BOUNDARY_DECIDABLE_ANSWERS = {
  business_activity: ["meetings", "negotiation", "conference"],
  // `property`/`bank_deposit` added (PR-D3, D3-1): `mapPurposes` now routes
  // both to SECOND_HOME alone, and `el.e33.property-basis`/`el.e33.
  // deposit-basis` decide E33 off the Second Home facts the interview
  // already collects for these two vehicles — holding them discarded a
  // deterministic answer the same way `family_sponsor` did above.
  investment_vehicle: ["pt_pma", "property", "bank_deposit"],
  // `family_sponsor` added 2026-09-12 (NARROW-2, owner ruling SHWEB-20260911:
  // hold is the exception, a deterministic pack answer is not). `el.e33f.
  // retirement` (rulepack-prod-020) decides SUPPORT for E33F off
  // `secondhome.passive_monthly_income_usd >= 3000` and `family.
  // sponsor_confirmed == true` alone — it never reads `retirement_basis` at
  // all — so this table was UNDER-inclusive: an applicant who answers
  // `family_sponsor` and clears both of those facts already has a signed,
  // deterministic SUPPORTED E33F, and raising ACTIVITY_BOUNDARY here only
  // deletes it. `property` and `undecided` stay undecidable: no pack rule
  // grants either an E33F path, so holding them loses nothing proven.
  retirement_basis: ["bank_deposit", "passive_income", "family_sponsor"],
  diaspora_connection: ["former_wni", "descendant", "family"],
  diaspora_documents: ["yes", "no"],
  // D3-B (PR-D3, owner ruling SHWEB-20260911) investigated pack-outward,
  // NARROW-2 style, whether any of the 8 options (transit/medical/
  // volunteer/religious/arts_sport/journalism/crew/other) is decided by a
  // seq-20 rule. RESULT: NONE is, and the list stays empty — not a
  // judgement call, a structural fact. `other_purpose`'s own
  // `decisionMapping` is `HUMAN_CONTEXT` (tree.ts) — it maps to NO
  // FactPath at all, and `mapOracleFactsToApplicantFacts` never reads
  // `facts.other_purpose` anywhere — so no rule in the signed pack can
  // ever see which of the 8 values was chosen; the wire request is
  // byte-identical regardless. Verified against rulepack-prod-020.
  // signed.json: exactly 5 rules cover the OTHER purpose
  // (`el.c6.social`, the one ELIGIBILITY rule that can grant a product,
  // plus 4 advisory/BRIDGING-only rules), and `el.c6.social`'s
  // `required_facts` is `family.sponsor_confirmed` /
  // `intent.purposes` / `intent.stay_days` alone — nothing derived from
  // this question. Releasing any value here would therefore not be
  // "found decidable", it would be inventing a distinction the engine
  // cannot draw, on a purpose where the wrong side hands a visitor a
  // visit visa for a legally excluded activity. C6's actual release
  // (D3-2) rests solely on the `other_paid_activity = no` branch, which
  // this table already lists below.
  other_purpose: [],
  // `yes`/`no` added (PR-D3, D3-2): `mapPurposes` now routes `yes` to
  // EMPLOYMENT (only `el.e23-employment-support` covers it) and leaves `no`
  // on OTHER (`el.c6.social` stays reachable) — both are decisive on the
  // pack's own terms, so holding either discarded a deterministic answer.
  // `unsure` is not listed: it stays undecidable, and the generic
  // `NOT_CERTAIN` flag (a disclosed uncertainty, not a derived one) already
  // holds on it.
  other_paid_activity: ["yes", "no"],
} as const satisfies Readonly<Record<string, readonly string[]>>;

/** Question ids the ACTIVITY_BOUNDARY table classifies. */
export type ActivityBoundaryQuestionId =
  keyof typeof ACTIVITY_BOUNDARY_DECIDABLE_ANSWERS;

/** True when this interview answered a classified question with a value the
 * signed pack cannot decide. Unanswered questions never hold. */
function hasUndecidableActivityAnswer(facts: OracleFacts): boolean {
  for (const [questionId, decidable] of Object.entries(
    ACTIVITY_BOUNDARY_DECIDABLE_ANSWERS,
  ) as [ActivityBoundaryQuestionId, readonly string[]][]) {
    const answer = facts[questionId];
    if (answer === undefined) continue;
    if (!decidable.includes(answer)) return true;
  }
  return false;
}

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
  // Human-context answers the signed vocabulary cannot decide may only lower
  // the result to review. An answer it CAN decide must not: this flag is a
  // hold that deletes candidates, never a label (see the table above).
  if (hasUndecidableActivityAnswer(facts)) {
    flags.add("ACTIVITY_BOUNDARY");
  }
  // NARROW-1 (owner ruling SHWEB-20260911, 2026-09-12 20:35 WITA): the flag
  // used to fire on the mere PRESENCE of `family_sponsor_status_code` /
  // `family_sponsor_permit_basis` — i.e. because the sponsor is foreign, not
  // because any candidate the pack had proven actually needs that fact. That
  // is the OVER-match shape (guard #3): `el.c1.tourism-family` (rulepack-
  // prod-020) reads no sponsor fact at all, so a foreign sponsor deleted a
  // verdict it cannot affect. `family_sponsor_permit_basis` is dropped from
  // the trigger entirely: no rule in seq-20 reads `family.sponsor_permit_
  // basis` (it is HUMAN_CONTEXT only, never wired to a FACT — see
  // `mapFamilySponsorPermitBasis`, below), so it could never have been the
  // fact a held candidate needed.
  //
  // Hold now only when:
  //  (i) the applicant said `unsure` — a real disclosed uncertainty, not a
  //      derived one; or
  //  (ii) the relation answered has a pack product that genuinely depends on
  //       the sponsor being resolved. `_apply_disclosed_review_flags`
  //       (evaluate_path.py) is monotone over the WHOLE decision, so a
  //       per-candidate hold is not available here — this is the frontend,
  //       interview-time, RELATION-level proxy the constraint allows.
  //
  // Today exactly one relation qualifies for (ii): STEPCHILD.
  // `el.e31d-stepchild-support` requires `family.sponsor_confirmed` with
  // `on_unknown: NEEDS_INPUT` — the only family-relation product whose
  // ELIGIBILITY is gated (not merely annotated) by a sponsor fact. SPOUSE /
  // PARENT / CHILD / SIBLING each have a "*-sponsor-itas-itap" rule reading
  // `family.sponsor_status_code`, but every one of them is `on_unknown:
  // NO_EFFECT` — an unresolved sponsor status changes nothing they decide,
  // so holding on their behalf would delete a proven verdict for no reason,
  // the exact defect this narrowing exists to cure. Pinned against pack
  // drift by "AMBIGUOUS_SPONSOR relation proxy tracks the signed pack" in
  // fact-mapper.test.ts, which reads every production pack on disk and
  // fails if that set of relations ever changes.
  const RELATIONS_WITH_SPONSOR_DEPENDENT_PRODUCT: ReadonlySet<string> = new Set(
    ["STEPCHILD"],
  );
  const sponsorRelationUnresolved =
    facts.family_sponsor_status_code !== undefined &&
    facts.family_relation !== undefined &&
    RELATIONS_WITH_SPONSOR_DEPENDENT_PRODUCT.has(facts.family_relation);
  if (
    facts.family_sponsor_status_code === "unsure" ||
    facts.family_sponsor_confirmed === "unsure" ||
    sponsorRelationUnresolved
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
    "immigration.renewal_paid": booleanFact(facts.renewal_paid),
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
