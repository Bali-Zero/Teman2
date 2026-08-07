import { describe, expect, it } from "vitest";
import { buildPreviewOutcome } from "./preview-adapter";

describe("preview adapter", () => {
  it("is visibly non-authoritative and can never expose a candidate", () => {
    const outcome = buildPreviewOutcome(
      {
        category: "work",
        work_payer: "yes",
        review_gate: "none",
      },
      new Date("2026-08-03T00:00:00.000Z"),
    );

    expect(outcome).toMatchObject({
      state: "TEMPORARILY_UNAVAILABLE",
      provenance: "PREVIEW",
      assessment: null,
      candidates: [],
      sources: [],
      outage: { retryable: false },
    });
    expect(JSON.stringify(outcome)).not.toContain("C1");
  });
});
