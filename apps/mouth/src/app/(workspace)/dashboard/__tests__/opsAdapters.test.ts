/**
 * Ops panel adapter tests — WS2 slice 2.
 * Contract under test: honest mapping from the real backend DTOs, and
 * degradation to idle/empty — never fabrication — on any failure.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { getSystemPulse, getComplianceAlerts } from "../_lib/opsAdapters";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn() },
}));

const mockedGet = vi.mocked(api.get);

function healthDto(checks: Record<string, unknown>) {
  return {
    overall_status: "ok",
    timestamp: "2026-07-22T00:00:00Z",
    checks,
    system_metrics: {},
    service_registry: {},
  };
}

function checkDto(
  status: string,
  latency_ms: number | null = 10,
  message = "ok",
) {
  return { name: "x", status, message, latency_ms, timestamp: 1 };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("getSystemPulse", () => {
  it("maps backend checks to service rows (status, latency, detail)", async () => {
    mockedGet.mockResolvedValue(
      healthDto({
        Database: checkDto("ok", 12.4, "Connected"),
        Qdrant: checkDto("warning", 88.6, "Slow search"),
        Redis: checkDto("error", null, "Connection refused"),
        API: checkDto("skipped", null, "Self-check skipped"),
        "CRM Models": checkDto("ok", 3.2, "Loaded"),
        "Collection Manager": checkDto("ok", 5, "11 collections"),
      }),
    );
    const services = await getSystemPulse();
    expect(services).toHaveLength(6);
    const byId = Object.fromEntries(services.map((s) => [s.id, s]));
    expect(byId.postgres).toMatchObject({
      label: "PostgreSQL",
      status: "ok",
      latencyMs: 12, // rounded, real measured value
      detail: "Connected",
    });
    expect(byId.qdrant.status).toBe("warn");
    expect(byId.qdrant.latencyMs).toBe(89);
    expect(byId.redis.status).toBe("down");
    expect(byId["backend-api"].status).toBe("idle"); // skipped → idle
  });

  it("omits latencyMs when the probe measured none and never synthesizes barPct", async () => {
    mockedGet.mockResolvedValue(
      healthDto({ Database: checkDto("ok", null, "Connected") }),
    );
    const services = await getSystemPulse();
    const pg = services.find((s) => s.id === "postgres")!;
    expect(pg.latencyMs).toBeUndefined();
    expect(pg.barPct).toBeUndefined();
  });

  it("marks services missing from the response as idle 'no probe wired'", async () => {
    mockedGet.mockResolvedValue(
      healthDto({ Database: checkDto("ok", 9, "Connected") }),
    );
    const services = await getSystemPulse();
    const redis = services.find((s) => s.id === "redis")!;
    expect(redis).toMatchObject({ status: "idle", detail: "no probe wired" });
  });

  it("returns all-idle 'probe unavailable' on total fetch failure, no throw", async () => {
    mockedGet.mockRejectedValue(new Error("HTTP 403"));
    const services = await getSystemPulse();
    expect(services).toHaveLength(6);
    for (const s of services) {
      expect(s.status).toBe("idle");
      expect(s.detail).toBe("probe unavailable");
      expect(s.latencyMs).toBeUndefined();
    }
  });

  it("maps unknown check statuses to idle, never guesses health", async () => {
    mockedGet.mockResolvedValue(
      healthDto({ Database: checkDto("degraded", 5, "???") }),
    );
    const services = await getSystemPulse();
    expect(services.find((s) => s.id === "postgres")!.status).toBe("idle");
  });
});

describe("getComplianceAlerts", () => {
  const row = (
    id: string,
    severity: string,
    days: number,
    status = "pending",
    over: Record<string, unknown> = {},
  ) => ({
    alert_id: id,
    client_id: 2207,
    category: "visa_expiry",
    severity,
    status,
    deadline: "2026-08-01",
    days_until: days,
    message_en: `Alert ${id}`,
    message_it: null,
    suggested_action: null,
    ...over,
  });

  it("maps rows to radar props, soonest deadline first, capped at limit", async () => {
    mockedGet.mockResolvedValue({
      items: [
        row("a1", "critical", 30),
        row("a2", "urgent", 6),
        row("a3", "info", 21),
      ],
      limit: 50,
      offset: 0,
    });
    const alerts = await getComplianceAlerts(6);
    expect(alerts.map((a) => a.id)).toEqual(["a2", "a3", "a1"]);
    expect(alerts[0]).toMatchObject({
      title: "Alert a2",
      detail: "CLI-2207 · visa expiry",
      severity: "urgent",
      timeLeft: "6d",
    });
  });

  it("drops closed-out statuses (resolved/expired)", async () => {
    mockedGet.mockResolvedValue({
      items: [
        row("a1", "critical", 6, "resolved"),
        row("a2", "critical", 7, "expired"),
        row("a3", "warning", 8, "acknowledged"),
        row("a4", "info", 9, "sent"),
      ],
      limit: 50,
      offset: 0,
    });
    const alerts = await getComplianceAlerts(6);
    expect(alerts.map((a) => a.id)).toEqual(["a3", "a4"]);
  });

  it("renders negative days_until as 'overdue' and unknown severity as info", async () => {
    mockedGet.mockResolvedValue({
      items: [row("a1", "purple", -3)],
      limit: 50,
      offset: 0,
    });
    const alerts = await getComplianceAlerts(6);
    expect(alerts[0].timeLeft).toBe("overdue");
    expect(alerts[0].severity).toBe("info");
  });

  it("falls back to the category as title when message_en is null", async () => {
    mockedGet.mockResolvedValue({
      items: [row("a1", "info", 4, "pending", { message_en: null })],
      limit: 50,
      offset: 0,
    });
    const alerts = await getComplianceAlerts(6);
    expect(alerts[0].title).toBe("visa expiry");
  });

  it("returns an empty list on total fetch failure, no throw", async () => {
    mockedGet.mockRejectedValue(new Error("network down"));
    await expect(getComplianceAlerts(6)).resolves.toEqual([]);
  });
});
