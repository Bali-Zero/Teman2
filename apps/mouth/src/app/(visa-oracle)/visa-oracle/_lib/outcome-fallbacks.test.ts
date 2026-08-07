import { describe, expect, it } from "vitest";
import {
  buildClientGuardOutcome,
  buildDegradedHumanReviewOutcome,
  buildNetworkFailureOutcome,
} from "./outcome-fallbacks";

describe("non-engine OutcomeViewModel fallbacks", () => {
  it("marks a client guard as a local hold with no decision or candidates", () => {
    const outcome = buildClientGuardOutcome({
      code: "UNREPRESENTABLE_REVIEW_FACT",
      assumptions: [{ id: "a", questionId: "review_gate", editable: true }],
    });
    expect(outcome).toMatchObject({
      state: "TEMPORARILY_UNAVAILABLE",
      provenance: "CLIENT_GUARD",
      assessment: null,
      candidates: [],
      pathsRemaining: 0,
      outage: {
        code: "UNREPRESENTABLE_REVIEW_FACT",
        retryable: false,
      },
    });
    expect(outcome.assumptions).toHaveLength(1);
    expect(outcome.nextSteps).toHaveLength(3);
  });

  it("marks a network failure separately and allows a safe retry", () => {
    const outcome = buildNetworkFailureOutcome({ code: "TIMEOUT" });
    expect(outcome).toMatchObject({
      provenance: "NETWORK_FAILURE",
      assessment: null,
      candidates: [],
      outage: { code: "TIMEOUT", retryable: true },
    });
  });

  it("can disable retry when server idempotency is unavailable", () => {
    const outcome = buildNetworkFailureOutcome({
      code: "IDEMPOTENCY_UNAVAILABLE",
      retryable: false,
    });
    expect(outcome.outage.retryable).toBe(false);
  });

  it("reports a degraded HUMAN_REVIEW_REQUIRED honestly — never as no evaluation submitted", () => {
    const outcome = buildDegradedHumanReviewOutcome({
      assumptions: [{ id: "a", questionId: "review_gate", editable: true }],
    });
    expect(outcome).toMatchObject({
      state: "HUMAN_REVIEW_REQUIRED",
      provenance: "CLIENT_GUARD",
      assessment: null,
      candidates: [],
      pathsRemaining: 1,
    });
    expect(outcome.assumptions).toHaveLength(1);
    expect(outcome.nextSteps).toHaveLength(3);
    expect(outcome.reviewReasons).toHaveLength(1);
    expect(outcome.reviewReasons[0].sourceIds).toEqual([]);
    for (const text of Object.values(outcome.reviewReasons[0].message)) {
      expect(text.toLowerCase()).not.toContain("no evaluation was submitted");
    }
  });
});
