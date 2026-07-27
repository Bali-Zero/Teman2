/**
 * Visa Oracle v2 — SHADOW fact mapper.
 *
 * Pure, no I/O: turns the mock interview's `OracleFacts` (a handful of
 * UI-only option keys — `tree.ts`) into the wire-format `ApplicantFacts`
 * payload the LIVE `visa_engine` expects
 * (`apps/backend-rag/backend/services/visa_engine/models.py::ApplicantFacts`
 * / `ApplicantFactsData`, `extra="forbid"` — every one of the 40 keys must
 * be present, and no extra key is tolerated).
 *
 * This module NEVER decides what the user sees — it exists so
 * `shadow-client.ts` can build the body of a fire-and-forget SHADOW POST.
 * An all-UNKNOWN payload is contract-valid (the interview only ever
 * answers ~8 of the 40 paths on any single path through the tree; the
 * other ~32 are honestly UNKNOWN, never invented).
 *
 * Judgment calls made here (see the report this shipped with for the full
 * rationale — repeated as comments at each call site below too):
 *  - `in_indonesia === "unsure"` resolves to KNOWN(true), mirroring the
 *    ALREADY-established conservative policy `tree.ts`'s own
 *    `getLane()`/`mock-engine.ts`'s `resolvedFacts()` apply to this exact
 *    field. No other field gets this treatment — only `in_indonesia` was
 *    named for it in the brief.
 *  - `category` tiles map onto `VisaPurpose` members 1:1 where an
 *    unambiguous match exists; "diaspora" does not (no VisaPurpose member
 *    captures it without conflating it with the generic "other" tile) and
 *    is left UNKNOWN/NOT_APPLICABLE rather than forced onto a poor fit.
 *  - `tourism_duration`'s three buckets ("Up to 30 days" / "31–60 days" /
 *    "60+ days" — i18n.ts) collapse to a single canonical day count: the
 *    upper bound of each bucket (30 / 60), and 90 for the open-ended
 *    "extended" bucket (an arbitrary interior representative — that path
 *    is already flagged TEMPORARILY_UNAVAILABLE by `mock-engine.ts`'s own
 *    "honest limitation of the prototype" branch, so no visible UI ever
 *    depends on this number).
 *  - `review_gate`'s `overstay_or_blacklist` checklist item maps to a
 *    SINGLE `ViolationType` member, `OVERSTAY` (not `BLACKLIST` — a
 *    judgment call; see `mapViolationHistory` below).
 *  - `remote_income` has no `FactPath` at all (confirmed against
 *    `enums.py`'s `FactPath` — there is no income-threshold fact in the
 *    40) and is intentionally never referenced here.
 */
import { parseIsoDateUtc, type CategoryKey, type OracleFacts } from "./tree";

export const SCHEMA_VERSION = "1.0.0" as const;

export type UnknownReasonWire =
  | "NOT_ASKED"
  | "NOT_PROVIDED"
  | "UNVERIFIED"
  | "CONFLICTING"
  | "NOT_APPLICABLE";

/** Mirrors `models.py`'s `UnknownFact`/`Known*` discriminated union
 * exactly: `{status:"KNOWN", value}` or `{status:"UNKNOWN", reason}` —
 * never a third shape, never both keys at once. */
export type FactValue<T> =
  | { status: "KNOWN"; value: T }
  | { status: "UNKNOWN"; reason: UnknownReasonWire };

function known<T>(value: T): FactValue<T> {
  return { status: "KNOWN", value };
}

/** No generic parameter needed: the UNKNOWN branch carries no `value`, so
 * this return type structurally satisfies `FactValue<T>` for every `T`. */
function unknownFact(reason: UnknownReasonWire): {
  status: "UNKNOWN";
  reason: UnknownReasonWire;
} {
  return { status: "UNKNOWN", reason };
}

const NOT_ASKED: UnknownReasonWire = "NOT_ASKED";
const UNVERIFIED: UnknownReasonWire = "UNVERIFIED";
const NOT_PROVIDED: UnknownReasonWire = "NOT_PROVIDED";
const NOT_APPLICABLE: UnknownReasonWire = "NOT_APPLICABLE";

/**
 * The 40 `ApplicantFactsData` wire keys (dotted `FactPath` aliases, exact
 * `Field(alias=...)` strings from `models.py`), each typed to the JSON
 * shape its `*Fact` union actually carries. `populate_by_name` is NOT set
 * on the Python side, so these dotted strings — never a Python attribute
 * name — are the only accepted keys.
 */
