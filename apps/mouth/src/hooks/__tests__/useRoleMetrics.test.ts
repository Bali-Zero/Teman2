import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useRoleMetrics } from "../useRoleMetrics";

// Mock the api module
vi.mock("@/lib/api", () => ({
  api: {
    request: vi.fn(),
  },
}));

import { api } from "@/lib/api";

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
}

describe("useRoleMetrics", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns isLoading true initially", () => {
    vi.mocked(api.request).mockResolvedValue({} as never);
    const { result } = renderHook(() => useRoleMetrics("team", "user-123"), {
      wrapper: makeWrapper(),
    });
    expect(result.current.isLoading).toBe(true);
  });

  it("returns data on success", async () => {
    const mockData = {
      role: "team",
      metrics: {
        assigned_cases: 5,
        prossima_scadenza: null,
        doc_mancanti: 2,
        clienti_assegnati: 8,
        stalled_count: 1,
      },
      alerts: [],
    };
    vi.mocked(api.request).mockResolvedValue(mockData);

    const { result } = renderHook(() => useRoleMetrics("team", "user-123"), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.data).toEqual(mockData);
    expect(result.current.isError).toBe(false);
  });

  it("returns isError true on failure", async () => {
    vi.mocked(api.request).mockRejectedValue(new Error("network error"));

    const { result } = renderHook(
      () => useRoleMetrics("accounting", "user-456"),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.isError).toBe(true);
    expect(result.current.data).toBeUndefined();
  });

  it("calls correct API endpoint with role and userId", async () => {
    vi.mocked(api.request).mockResolvedValue({} as never);

    renderHook(() => useRoleMetrics("tax", "user-789"), {
      wrapper: makeWrapper(),
    });

    await waitFor(() =>
      expect(vi.mocked(api.request)).toHaveBeenCalledWith(
        "/api/dashboard/role-metrics?role=tax&user_id=user-789",
      ),
    );
  });
});
