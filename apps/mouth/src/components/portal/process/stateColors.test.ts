import { describe, it, expect } from "vitest";
import { STATE_COLORS } from "./stateColors";
import { ProcessStepState } from "@/lib/schemas/process";

describe("STATE_COLORS", () => {
  it("has an entry for every ProcessStepState", () => {
    for (const state of ProcessStepState.options) {
      expect(STATE_COLORS[state]).toBeDefined();
    }
  });

  it("each entry has bg/fg/border non-empty strings", () => {
    for (const style of Object.values(STATE_COLORS)) {
      expect(typeof style.bg).toBe("string");
      expect(style.bg).not.toBe("");
      expect(typeof style.fg).toBe("string");
      expect(style.fg).not.toBe("");
      expect(typeof style.border).toBe("string");
      expect(style.border).not.toBe("");
    }
  });

  it("danger states use danger palette with --bz-danger fallback", () => {
    expect(STATE_COLORS.cancelled.fg).toContain("--bz-danger");
  });

  it("success states use success palette", () => {
    expect(STATE_COLORS.completed.fg).toContain("--bz-success");
    expect(STATE_COLORS.approved.fg).toContain("--bz-success");
  });

  it("warning states use warning palette", () => {
    expect(STATE_COLORS.waiting_documents.fg).toContain("--bz-warning");
    expect(STATE_COLORS.payment_pending.fg).toContain("--bz-warning");
  });
});