export interface ApplicantFactsDataWire {
  "person.birth_date": FactValue<string>;
  "person.nationalities": FactValue<string[]>;
  "person.marital_status": FactValue<string>;
  "immigration.currently_in_indonesia": FactValue<boolean>;
  "immigration.current_status_code": FactValue<string>;
  "immigration.current_status_expiry": FactValue<string>;
  "immigration.last_entry_date": FactValue<string>;
  "immigration.overstay_days": FactValue<number>;
  "immigration.violation_history": FactValue<string[]>;
  "intent.purposes": FactValue<string[]>;
  "intent.stay_days": FactValue<number>;
  "intent.desired_entry_date": FactValue<string>;
  "intent.entry_pattern": FactValue<string>;
  "intent.requested_product_code": FactValue<string>;
  "work.employer_country_code": FactValue<string>;
  "work.employer_is_indonesian_entity": FactValue<boolean>;
  "work.serves_indonesian_clients": FactValue<boolean>;
  "work.indonesia_source_compensation": FactValue<boolean>;
  "work.indonesian_work_sponsor_confirmed": FactValue<boolean>;
  "investment.pt_pma_committed": FactValue<boolean>;
  "investment.investment_capital_idr": FactValue<number>;
  "investment.paid_up_capital_idr": FactValue<number>;
  "investment.proposed_role": FactValue<string>;
  "family.relation_to_sponsor": FactValue<string>;
  "family.sponsor_nationalities": FactValue<string[]>;
  "family.sponsor_status_code": FactValue<string>;
  "family.marriage_registered": FactValue<boolean>;
  "family.sponsor_confirmed": FactValue<boolean>;
  "study.level": FactValue<string>;
  "study.admission_confirmed": FactValue<boolean>;
  "study.sponsor_confirmed": FactValue<boolean>;
  "secondhome.bank_deposit_usd": FactValue<number>;
  "secondhome.bank_deposit_at_state_bank": FactValue<boolean>;
  "secondhome.bank_deposit_in_own_name": FactValue<boolean>;
  "secondhome.qualifying_property_value_usd": FactValue<number>;
  "secondhome.passive_monthly_income_usd": FactValue<number>;
  "process.application_channel": FactValue<string>;
  "process.wants_onshore_conversion": FactValue<boolean>;
  "commercial.service_fee_budget_idr": FactValue<number>;
  "commercial.wants_quote": FactValue<boolean>;
}

export interface ApplicantFactsWire {
  schema_version: typeof SCHEMA_VERSION;
  assessment_id: string;
  /** UTC instant, rendered with a trailing "Z" — never "+00:00"
   * (`models.py`'s `_validate_utc` requires timezone-aware + zero
   * offset; `Date.prototype.toISOString()` already always ends in "Z"). */
  collected_at: string;
  facts: ApplicantFactsDataWire;
}

// ---------------------------------------------------------------------------
// Per-question mappers
// ---------------------------------------------------------------------------

/** `in_indonesia` -> `immigration.currently_in_indonesia`. "unsure" resolves
 * to KNOWN(true) — the SAME conservative policy `tree.ts`'s `getLane()`
 * (via `mock-engine.ts`'s `resolvedFacts()`) already applies to this exact
 * field: `in_indonesia`'s own `notSure.conservativeValue` is `"yes"`. This
 * is the ONE field the task brief explicitly carves this treatment out
 * for — no other field in this mapper resolves "unsure" to a KNOWN value. */
export function mapCurrentlyInIndonesia(
  facts: OracleFacts,
): FactValue<boolean> {
  const v = facts.in_indonesia;
  if (v === "yes") return known(true);
  if (v === "no") return known(false);
  if (v === "unsure") return known(true);
  return unknownFact(NOT_ASKED);
}

/** Generic ISO-date mapper, shared by every `DateFact` field this route
 * actually collects (today: only `permit_expiry`). "unsure" (the
 * `NotSure` sentinel — `permit_expiry`'s own `notSure.mode` is
 * `"human-review"`) maps to UNVERIFIED, never a guessed date. A
 * present-but-not-calendar-valid string (should never happen behind a
 * native `<input type="date">`, but this module never trusts the DOM)
 * maps to NOT_PROVIDED rather than risk sending the engine a value its
 * own `KnownDate` validator would reject. */
