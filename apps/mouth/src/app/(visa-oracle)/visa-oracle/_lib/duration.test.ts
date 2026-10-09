import { describe, expect, it } from "vitest";
import { buildEngineOutcome } from "./engine-adapter";
import {
  VisaOracleResponseError,
  parseVisaOracleEvaluateResponse,
} from "./engine-response";
import { makeVisaOracleResponse } from "./visa-oracle-test-fixture";

const OPTIONS = [
  {
    days: 365,
    amount_idr: 11_000_000,
    selected: false,
    status: "AVAILABLE",
    reason_code: "DURATION_OPTION",
    pricing_key: "E31A_1Y",
  },
  {
    days: 730,
    amount_idr: 15_000_000,
    selected: true,
    status: "AVAILABLE",
    reason_code: "DURATION_OPTION",
    pricing_key: "E31A_2Y",
  },
];

function responseWith(extra: Record<string, unknown>) {
  const response = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
  Object.assign(response.display.candidates[0], extra);
  return response;
}

describe("duration pricing — response guard", () => {
  it("parses a response with none of the duration fields", () => {
    expect(() =>
      parseVisaOracleEvaluateResponse(
        makeVisaOracleResponse("SUPPORTED_CANDIDATES"),
      ),
    ).not.toThrow();
  });

  it("parses the full set of duration fields", () => {
    expect(() =>
      parseVisaOracleEvaluateResponse(
        responseWith({
          selected_duration_days: 730,
          duration_options: OPTIONS,
          extension_required: false,
        }),
      ),
    ).not.toThrow();
  });

  it("accepts a null amount and null optional fields", () => {
    const options = [{ ...OPTIONS[0], amount_idr: null }, OPTIONS[1]];
    expect(() =>
      parseVisaOracleEvaluateResponse(
        responseWith({
          selected_duration_days: null,
          duration_options: options,
          extension_required: null,
        }),
      ),
    ).not.toThrow();
  });

  it("rejects a malformed option", () => {
    expect(() =>
      parseVisaOracleEvaluateResponse(
        responseWith({
          selected_duration_days: 730,
          duration_options: [{ ...OPTIONS[1], selected: "yes" }],
        }),
      ),
    ).toThrow(VisaOracleResponseError);
  });
});

describe("duration pricing — adapter mapping", () => {
  function candidateOf(extra: Record<string, unknown>) {
    const outcome = buildEngineOutcome(responseWith(extra));
    if (outcome.state !== "SUPPORTED_CANDIDATES") throw new Error("state");
    return outcome.candidates[0];
  }

  it("maps the three fields onto the candidate", () => {
    expect(
      candidateOf({
        selected_duration_days: 730,
        duration_options: OPTIONS,
        extension_required: true,
      }).duration,
    ).toEqual({
      selectedDays: 730,
      options: [
        { days: 365, amountIdr: 11_000_000, selected: false },
        { days: 730, amountIdr: 15_000_000, selected: true },
      ],
      extensionRequired: true,
    });
  });

  it("carries no duration when the engine omits selected_duration_days", () => {
    const candidate = candidateOf({ duration_options: OPTIONS });
    expect(candidate.duration).toBeUndefined();
    expect("duration" in candidate).toBe(false);
  });
});
