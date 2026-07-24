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

  it("danger states use the semantic --state-danger token", () => {
    expect(STATE_COLORS.cancelled.fg).toContain("--state-danger");
  });

  it("success states use the semantic --state-success token", () => {
    expect(STATE_COLORS.completed.fg).toContain("--state-success");
    expect(STATE_COLORS.approved.fg).toContain("--state-success");
  });

  it("warning states use the semantic --state-warning token", () => {
    expect(STATE_COLORS.waiting_documents.fg).toContain("--state-warning");
    expect(STATE_COLORS.payment_pending.fg).toContain("--state-warning");
  });

  it("in-flight states use the semantic --state-info token", () => {
    expect(STATE_COLORS.on_process.fg).toContain("--state-info");
    expect(STATE_COLORS.in_progress.fg).toContain("--state-info");
    expect(STATE_COLORS.submitted_to_gov.fg).toContain("--state-info");
  });

  it("money-in-flight states read copper text with the slice-1 fallback", () => {
    expect(STATE_COLORS.sending_invoice.fg).toContain("--bz-copper-text");
    expect(STATE_COLORS.sending_invoice.fg).toContain("--tx-secondary");
    expect(STATE_COLORS.quotation_sent.fg).toContain("--bz-copper-text");
  });
});