function mapDateFact(iso: string | undefined): FactValue<string> {
  if (iso === undefined) return unknownFact(NOT_ASKED);
  if (iso === "unsure") return unknownFact(UNVERIFIED);
  if (parseIsoDateUtc(iso) === null) return unknownFact(NOT_PROVIDED);
  return known(iso);
}

/** `permit_expiry` -> `immigration.current_status_expiry`. */
export function mapCurrentStatusExpiry(facts: OracleFacts): FactValue<string> {
  return mapDateFact(facts.permit_expiry);
}

/**
 * `category` tile -> `VisaPurpose` member (spec's closed enum,
 * `enums.py`). Only tiles with an unambiguous 1:1 semantic match are
 * included — "diaspora" is deliberately absent (see `mapPurposes` below).
 */
export const CATEGORY_TO_PURPOSE: Partial<Record<CategoryKey, string>> = {
  tourism: "TOURISM",
  business: "BUSINESS_MEETINGS",
  work: "EMPLOYMENT",
  invest: "INVESTMENT",
  remote: "REMOTE_WORK",
  family: "FAMILY",
  retirement: "RETIREMENT",
  study: "STUDY",
  other: "OTHER",
  // "diaspora": intentionally omitted — see mapPurposes().
};

/** `category` -> `intent.purposes`. A tile WAS answered (asked), but
 * "diaspora" has no clean `VisaPurpose` member — forcing it onto the
 * generic `OTHER` would conflate it with the "other" tile, a materially
 * different signal the interview deliberately offers as a DISTINCT
 * option. Judgment call: NOT_APPLICABLE (the answer exists, it just
 * doesn't translate to this vocabulary), never NOT_ASKED. */
export function mapPurposes(facts: OracleFacts): FactValue<string[]> {
  const category = facts.category as CategoryKey | undefined;
  if (category === undefined) return unknownFact(NOT_ASKED);
  const purpose = CATEGORY_TO_PURPOSE[category];
  if (purpose === undefined) return unknownFact(NOT_APPLICABLE);
  return known([purpose]);
}

/**
 * Bucket -> single canonical day count for `intent.stay_days` (a scalar
 * `NonNegativeIntegerFact` — the interview only ever collects a BUCKET,
 * never an exact count). Judgment call: the upper bound of each
 * i18n-labelled bucket (i18n.ts: "Up to 30 days" / "31–60 days" /
 * "60+ days"). "extended" has no upper bound in the copy; 90 is an
 * arbitrary interior representative — `mock-engine.ts`'s `evaluate()`
 * already routes "extended" to TEMPORARILY_UNAVAILABLE as an "honest
 * limitation of the prototype", so no visible UI path ever depends on
 * this number.
 */
export const TOURISM_DURATION_DAYS: Record<string, number> = {
  short: 30,
  medium: 60,
  extended: 90,
};

/** `tourism_duration` -> `intent.stay_days`. "unsure" maps to UNVERIFIED
 * per the general "user said not sure" discipline — NOT the conservative
 * "short"-bucket resolution `tree.ts` applies elsewhere for this same
 * field's UI behavior; the task brief only named `in_indonesia` for that
 * carve-out, so this mapper does not extend it here (documented judgment
 * call — see module docstring / shipped report). */
export function mapStayDays(facts: OracleFacts): FactValue<number> {
  const v = facts.tourism_duration;
  if (v === undefined) return unknownFact(NOT_ASKED);
  if (v === "unsure") return unknownFact(UNVERIFIED);
  const days = TOURISM_DURATION_DAYS[v];
  if (days === undefined) return unknownFact(NOT_ASKED);
  return known(days);
}

/** `work_payer` -> `work.employer_is_indonesian_entity`. */
export function mapEmployerIsIndonesianEntity(
  facts: OracleFacts,
): FactValue<boolean> {
  const v = facts.work_payer;
  if (v === "yes") return known(true);
  if (v === "no") return known(false);
  if (v === "unsure") return unknownFact(UNVERIFIED);
  return unknownFact(NOT_ASKED);
}

export interface RemoteClientsDerived {
  servesIndonesianClients: FactValue<boolean>;
  indonesiaSourceCompensation: FactValue<boolean>;
}

