import type { ReactNode } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import {
  QueryClient,
  QueryClientProvider,
  type QueryKey,
} from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  dashboardApi,
  type DashboardData,
} from "@/lib/api/dashboard/dashboard.api";
import {
  dashboardQueryKey,
  removeDashboardQueries,
  useDashboardData,
} from "./useDashboardData";

vi.mock("@/lib/api/dashboard/dashboard.api", () => ({
  dashboardApi: {
    getDashboardSummary: vi.fn(),
  },
}));
vi.mock("@/lib/logger");

const summaryFor = (email: string): DashboardData => ({
  user: { email, role: "team", is_admin: false },
  stats: {
    activeCases: 0,
    criticalDeadlines: 0,
    pendingInvoices: 0,
    whatsappUnread: 0,
    emailUnread: 0,
    hoursWorked: "0h 0m",
  },
  data: {
    practices: [],
    interactions: [],
    email: { connected: false, unread_count: 0 },
  },
  system_status: "healthy",
  last_updated: Date.now(),
});

const createClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

const wrapperFor =
  (queryClient: QueryClient) =>
  ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

describe("useDashboardData identity isolation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("disables the summary query until an authenticated identity exists", () => {
    const queryClient = createClient();

    const { result } = renderHook(() => useDashboardData(""), {
      wrapper: wrapperFor(queryClient),
    });

    expect(result.current.user.email).toBe("");
    expect(dashboardApi.getDashboardSummary).not.toHaveBeenCalled();
  });

  it("uses a fresh cache entry after an account switch", async () => {
    const queryClient = createClient();
    vi.mocked(dashboardApi.getDashboardSummary)
      .mockResolvedValueOnce(summaryFor("admin@example.test"))
      .mockResolvedValueOnce(summaryFor("member@example.test"));

    const { result, rerender } = renderHook(
      ({ identity }) => useDashboardData(identity),
      {
        initialProps: { identity: "admin@example.test" },
        wrapper: wrapperFor(queryClient),
      },
    );

    await waitFor(() => {
      expect(result.current.user.email).toBe("admin@example.test");
    });

    rerender({ identity: "member@example.test" });

    expect(result.current.user.email).toBe("");
    await waitFor(() => {
      expect(result.current.user.email).toBe("member@example.test");
    });
    expect(
      queryClient.getQueryData(dashboardQueryKey("admin@example.test")),
    ).toBeDefined();
    expect(
      queryClient.getQueryData(dashboardQueryKey("member@example.test")),
    ).toBeDefined();
  });

  it("removes only dashboard-family queries on logout", () => {
    const queryClient = createClient();
    const dashboardKeys: QueryKey[] = [
      ["dashboard", "admin@example.test"],
      ["intel-feed", "admin@example.test"],
      ["intake-review-count", "admin@example.test"],
      ["system-pulse", "admin@example.test"],
      ["compliance-radar", "admin@example.test"],
      ["team-stats", "admin@example.test"],
      ["role-metrics", "admin", "admin@example.test"],
    ];
    for (const key of dashboardKeys) {
      queryClient.setQueryData(key, { sensitive: true });
    }
    queryClient.setQueryData(["public-reference"], { retained: true });

    removeDashboardQueries(queryClient);

    for (const key of dashboardKeys) {
      expect(queryClient.getQueryData(key)).toBeUndefined();
    }
    expect(queryClient.getQueryData(["public-reference"])).toEqual({
      retained: true,
    });
  });
});
