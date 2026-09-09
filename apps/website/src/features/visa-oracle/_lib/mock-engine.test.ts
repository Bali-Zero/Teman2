import { describe, expect, it } from "vitest";
import { PREVIEW_STATES, createPreviewHarnessState } from "./mock-engine";

describe("preview state harness — never a recommendation authority", () => {
  it("covers all five UI states without accepting applicant facts", () => {
    expect(PREVIEW_STATES).toEqual([
      "SUPPORTED_CANDIDATES",
      "NEEDS_INPUT",
      "HUMAN_REVIEW_REQUIRED",
      "NO_SUPPORTED_PATH",
      "TEMPORARILY_UNAVAILABLE",
    ]);
  });

  it.each(PREVIEW_STATES)(
    "%s is assessment-less and always carries zero candidates",
    (state) => {
      expect(createPreviewHarnessState(state)).toMatchObject({
        provenance: "PREVIEW",
        assessment: null,
        state,
        candidates: [],
      });
    },
  );

  it.each(PREVIEW_STATES)(
    "%s exposes unavailable price/timeline and no invented documents",
    (state) => {
      const preview = createPreviewHarnessState(state);
      expect(preview.content).toEqual({
        price: { status: "UNAVAILABLE" },
        timeline: { status: "UNAVAILABLE" },
        documents: { status: "UNKNOWN", items: [] },
      });
    },
  );

  it("is deterministic state scaffolding", () => {
    expect(createPreviewHarnessState("NEEDS_INPUT")).toEqual(
      createPreviewHarnessState("NEEDS_INPUT"),
    );
  });
});
