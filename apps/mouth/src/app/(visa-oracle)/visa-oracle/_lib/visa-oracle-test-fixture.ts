import type { VisaOracleEvaluateResponse } from "./visa-oracle-contract";

export const TEST_NOW = "2026-08-03T04:00:00Z";
export const TEST_SOURCE_ID = "11111111-1111-4111-8111-111111111111";
export const TEST_PRODUCT_ID = "22222222-2222-4222-8222-222222222222";
const DECISION_ID = "33333333-3333-4333-8333-333333333333";
const RULE_PACK_ID = "44444444-4444-4444-8444-444444444444";
const SHA = "a".repeat(64);

type State = VisaOracleEvaluateResponse["decision"]["state"];

export function makeVisaOracleResponse(
  state: State = "SUPPORTED_CANDIDATES",
): VisaOracleEvaluateResponse {
  const evaluated = state !== "TEMPORARILY_UNAVAILABLE";
  const supported = state === "SUPPORTED_CANDIDATES";
  const source = {
    source_record_id: TEST_SOURCE_ID,
    source_key: "official-immigration-source",
    title: "Official immigration regulation",
    publisher: "Directorate General of Immigration",
    authority_type: "IMPLEMENTING_REGULATION" as const,
    is_primary_authority: true,
    status: "VERIFIED" as const,
    document_number: "1/2026",
    canonical_url: "https://www.imigrasi.go.id/regulation",
    locators: [{ kind: "ARTICLE" as const, value: "1" }],
    legal_period_from: TEST_NOW,
    legal_period_to: null,
    recorded_period_from: TEST_NOW,
    retrieved_at: TEST_NOW,
    verified_at: TEST_NOW,
    applicability: {
      status: "APPLICABLE" as const,
      effective_at: TEST_NOW,
      observed_at: TEST_NOW,
    },
    freshness: {
      status: "CURRENT" as const,
      reason_code: "SOURCE_CURRENT",
      evaluated_at: TEST_NOW,
      verified_at: TEST_NOW,
      max_age_seconds: 86_400,
    },
  };
  const candidate = {
    rank: 1,
    product_version_id: TEST_PRODUCT_ID,
    product_code: "C1",
    score: 100,
    covered_purposes: ["TOURISM"],
    support_rule_ids: ["support-c1"],
    source_refs: [TEST_SOURCE_ID],
    reason_codes: ["TOURISM_SUPPORTED"],
  };
  const displayCandidate = {
    product_code: "C1",
    product_version_id: TEST_PRODUCT_ID,
    rank: 1,
    name: { en: "Visit Visa C1", id: "Visa Kunjungan C1" },
    tagline: { en: "Verified visit path", id: "Jalur kunjungan terverifikasi" },
    stay_policy: {
      stay: { kind: "FIXED_DAYS" as const, minimum_days: 60, maximum_days: 60 },
      extension: {
        allowed: true,
        maximum_extensions: 2,
        days_per_extension: 60,
      },
    },
    documentation: {
      status: "UNKNOWN" as const,
      reason_code: "DOCUMENTATION_NOT_VERIFIED",
      observed_at: TEST_NOW,
      requirements: [],
      checklist: [],
    },
    processing_timeline: {
      status: "UNKNOWN" as const,
      reason_code: "TIMELINE_NOT_VERIFIED",
      observed_at: TEST_NOW,
      anchor_date: null,
      estimated_completion_from: null,
      estimated_completion_to: null,
    },
    availability: {
      legal_eligibility: "SUPPORTED" as const,
      operational_availability: {
        status: "UNKNOWN" as const,
        reason_code: "OPERATIONAL_AVAILABILITY_UNKNOWN",
        observed_at: TEST_NOW,
        source_refs: [],
      },
      bali_zero_service_availability: {
        status: "UNKNOWN" as const,
        reason_code: "SERVICE_AVAILABILITY_UNKNOWN",
        observed_at: TEST_NOW,
        source_refs: [],
      },
    },
    pricing: {
      status: "CONTACT_REQUIRED" as const,
      reason_code: "PRICE_CONTACT_REQUIRED",
      evaluated_at: TEST_NOW,
      catalog_last_updated: null,
      catalog_sha256: null,
      row_sha256: null,
    },
  };

  return {
    mode: "ENGINE",
    decision: {
      schema_version: "1.0.0",
      decision_id: evaluated ? DECISION_ID : null,
      public_id: evaluated ? "abcdef1234567890" : null,
      state,
      effective_at: TEST_NOW,
      observed_at: TEST_NOW,
      evaluated_at: TEST_NOW,
      rule_pack: evaluated
        ? {
            rule_pack_id: RULE_PACK_ID,
            sequence: 1,
            version: "1.0.0",
            payload_sha256: SHA,
          }
        : null,
      facts_fingerprint: evaluated
        ? { algorithm: "HMAC-SHA256", key_id: "facts-key", digest: SHA }
        : null,
      candidates: supported ? [candidate] : [],
      missing_facts: state === "NEEDS_INPUT" ? ["intent.stay_days"] : [],
      review_reasons:
        state === "HUMAN_REVIEW_REQUIRED"
          ? [
              {
                code: "DISCLOSED_ACTIVITY_BOUNDARY_REVIEW",
                rule_ids: [],
                source_refs: [],
              },
            ]
          : [],
      no_path_reasons:
        state === "NO_SUPPORTED_PATH"
          ? [
              {
                code: "NO_SUPPORTED_PATH",
                rule_ids: ["no-path"],
                source_refs: [TEST_SOURCE_ID],
              },
            ]
          : [],
      outage:
        state === "TEMPORARILY_UNAVAILABLE"
          ? { code: "RULE_PACK_UNAVAILABLE", retryable: true }
          : null,
      quotes: [],
      notices: [],
      trace_sha256: evaluated ? SHA : null,
      decision_integrity: evaluated
        ? { algorithm: "HMAC-SHA256", key_id: "decision-key", digest: SHA }
        : null,
    },
    sources: [source],
    display: { candidates: supported ? [displayCandidate] : [] },
  };
}

