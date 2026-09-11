import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  sessionState: "authenticated" as
    "pending" | "authenticated" | "anonymous" | "unknown",
  api: {
    // Pre-cure production code still calls this directly (class-audit #9,
    // not yet migrated at RED time) — fixed `true`, never the thing a test
    // asserts against. `sessionState` above is what drives the gate.
    isAuthenticated: vi.fn().mockReturnValue(true),
    get: vi.fn(),
    isAdmin: vi.fn(),
  },
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock("@/lib/api", () => ({ api: mocks.api }));
vi.mock("@/lib/logger", () => ({ logger: mocks.logger }));
vi.mock("./useSessionState", () => ({
  useSessionState: () => mocks.sessionState,
}));

import { useCellStatus } from "./useCellStatus";

describe("useCellStatus — session + admin gate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.sessionState = "authenticated";
    mocks.api.isAdmin.mockReturnValue(true);
    mocks.api.get.mockResolvedValue({
      alive: true,
      last_pulse: null,
      recent_pulses: [],
      uptime_24h: {
        green_percent: 100,
        yellow_percent: 0,
        red_percent: 0,
        total_pulses: 0,
      },
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("polls when session is authenticated AND the user is admin", async () => {
    const { result } = renderHook(() => useCellStatus(10000));

    await waitFor(() => expect(mocks.api.get).toHaveBeenCalledTimes(1));
    expect(mocks.api.get).toHaveBeenCalledWith("/api/cell/status");
    await waitFor(() => expect(result.current.loading).toBe(false));
  });

  it("does not poll while the session is still pending", async () => {
    mocks.sessionState = "pending";

    renderHook(() => useCellStatus(10000));
    await Promise.resolve();
    await Promise.resolve();

    expect(mocks.api.get).not.toHaveBeenCalled();
  });

  it("does not poll when the session resolves anonymous", async () => {
    mocks.sessionState = "anonymous";

    renderHook(() => useCellStatus(10000));
    await Promise.resolve();
    await Promise.resolve();

    expect(mocks.api.get).not.toHaveBeenCalled();
  });

  it("does not poll when the session probe is inconclusive (unknown)", async () => {
    mocks.sessionState = "unknown";

    renderHook(() => useCellStatus(10000));
    await Promise.resolve();
    await Promise.resolve();

    expect(mocks.api.get).not.toHaveBeenCalled();
  });

  it("does not poll when authenticated but not an admin", async () => {
    mocks.api.isAdmin.mockReturnValue(false);

    renderHook(() => useCellStatus(10000));
    await Promise.resolve();
    await Promise.resolve();

    expect(mocks.api.get).not.toHaveBeenCalled();
  });
});
