import { describe, expect, it } from "vitest";
import {
  parseVisaOracleEvaluateResponse,
  requireEngineResponse,
  VisaOracleResponseError,
} from "./engine-response";
import {
  makeHumanReviewWithEligibleCandidates,
  makeVisaOracleResponse,
} from "./visa-oracle-test-fixture";

describe("Visa Oracle engine response runtime guard", () => {
  it.each([
    "SUPPORTED_CANDIDATES",
    "NEEDS_INPUT",
    "HUMAN_REVIEW_REQUIRED",
    "NO_SUPPORTED_PATH",
    "TEMPORARILY_UNAVAILABLE",
  ] as const)("accepts a contract-valid %s response", (state) => {
    expect(
      parseVisaOracleEvaluateResponse(makeVisaOracleResponse(state)).decision
        .state,
    ).toBe(state);
  });

  it("applies the second authority gate to response.mode", () => {
    const curated = makeVisaOracleResponse();
    curated.mode = "CURATED";
    expect(parseVisaOracleEvaluateResponse(curated).mode).toBe("CURATED");
    expect(() => requireEngineResponse(curated)).toThrowError(
      new VisaOracleResponseError("NON_ENGINE_MODE"),
    );
  });

  it("rejects candidate reorder, dangling sources and state invariant drift", () => {
    const reordered = makeVisaOracleResponse();
    reordered.display.candidates[0].rank = 2;
    expect(() => parseVisaOracleEvaluateResponse(reordered)).toThrowError(
      expect.objectContaining({ code: "RESPONSE_INVARIANT" }),
    );

    const dangling = makeVisaOracleResponse();
    dangling.decision.candidates[0].source_refs = [
      "99999999-9999-4999-8999-999999999999",
    ];
    expect(() => parseVisaOracleEvaluateResponse(dangling)).toThrowError(
      expect.objectContaining({ code: "RESPONSE_INVARIANT" }),
    );

    const wrongState = makeVisaOracleResponse("NEEDS_INPUT");
    wrongState.decision.missing_facts = [];
    expect(() => parseVisaOracleEvaluateResponse(wrongState)).toThrowError(
      expect.objectContaining({ code: "RESPONSE_INVARIANT" }),
    );
  });

  it("keeps UNKNOWN documentation and timeline distinct from verified values", () => {
    const documents = makeVisaOracleResponse();
    documents.display.candidates[0].documentation.requirements = [
      { en: "Passport", id: "Paspor" },
    ];
    expect(() => parseVisaOracleEvaluateResponse(documents)).toThrowError(
      expect.objectContaining({ code: "RESPONSE_INVARIANT" }),
    );

    const timeline = makeVisaOracleResponse();
    timeline.display.candidates[0].processing_timeline.anchor_date =
      "2026-08-03";
    expect(() => parseVisaOracleEvaluateResponse(timeline)).toThrowError(
      expect.objectContaining({ code: "RESPONSE_INVARIANT" }),
    );
  });

  it("rejects calendar dates that JavaScript would silently normalize", () => {
    const response = makeVisaOracleResponse();
    response.display.candidates[0].pricing.catalog_last_updated = "2026-02-30";
    expect(() => parseVisaOracleEvaluateResponse(response)).toThrowError(
      expect.objectContaining({ code: "MALFORMED_RESPONSE" }),
    );
  });

  it("accepts only exact UTC instants and rejects normalized or local formats", () => {
    for (const invalid of [
      "2026-02-30T04:00:00Z",
      "2026-08-03 04:00:00Z",
      "Aug 3 2026 04:00:00 GMT",
      "2026-08-03T04:00:00-00:00",
    ]) {
      const response = makeVisaOracleResponse();
      response.decision.evaluated_at = invalid;
      expect(() => parseVisaOracleEvaluateResponse(response)).toThrowError(
        expect.objectContaining({ code: "MALFORMED_RESPONSE" }),
      );
    }

    const pythonUtc = makeVisaOracleResponse();
    pythonUtc.decision.evaluated_at = "2026-08-03T04:00:00.123456+00:00";
    expect(
      parseVisaOracleEvaluateResponse(pythonUtc).decision.evaluated_at,
    ).toBe("2026-08-03T04:00:00.123456+00:00");
  });

  it("requires every evaluated identity and integrity field", () => {
    for (const field of [
      "decision_id",
      "public_id",
      "rule_pack",
      "facts_fingerprint",
      "trace_sha256",
      "decision_integrity",
    ] as const) {
      const response = makeVisaOracleResponse();
      delete (response.decision as unknown as Record<string, unknown>)[field];
      expect(
        () => parseVisaOracleEvaluateResponse(response),
        field,
      ).toThrowError(expect.objectContaining({ code: "RESPONSE_INVARIANT" }));
    }
  });

  it("rejects malformed UUID, digest, key id and HMAC metadata", () => {
    const corruptions: Array<
      (response: ReturnType<typeof makeVisaOracleResponse>) => void
    > = [
      (response) => {
        response.decision.decision_id = "not-a-uuid";
      },
      (response) => {
        response.decision.public_id = "UPPERCASE-NOT-PUBLIC";
      },
      (response) => {
        response.decision.rule_pack!.rule_pack_id = "not-a-uuid";
      },
      (response) => {
        response.decision.rule_pack!.payload_sha256 = "A".repeat(64);
      },
      (response) => {
        response.decision.trace_sha256 = "short";
      },
      (response) => {
        response.decision.facts_fingerprint = {
          algorithm: "HMAC-SHA256",
          key_id: "1-invalid-key",
          digest: "a".repeat(64),
        };
      },
      (response) => {
        const integrity = response.decision
          .decision_integrity as unknown as Record<string, unknown>;
        integrity.algorithm = "SHA256";
      },
      (response) => {
        response.decision.decision_integrity = {
          algorithm: "HMAC-SHA256",
          key_id: "decision-key",
          digest: "not-a-sha256",
        };
      },
    ];

    for (const corrupt of corruptions) {
      const response = makeVisaOracleResponse();
      corrupt(response);
      expect(() => parseVisaOracleEvaluateResponse(response)).toThrowError(
        expect.objectContaining({ code: "MALFORMED_RESPONSE" }),
      );
    }
  });

  /**
   * Owner ruling #5 (2026-08-25, OWNER-RULINGS-2026-08-25.md §5). Found the
   * hard way: this runtime guard used to reject ANY non-SUPPORTED_CANDIDATES
   * response carrying a candidate — a fourth, previously unlisted site of
   * the same premise RULING5-BLAST-RADIUS-FRONTEND.md named three others
   * for. Watched RED against the pre-fix `verifyStateInvariants` (reverted
   * locally): `parseVisaOracleEvaluateResponse` threw `RESPONSE_INVARIANT`
   * on the exact measured production case below.
   */
  it("accepts a HUMAN_REVIEW_REQUIRED response carrying the candidates a visitor already qualifies for", () => {
    const response = makeHumanReviewWithEligibleCandidates();
    const parsed = parseVisaOracleEvaluateResponse(response);
    expect(parsed.decision.state).toBe("HUMAN_REVIEW_REQUIRED");
    expect(parsed.decision.candidates).toHaveLength(2);
    expect(parsed.display.candidates).toHaveLength(2);
  });

  it("still forbids a quote on HUMAN_REVIEW_REQUIRED even when it carries candidates (contract C1)", () => {
    const response = makeHumanReviewWithEligibleCandidates();
    response.decision.quotes = [
      {
        quote_id: "66666666-6666-4666-8666-666666666666",
        product_version_id: response.decision.candidates[0].product_version_id,
        product_code: response.decision.candidates[0].product_code,
        status: "AVAILABLE",
        currency: "IDR",
        amount: 1_000_000,
        pricing_key: { category: "visa", item_key: "D12" },
        catalog_version: "2026.08",
        catalog_sha256: "b".repeat(64),
        row_sha256: "c".repeat(64),
        quoted_at: "2026-08-03T04:00:00Z",
        valid_until: null,
        reason_code: "PRICE_AVAILABLE",
      },
    ];
    expect(() => parseVisaOracleEvaluateResponse(response)).toThrowError(
      expect.objectContaining({ code: "RESPONSE_INVARIANT" }),
    );
  });

  it("still forbids a candidate on every OTHER non-SUPPORTED_CANDIDATES state (the relaxation is HUMAN_REVIEW_REQUIRED-only)", () => {
    for (const state of [
      "NEEDS_INPUT",
      "NO_SUPPORTED_PATH",
      "TEMPORARILY_UNAVAILABLE",
    ] as const) {
      const response = makeVisaOracleResponse(state);
      const supported = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
      response.decision.candidates = supported.decision.candidates;
      response.display.candidates = supported.display.candidates;
      expect(
        () => parseVisaOracleEvaluateResponse(response),
        state,
      ).toThrowError(expect.objectContaining({ code: "RESPONSE_INVARIANT" }));
    }
  });

  it("forbids evaluated identity and seals on outage responses", () => {
    const evaluated = makeVisaOracleResponse();
    const evaluatedDecision = evaluated.decision as unknown as Record<
      string,
      unknown
    >;
    for (const field of [
      "decision_id",
      "public_id",
      "rule_pack",
      "facts_fingerprint",
      "trace_sha256",
      "decision_integrity",
    ] as const) {
      const outage = makeVisaOracleResponse("TEMPORARILY_UNAVAILABLE");
      (outage.decision as unknown as Record<string, unknown>)[field] =
        evaluatedDecision[field];
      expect(() => parseVisaOracleEvaluateResponse(outage), field).toThrowError(
        expect.objectContaining({ code: "RESPONSE_INVARIANT" }),
      );
    }
  });
});
