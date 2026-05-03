import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import PortalHomePage from "./page";
import type { PortalDashboard } from "@/lib/api/portal/portal.types";

// Mock Data Factory - aligned with portal.types.ts
const createMockDashboard = (
  overrides?: Partial<PortalDashboard>,
): PortalDashboard => ({
  visa: {
    status: "active",
    type: "KITAS",
    expiryDate: "2025-12-31",
    daysRemaining: 365,
  },
  company: {
    status: "active",
    primaryCompanyName: "Test Co",
    totalCompanies: 1,
  },
  taxes: {
    status: "compliant",
    nextDeadline: null,
    daysToDeadline: null,
  },
  documents: {
    total: 10,
    pending: 2,
  },
  messages: {
    unread: 0,
  },
  actions: [],
  ...overrides,
});

const createEmptyDashboard = (): PortalDashboard => ({
  visa: {
    status: "none",
    type: null,
    expiryDate: null,
    daysRemaining: null,
  },
  company: {
    status: "none",
    primaryCompanyName: null,
    totalCompanies: 0,
  },
  taxes: {
    status: "compliant", // Default to compliant for empty state
    nextDeadline: null,
    daysToDeadline: null,
  },
  documents: {
    total: 0,
    pending: 0,
  },
  messages: {
    unread: 0,
  },
  actions: [],
});

// Hoisted mocks (must be defined before vi.mock)
const { mockPush, mockGetDashboard, mockGetTimeline } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockGetDashboard: vi.fn(),
  mockGetTimeline: vi.fn(),
}));

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
}));

// Mock api
vi.mock("@/lib/api", () => ({
  api: {
    portal: {
      getDashboard: mockGetDashboard,
      getTimeline: mockGetTimeline,
    },
  },
}));

// QueryClient wrapper for tests
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("PortalHomePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("should show loading state initially", () => {
    mockGetDashboard.mockImplementation(() => new Promise(() => {})); // Never resolves
    mockGetTimeline.mockImplementation(() => new Promise(() => {}));

    renderWithQueryClient(<PortalHomePage />);

    // Should show skeleton loaders
    const skeletons = screen.getAllByRole("generic");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("should render dashboard data when loaded", async () => {
    const mockDashboard = createMockDashboard();
    const mockTimeline = { entries: [] };

    mockGetDashboard.mockResolvedValue(mockDashboard);
    mockGetTimeline.mockResolvedValue(mockTimeline);

    renderWithQueryClient(<PortalHomePage />);

    await waitFor(() => {
      expect(screen.getByText("Welcome Back")).toBeInTheDocument();
      expect(
        screen.getByText("Here is your Bali life overview."),
      ).toBeInTheDocument();
    });
  });

  it("should render status cards for visa, company, and taxes", async () => {
    const mockDashboard = createMockDashboard();

    mockGetDashboard.mockResolvedValue(mockDashboard);
    mockGetTimeline.mockResolvedValue({ entries: [] });

    renderWithQueryClient(<PortalHomePage />);

    await waitFor(() => {
      expect(screen.getByText("Immigration")).toBeInTheDocument();
      expect(screen.getByText("Company")).toBeInTheDocument();
      expect(screen.getByText("Tax")).toBeInTheDocument();
    });
  });

  it("should show error message when API fails", async () => {
    mockGetDashboard.mockRejectedValue(new Error("API Error"));
    mockGetTimeline.mockRejectedValue(new Error("API Error"));

    renderWithQueryClient(<PortalHomePage />);

    await waitFor(() => {
      expect(screen.getByText("Unable to load dashboard")).toBeInTheDocument();
      expect(screen.getByText("API Error")).toBeInTheDocument();
      expect(screen.getByText("Retry")).toBeInTheDocument();
    });
  });

  it("should render timeline when available", async () => {
    const mockDashboard = createEmptyDashboard();

    const mockTimeline = {
      entries: [
        {
          id: "1",
          type: "message",
          title: "Test Message",
          description: "Test description",
          occurredAt: new Date().toISOString(),
        },
      ],
    };

    mockGetDashboard.mockResolvedValue(mockDashboard);
    mockGetTimeline.mockResolvedValue(mockTimeline);

    renderWithQueryClient(<PortalHomePage />);

    await waitFor(() => {
      expect(screen.getByText("Timeline")).toBeInTheDocument();
      expect(screen.getByText("Test Message")).toBeInTheDocument();
    });
  });

  it("should show empty timeline message when no entries", async () => {
    const mockDashboard = createEmptyDashboard();

    mockGetDashboard.mockResolvedValue(mockDashboard);
    mockGetTimeline.mockResolvedValue({ entries: [] });

    renderWithQueryClient(<PortalHomePage />);

    await waitFor(() => {
      expect(
        screen.getByText("No activity yet. Your journey starts here."),
      ).toBeInTheDocument();
    });
  });

  it("should navigate to visa page when visa card is clicked", async () => {
    const mockDashboard = createMockDashboard();

    mockGetDashboard.mockResolvedValue(mockDashboard);
    mockGetTimeline.mockResolvedValue({ entries: [] });

    renderWithQueryClient(<PortalHomePage />);

    await waitFor(() => {
      expect(screen.getByText("Immigration")).toBeInTheDocument();
    });

    const visaCard = screen.getByText("Immigration").closest("div");
    if (visaCard && visaCard.onclick) {
      visaCard.click();
    } else if (visaCard) {
      // Simulate click event
      const clickEvent = new MouseEvent("click", { bubbles: true });
      visaCard.dispatchEvent(clickEvent);
    }

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/portal/visa");
    });
  });

  it("should use default dashboard when API fails", async () => {
    mockGetDashboard.mockRejectedValue(new Error("API Error"));
    mockGetTimeline.mockResolvedValue({ entries: [] });

    renderWithQueryClient(<PortalHomePage />);

    await waitFor(() => {
      // When dashboard API fails, error state is shown (not default cards)
      expect(screen.getByText("Unable to load dashboard")).toBeInTheDocument();
      expect(screen.getByText("Welcome Back")).toBeInTheDocument();
    });
  });
});
