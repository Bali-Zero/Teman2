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
    pricing_key: { category: "visa", item_key: "E31A_1Y" },
  },
  {
    days: 730,
    amount_idr: 15_000_000,
    selected: true,
    status: "AVAILABLE",
    reason_code: "DURATION_OPTION",
    pricing_key: { category: "visa", item_key: "E31A_2Y" },
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

  it.each([
    ["a non-increasing day list", [OPTIONS[1], OPTIONS[0]], 365],
    [
      "two selected options",
      [{ ...OPTIONS[0], selected: true }, OPTIONS[1]],
      730,
    ],
    ["a selected option that is not selected_duration_days", OPTIONS, 365],
    ["a malformed option", [{ ...OPTIONS[1], selected: "yes" }], 730],
  ])(
    "drops the whole duration block for %s, never crashing",
    (_name, options, days) => {
      const parsed = parseVisaOracleEvaluateResponse(
        responseWith({
          selected_duration_days: days,
          duration_options: options,
          extension_required: false,
        }),
      );
      const candidate = parsed.display.candidates[0];
      expect(candidate.selected_duration_days).toBeUndefined();
      expect(candidate.duration_options).toBeUndefined();
      expect(candidate.extension_required).toBeUndefined();
    },
  );

  it("drops extension_required: true when there are no options", () => {
    const parsed = parseVisaOracleEvaluateResponse(
      responseWith({ extension_required: true }),
    );
    expect(parsed.display.candidates[0].extension_required).toBeUndefined();
  });
});

describe("duration pricing — adapter mapping", () => {
  function candidateOf(extra: Record<string, unknown>) {
    const outcome = buildEngineOutcome(responseWith(extra));
    if (outcome.state !== "SUPPORTED_CANDIDATES") throw new Error("state");
    return outcome.candidates[0];
  }

  it("carries no duration when the engine omits selected_duration_days", () => {
    const candidate = candidateOf({ duration_options: OPTIONS });
    expect(candidate.duration).toBeUndefined();
    expect("duration" in candidate).toBe(false);
  });
});

describe("duration pricing — the quote must belong to the selected option", () => {
  function quote(
    item: string,
    amount: number,
    productId: string,
    code: string,
  ) {
    return {
      quote_id: "55555555-5555-4555-8555-555555555555",
      product_version_id: productId,
      product_code: code,
      status: "AVAILABLE",
      currency: "IDR",
      amount,
      pricing_key: { category: "visa", item_key: item },
      catalog_version: "2026.08",
      catalog_sha256: "b".repeat(64),
      row_sha256: "c".repeat(64),
      quoted_at: "2026-08-03T04:00:00Z",
      valid_until: null,
      reason_code: "PRICE_AVAILABLE",
    };
  }

  function candidateWith(quotes: (id: string, code: string) => unknown[]) {
    const response = responseWith({
      selected_duration_days: 730,
      duration_options: OPTIONS,
      extension_required: false,
    });
    const candidate = response.display.candidates[0];
    candidate.pricing = {
      status: "AVAILABLE",
      reason_code: "PRICE_AVAILABLE",
      evaluated_at: "2026-08-03T04:00:00Z",
      catalog_last_updated: "2026-08-03",
      catalog_sha256: "b".repeat(64),
      row_sha256: "c".repeat(64),
    };
    response.decision.quotes = quotes(
      candidate.product_version_id,
      candidate.product_code,
    ) as never;
    const outcome = buildEngineOutcome(response);
    if (outcome.state !== "SUPPORTED_CANDIDATES") throw new Error("state");
    return outcome.candidates[0];
  }

  it("shows price and permit together when the quote is the selected option's", () => {
    const candidate = candidateWith((id, code) => [
      quote("E31A_2Y", 15_000_000, id, code),
    ]);
    expect(candidate.price).toMatchObject({
      status: "AVAILABLE",
      amount: 15_000_000,
    });
    expect(candidate.duration).toEqual({
      selectedDays: 730,
      options: [
        { days: 365, amountIdr: 11_000_000, selected: false },
        { days: 730, amountIdr: 15_000_000, selected: true },
      ],
      extensionRequired: false,
    });
  });

  it("picks the selected option's quote when the engine sent several", () => {
    const candidate = candidateWith((id, code) => [
      quote("E31A_1Y", 11_000_000, id, code),
      quote("E31A_2Y", 15_000_000, id, code),
    ]);
    expect(candidate.price).toMatchObject({
      status: "AVAILABLE",
      amount: 15_000_000,
    });
    expect(candidate.duration?.selectedDays).toBe(730);
  });

  it.each([
    ["another option's pricing key", "E31A_1Y", 15_000_000],
    ["the right key with another amount", "E31A_2Y", 11_000_000],
  ])(
    "falls back to the advisor line, with no permit label, for %s",
    (_name, item, amount) => {
      const candidate = candidateWith((id, code) => [
        quote(item, amount, id, code),
      ]);
      expect(candidate.price.status).not.toBe("AVAILABLE");
      if (candidate.price.status === "AVAILABLE") throw new Error("price");
      expect(candidate.price.message?.en).toBe(
        "The price for this path is confirmed by a Bali Zero advisor.",
      );
      expect(candidate.duration).toBeUndefined();
    },
  );
});
