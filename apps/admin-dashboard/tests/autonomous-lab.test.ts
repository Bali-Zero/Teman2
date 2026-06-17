import { afterEach, describe, expect, it, vi } from "vitest";

import {
  labSnapshot,
  loadAutonomousLabControlRoomData,
} from "@/lib/autonomous-lab";

describe("loadAutonomousLabControlRoomData", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("falls back when the backend returns no run previews", async () => {
    vi.stubEnv("AUTONOMOUS_LAB_BACKEND_URL", "http://lab-backend.test");
    vi.stubEnv("AUTONOMOUS_LAB_API_KEY", "test-key");
    const scheduler = {
      version: "autonomous-lab-v1-h24-scheduler",
      updated_at: "2026-06-17T00:00:00+00:00",
      enabled: true,
      db_available: false,
      placement: {
        machine_role: "pro_runtime",
        can_enqueue: true,
        can_claim_runs: true,
        can_consume_outbox: true,
        heavy_work_destination: "local Pro runtime",
        reason: "test scheduler",
      },
      tick_interval_seconds: 60,
      worker_id: "lab-worker:test",
      state: "db_unavailable",
      can_tick: false,
      next_tick_not_before: "2026-06-17T00:01:00+00:00",
      next_action: "attach the runtime database before ticking the worker",
      tick_mode: "bounded_single_tick",
      autonomous_execution_allowed: false,
      manual_promotion_required: true,
      safeguards: ["single_tick_only", "db_required"],
    };

    const fetchMock = vi.fn(async (input: unknown) => {
      const endpoint = String(input).split("/").pop();
      const payload =
        endpoint === "status"
          ? labSnapshot
          : endpoint === "runs"
            ? { runs: [] }
            : endpoint === "scheduler"
              ? scheduler
              : {};

      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const data = await loadAutonomousLabControlRoomData();

    expect(data.source).toBe("fallback");
    expect(data.backendError).toBe("backend returned no lab run previews");
    expect(data.runs).toHaveLength(1);
    expect(data.runs[0]?.checkpoints.length).toBeGreaterThan(0);
    expect(data.scheduler.state).toBe("db_unavailable");
  });
});
