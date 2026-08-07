import { describe, expect, it } from "vitest";
import { buildEngineOutcome } from "./engine-adapter";
import { buildPreviewOutcome } from "./preview-adapter";
import { shadowParityMatches } from "./shadow-parity";
import { makeVisaOracleResponse } from "./visa-oracle-test-fixture";

describe("shadow public-contract parity", () => {
  it("matches CURATED user semantics despite identity and audit-clock drift", () => {
    const response = makeVisaOracleResponse();
    const candidate = response.display.candidates[0];
    candidate.pricing = {
      status: "AVAILABLE",
      reason_code: "PRICE_AVAILABLE",
      evaluated_at: "2026-08-03T04:00:00Z",
      catalog_last_updated: "2026-08-03",
      catalog_sha256: "b".repeat(64),
      row_sha256: "c".repeat(64),
    };
    response.decision.quotes = [
      {
        quote_id: "55555555-5555-4555-8555-555555555555",
        product_version_id: candidate.product_version_id,
        product_code: candidate.product_code,
        status: "AVAILABLE",
        currency: "IDR",
        amount: 3_250_000,
        pricing_key: { category: "visa", item_key: "C1" },
        catalog_version: "2026.08",
        catalog_sha256: "b".repeat(64),
        row_sha256: "c".repeat(64),
        quoted_at: "2026-08-03T04:00:00Z",
        valid_until: "2026-08-10T04:00:00Z",
        reason_code: "PRICE_AVAILABLE",
      },
    ];
    const outcome = buildEngineOutcome(response);
    response.mode = "CURATED";
    response.decision.decision_id = "55555555-5555-4555-8555-555555555555";
    response.decision.public_id = "different123456789";
    response.decision.effective_at = "2026-08-03T05:00:00Z";
    response.decision.observed_at = "2026-08-03T05:00:00Z";
    response.decision.evaluated_at = "2026-08-03T06:00:00Z";
    response.decision.rule_pack!.rule_pack_id =
      "66666666-6666-4666-8666-666666666666";
    response.sources[0].applicability.effective_at = "2026-08-03T05:00:00Z";
    response.sources[0].applicability.observed_at = "2026-08-03T05:00:00Z";
    response.sources[0].freshness.evaluated_at = "2026-08-03T05:00:00Z";
    response.decision.quotes[0].quoted_at = "2026-08-03T06:00:00Z";
    expect(shadowParityMatches(response, outcome)).toBe(true);
  });

  it("detects different reasons despite identical state and candidate order", () => {
    const response = makeVisaOracleResponse();
    const outcome = buildEngineOutcome(response);
    response.decision.candidates[0].reason_codes = ["DIFFERENT_REASON"];
    expect(shadowParityMatches(response, outcome)).toBe(false);
  });

  it("does not call the zero-candidate preview harness parity", () => {
    const response = makeVisaOracleResponse("TEMPORARILY_UNAVAILABLE");
    const preview = buildPreviewOutcome({}, new Date("2026-08-03T04:00:00Z"));
    expect(shadowParityMatches(response, preview)).toBe(false);
  });

  it("detects different empty-state reason, outage and source semantics", () => {
    const needsInput = makeVisaOracleResponse("NEEDS_INPUT");
    const needsInputBaseline = buildEngineOutcome(needsInput);
    needsInput.decision.missing_facts = ["person.birth_date"];
    expect(shadowParityMatches(needsInput, needsInputBaseline)).toBe(false);

    const outage = makeVisaOracleResponse("TEMPORARILY_UNAVAILABLE");
    const outageBaseline = buildEngineOutcome(outage);
    outage.decision.outage!.code = "DATABASE_UNAVAILABLE";
    expect(shadowParityMatches(outage, outageBaseline)).toBe(false);

    const noPath = makeVisaOracleResponse("NO_SUPPORTED_PATH");
    const noPathBaseline = buildEngineOutcome(noPath);
    noPath.sources[0].title = "Different official source";
    expect(shadowParityMatches(noPath, noPathBaseline)).toBe(false);
  });
});
