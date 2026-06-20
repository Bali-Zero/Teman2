import { describe, expect, it } from "vitest";

import { classifyResolvedDecideError } from "./decide-error";

describe("classifyResolvedDecideError", () => {
  it("treats an already-routed (filed) 409 as already_filed", () => {
    // The exact backend detail surfaced verbatim into Error.message by the api client.
    expect(
      classifyResolvedDecideError(
        "Proposal must be review_claimed (status=routed).",
      ),
    ).toBe("already_filed");
  });

  it("treats an already-rejected 409 as already_rejected", () => {
    expect(
      classifyResolvedDecideError(
        "Proposal must be review_claimed (status=rejected).",
      ),
    ).toBe("already_rejected");
  });

  it("does NOT swallow a still-claimable / unexpected status (stays on error path)", () => {
    // e.g. review_pending — the proposal is still actionable, a real conflict.
    expect(
      classifyResolvedDecideError(
        "Proposal must be review_claimed (status=review_pending).",
      ),
    ).toBeNull();
  });

  it("does NOT swallow a different 409 (lease expired)", () => {
    expect(
      classifyResolvedDecideError("Claim lease expired - re-claim first."),
    ).toBeNull();
  });

  it("does NOT swallow a generic network / 500 failure", () => {
    expect(classifyResolvedDecideError("HTTP 500")).toBeNull();
    expect(classifyResolvedDecideError("Failed to fetch")).toBeNull();
  });

  it("is null-safe", () => {
    expect(classifyResolvedDecideError(undefined)).toBeNull();
    expect(classifyResolvedDecideError(null)).toBeNull();
    expect(classifyResolvedDecideError("")).toBeNull();
  });
});