/** `remote_clients` -> `work.serves_indonesian_clients` +
 * `work.indonesia_source_compensation` (one UI question, two FactPaths).
 * "mixed" is treated the same as "indonesian" for BOTH facts (task
 * brief, verbatim) — the mock engine's own `adjustEligibility()` already
 * treats "mixed" as a real (not excluded) tolerance-risk lane, so KNOWN
 * true/true here is consistent with how the rest of this route already
 * reads that answer, not a new interpretation invented for SHADOW. */
export function mapRemoteClientsDerived(
  facts: OracleFacts,
): RemoteClientsDerived {
  const v = facts.remote_clients;
  if (v === "foreign") {
    return {
      servesIndonesianClients: known(false),
      indonesiaSourceCompensation: known(false),
    };
  }
  if (v === "indonesian" || v === "mixed") {
    return {
      servesIndonesianClients: known(true),
      indonesiaSourceCompensation: known(true),
    };
  }
  if (v === "unsure") {
    return {
      servesIndonesianClients: unknownFact(UNVERIFIED),
      indonesiaSourceCompensation: unknownFact(UNVERIFIED),
    };
  }
  return {
    servesIndonesianClients: unknownFact(NOT_ASKED),
    indonesiaSourceCompensation: unknownFact(NOT_ASKED),
  };
}

/** The single `ViolationType` member `review_gate`'s `overstay_or_blacklist`
 * checklist item maps to. Judgment call: `OVERSTAY`, not `BLACKLIST` —
 * the task brief asks for "the violation enum member" (singular), and
 * overstay is the base/verifiable status (also the first-named half of
 * the UI item's own key, and `ViolationType`'s first declared member);
 * blacklist is typically a downstream consequence OF a violation like
 * overstay, not an independent status this checklist item was designed
 * to distinguish from it. Documented here rather than silently picked. */
export const VIOLATION_MEMBER_FOR_OVERSTAY_OR_BLACKLIST = "OVERSTAY";

/** `review_gate` -> `immigration.violation_history`. ONLY the
 * `overstay_or_blacklist` item maps — the brief is literal and exhaustive
 * here: `REVIEW_GATE_ITEMS` has 6 members (`none`, the one mapped item,
 * and exactly 4 others — `criminal_record`/`health_flag`/`prior_refusal`/
 * `not_certain`), and ALL FOUR of those others "have no FactPath and stay
 * UI-side" — `not_certain` is not an exception, even though it reads like
 * a general "I'm not sure" flag. Its selection has ZERO effect on this
 * fact, exactly like the other 3. The stored fact is `QuestionScreen.tsx`'s
 * own sorted, comma-joined item-key CSV (`"none"` or e.g.
 * `"criminal_record,overstay_or_blacklist"`). Whenever `overstay_or_blacklist`
 * is absent — `"none"`, or any combination of the other 4 UI-only flags —
 * this fact is KNOWN empty: `KnownViolationSet` is documented as
 * meaningful with `value=[]` ("we asked, they have zero violations"), and
 * we DID ask (via this exact checklist item), just got a negative answer
 * for it specifically. */
export function mapViolationHistory(facts: OracleFacts): FactValue<string[]> {
  const raw = facts.review_gate;
  if (raw === undefined) return unknownFact(NOT_ASKED);
  const items = raw.split(",");
  if (items.includes("overstay_or_blacklist")) {
    return known([VIOLATION_MEMBER_FOR_OVERSTAY_OR_BLACKLIST]);
  }
  return known([]);
}

// ---------------------------------------------------------------------------
// Envelope
// ---------------------------------------------------------------------------

export interface MapFactsOptions {
  /** Generated by the caller (`shadow-client.ts`), never here — keeps
   * this module free of randomness/side effects. */
  assessmentId: string;
  /**
   * Reused, never re-read: the caller MUST pass the SAME frozen `Date`
   * instance `OracleShell` already captured for the verdict/lane
   * computation (`frozenToday`) — a second independent `new Date()` read
   * here could disagree with it across a UTC-midnight boundary (Finding
   * #9, `OracleShell.tsx`'s own docstring). This module never calls
   * `new Date()` itself.
   */
  collectedAt: Date;
}

/**
 * Map the mock interview's `OracleFacts` to the full 40-key
 * `ApplicantFacts` wire payload. Pure: identical inputs always produce an
 * identical output (unit-tested below).
 */
