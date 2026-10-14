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

  it("reads an optional working-day window and keeps old responses unchanged", () => {
    const old = makeVisaOracleResponse();
    expect(() => parseVisaOracleEvaluateResponse(old)).not.toThrow();

    const available = makeVisaOracleResponse();
    Object.assign(available.display.candidates[0].processing_timeline, {
      status: "AVAILABLE",
      reason_code: "BALI_ZERO_TYPICAL_PROCESSING_TIME",
      anchor_date: "2026-10-09",
      estimated_completion_from: "2026-10-20",
      estimated_completion_to: "2026-10-23",
      working_days_min: 7,
      working_days_max: 10,
    });
    expect(() => parseVisaOracleEvaluateResponse(available)).not.toThrow();

    for (const [min, max] of [
      [10, 7],
      [-1, 3],
      [1.5, 3],
      [3, undefined],
      [undefined, 3],
    ]) {
      const bad = structuredClone(available);
      const line = bad.display.candidates[0].processing_timeline as Record<
        string,
        unknown
      >;
      line.working_days_min = min;
      line.working_days_max = max;
      if (min === undefined) delete line.working_days_min;
      if (max === undefined) delete line.working_days_max;
      expect(() => parseVisaOracleEvaluateResponse(bad)).toThrowError(
        expect.objectContaining({ code: expect.any(String) }),
      );
    }

    const unknownWithWindow = makeVisaOracleResponse();
    Object.assign(unknownWithWindow.display.candidates[0].processing_timeline, {
      working_days_min: 3,
      working_days_max: 5,
    });
    expect(() =>
      parseVisaOracleEvaluateResponse(unknownWithWindow),
    ).toThrowError(expect.objectContaining({ code: "RESPONSE_INVARIANT" }));
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

  it("validates display.candidates[].prohibited_activities (optional, malformed shapes, duplicates allowed)", () => {
    const valid = makeVisaOracleResponse();
    valid.display.candidates[0].prohibited_activities = [
      "overstay",
      "sale_of_goods_or_services",
    ];
    expect(
      parseVisaOracleEvaluateResponse(valid).display.candidates[0]
        .prohibited_activities,
    ).toEqual(["overstay", "sale_of_goods_or_services"]);

    const withoutKey = makeVisaOracleResponse();
    delete (
      withoutKey.display.candidates[0] as unknown as Record<string, unknown>
    ).prohibited_activities;
    expect(
      parseVisaOracleEvaluateResponse(withoutKey).display.candidates[0]
        .prohibited_activities,
    ).toBeUndefined();

    for (const bad of [null, "overstay", 123, [42], [""], ["   "]]) {
      const malformed = makeVisaOracleResponse();
      (
        malformed.display.candidates[0] as unknown as Record<string, unknown>
      ).prohibited_activities = bad;
      expect(() => parseVisaOracleEvaluateResponse(malformed)).toThrowError(
        expect.objectContaining({ code: "MALFORMED_RESPONSE" }),
      );
    }

    const duplicate = makeVisaOracleResponse();
    duplicate.display.candidates[0].prohibited_activities = [
      "overstay",
      "overstay",
    ];
    expect(
      parseVisaOracleEvaluateResponse(duplicate).display.candidates[0]
        .prohibited_activities,
    ).toEqual(["overstay", "overstay"]);
  });

  it("parses valid stay_policy shapes and optional nulls", () => {
    const valid = makeVisaOracleResponse();
    expect(
      parseVisaOracleEvaluateResponse(valid).display.candidates[0].stay_policy,
    ).toEqual(valid.display.candidates[0].stay_policy);

    const withNulls = makeVisaOracleResponse();
    withNulls.display.candidates[0].stay_policy = {
      stay: {
        kind: "VARIABLE_BY_GRANT",
        minimum_days: null,
        maximum_days: 60,
      },
      extension: {
        status: null,
        reason_code: null,
        allowed: false,
        maximum_extensions: 0,
        days_per_extension: null,
      },
    };
    expect(() => parseVisaOracleEvaluateResponse(withNulls)).not.toThrow();

    const notApplicable = makeVisaOracleResponse();
    notApplicable.display.candidates[0].stay_policy = {
      stay: {
        kind: "NOT_APPLICABLE",
        minimum_days: null,
        maximum_days: null,
      },
      extension: {
        status: "UNKNOWN",
        reason_code: "EXTENSION_POLICY_NOT_ENCODED_IN_PACK",
        allowed: false,
        maximum_extensions: 0,
        days_per_extension: null,
      },
    };
    expect(() => parseVisaOracleEvaluateResponse(notApplicable)).not.toThrow();
  });

  it("accepts unknown extra keys on stay_policy, stay, and extension", () => {
    const response = makeVisaOracleResponse();
    const policy = response.display.candidates[0]
      .stay_policy as unknown as Record<string, unknown>;
    policy.extra_policy_key = "forward-compatible";
    (policy.stay as Record<string, unknown>).extra_stay_key = 1;
    (policy.extension as Record<string, unknown>).extra_extension_key = true;
    expect(() => parseVisaOracleEvaluateResponse(response)).not.toThrow();
  });

  it("rejects a display candidate with an absent stay_policy", () => {
    const absent = makeVisaOracleResponse();
    delete (absent.display.candidates[0] as unknown as Record<string, unknown>)
      .stay_policy;
    expect(() => parseVisaOracleEvaluateResponse(absent)).toThrowError(
      expect.objectContaining({ code: "MALFORMED_RESPONSE" }),
    );
  });

  it("rejects malformed stay_policy shapes", () => {
    const corruptions: Array<
      [string, (candidate: Record<string, unknown>) => void]
    > = [
      [
        "allowed as string 'true'",
        (c) => {
          (
            (c.stay_policy as Record<string, unknown>).extension as Record<
              string,
              unknown
            >
          ).allowed = "true";
        },
      ],
      [
        "allowed as number 1",
        (c) => {
          (
            (c.stay_policy as Record<string, unknown>).extension as Record<
              string,
              unknown
            >
          ).allowed = 1;
        },
      ],
      [
        "non-integer maximum_days",
        (c) => {
          (
            (c.stay_policy as Record<string, unknown>).stay as Record<
              string,
              unknown
            >
          ).maximum_days = 365.5;
        },
      ],
      [
        "negative maximum_days",
        (c) => {
          (
            (c.stay_policy as Record<string, unknown>).stay as Record<
              string,
              unknown
            >
          ).maximum_days = -1;
        },
      ],
      [
        "minimum_days greater than maximum_days",
        (c) => {
          const stay = (c.stay_policy as Record<string, unknown>)
            .stay as Record<string, unknown>;
          stay.minimum_days = 730;
          stay.maximum_days = 365;
        },
      ],
      [
        "FIXED_DAYS with null maximum_days",
        (c) => {
          const stay = (c.stay_policy as Record<string, unknown>)
            .stay as Record<string, unknown>;
          stay.kind = "FIXED_DAYS";
          stay.minimum_days = null;
          stay.maximum_days = null;
        },
      ],
      [
        "NOT_APPLICABLE with non-null days",
        (c) => {
          const stay = (c.stay_policy as Record<string, unknown>)
            .stay as Record<string, unknown>;
          stay.kind = "NOT_APPLICABLE";
          stay.minimum_days = 60;
          stay.maximum_days = 60;
        },
      ],
      [
        "unknown stay.kind",
        (c) => {
          (
            (c.stay_policy as Record<string, unknown>).stay as Record<
              string,
              unknown
            >
          ).kind = "OPEN_ENDED";
        },
      ],
      [
        "stay missing",
        (c) => {
          delete (c.stay_policy as Record<string, unknown>).stay;
        },
      ],
      [
        "extension missing",
        (c) => {
          delete (c.stay_policy as Record<string, unknown>).extension;
        },
      ],
      [
        "unknown extension.status",
        (c) => {
          (
            (c.stay_policy as Record<string, unknown>).extension as Record<
              string,
              unknown
            >
          ).status = "MAYBE";
        },
      ],
      [
        "maximum_extensions > 100",
        (c) => {
          (
            (c.stay_policy as Record<string, unknown>).extension as Record<
              string,
              unknown
            >
          ).maximum_extensions = 101;
        },
      ],
      [
        "days_per_extension < 1",
        (c) => {
          (
            (c.stay_policy as Record<string, unknown>).extension as Record<
              string,
              unknown
            >
          ).days_per_extension = 0;
        },
      ],
    ];

    for (const [label, corrupt] of corruptions) {
      const response = makeVisaOracleResponse();
      corrupt(
        response.display.candidates[0] as unknown as Record<string, unknown>,
      );
      expect(
        () => parseVisaOracleEvaluateResponse(response),
        label,
      ).toThrowError(expect.objectContaining({ code: "MALFORMED_RESPONSE" }));
    }
  });
});
