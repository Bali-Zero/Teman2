import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
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
    status: "upcoming",
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
    status: "none", // No deadline tracked for empty state
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
const { mockPush, mockGetDashboard, mockGetDashboardSummary, mockGetTimeline } =
  vi.hoisted(() => ({
    mockPush: vi.fn(),
    mockGetDashboard: vi.fn(),
    mockGetDashboardSummary: vi.fn(),
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
      getDashboardSummary: mockGetDashboardSummary,
      getTimeline: mockGetTimeline,
    },
  },
}));

// QueryClient wrapper for tests
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, retryDelay: 0 },
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
    mockGetDashboardSummary.mockResolvedValue({
      open_actions: [],
      upcoming_deadlines: [],
      unread_messages: 0,
    });
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
      expect(screen.getByText("Welcome back.")).toBeInTheDocument();
      expect(
        screen.getByText("Here is your Bali life overview."),
      ).toBeInTheDocument();
    });
  });

  it("renders the facts-locked client recap returned by the summary API", async () => {
    mockGetDashboard.mockResolvedValue(createMockDashboard());
    mockGetTimeline.mockResolvedValue({ entries: [] });
    mockGetDashboardSummary.mockResolvedValue({
      open_actions: [],
      upcoming_deadlines: [],
      unread_messages: 0,
      recap: {
        text: "Welcome back. Nothing needs your attention right now.",
        polished: false,
        disclaimer:
          "Summary of your Bali Zero records — not legal advice. Always confirm with your case officer.",
      },
    });

    renderWithQueryClient(<PortalHomePage />);

    expect(await screen.findByText("Your update")).toBeInTheDocument();
    expect(
      screen.getByText("Welcome back. Nothing needs your attention right now."),
    ).toBeInTheDocument();
    expect(screen.getByText(/not legal advice/i)).toBeInTheDocument();
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
      expect(
        screen.getByText(/couldn't load all of your portal information/i),
      ).toBeInTheDocument();
      expect(screen.queryByText("API Error")).not.toBeInTheDocument();
      expect(screen.getByText("Retry")).toBeInTheDocument();
    });
  });

  it("settles a missing client as a safe account-link state with retry", async () => {
    mockGetDashboard
      .mockRejectedValueOnce(
        Object.assign(new Error("Client not found"), { statusCode: 404 }),
      )
      .mockResolvedValueOnce(createEmptyDashboard());
    mockGetTimeline.mockResolvedValue({ entries: [] });

    renderWithQueryClient(<PortalHomePage />);

    expect(
      await screen.findByText("Client profile connection needed"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Client not found")).not.toBeInTheDocument();
    expect(mockGetDashboard).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByText("Immigration")).toBeInTheDocument();
    expect(mockGetDashboard).toHaveBeenCalledTimes(2);
  });

  it("keeps a generic 403 in the authorization error path", async () => {
    mockGetDashboard.mockRejectedValue(
      Object.assign(new Error("Forbidden"), { statusCode: 403 }),
    );
    mockGetTimeline.mockResolvedValue({ entries: [] });

    renderWithQueryClient(<PortalHomePage />);

    expect(
      await screen.findByText("Unable to load dashboard"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Client profile connection needed"),
    ).not.toBeInTheDocument();
    expect(mockGetDashboard).toHaveBeenCalledTimes(1);
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
      expect(screen.getByText("Recent activity")).toBeInTheDocument();
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

    fireEvent.click(screen.getByLabelText("Immigration status"));

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
      expect(screen.getByText("Welcome back.")).toBeInTheDocument();
    });
  });

  // ── WS3 · GARUDA Day Edition (2026-07-24) ────────────────────────────
  // Day-theme token alignment: serif masthead, semantic --state-* tokens
  // for status colors, daylight copper steps for accent text.

  it("renders the day-edition serif masthead (no dark lux gradient)", async () => {
    mockGetDashboard.mockResolvedValue(createMockDashboard());
    mockGetTimeline.mockResolvedValue({ entries: [] });

    renderWithQueryClient(<PortalHomePage />);

    await waitFor(() => {
      const h1 = screen.getByRole("heading", {
        level: 1,
        name: "Welcome back.",
      });
      // Cormorant via the globally wired --font-serif token (inline style)
      expect(h1.style.fontFamily).toContain("--font-serif");
      // The white→gray lux gradient is invisible on paper — must be gone
      expect(h1.className).not.toContain("lux-text-gradient");
      expect(h1.className).toContain("text-[var(--tx-pure)]");
    });
  });

  it("status columns carry the state as an outlined word, not a fill", async () => {
    mockGetDashboard.mockResolvedValue(
      createMockDashboard({
        visa: {
          status: "active",
          type: "KITAS",
          expiryDate: "2025-12-31",
          daysRemaining: 365,
        },
        taxes: {
          status: "attention",
          nextDeadline: "2025-11-15",
          daysToDeadline: 20,
        },
      }),
    );
    mockGetTimeline.mockResolvedValue({ entries: [] });

    renderWithQueryClient(<PortalHomePage />);

    await waitFor(() => {
      // R19: the card is a hairline column; the state is an outlined WORD
      const visaCard = screen.getByLabelText("Immigration status");
      expect(within(visaCard).getByText("Active").className).toContain(
        "text-[var(--state-success)]",
      );
      expect(visaCard.className).not.toContain("crystal-stat-card");

      const taxCard = screen.getByLabelText("Tax status");
      expect(within(taxCard).getByText("Needs you").className).toContain(
        "text-[var(--bz-copper-text)]",
      );
      expect(taxCard.innerHTML).not.toContain("var(--state-danger)");
    });
  });

  it("quick-stats chips are hairline pills with a copper icon, no state fill", async () => {
    mockGetDashboard.mockResolvedValue(
      createMockDashboard({
        documents: { total: 10, pending: 2 },
        messages: { unread: 3 },
      }),
    );
    mockGetTimeline.mockResolvedValue({ entries: [] });

    renderWithQueryClient(<PortalHomePage />);

    await waitFor(() => {
      const docsChip = screen.getByRole("button", {
        name: /2 documents pending/,
      });
      expect(docsChip.className).toContain("rounded-full");
      expect(docsChip.className).toContain("border-[var(--tx-tertiary)]");
      expect(docsChip.getAttribute("style")).toBeNull();
      expect(docsChip.innerHTML).toContain("text-[var(--bz-copper)]");

      const msgsChip = screen.getByRole("button", {
        name: /3 unread messages/,
      });
      expect(msgsChip.className).toContain("rounded-full");
      expect(msgsChip.getAttribute("style")).toBeNull();
      expect(msgsChip.innerHTML).toContain("text-[var(--bz-copper)]");
    });
  });

  it("action items carry the priority as a word in an outlined pill", async () => {
    mockGetDashboard.mockResolvedValue(
      createMockDashboard({
        documents: { total: 0, pending: 0 },
        actions: [
          {
            id: "a1",
            title: "Pay invoice",
            description: "Invoice due",
            priority: "high",
            type: "billing",
            href: "/portal/billing",
          },
        ],
      }),
    );
    mockGetTimeline.mockResolvedValue({ entries: [] });

    renderWithQueryClient(<PortalHomePage />);

    await waitFor(() => {
      const actionBtn = screen.getByText("Pay invoice").closest("button");
      expect(actionBtn).not.toBeNull();
      expect(actionBtn?.className).not.toContain("var(--state-danger)");
      expect(
        within(actionBtn as HTMLElement).getByText("Needs you").className,
      ).toContain("text-[var(--bz-copper-text)]");
    });
  });
  it("renders the leading matter as the next move and the rest as an index", async () => {
    mockGetDashboard.mockResolvedValue(createEmptyDashboard());
    mockGetTimeline.mockResolvedValue({ entries: [] });
    mockGetDashboardSummary.mockResolvedValue({
      open_actions: [
        {
          id: 142,
          title: "Second Home Visa renewal",
          type: "visa_e33",
          pending_from_client: "bank statement, last three months",
          status: "waiting_documents",
        },
        {
          id: 98,
          title: "LKPM Q3 report",
          type: "lkpm",
          pending_from_client: null,
          status: "in_progress",
        },
      ],
      upcoming_deadlines: [],
      unread_messages: 0,
    });

    renderWithQueryClient(<PortalHomePage />);

    expect(await screen.findByText(/Your next move/)).toBeInTheDocument();
    expect(
      screen.getByText("bank statement, last three months").className,
    ).toContain("text-[var(--bz-copper-text)]");
    // the second matter is a numbered index row, not a second card
    const indexRow = screen.getByText("LKPM Q3 report").closest("button");
    expect(indexRow).not.toBeNull();
    expect(within(indexRow as HTMLElement).getByText("02")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Open matter" }));
    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/portal/matters/142");
    });
  });
});
