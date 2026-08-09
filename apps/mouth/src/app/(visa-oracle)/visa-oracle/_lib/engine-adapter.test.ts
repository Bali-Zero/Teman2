import { describe, expect, it } from "vitest";
import { buildEngineOutcome } from "./engine-adapter";
import { makeVisaOracleResponse } from "./visa-oracle-test-fixture";

describe("Visa Oracle authoritative outcome adapter", () => {
  it.each([
    "SUPPORTED_CANDIDATES",
    "NEEDS_INPUT",
    "HUMAN_REVIEW_REQUIRED",
    "NO_SUPPORTED_PATH",
    "TEMPORARILY_UNAVAILABLE",
  ] as const)(
    "maps engine state %s without fabricating candidates",
    (state) => {
      const outcome = buildEngineOutcome(makeVisaOracleResponse(state));
      expect(outcome.state).toBe(state);
      expect(outcome.provenance).toBe("ENGINE");
      expect(outcome.candidates).toHaveLength(
        state === "SUPPORTED_CANDIDATES" ? 1 : 0,
      );
    },
  );

  it("uses only processing/pricing/document assessments, never stay policy or mock content", () => {
    const outcome = buildEngineOutcome(makeVisaOracleResponse());
    expect(outcome.state).toBe("SUPPORTED_CANDIDATES");
    if (outcome.state !== "SUPPORTED_CANDIDATES")
      throw new Error("unexpected state");
    const candidate = outcome.candidates[0];
    expect(candidate.timeline).toMatchObject({ status: "UNAVAILABLE" });
    expect(candidate.price).toMatchObject({ status: "CONTACT_REQUIRED" });
    expect(candidate.documents).toEqual([]);
    expect(JSON.stringify(candidate)).not.toContain("60 days");
  });

  it("renders an exact PricingTool quote as one all-inclusive IDR amount", () => {
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
    expect(outcome.state).toBe("SUPPORTED_CANDIDATES");
    if (outcome.state !== "SUPPORTED_CANDIDATES")
      throw new Error("unexpected state");
    expect(outcome.candidates[0].price).toEqual({
      status: "AVAILABLE",
      currency: "IDR",
      amount: 3_250_000,
      allInclusive: true,
      quotedAtIso: "2026-08-03T04:00:00Z",
      validUntilIso: "2026-08-10T04:00:00Z",
    });
  });

  it("fails closed for CURATED, untrusted, stale or secondary decisive evidence", () => {
    for (const mutate of [
      (response: ReturnType<typeof makeVisaOracleResponse>) => {
        response.mode = "CURATED";
      },
      (response: ReturnType<typeof makeVisaOracleResponse>) => {
        response.sources[0].canonical_url =
          "https://imigrasi.go.id.evil.test/x";
      },
      (response: ReturnType<typeof makeVisaOracleResponse>) => {
        response.sources[0].freshness.status = "STALE";
      },
      (response: ReturnType<typeof makeVisaOracleResponse>) => {
        response.sources[0].is_primary_authority = false;
      },
    ]) {
      const response = makeVisaOracleResponse();
      mutate(response);
      expect(() => buildEngineOutcome(response)).toThrow();
    }
  });

  it("never renders a known operational or service axis without decisive evidence", () => {
    for (const axis of [
      "operational_availability",
      "bali_zero_service_availability",
    ] as const) {
      const missing = makeVisaOracleResponse();
      missing.display.candidates[0].availability[axis] = {
        status: "AVAILABLE",
        reason_code: "AXIS_AVAILABLE",
        observed_at: "2026-08-03T04:00:00Z",
        source_refs: [],
      };
      expect(() => buildEngineOutcome(missing)).toThrow();

      const untrusted = makeVisaOracleResponse();
      untrusted.display.candidates[0].availability[axis] = {
        status: "AVAILABLE",
        reason_code: "AXIS_AVAILABLE",
        observed_at: "2026-08-03T04:00:00Z",
        source_refs: [untrusted.sources[0].source_record_id],
      };
      untrusted.sources[0].canonical_url = "https://evil.test/source";
      expect(() => buildEngineOutcome(untrusted)).toThrow();
    }
  });

  it("rejects decisive evidence whose legal, recorded or verification clocks are in the future", () => {
    const mutations: Array<
      (response: ReturnType<typeof makeVisaOracleResponse>) => void
    > = [
      (response) => {
        response.sources[0].retrieved_at = "2026-08-03T05:00:00Z";
      },
      (response) => {
        response.sources[0].verified_at = "2026-08-03T05:00:00Z";
      },
      (response) => {
        response.sources[0].legal_period_from = "2026-08-03T05:00:00Z";
      },
      (response) => {
        response.sources[0].legal_period_to = "2026-08-03T03:59:59Z";
      },
      (response) => {
        response.sources[0].recorded_period_from = "2026-08-03T05:00:00Z";
      },
      (response) => {
        response.sources[0].applicability.effective_at = "2026-08-03T03:59:59Z";
      },
      (response) => {
        response.sources[0].applicability.observed_at = "2026-08-03T03:59:59Z";
      },
      (response) => {
        response.sources[0].freshness.evaluated_at = "2026-08-03T03:59:59Z";
      },
      (response) => {
        response.sources[0].freshness.verified_at = "2026-08-03T03:59:59Z";
      },
    ];
    for (const mutate of mutations) {
      const response = makeVisaOracleResponse();
      mutate(response);
      expect(() => buildEngineOutcome(response)).toThrow();
    }
  });

  it("keeps a trusted stale or unknown primary source as a review hold, not support", () => {
    const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    response.sources[0].freshness.status = "UNKNOWN";
    response.sources[0].applicability.status = "UNKNOWN";
    response.sources[0].verified_at = "2026-08-04T04:00:00Z";
    response.decision.review_reasons[0].source_refs = [
      response.sources[0].source_record_id,
    ];

    const outcome = buildEngineOutcome(response, {
      interviewBranchesRemaining: 3,
    });
    expect(outcome).toMatchObject({
      state: "HUMAN_REVIEW_REQUIRED",
      pathsRemaining: 3,
    });
    expect(outcome.sources).toHaveLength(1);
  });

  it("rejects an untrusted source even when it is used only as a review hold", () => {
    const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    response.sources[0].canonical_url = "https://imigrasi.go.id.evil.test/x";
    response.decision.review_reasons[0].source_refs = [
      response.sources[0].source_record_id,
    ];
    expect(() => buildEngineOutcome(response)).toThrow();
  });

  it("curates review-reason copy for a known code, EN and ID", () => {
    const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    response.decision.review_reasons[0].code = "CALLING_VISA_REVIEW";

    const outcome = buildEngineOutcome(response);
    expect(outcome.state).toBe("HUMAN_REVIEW_REQUIRED");
    if (outcome.state !== "HUMAN_REVIEW_REQUIRED")
      throw new Error("unexpected state");
    const message = outcome.reviewReasons[0].message;
    expect(message.en).toMatch(/calling visa/i);
    expect(message.id).toMatch(/calling visa/i);
    expect(message.en.toLowerCase()).not.toContain(
      "no evaluation was submitted",
    );
    expect(message.en).not.toContain("Verified reason:");
  });

  it("falls back to an honest generic sentence for an unmapped review-reason code", () => {
    const response = makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED");
    response.decision.review_reasons[0].code = "SOME_FUTURE_RULE_CODE";

    const outcome = buildEngineOutcome(response);
    expect(outcome.state).toBe("HUMAN_REVIEW_REQUIRED");
    if (outcome.state !== "HUMAN_REVIEW_REQUIRED")
      throw new Error("unexpected state");
    const message = outcome.reviewReasons[0].message;
    expect(message.en).not.toContain("SOME_FUTURE_RULE_CODE");
    expect(message.en).not.toContain("Verified reason:");
    expect(message.en.toLowerCase()).not.toContain(
      "no evaluation was submitted",
    );
    expect(message.en.toLowerCase()).toContain("judgment");
  });

  it("maps missing engine facts back to editable interview questions", () => {
    const outcome = buildEngineOutcome(makeVisaOracleResponse("NEEDS_INPUT"));
    expect(outcome.state).toBe("NEEDS_INPUT");
    if (outcome.state !== "NEEDS_INPUT") throw new Error("unexpected state");
    expect(outcome.missingInputs[0]).toMatchObject({
      code: "intent.stay_days",
      questionId: "stay_days",
    });
  });
});
