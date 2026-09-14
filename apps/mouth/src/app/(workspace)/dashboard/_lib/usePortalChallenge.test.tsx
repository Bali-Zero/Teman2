import type { ReactNode } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { dashboardApi } from "@/lib/api/dashboard/dashboard.api";
import { usePortalChallenge } from "./usePortalChallenge";

vi.mock("@/lib/api/dashboard/dashboard.api", () => ({
  dashboardApi: {
    getPortalChallenge: vi.fn(),
  },
}));
vi.mock("@/lib/logger");

const createClient = () =>
  new QueryClient({ defaultOptions: { queries: { retry: false } } });

const wrapperFor =
  (queryClient: QueryClient) =>
  ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

describe("usePortalChallenge", () => {
  it("resolves the real contract shape as-is", async () => {
    const response = {
      status: "live" as const,
      window_start: "2026-09-14T00:00:00+08:00",
      window_end: "2026-09-29T23:59:59+08:00",
      timezone: "Asia/Makassar" as const,
      generated_at: "2026-09-14T01:00:00+08:00",
      tiers: [],
      tax_rules: {
        podium_super_bonus_idr: 0,
        best_tax_fallback_idr: 0,
        best_tax_fallback_threshold: 0,
      },
      team_total_activations: 0,
      entries: [],
      recent_activations: [],
    };
    vi.mocked(dashboardApi.getPortalChallenge).mockResolvedValue(response);
    const client = createClient();
    const { result } = renderHook(() => usePortalChallenge("me@example.com"), {
      wrapper: wrapperFor(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(response);
  });

  it("degrades to null on a thrown error (404 while the endpoint is not deployed)", async () => {
    vi.mocked(dashboardApi.getPortalChallenge).mockRejectedValue(
      new Error("404"),
    );
    const client = createClient();
    const { result } = renderHook(() => usePortalChallenge("me@example.com"), {
      wrapper: wrapperFor(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeNull();
  });

  it("degrades to null on a 200 whose body is not a PortalChallengeResponse (e.g. an unmatched-route stub answering {success:true,data:{}})", async () => {
    vi.mocked(dashboardApi.getPortalChallenge).mockResolvedValue({
      success: true,
      data: {},
      // eslint-disable-next-line @typescript-eslint/no-explicit-any -- deliberately malformed to reproduce the crash this guards against
    } as any);
    const client = createClient();
    const { result } = renderHook(() => usePortalChallenge("me@example.com"), {
      wrapper: wrapperFor(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeNull();
  });

  it("degrades to null when entries/tiers/recent_activations are missing but other fields look right", async () => {
    vi.mocked(dashboardApi.getPortalChallenge).mockResolvedValue({
      status: "live",
      team_total_activations: 5,
      tax_rules: {},
      // entries, tiers, recent_activations intentionally absent
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);
    const client = createClient();
    const { result } = renderHook(() => usePortalChallenge("me@example.com"), {
      wrapper: wrapperFor(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeNull();
  });
});
