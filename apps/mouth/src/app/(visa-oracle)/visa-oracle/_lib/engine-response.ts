import type { VisaOracleEvaluateResponse } from "./visa-oracle-contract";

export type VisaOracleResponseErrorCode =
  "MALFORMED_RESPONSE" | "RESPONSE_INVARIANT" | "NON_ENGINE_MODE";

export class VisaOracleResponseError extends Error {
  constructor(public readonly code: VisaOracleResponseErrorCode) {
    super(code);
    this.name = "VisaOracleResponseError";
  }
}

type JsonRecord = Record<string, unknown>;

const STATES = new Set([
  "SUPPORTED_CANDIDATES",
  "NEEDS_INPUT",
  "HUMAN_REVIEW_REQUIRED",
  "NO_SUPPORTED_PATH",
  "TEMPORARILY_UNAVAILABLE",
]);
const AVAILABILITY = new Set(["AVAILABLE", "UNAVAILABLE", "UNKNOWN"]);
const PRICING = new Set([
  "AVAILABLE",
  "CONTACT_REQUIRED",
  "UNAVAILABLE",
  "UNKNOWN",
]);
const SOURCE_STATUS = new Set([
  "VERIFIED",
  "SUPERSEDED",
  "REVOKED",
  "UNAVAILABLE",
]);
const APPLICABILITY = new Set([
  "APPLICABLE",
  "NOT_YET_EFFECTIVE",
  "EXPIRED",
  "SUPERSEDED",
  "REVOKED",
  "UNAVAILABLE",
  "UNKNOWN",
]);
const FRESHNESS = new Set(["CURRENT", "STALE", "UNKNOWN"]);
const UTC_INSTANT =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(?:Z|\+00:00)$/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const PUBLIC_ID = /^[a-z0-9]{16,20}$/;
const SHA256 = /^[a-f0-9]{64}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const IDENTIFIER = /^[A-Za-z][A-Za-z0-9_.:-]{0,127}$/;

function malformed(): never {
  throw new VisaOracleResponseError("MALFORMED_RESPONSE");
}

function invariant(): never {
  throw new VisaOracleResponseError("RESPONSE_INVARIANT");
}

function record(value: unknown): JsonRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    malformed();
  }
  return value as JsonRecord;
}

function string(value: unknown, allowEmpty = false): string {
  if (typeof value !== "string" || (!allowEmpty && value.length === 0)) {
    malformed();
  }
  return value;
}

function nullableString(value: unknown): string | null {
  return value === null ? null : string(value);
}

function integer(value: unknown, minimum = 0): number {
  if (!Number.isSafeInteger(value) || (value as number) < minimum) malformed();
  return value as number;
}

function array(value: unknown): unknown[] {
  if (!Array.isArray(value)) malformed();
  return value;
}

function stringArray(value: unknown): string[] {
  const result = array(value).map((item) => string(item));
  if (new Set(result).size !== result.length) invariant();
  return result;
}

function oneOf(value: unknown, accepted: Set<string>): string {
  const candidate = string(value);
  if (!accepted.has(candidate)) malformed();
  return candidate;
}

function utc(value: unknown): string {
  const candidate = string(value);
  const match = UTC_INSTANT.exec(candidate);
  if (!match) {
    malformed();
  }
  const [, yearText, monthText, dayText, hourText, minuteText, secondText] =
    match;
  const [year, month, day, hour, minute, second] = [
    yearText,
    monthText,
    dayText,
    hourText,
    minuteText,
    secondText,
  ].map(Number);
  const parsed = new Date(candidate);
  if (
    !Number.isFinite(parsed.valueOf()) ||
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day ||
    parsed.getUTCHours() !== hour ||
    parsed.getUTCMinutes() !== minute ||
    parsed.getUTCSeconds() !== second
  ) {
    malformed();
  }
  return candidate;
}

function date(value: unknown): string {
  const candidate = string(value);
  if (!ISO_DATE.test(candidate)) {
    malformed();
  }
  const [year, month, day] = candidate.split("-").map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  if (
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== day
  ) {
    malformed();
  }
  return candidate;
}

function nullableDate(value: unknown): string | null {
  return value === null ? null : date(value);
}

function uuid(value: unknown): string {
  const candidate = string(value);
  if (!UUID.test(candidate)) malformed();
  return candidate;
}

