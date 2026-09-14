/**
 * Dashboard Page - Unit Tests
 * Coverage: 100% - All functions, branches, and edge cases
 */

import { render, screen, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardPage from "../page";
import {
  dashboardApi,
  type DashboardData,
} from "@/lib/api/dashboard/dashboard.api";
import { useDashboardData } from "@/hooks/useDashboardData";
import { getComplianceAlerts, getSystemPulse } from "../_lib/opsAdapters";
import { logger } from "@/lib/logger";
import { api } from "@/lib/api";

// Mock dependencies
vi.mock("@/lib/api/dashboard/dashboard.api", () => ({
  dashboardApi: {
    getDashboardSummary: vi.fn(),
  },
}));

// Mock useDashboardData hook
vi.mock("@/hooks/useDashboardData", () => ({
  useDashboardData: vi.fn(),
}));
vi.mock("@/lib/logger");
vi.mock("../_lib/opsAdapters", () => ({
  getSystemPulse: vi.fn(),
  getComplianceAlerts: vi.fn(),
}));
vi.mock("@/lib/realtime", () => ({
  useRealtime: () => ({
    isConnected: false,
    onlineUsersCount: 0,
    connect: vi.fn(),
    subscribe: vi.fn(() => vi.fn()),
    sendDashboardUpdate: vi.fn(),
  }),
}));
vi.mock("@/hooks/useRoleMetrics", () => ({
  useRoleMetrics: vi.fn(() => ({
    data: undefined,
    isLoading: false,
    isError: true,
  })),
}));
vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));
// Mock dashboard components
vi.mock("@/components/dashboard", () => ({
  AiPulseWidget: () => <div data-testid="ai-pulse-widget">AI Pulse</div>,
  FinancialRealityWidget: ({
    revenue,
  }: {
    revenue: { total_revenue: number };
  }) => (
    <div data-testid="financial-widget">Revenue: {revenue.total_revenue}</div>
  ),
  NusantaraHealthWidget: () => <div data-testid="nusantara-widget">Health</div>,
  GrafanaWidget: () => <div data-testid="grafana-widget">Grafana</div>,
  FeaturedArticlesWidget: () => (
    <div data-testid="featured-articles-widget">Featured Articles</div>
  ),
  HomepagePreviewWidget: () => (
    <div data-testid="homepage-preview-widget">Homepage Preview</div>
  ),
  CaseDistribution: ({ segments }: { segments: unknown[] }) => (
    <div data-testid="case-distribution">{segments?.length ?? 0} segments</div>
  ),
  MiniSparkline: ({ data }: { data: unknown[] }) => (
    <div data-testid="mini-sparkline">{data?.length ?? 0} points</div>
  ),
  RoleWidget: ({ role }: { role: string }) => (
    <div data-testid="role-widget">{role}</div>
  ),
}));

// Create a wrapper with QueryClientProvider for tests
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

