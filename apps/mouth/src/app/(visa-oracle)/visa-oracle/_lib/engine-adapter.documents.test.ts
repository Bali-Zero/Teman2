import { describe, expect, it, vi } from "vitest";

const emitVisaOracleTelemetry = vi.hoisted(() => vi.fn());
vi.mock("./telemetry", () => ({ emitVisaOracleTelemetry }));

import { buildEngineOutcome } from "./engine-adapter";
import { parseVisaOracleEvaluateResponse } from "./engine-response";
import { makeVisaOracleResponse } from "./visa-oracle-test-fixture";
import recorded from "./fixtures/documentation-catalogue.recorded.json";

type Block = ReturnType<
  typeof makeVisaOracleResponse
>["display"]["candidates"][number]["documentation"];

function responseWith(code: string, documentation: Block) {
  const response = makeVisaOracleResponse();
  response.decision.candidates[0].product_code = code;
  response.display.candidates[0].product_code = code;
  response.display.candidates[0].documentation = documentation;
  return response;
}

function documentsOf(response: ReturnType<typeof makeVisaOracleResponse>) {
  const outcome = buildEngineOutcome(parseVisaOracleEvaluateResponse(response));
  expect(outcome.state).toBe("SUPPORTED_CANDIDATES");
  if (outcome.state !== "SUPPORTED_CANDIDATES")
    throw new Error("unexpected state");
  return outcome.candidates[0].documents;
}

describe("a recorded backend documentation block reaches the result page", () => {
  it("lists the E33F checklist, penjamin letter first, in both languages", () => {
    expect(recorded.E33F.status).toBe("AVAILABLE");
    const documents = documentsOf(responseWith("E33F", recorded.E33F as Block));
    expect(documents.length).toBe(
      recorded.E33F.requirements.length + recorded.E33F.checklist.length,
    );
    expect(documents[0].label).toEqual({
      en: "Sponsorship letter from the sponsor (surat penjaminan)",
      id: "Surat penjaminan dari penjamin",
    });
    expect(documents.every((d) => d.status === "REQUIRED")).toBe(true);
    expect(documents.every((d) => d.label.en && d.label.id)).toBe(true);
  });

  it("shows no list for an E31B candidate whose documentation stays UNKNOWN", () => {
    expect(recorded.E31B.status).toBe("UNKNOWN");
    expect(documentsOf(responseWith("E31B", recorded.E31B as Block))).toEqual(
      [],
    );
  });

  it("still refuses an AVAILABLE block with no item and an UNKNOWN block with items", () => {
    const empty = responseWith("E33F", {
      ...recorded.E33F,
      requirements: [],
      checklist: [],
    } as Block);
    expect(() => parseVisaOracleEvaluateResponse(empty)).toThrowError(
      expect.objectContaining({ code: "RESPONSE_INVARIANT" }),
    );
    const listed = responseWith("E31B", {
      ...recorded.E33F,
      status: "UNKNOWN",
    } as Block);
    expect(() => parseVisaOracleEvaluateResponse(listed)).toThrowError(
      expect.objectContaining({ code: "RESPONSE_INVARIANT" }),
    );
  });
});
