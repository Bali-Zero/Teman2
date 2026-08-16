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

  it("renders the pinned gold-oracle HUMAN_REVIEW_REQUIRED baseline for a matched persona", () => {
    const outcome = buildPreviewOutcome(
      {
        category: "remote",
        work_payer: "unsure",
        remote_compensation: "no",
        remote_clients: "foreign",
        review_gate: "none",
      },
      new Date("2026-08-03T00:00:00.000Z"),
    );

    expect(outcome).toMatchObject({
      state: "HUMAN_REVIEW_REQUIRED",
      provenance: "PREVIEW",
      assessment: null,
      candidates: [],
      sources: [],
      reviewReasons: [{ code: "DISCLOSED_UNCERTAINTY_REVIEW" }],
    });
  });

  it("still falls back to the honest zero-candidate hold outside the pinned subset", () => {
    const outcome = buildPreviewOutcome(
      { category: "remote" },
      new Date("2026-08-03T00:00:00.000Z"),
    );
    expect(outcome.state).toBe("TEMPORARILY_UNAVAILABLE");
  });
});