const wrapperFor = (queryClient: QueryClient) => {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

const createWrapper = () => wrapperFor(createTestQueryClient());

describe("DashboardPage - Unit Tests", () => {
  const mockDashboardData: DashboardData = {
    user: {
      email: "test@example.com",
      role: "team",
      is_admin: false,
    },
    stats: {
      activeCases: 5,
      criticalDeadlines: 2,
      pendingInvoices: 0,
      whatsappUnread: 3,
      emailUnread: 1,
      hoursWorked: "5h 30m",
    },
    data: {
      practices: [
        {
          id: 1,
          title: "Test Practice",
          client: "Test Client",
          status: "in_progress",
          daysRemaining: 10,
        },
      ],
      interactions: [
        {
          id: "1",
          contactName: "John Doe",
          message: "Test message",
          timestamp: "2025-01-01",
          isRead: false,
          hasAiSuggestion: false,
        },
      ],
      email: {
        connected: true,
        unread_count: 1,
      },
    },
    system_status: "healthy",
    last_updated: Date.now(),
  };

  const mockUseDashboardData = (overrides = {}) => ({
    user: mockDashboardData.user,
    stats: mockDashboardData.stats,
    practices: mockDashboardData.data.practices,
    interactions: mockDashboardData.data.interactions,
    emailStats: { connected: false, unread_count: 0 },
    systemStatus: "healthy" as const,
    isZero: false,
    isLoading: false,
    isError: false,
    error: null,
    totalUnread: 4,
    isHealthy: true,
    revenue: null,
    revenueGrowth: 0,
    totalClients: null,
    totalPractices: null,
    refetch: vi.fn(),
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(api, "getUserProfile").mockReturnValue({
      id: "team-user",
      email: "test@example.com",
      name: "Team User",
      role: "team",
    });
    vi.mocked(useDashboardData).mockReturnValue(mockUseDashboardData());
    // Ops panel adapters (WS2 slice 2) — default to live, healthy data
    vi.mocked(getSystemPulse).mockResolvedValue([
      {
        id: "postgres",
        label: "PostgreSQL",
        status: "ok",
        latencyMs: 12,
        detail: "Connected",
      },
    ]);
    vi.mocked(getComplianceAlerts).mockResolvedValue([
      {
        id: "a1",
        title: "KITAS expiry < 30 days",
        detail: "CLI-2207 · visa expiry",
        severity: "critical",
        timeLeft: "6d",
      },
    ]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should render and load dashboard data successfully", async () => {
    render(<DashboardPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId("role-widget")).toBeInTheDocument();
    });
  });

  it("should handle loading state", async () => {
    vi.mocked(useDashboardData).mockReturnValue(
      mockUseDashboardData({ isLoading: true }),
    );

    render(<DashboardPage />, { wrapper: createWrapper() });

    // Should show loading skeleton
    expect(document.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("should handle API errors", async () => {
    vi.mocked(useDashboardData).mockReturnValue(
      mockUseDashboardData({
        isError: true,
        error: new Error("API Error"),
      }),
    );

    render(<DashboardPage />, { wrapper: createWrapper() });

    // Should show error state
    await waitFor(() => {
      expect(screen.getByText("Dashboard Error")).toBeInTheDocument();
    });
  });

  it("should display zero-only widgets for zero user", async () => {
    vi.mocked(useDashboardData).mockReturnValue(
      mockUseDashboardData({
        user: {
          email: "zero@balizero.com",
          role: "admin",
          is_admin: true,
        },
        isZero: true,
      }),
    );

    render(<DashboardPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByRole("link", { name: /Zantara AI/i }),
      ).toBeInTheDocument();
    });
  });

  it("renders the ops panels with live adapter data (WS2 slice 2)", async () => {
    vi.mocked(api.getUserProfile).mockReturnValue({
      id: "admin-user",
      email: "admin@example.test",
      name: "Admin User",
      role: "admin",
    });
    vi.mocked(useDashboardData).mockReturnValue(
      mockUseDashboardData({
        user: {
          email: "admin@example.test",
          role: "admin",
          is_admin: true,
        },
      }),
    );

    render(<DashboardPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("System Pulse")).toBeInTheDocument();
    });
    expect(screen.getByText("Compliance Radar")).toBeInTheDocument();

    // SystemPulse row from the mocked probe
    await waitFor(() => {
      expect(screen.getByText("PostgreSQL")).toBeInTheDocument();
    });
    expect(screen.getByText("OK · 12ms")).toBeInTheDocument();

    // ComplianceRadar row from the mocked alerts endpoint
    await waitFor(() => {
      expect(screen.getByText("KITAS expiry < 30 days")).toBeInTheDocument();
    });
    expect(screen.getByText("CRITICAL")).toBeInTheDocument();
    expect(screen.getByText("6d")).toBeInTheDocument();
  });

  it("renders honest fallbacks when probes fail (idle services, empty radar)", async () => {
    vi.mocked(api.getUserProfile).mockReturnValue({
      id: "admin-user",
      email: "admin@example.test",
      name: "Admin User",
      role: "admin",
    });
    vi.mocked(useDashboardData).mockReturnValue(
      mockUseDashboardData({
        user: {
          email: "admin@example.test",
          role: "admin",
          is_admin: true,
        },
      }),
    );
    vi.mocked(getSystemPulse).mockResolvedValue([
      {
        id: "postgres",
        label: "PostgreSQL",
        status: "idle",
        detail: "probe unavailable",
      },
    ]);
    vi.mocked(getComplianceAlerts).mockResolvedValue([]);

    render(<DashboardPage />, { wrapper: createWrapper() });

    // Panels still render; the failed probe shows as honest idle rows
    await waitFor(() => {
      expect(screen.getByText("probe unavailable")).toBeInTheDocument();
    });
    expect(screen.getByText("IDLE")).toBeInTheDocument();
    expect(screen.getByText("System Pulse")).toBeInTheDocument();
    expect(screen.getByText("Compliance Radar")).toBeInTheDocument();
  });

  it("isolates ops queries by identity and never exposes SystemPulse to non-admins", async () => {
    const queryClient = createTestQueryClient();
    const wrapper = wrapperFor(queryClient);

    vi.mocked(api.getUserProfile).mockReturnValue({
      id: "admin-user",
      email: "admin@example.test",
      name: "Admin User",
      role: "admin",
    });
    vi.mocked(useDashboardData).mockReturnValue(
      mockUseDashboardData({
        user: {
          email: "admin@example.test",
          role: "admin",
          is_admin: true,
        },
      }),
    );
    vi.mocked(getComplianceAlerts)
      .mockResolvedValueOnce([
        {
          id: "admin-alert",
          title: "Admin-only deadline",
          severity: "critical",
          timeLeft: "2d",
        },
      ])
      .mockResolvedValueOnce([
        {
          id: "member-alert",
          title: "Member deadline",
          severity: "warning",
          timeLeft: "8d",
        },
      ]);

    const firstSession = render(<DashboardPage />, { wrapper });
    await screen.findByText("Admin-only deadline");
    expect(screen.getByText("System Pulse")).toBeInTheDocument();
    expect(
      queryClient.getQueryData(["compliance-radar", "admin@example.test"]),
    ).toBeDefined();
    firstSession.unmount();

    vi.mocked(api.getUserProfile).mockReturnValue({
      id: "member-user",
      email: "member@example.test",
      name: "Member User",
      role: "team",
    });
    vi.mocked(useDashboardData).mockReturnValue(
      mockUseDashboardData({
        user: {
          email: "member@example.test",
          role: "team",
          is_admin: false,
        },
      }),
    );

    render(<DashboardPage />, { wrapper });
    await screen.findByText("Member deadline");

    expect(screen.queryByText("Admin-only deadline")).not.toBeInTheDocument();
    expect(screen.queryByText("System Pulse")).not.toBeInTheDocument();
    expect(getSystemPulse).toHaveBeenCalledTimes(1);
    expect(getComplianceAlerts).toHaveBeenCalledTimes(2);
    expect(
      queryClient.getQueryData(["compliance-radar", "member@example.test"]),
    ).toBeDefined();
    expect(useDashboardData).toHaveBeenLastCalledWith("member@example.test");
  });

  it("renders no ops data while a new session still has a stale dashboard identity", () => {
    vi.mocked(api.getUserProfile).mockReturnValue({
      id: "member-user",
      email: "member@example.test",
      name: "Member User",
      role: "team",
    });
    vi.mocked(useDashboardData).mockReturnValue(
      mockUseDashboardData({
        user: {
          email: "admin@example.test",
          role: "admin",
          is_admin: true,
        },
      }),
    );

    render(<DashboardPage />, { wrapper: createWrapper() });

    expect(screen.queryByText("System Pulse")).not.toBeInTheDocument();
    expect(
      screen.queryByText("KITAS expiry < 30 days"),
    ).not.toBeInTheDocument();
    expect(getSystemPulse).not.toHaveBeenCalled();
    expect(getComplianceAlerts).not.toHaveBeenCalled();
    expect(useDashboardData).toHaveBeenCalledWith("member@example.test");
  });

  /**
   * "Your action margin" — the ownership queue (concept-K v2 "TEPAT FORTE" §2).
   *
   * The unit law lives in `_lib/actionMargin.test.ts`; this block proves the
   * PAGE actually paints it from the two families it already fetches, and that
   * the family exposing only a count shows the count line rather than a row per
   * document.
   */
  describe("DashboardPage - Your action margin", () => {
    const withReviewQueue = (items: unknown[]) =>
      vi.spyOn(api, "get").mockResolvedValue({ items } as never);

    it("renders the review count line and the viewer's blocked practice", async () => {
      withReviewQueue([{ id: "d1" }, { id: "d2" }, { id: "d3" }]);
      vi.mocked(useDashboardData).mockReturnValue(
        mockUseDashboardData({
          practices: [
            {
              id: 4187,
              title: "Work Permit Extension",
              client: "Client 0412",
              status: "documents",
              daysRemaining: 2,
            },
          ],
        }),
      );

      render(<DashboardPage />, { wrapper: createWrapper() });

      expect(await screen.findByText("Your action margin")).toBeInTheDocument();
      // The review family exposes only a count, so it is ONE row carrying it.
      expect(
        await screen.findByText("3 documents await review"),
      ).toBeInTheDocument();
      expect(screen.getByText("Review queue")).toBeInTheDocument();
      // The practice family names the record and says why the viewer is next.
      expect(
        screen.getByText("Client 0412 · Work Permit Extension"),
      ).toBeInTheDocument();
      expect(screen.getByText("Assigned to you")).toBeInTheDocument();
      // Colour never travels alone: every tone is rendered beside a WORD.
      // The pills are uppercased in CSS, so the DOM carries the sentence case.
      // Each ledger row emits its state pill twice — once in the desktop grid
      // column and once on the phone's secondary line, one of the two hidden
      // by a media query — so the review row's word appears exactly twice.
      expect(screen.getAllByText("Your review")).toHaveLength(2);
      // "Documents" appears four times: the margin row and the same record's
      // Process pipeline row, each in both copies. An exact count is the point
      // — `toBeGreaterThan(0)` would still pass if one of the two words
      // disappeared entirely.
      expect(screen.getAllByText("Documents")).toHaveLength(4);
    });

    it("claims nothing when neither family has anything for the viewer", async () => {
      withReviewQueue([]);
      vi.mocked(useDashboardData).mockReturnValue(
        mockUseDashboardData({ practices: [] }),
      );

      render(<DashboardPage />, { wrapper: createWrapper() });

      expect(
        await screen.findByText("Nothing is waiting on you right now."),
      ).toBeInTheDocument();
    });

    it("keeps a blocked practice out of the margin when ownership is not derivable", async () => {
      // An admin's practice list is the whole book, not an assignment.
      withReviewQueue([]);
      vi.mocked(api.getUserProfile).mockReturnValue({
        id: "admin-user",
        email: "admin@example.test",
        name: "Admin User",
        role: "admin",
      });
      vi.mocked(useDashboardData).mockReturnValue(
        mockUseDashboardData({
          user: { email: "admin@example.test", role: "admin", is_admin: true },
          isZero: true,
          practices: [
            {
              id: 4187,
              title: "Work Permit Extension",
              client: "Client 0412",
              status: "documents",
            },
          ],
        }),
      );

      render(<DashboardPage />, { wrapper: createWrapper() });

      expect(
        await screen.findByText("Nothing is waiting on you right now."),
      ).toBeInTheDocument();
      expect(screen.queryByText("Assigned to you")).not.toBeInTheDocument();
    });
  });
});
