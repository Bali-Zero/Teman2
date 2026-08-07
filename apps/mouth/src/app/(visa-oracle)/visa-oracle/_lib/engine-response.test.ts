import { describe, expect, it } from "vitest";
import {
  parseVisaOracleEvaluateResponse,
  requireEngineResponse,
  VisaOracleResponseError,
} from "./engine-response";
import { makeVisaOracleResponse } from "./visa-oracle-test-fixture";

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