function fingerprint(value: unknown): void {
  const item = record(value);
  if (item.algorithm !== "HMAC-SHA256") malformed();
  if (!IDENTIFIER.test(string(item.key_id))) malformed();
  if (!SHA256.test(string(item.digest))) malformed();
}

function verifiedEvaluationIdentity(decision: JsonRecord, state: string): void {
  const fields = [
    decision.decision_id,
    decision.public_id,
    decision.rule_pack,
    decision.facts_fingerprint,
    decision.trace_sha256,
    decision.decision_integrity,
  ];

  if (state === "TEMPORARILY_UNAVAILABLE") {
    if (fields.some((field) => field !== null)) invariant();
    return;
  }
  if (fields.some((field) => field === null || field === undefined)) {
    invariant();
  }

  uuid(decision.decision_id);
  if (!PUBLIC_ID.test(string(decision.public_id))) malformed();
  const pack = record(decision.rule_pack);
  uuid(pack.rule_pack_id);
  integer(pack.sequence, 1);
  string(pack.version);
  if (!SHA256.test(string(pack.payload_sha256))) malformed();
  fingerprint(decision.facts_fingerprint);
  if (!SHA256.test(string(decision.trace_sha256))) malformed();
  fingerprint(decision.decision_integrity);
}

function productNames(value: unknown): void {
  const names = record(value);
  string(names.en);
  string(names.id);
}

function reason(value: unknown): string[] {
  const item = record(value);
  string(item.code);
  stringArray(item.rule_ids);
  return stringArray(item.source_refs);
}

function availability(value: unknown): string[] {
  const item = record(value);
  oneOf(item.status, AVAILABILITY);
  string(item.reason_code);
  utc(item.observed_at);
  return stringArray(item.source_refs);
}

function verifyStateInvariants(decision: JsonRecord): void {
  const state = string(decision.state);
  const candidates = array(decision.candidates);
  const quotes = array(decision.quotes);
  const missing = array(decision.missing_facts);
  const review = array(decision.review_reasons);
  const noPath = array(decision.no_path_reasons);
  const outage = decision.outage;

  if (state === "SUPPORTED_CANDIDATES") {
    if (
      candidates.length === 0 ||
      missing.length > 0 ||
      review.length > 0 ||
      noPath.length > 0 ||
      outage !== null
    ) {
      invariant();
    }
    return;
  }
  // `quotes` stays forbidden on EVERY non-SUPPORTED_CANDIDATES state, no
  // exception (contract C1: nothing outside SUPPORTED_CANDIDATES can ever
  // carry a resolved price). `candidates` is relaxed ONLY for
  // HUMAN_REVIEW_REQUIRED — owner ruling #5 (2026-08-25,
  // OWNER-RULINGS-2026-08-25.md §5, `REVIEW-EMPTIES-CANDIDATES.md` option
  // (2)): the products a visitor is genuinely already eligible for can now
  // travel alongside a review verdict (state precedence is untouched — this
  // is still HUMAN_REVIEW_REQUIRED, not a demotion to SUPPORTED_CANDIDATES).
  // NEEDS_INPUT, NO_SUPPORTED_PATH and TEMPORARILY_UNAVAILABLE still forbid
  // candidates entirely — none of them has a signed rule pack that populates
  // one, and relaxing them here would be speculative, not measured.
  //
  // CORRECTED 2026-08-25: before this, this line unconditionally rejected
  // ANY non-SUPPORTED_CANDIDATES response carrying a candidate — a fourth,
  // previously unlisted site of the same "only SUPPORTED_CANDIDATES can have
  // candidates" premise RULING5-BLAST-RADIUS-FRONTEND.md named three others
  // for (models.py, engine-adapter.ts, OracleShell.tsx). Left unfixed, this
  // client-side runtime guard would have thrown `RESPONSE_INVARIANT` on
  // every real production response the backend fix produces, before it ever
  // reached `engine-adapter.ts` — silently falling back to a degraded,
  // candidate-less outcome and making the other three fixes unreachable.
  // Found empirically: a RED-first `OracleShell.test.tsx` integration test
  // driving a real HUMAN_REVIEW_REQUIRED-with-candidates response through
  // `fetch` still asserted `tier: "T3"` even after `engine-adapter.ts` and
  // `OracleShell.tsx` were both fixed — this was why.
  if (quotes.length > 0) invariant();
  if (candidates.length > 0 && state !== "HUMAN_REVIEW_REQUIRED") invariant();
  if (
    state === "NEEDS_INPUT" &&
    (missing.length === 0 ||
      review.length > 0 ||
      noPath.length > 0 ||
      outage !== null)
  ) {
    invariant();
  }
  if (
    state === "HUMAN_REVIEW_REQUIRED" &&
    (missing.length > 0 ||
      review.length === 0 ||
      noPath.length > 0 ||
      outage !== null)
  ) {
    invariant();
  }
  if (
    state === "NO_SUPPORTED_PATH" &&
    (missing.length > 0 ||
      review.length > 0 ||
      noPath.length === 0 ||
      outage !== null)
  ) {
    invariant();
  }
  if (
    state === "TEMPORARILY_UNAVAILABLE" &&
    (missing.length > 0 ||
      review.length > 0 ||
      noPath.length > 0 ||
      outage === null)
  ) {
    invariant();
  }
}