export function mapOracleFactsToApplicantFacts(
  facts: OracleFacts,
  options: MapFactsOptions,
): ApplicantFactsWire {
  const remoteClients = mapRemoteClientsDerived(facts);

  const data: ApplicantFactsDataWire = {
    "person.birth_date": unknownFact(NOT_ASKED),
    "person.nationalities": unknownFact(NOT_ASKED),
    "person.marital_status": unknownFact(NOT_ASKED),
    "immigration.currently_in_indonesia": mapCurrentlyInIndonesia(facts),
    "immigration.current_status_code": unknownFact(NOT_ASKED),
    "immigration.current_status_expiry": mapCurrentStatusExpiry(facts),
    "immigration.last_entry_date": unknownFact(NOT_ASKED),
    "immigration.overstay_days": unknownFact(NOT_ASKED),
    "immigration.violation_history": mapViolationHistory(facts),
    "intent.purposes": mapPurposes(facts),
    "intent.stay_days": mapStayDays(facts),
    "intent.desired_entry_date": unknownFact(NOT_ASKED),
    "intent.entry_pattern": unknownFact(NOT_ASKED),
    "intent.requested_product_code": unknownFact(NOT_ASKED),
    "work.employer_country_code": unknownFact(NOT_ASKED),
    "work.employer_is_indonesian_entity": mapEmployerIsIndonesianEntity(facts),
    "work.serves_indonesian_clients": remoteClients.servesIndonesianClients,
    "work.indonesia_source_compensation":
      remoteClients.indonesiaSourceCompensation,
    "work.indonesian_work_sponsor_confirmed": unknownFact(NOT_ASKED),
    "investment.pt_pma_committed": unknownFact(NOT_ASKED),
    "investment.investment_capital_idr": unknownFact(NOT_ASKED),
    "investment.paid_up_capital_idr": unknownFact(NOT_ASKED),
    "investment.proposed_role": unknownFact(NOT_ASKED),
    "family.relation_to_sponsor": unknownFact(NOT_ASKED),
    "family.sponsor_nationalities": unknownFact(NOT_ASKED),
    "family.sponsor_status_code": unknownFact(NOT_ASKED),
    "family.marriage_registered": unknownFact(NOT_ASKED),
    "family.sponsor_confirmed": unknownFact(NOT_ASKED),
    "study.level": unknownFact(NOT_ASKED),
    "study.admission_confirmed": unknownFact(NOT_ASKED),
    "study.sponsor_confirmed": unknownFact(NOT_ASKED),
    "secondhome.bank_deposit_usd": unknownFact(NOT_ASKED),
    "secondhome.bank_deposit_at_state_bank": unknownFact(NOT_ASKED),
    "secondhome.bank_deposit_in_own_name": unknownFact(NOT_ASKED),
    "secondhome.qualifying_property_value_usd": unknownFact(NOT_ASKED),
    "secondhome.passive_monthly_income_usd": unknownFact(NOT_ASKED),
    "process.application_channel": unknownFact(NOT_ASKED),
    "process.wants_onshore_conversion": unknownFact(NOT_ASKED),
    "commercial.service_fee_budget_idr": unknownFact(NOT_ASKED),
    "commercial.wants_quote": unknownFact(NOT_ASKED),
    // remote_income intentionally has no representation anywhere above:
    // no FactPath exists for it (verified against enums.py's FactPath —
    // there is no income-threshold fact among the 40). Never invented.
  };

  return {
    schema_version: SCHEMA_VERSION,
    assessment_id: options.assessmentId,
    collected_at: options.collectedAt.toISOString(),
    facts: data,
  };
}

/**
 * A stable, order-independent serialization of a mapped
 * `ApplicantFactsDataWire` — the SHADOW-dedupe key (`OracleShell.tsx`'s
 * own dedupe effect, and this function's test coverage). Keys are sorted
 * before serializing so the result never depends on the object's own
 * insertion order (`mapOracleFactsToApplicantFacts` always builds `data`
 * with the same 40 keys in the same literal order today, but this
 * function does not lean on that fact holding forever). Deliberately
 * excludes `schema_version`/`assessment_id`/`collected_at` — the caller
 * passes only the `.facts` sub-object — because a fresh random
 * `assessment_id` and a `collected_at` that only changes across attempts
 * (never within one, per `frozenToday`) must never make two otherwise-
 * identical interviews compare as "different".
 */
export function stableFactsKey(data: ApplicantFactsDataWire): string {
  return JSON.stringify(
    Object.keys(data)
      .sort()
      .map((key) => [key, data[key as keyof ApplicantFactsDataWire]]),
  );
}
