/**
 * Tests for process timeline Zod schemas.
 *
 * Verifies that schemas match the actual shape emitted by
 * `GET /api/portal/process/{practice_id}/timeline` defined in
 * `apps/backend-rag/backend/app/routers/portal_process_timeline.py`.
 */

import { describe, expect, it } from "vitest";

import {
  ProcessStep,
  ProcessStepState,
  ProcessTimelineData,
  ProcessTimelineResponse,
} from "./process";

// A minimal valid response mirroring the BE single-step fallback path
// (when `practice_status_log` has no rows, the router fabricates one step
// from `practice.status` + `practice.start_date`).
const minimalResponse = {
  success: true,
  data: {
    practice_id: 42,
    practice_name: "KITAS Working Visa",
    practice_category: "immigration",
    current_status: "on_process",
    assigned_to: "asya@balizero.com",
    start_date: "2026-04-01",
    completion_date: null,
    expiry_date: null,
    steps: [
      {
        status: "on_process",
        label: "On Process",
        completed: false,
        is_current: true,
        changed_at: "2026-04-01",
        changed_by: null,
      },
    ],
  },
};

describe("ProcessTimelineResponse", () => {
  it("parses a valid minimal response", () => {
    const parsed = ProcessTimelineResponse.parse(minimalResponse);
    expect(parsed.success).toBe(true);
    expect(parsed.data.practice_id).toBe(42);
    expect(parsed.data.steps).toHaveLength(1);
    expect(parsed.data.steps[0].status).toBe("on_process");
    expect(parsed.data.steps[0].is_current).toBe(true);
  });

  it("parses a multi-step history response (history rows path)", () => {
    const multi = {
      success: true,
      data: {
        practice_id: 101,
        practice_name: "PMA Setup",
        practice_category: "company",
        current_status: "completed",
        assigned_to: null,
        start_date: "2026-01-10",
        completion_date: "2026-03-30",
        expiry_date: null,
        steps: [
          {
            status: "inquiry",
            label: "Inquiry",
            completed: true,
            is_current: false,
            changed_at: "2026-01-10 09:00:00+00:00",
            changed_by: "damar@balizero.com",
          },
          {
            status: "sending_invoice",
            label: "Sending Invoice",
            completed: true,
            is_current: false,
            changed_at: "2026-01-12 11:30:00+00:00",
            changed_by: "asya@balizero.com",
          },
          {
            status: "completed",
            label: "Completed",
            completed: false,
            is_current: true,
            changed_at: "2026-03-30 16:45:00+00:00",
            changed_by: "zero@balizero.com",
          },
        ],
      },
    };
    const parsed = ProcessTimelineResponse.parse(multi);
    expect(parsed.data.steps).toHaveLength(3);
    expect(parsed.data.steps[2].is_current).toBe(true);
  });

  it("rejects an unknown state", () => {
    const bad = {
      ...minimalResponse,
      data: {
        ...minimalResponse.data,
        current_status: "fictional_state",
      },
    };
    const result = ProcessTimelineResponse.safeParse(bad);
    expect(result.success).toBe(false);
  });

  it("rejects a malformed response (wrong top-level shape)", () => {
    // No `data` wrapper, no `success` — just a bare array.
    const malformed = [{ status: "inquiry", label: "Inquiry" }];
    const result = ProcessTimelineResponse.safeParse(malformed);
    expect(result.success).toBe(false);

    // Missing required `steps` array inside `data`.
    const noSteps = {
      success: true,
      data: {
        practice_id: 1,
        current_status: "inquiry",
        // steps missing
      },
    };
    const result2 = ProcessTimelineResponse.safeParse(noSteps);
    expect(result2.success).toBe(false);
  });

  it("ProcessStepState.options exhaustively matches BE-emitted status strings", () => {
    // Canonical states from practice_state_machine.py VALID_TRANSITIONS keys.
    const canonical = [
      "inquiry",
      "waiting_documents",
      "sending_invoice",
      "on_process",
      "completed",
      "cancelled",
    ];
    // Legacy states in LEGACY_STATE_MAP (router may emit these from
    // historical practice_status_log rows).
    const legacy = [
      "quotation_sent",
      "payment_pending",
      "waiting_payment",
      "in_progress",
      "submitted_to_gov",
      "approved",
    ];
    const expected = [...canonical, ...legacy].sort();
    const actual = [...ProcessStepState.options].sort();
    expect(actual).toEqual(expected);
  });

  it("rejects a negative or non-integer practice_id", () => {
    const negative = {
      ...minimalResponse,
      data: { ...minimalResponse.data, practice_id: -5 },
    };
    expect(ProcessTimelineResponse.safeParse(negative).success).toBe(false);

    const floaty = {
      ...minimalResponse,
      data: { ...minimalResponse.data, practice_id: 3.14 },
    };
    expect(ProcessTimelineResponse.safeParse(floaty).success).toBe(false);

    const stringy = {
      ...minimalResponse,
      data: { ...minimalResponse.data, practice_id: "42" },
    };
    expect(ProcessTimelineResponse.safeParse(stringy).success).toBe(false);
  });

  it("handles optional/nullable fields in a step (null, undefined, absent)", () => {
    // All-null timestamps + user.
    const allNull = ProcessStep.parse({
      status: "inquiry",
      label: "Inquiry",
      completed: false,
      is_current: true,
      changed_at: null,
      changed_by: null,
    });
    expect(allNull.changed_at).toBeNull();
    expect(allNull.changed_by).toBeNull();

    // Fields entirely absent — BE single-step fallback uses `.get()` which
    // may omit `changed_by` from the dict entirely.
    const absent = ProcessStep.parse({
      status: "completed",
      label: "Completed",
      completed: true,
      is_current: false,
    });
    expect(absent.changed_at).toBeUndefined();
    expect(absent.changed_by).toBeUndefined();

    // Data-level optional/nullable fields.
    const minData = ProcessTimelineData.parse({
      practice_id: 7,
      current_status: "inquiry",
      steps: [],
    });
    expect(minData.assigned_to).toBeUndefined();
    expect(minData.practice_name).toBeUndefined();
    expect(minData.start_date).toBeUndefined();
  });
});
