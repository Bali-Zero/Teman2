import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { usePortalDashboard } from "./usePortal";

const { mockGetDashboard } = vi.hoisted(() => ({
  mockGetDashboard: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    portal: {
      getDashboard: mockGetDashboard,
    },
  },
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retryDelay: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

describe("usePortalDashboard retry policy", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does not retry an expected 404 client-state response", async () => {
    mockGetDashboard.mockRejectedValue(
      Object.assign(new Error("Client not found"), { statusCode: 404 }),
    );

    const { result } = renderHook(() => usePortalDashboard(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(mockGetDashboard).toHaveBeenCalledTimes(1);
  });

  it("continues retrying a transient 5xx response", async () => {
    mockGetDashboard
      .mockRejectedValueOnce(
        Object.assign(new Error("Service unavailable"), { statusCode: 503 }),
      )
      .mockResolvedValueOnce({});

    const { result } = renderHook(() => usePortalDashboard(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockGetDashboard).toHaveBeenCalledTimes(2);
  });

  it("continues retrying a transient timeout", async () => {
    mockGetDashboard
      .mockRejectedValueOnce(new Error("Request timeout"))
      .mockResolvedValueOnce({});

    const { result } = renderHook(() => usePortalDashboard(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockGetDashboard).toHaveBeenCalledTimes(2);
  });
});
