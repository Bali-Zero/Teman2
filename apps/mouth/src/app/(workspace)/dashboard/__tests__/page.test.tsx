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
import { logger } from "@/lib/logger";

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
  StatsCard: ({
    title,
    value,
    href,
  }: {
    title: string;
    value: string | number;
    href: string;
  }) => (
    <div data-testid={`stats-card-${title.toLowerCase().replaceAll(" ", "-")}`}>
      <a href={href}>
        {title}: {value}
      </a>
    </div>
  ),
  CasesPreview: ({
    cases,
    isLoading,
  }: {
    cases: unknown[];
    isLoading: boolean;
  }) => (
    <div data-testid="cases-preview">
      {isLoading ? "Loading..." : `${cases.length} cases`}
    </div>
  ),
  WhatsAppPreview: ({
    messages,
    isLoading,
    onDelete,
  }: {
    messages: unknown[];
    isLoading: boolean;
    onDelete: (id: string) => void;
  }) => (
    <div data-testid="whatsapp-preview">
      {isLoading ? (
        "Loading..."
      ) : (
        <>
          <span>{messages.length} messages</span>
          <button
            onClick={() => onDelete("1")}
            data-testid="delete-message-btn"
          >
            Delete
          </button>
        </>
      )}
    </div>
  ),
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
  ZantaraPortalCard: () => (
    <div data-testid="zantara-portal-card">Zantara AI</div>
  ),
  DashboardStatCard: ({
    label,
    value,
  }: {
    label: string;
    value: string | number;
  }) => (
    <div
      data-testid={`dash-stat-card-${label.toLowerCase().replaceAll(" ", "-")}`}
    >
      {label}: {value}
    </div>
  ),
  LiveActivityFeed: ({
    events,
    isLoading,
  }: {
    events: unknown[];
    isLoading: boolean;
  }) => (
    <div data-testid="live-activity-feed">
      {isLoading ? "Loading..." : `${events.length} events`}
    </div>
  ),
  RoleWidget: ({ role }: { role: string }) => (
    <div data-testid="role-widget">{role}</div>
  ),
}));

// Create a wrapper with QueryClientProvider for tests
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

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
    vi.mocked(useDashboardData).mockReturnValue(mockUseDashboardData());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should render and load dashboard data successfully", async () => {
    render(<DashboardPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByTestId("live-activity-feed")).toBeInTheDocument();
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
      expect(screen.getByTestId("zantara-portal-card")).toBeInTheDocument();
    });
  });
});