const REVIEW_D12_ID = "55555555-5555-4555-8555-555555555551";
const REVIEW_E28A_ID = "55555555-5555-4555-8555-555555555552";

/**
 * Reproduces the MEASURED production case from
 * `docs/plans/2026-08-24-visa-oracle-live/RULING5-BLAST-RADIUS-FRONTEND.md`:
 * a plausible investor (PT PMA committed, capital above E28A minimums)
 * naming E28B/C/D/F as the requested product comes back
 * `HUMAN_REVIEW_REQUIRED` carrying TWO real candidates — `D12` and `E28A` —
 * with `quotes` empty and, at the display layer, `pricing.status ==
 * "CONTACT_REQUIRED"` / `pricing.reason_code ==
 * "PRICING_PENDING_HUMAN_REVIEW"` (backend: `evaluate_path.py:813`,
 * `test_evaluate_endpoint.py:2083`).
 *
 * Deliberately TWO, never one: `REVIEW-EMPTIES-CANDIDATES.md` measured only
 * `E28A` because it exercised a different gold persona — a fixture that pins
 * a single candidate here would hide exactly the bug (a UI that assumes a
 * singular) this fixture exists to catch.
 */
export function makeHumanReviewWithEligibleCandidates(): VisaOracleEvaluateResponse {
  const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");

  const decisionCandidate = (
    code: string,
    rank: number,
    versionId: string,
  ) => ({
    rank,
    product_version_id: versionId,
    product_code: code,
    score: 90,
    covered_purposes: ["INVESTMENT"],
    support_rule_ids: [`support-${code.toLowerCase()}`],
    source_refs: [TEST_SOURCE_ID],
    reason_codes: ["E28A_INVESTMENT_ELIGIBLE"],
  });

  const displayCandidate = (
    code: string,
    rank: number,
    versionId: string,
    name: string,
  ) => ({
    product_code: code,
    product_version_id: versionId,
    rank,
    name: { en: name, id: name },
    tagline: null,
    stay_policy: {
      stay: {
        kind: "FIXED_DAYS" as const,
        minimum_days: 365,
        maximum_days: 365,
      },
      extension: {
        allowed: true,
        maximum_extensions: 1,
        days_per_extension: 365,
      },
    },
    documentation: {
      status: "UNKNOWN" as const,
      reason_code: "DOCUMENTATION_NOT_VERIFIED",
      observed_at: TEST_NOW,
      requirements: [],
      checklist: [],
    },
    processing_timeline: {
      status: "UNKNOWN" as const,
      reason_code: "TIMELINE_NOT_VERIFIED",
      observed_at: TEST_NOW,
      anchor_date: null,
      estimated_completion_from: null,
      estimated_completion_to: null,
    },
    availability: {
      legal_eligibility: "SUPPORTED" as const,
      operational_availability: {
        status: "UNKNOWN" as const,
        reason_code: "OPERATIONAL_AVAILABILITY_UNKNOWN",
        observed_at: TEST_NOW,
        source_refs: [],
      },
      bali_zero_service_availability: {
        status: "UNKNOWN" as const,
        reason_code: "SERVICE_AVAILABILITY_UNKNOWN",
        observed_at: TEST_NOW,
        source_refs: [],
      },
    },
    pricing: {
      status: "CONTACT_REQUIRED" as const,
      reason_code: "PRICING_PENDING_HUMAN_REVIEW",
      evaluated_at: TEST_NOW,
      catalog_last_updated: null,
      catalog_sha256: null,
      row_sha256: null,
    },
  });

  response.decision.candidates = [
    decisionCandidate("D12", 1, REVIEW_D12_ID),
    decisionCandidate("E28A", 2, REVIEW_E28A_ID),
  ];
  response.display.candidates = [
    displayCandidate("D12", 1, REVIEW_D12_ID, "Multiple-Entry Business Visa"),
    displayCandidate("E28A", 2, REVIEW_E28A_ID, "Investor KITAS (E28A)"),
  ];
  response.decision.quotes = [];
  return response;
}
