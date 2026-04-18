import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";
import React from "react";
import { useProcessTimeline } from "./useProcessTimeline";

// Mock the api module the hook depends on.
vi.mock("@/lib/api", () => ({
  api: {
    get: vi.fn(),
  },
}));

import { api } from "@/lib/api";

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
    {children}
  </SWRConfig>
);

const validResp = {
  success: true,
  data: {
    practice_id: 42,
    practice_name: "Test Practice",
    practice_category: "visa",
    current_status: "on_process",
    assigned_to: null,
    start_date: null,
    completion_date: null,
    expiry_date: null,
    steps: [
      {
        status: "inquiry",
        label: "Inquiry",
        completed: true,
        is_current: false,
        changed_at: null,
        changed_by: null,
      },
    ],
  },
};

describe("useProcessTimeline", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns parsed data on success", async () => {
    vi.mocked(api.get).mockResolvedValue(validResp as never);

    const { result } = renderHook(() => useProcessTimeline("42"), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());

    expect(result.current.data?.practice_id).toBe(42);
    expect(result.current.data?.steps).toHaveLength(1);
    expect(result.current.error).toBeUndefined();
    expect(vi.mocked(api.get)).toHaveBeenCalledWith(
      "/api/portal/process/42/timeline",
    );
  });

  it("surfaces schema drift as error", async () => {
    // Wrong shape — missing required `data` fields; Zod parse must throw.
    vi.mocked(api.get).mockResolvedValue({
      success: true,
      data: { version: 99 },
    } as never);

    const { result } = renderHook(() => useProcessTimeline("42"), { wrapper });
    await waitFor(() => expect(result.current.error).toBeTruthy());
    expect(result.current.data).toBeUndefined();
  });

  it("does not fetch when practiceId is null", () => {
    vi.mocked(api.get).mockResolvedValue(validResp as never);

    const { result } = renderHook(() => useProcessTimeline(null), { wrapper });

    expect(result.current.data).toBeUndefined();
    expect(vi.mocked(api.get)).not.toHaveBeenCalled();
  });

  it("surfaces non-success response as error", async () => {
    vi.mocked(api.get).mockResolvedValue({
      success: false,
      data: validResp.data,
    } as never);

    const { result } = renderHook(() => useProcessTimeline("42"), { wrapper });
    await waitFor(() => expect(result.current.error).toBeTruthy());
    expect(result.current.error?.message).toBe(
      "Timeline response not successful",
    );
    expect(result.current.data).toBeUndefined();
  });
});