/**
 * Runtime projection guard for the generated OpenAPI response. It validates
 * all fields the UI consumes plus cross-array/state integrity. Unknown JSON
 * never becomes a typed response merely through a TypeScript assertion.
 */
export function parseVisaOracleEvaluateResponse(
  value: unknown,
): VisaOracleEvaluateResponse {
  const response = record(value);
  if (response.mode !== "ENGINE" && response.mode !== "CURATED") malformed();

  const decision = record(response.decision);
  if (decision.schema_version !== "1.0.0") malformed();
  const state = oneOf(decision.state, STATES);
  utc(decision.effective_at);
  utc(decision.observed_at);
  utc(decision.evaluated_at);
  verifiedEvaluationIdentity(decision, state);
  stringArray(decision.missing_facts);
  const reviewReasons = array(decision.review_reasons);
  const noPathReasons = array(decision.no_path_reasons);
  const notices = array(decision.notices);
  const candidates = array(decision.candidates);
  const quotes = array(decision.quotes);
  if (decision.outage !== null) {
    const outage = record(decision.outage);
    string(outage.code);
    if (typeof outage.retryable !== "boolean") malformed();
  }

  const sourceIds = new Set<string>();
  for (const sourceValue of array(response.sources)) {
    const source = record(sourceValue);
    const id = string(source.source_record_id);
    if (sourceIds.has(id)) invariant();
    sourceIds.add(id);
    string(source.source_key);
    string(source.title);
    string(source.publisher);
    string(source.authority_type);
    if (typeof source.is_primary_authority !== "boolean") malformed();
    oneOf(source.status, SOURCE_STATUS);
    string(source.canonical_url);
    utc(source.legal_period_from);
    if (source.legal_period_to !== null) utc(source.legal_period_to);
    utc(source.recorded_period_from);
    utc(source.retrieved_at);
    utc(source.verified_at);
    const applicability = record(source.applicability);
    oneOf(applicability.status, APPLICABILITY);
    utc(applicability.effective_at);
    utc(applicability.observed_at);
    const freshness = record(source.freshness);
    oneOf(freshness.status, FRESHNESS);
    string(freshness.reason_code);
    utc(freshness.evaluated_at);
    utc(freshness.verified_at);
  }

  const referencedSources: string[] = [];
  for (const reasonValue of [...reviewReasons, ...noPathReasons, ...notices]) {
    referencedSources.push(...reason(reasonValue));
  }

  const display = record(response.display);
  const displayCandidates = array(display.candidates);
  if (displayCandidates.length !== candidates.length) invariant();

  const candidateIds = new Set<string>();
  for (let index = 0; index < candidates.length; index += 1) {
    const candidate = record(candidates[index]);
    const projected = record(displayCandidates[index]);
    const productId = string(candidate.product_version_id);
    if (candidateIds.has(productId)) invariant();
    candidateIds.add(productId);
    const code = string(candidate.product_code);
    const rank = integer(candidate.rank, 1);
    if (rank !== index + 1) invariant();
    if (
      projected.product_version_id !== productId ||
      projected.product_code !== code ||
      projected.rank !== rank
    ) {
      invariant();
    }
    const reasonCodes = stringArray(candidate.reason_codes);
    const candidateSourceRefs = stringArray(candidate.source_refs);
    if (reasonCodes.length === 0 || candidateSourceRefs.length === 0)
      invariant();
    referencedSources.push(...candidateSourceRefs);
    productNames(projected.name);
    if (projected.tagline !== null) productNames(projected.tagline);

    const availabilityProjection = record(projected.availability);
    if (availabilityProjection.legal_eligibility !== "SUPPORTED") malformed();
    referencedSources.push(
      ...availability(availabilityProjection.operational_availability),
      ...availability(availabilityProjection.bali_zero_service_availability),
    );

    const documentation = record(projected.documentation);
    if (
      documentation.status !== "AVAILABLE" &&
      documentation.status !== "UNKNOWN"
    ) {
      malformed();
    }
    string(documentation.reason_code);
    utc(documentation.observed_at);
    const requirements = array(documentation.requirements);
    const checklist = array(documentation.checklist);
    for (const item of [...requirements, ...checklist]) productNames(item);
    if (
      documentation.status === "UNKNOWN" &&
      (requirements.length > 0 || checklist.length > 0)
    ) {
      invariant();
    }
    if (
      documentation.status === "AVAILABLE" &&
      requirements.length === 0 &&
      checklist.length === 0
    ) {
      invariant();
    }

    const timeline = record(projected.processing_timeline);
    if (timeline.status !== "AVAILABLE" && timeline.status !== "UNKNOWN")
      malformed();
    string(timeline.reason_code);
    utc(timeline.observed_at);
    const anchor = nullableDate(timeline.anchor_date);
    const from = nullableDate(timeline.estimated_completion_from);
    const to = nullableDate(timeline.estimated_completion_to);
    if (timeline.status === "UNKNOWN") {
      if (anchor !== null || from !== null || to !== null) invariant();
    } else if (
      anchor === null ||
      from === null ||
      to === null ||
      from < anchor ||
      to < from
    ) {
      invariant();
    }

    const pricing = record(projected.pricing);
    oneOf(pricing.status, PRICING);
    string(pricing.reason_code);
    utc(pricing.evaluated_at);
    nullableDate(pricing.catalog_last_updated);
    const catalogHash = nullableString(pricing.catalog_sha256);
    const rowHash = nullableString(pricing.row_sha256);
    if (catalogHash !== null && !SHA256.test(catalogHash)) malformed();
    if (rowHash !== null && !SHA256.test(rowHash)) malformed();
    if (rowHash !== null && catalogHash === null) invariant();
    if (
      pricing.status === "AVAILABLE" &&
      (pricing.catalog_last_updated === null ||
        catalogHash === null ||
        rowHash === null)
    ) {
      invariant();
    }
  }

  const quotesByProduct = new Map<string, JsonRecord>();
  for (const quoteValue of quotes) {
    const quote = record(quoteValue);
    const productId = string(quote.product_version_id);
    if (!candidateIds.has(productId) || quotesByProduct.has(productId))
      invariant();
    quotesByProduct.set(productId, quote);
    string(quote.product_code);
    const status = string(quote.status);
    if (!["AVAILABLE", "CONTACT_REQUIRED", "UNAVAILABLE"].includes(status))
      malformed();
    if (quote.currency !== "IDR") malformed();
    utc(quote.quoted_at);
    if (quote.valid_until !== null) utc(quote.valid_until);
    string(quote.reason_code);
    if (status === "AVAILABLE") {
      integer(quote.amount, 0);
      if (
        quote.catalog_version === null ||
        !SHA256.test(string(quote.catalog_sha256)) ||
        !SHA256.test(string(quote.row_sha256))
      ) {
        invariant();
      }
    } else if (quote.amount !== null) {
      invariant();
    }
  }

  for (let index = 0; index < displayCandidates.length; index += 1) {
    const projected = record(displayCandidates[index]);
    const pricing = record(projected.pricing);
    const quote = quotesByProduct.get(string(projected.product_version_id));
    if (pricing.status === "AVAILABLE") {
      if (
        !quote ||
        quote.status !== "AVAILABLE" ||
        quote.reason_code !== pricing.reason_code
      ) {
        invariant();
      }
    } else if (quote && quote.status !== pricing.status) {
      invariant();
    }
  }

  if (referencedSources.some((id) => !sourceIds.has(id))) invariant();
  verifyStateInvariants(decision);
  return value as VisaOracleEvaluateResponse;
}

export function requireEngineResponse(
  response: VisaOracleEvaluateResponse,
): VisaOracleEvaluateResponse {
  if (response.mode !== "ENGINE") {
    throw new VisaOracleResponseError("NON_ENGINE_MODE");
  }
  return response;
}
