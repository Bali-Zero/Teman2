import { describe, it, expect } from "vitest";
import { getAllowedTransitions } from "./state-machine";
import type { PracticeState } from "./types";

describe("state-machine wire-vocabulary pin", () => {
  it("uses the literal 'In review' (with a space), matching the backend's PracticeState enum — never 'In_review'", () => {
    // products/garuda-voa/contracts/openapi.yaml PracticeState enum, verified
    // 2026-09-02: [Received, "In review", Blocked, Submitted, Approved,
    // Rejected, Delivered]. The DB column spells it `In_review`; the wire
    // contract does not, and this UI only ever reads the wire value.
    const received = getAllowedTransitions("Received");
    const beginReview = received.find((t) => t.transitionId === "PR-02");
    expect(beginReview?.targetState).toBe("In review");

    const blockedResumingToReview = getAllowedTransitions(
      "Blocked",
      "In review" as PracticeState,
    );
    expect(blockedResumingToReview).toHaveLength(1);
    expect(blockedResumingToReview[0].transitionId).toBe("PR-09");
    expect(blockedResumingToReview[0].targetState).toBe("In review");
  });

  it("narrows Blocked to zero options when resume_target is missing or unrecognized", () => {
    expect(getAllowedTransitions("Blocked", null)).toHaveLength(0);
    expect(getAllowedTransitions("Blocked", undefined)).toHaveLength(0);
  });

  it("returns no transitions for terminal states Rejected and Delivered", () => {
    expect(getAllowedTransitions("Rejected")).toHaveLength(0);
    expect(getAllowedTransitions("Delivered")).toHaveLength(0);
  });
});
