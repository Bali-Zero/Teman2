/**
 * Snapshot tests for the frontend mirror of the backend practice state
 * machine. The shape MUST match `VALID_TRANSITIONS` in
 * `apps/backend-rag/backend/services/crm/practice_state_machine.py`.
 *
 * If the backend changes its allowed transitions, these tests fail and
 * the developer must update both files together. This is the cheap
 * drift-detection mechanism that lets us avoid a backend round-trip
 * just to render a dropdown.
 */
import { describe, expect, it } from "vitest";

import {
  ADMIN_ONLY_TRANSITIONS,
  STATUS_LABELS,
  VALID_TRANSITIONS,
  getAllowedNextStatuses,
  type PracticeStatus,
} from "./state-machine";

describe("VALID_TRANSITIONS — backend snapshot", () => {
  it("has exactly 6 states", () => {
    expect(Object.keys(VALID_TRANSITIONS).sort()).toEqual([
      "cancelled",
      "completed",
      "inquiry",
      "on_process",
      "sending_invoice",
      "waiting_documents",
    ]);
  });

  it("has the canonical forward-progress chain", () => {
    expect(VALID_TRANSITIONS.inquiry).toContain("waiting_documents");
    expect(VALID_TRANSITIONS.waiting_documents).toContain("sending_invoice");
    expect(VALID_TRANSITIONS.sending_invoice).toContain("on_process");
    expect(VALID_TRANSITIONS.on_process).toContain("completed");
  });

  it("allows cancellation from every active state", () => {
    expect(VALID_TRANSITIONS.inquiry).toContain("cancelled");
    expect(VALID_TRANSITIONS.waiting_documents).toContain("cancelled");
    expect(VALID_TRANSITIONS.sending_invoice).toContain("cancelled");
    expect(VALID_TRANSITIONS.on_process).toContain("cancelled");
    expect(VALID_TRANSITIONS.completed).toContain("cancelled");
  });

  it("allows reopening a cancelled practice", () => {
    expect(VALID_TRANSITIONS.cancelled).toEqual(["inquiry"]);
  });

  it("rejects skipping the canonical chain", () => {
    // The original bug: inquiry → on_process should NOT be allowed.
    expect(VALID_TRANSITIONS.inquiry).not.toContain("on_process");
    expect(VALID_TRANSITIONS.inquiry).not.toContain("sending_invoice");
    expect(VALID_TRANSITIONS.inquiry).not.toContain("completed");
  });

  it("matches the exact backend table (drift detector)", () => {
    // Byte-for-byte mirror of practice_state_machine.py:20-26
    expect(VALID_TRANSITIONS).toEqual({
      inquiry: ["waiting_documents", "cancelled"],
      waiting_documents: ["sending_invoice", "inquiry", "cancelled"],
      sending_invoice: ["on_process", "waiting_documents", "cancelled"],
      on_process: ["completed", "sending_invoice", "cancelled"],
      completed: ["cancelled"],
      cancelled: ["inquiry"],
    });
  });
});

describe("ADMIN_ONLY_TRANSITIONS — backend snapshot", () => {
  it("matches the backend list", () => {
    expect(ADMIN_ONLY_TRANSITIONS).toEqual([
      ["completed", "cancelled"],
      ["cancelled", "inquiry"],
    ]);
  });
});

describe("STATUS_LABELS", () => {
  it("provides a label for every state", () => {
    for (const state of Object.keys(VALID_TRANSITIONS) as PracticeStatus[]) {
      expect(STATUS_LABELS[state]).toBeTruthy();
    }
  });
});

describe("getAllowedNextStatuses", () => {
  it("includes the current state so the dropdown keeps its selection", () => {
    expect(getAllowedNextStatuses("inquiry")).toContain("inquiry");
    expect(getAllowedNextStatuses("on_process")).toContain("on_process");
  });

  it("returns only legal forward + cancel from inquiry (the original bug case)", () => {
    expect(getAllowedNextStatuses("inquiry").sort()).toEqual([
      "cancelled",
      "inquiry",
      "waiting_documents",
    ]);
  });

  it("hides admin-only transitions for non-admins", () => {
    // From completed, the only allowed transition is to cancelled, which
    // is admin-only — so a non-admin sees ONLY the current state.
    expect(getAllowedNextStatuses("completed", false)).toEqual(["completed"]);
    // From cancelled, the only allowed transition is back to inquiry,
    // also admin-only — non-admins see only the current state.
    expect(getAllowedNextStatuses("cancelled", false)).toEqual(["cancelled"]);
  });

  it("exposes admin-only transitions to admins", () => {
    expect(getAllowedNextStatuses("completed", true)).toEqual([
      "completed",
      "cancelled",
    ]);
    expect(getAllowedNextStatuses("cancelled", true)).toEqual([
      "cancelled",
      "inquiry",
    ]);
  });

  it("does NOT include illegal jumps (regression test for kita.balizero.com bug)", () => {
    const fromInquiry = getAllowedNextStatuses("inquiry");
    expect(fromInquiry).not.toContain("on_process");
    expect(fromInquiry).not.toContain("sending_invoice");
    expect(fromInquiry).not.toContain("completed");
  });

  it("falls back to current-only on unknown / legacy states", () => {
    // The backend has a legacy state map (in_progress → on_process). The
    // frontend may receive a not-yet-normalized value from old data; we
    // keep the current value selectable but offer no transitions until
    // it is normalized.
    expect(getAllowedNextStatuses("in_progress" as PracticeStatus)).toEqual([
      "in_progress",
    ]);
    expect(getAllowedNextStatuses("payment_pending" as PracticeStatus)).toEqual([
      "payment_pending",
    ]);
  });
});
