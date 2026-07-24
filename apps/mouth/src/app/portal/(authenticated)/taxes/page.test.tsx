import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mockGetTaxOverview, mockToastError } = vi.hoisted(() => ({
  mockGetTaxOverview: vi.fn(),
  mockToastError: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    portal: {
      getTaxOverview: mockGetTaxOverview,
    },
  },
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ error: mockToastError }),
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn() },
}));

vi.mock("@/lib/analytics", () => ({
  trackTaxDashboardViewed: vi.fn(),
}));

import TaxesPage from "./page";

const TAX_DATA = {
  summary: {
    status: "attention",
    totalDue: 4_500_000,
    nextDeadline: new Date(Date.now() + 5 * 86400000).toISOString(),
    daysToDeadline: 5,
    pendingCount: 1,
    overdueCount: 1,
  },
  obligations: [
    {
      id: "ob-1",
      name: "PPh 25 Monthly Installment",
      type: "PPh 25",
      period: "Jul 2026",
      dueDate: new Date(Date.now() + 5 * 86400000).toISOString(),
      status: "pending",
      amount: 4_500_000,
    },
    {
      id: "ob-2",
      name: "PPN Monthly Return",
      type: "PPN",
      period: "Jun 2026",
      dueDate: new Date(Date.now() - 10 * 86400000).toISOString(),
      status: "overdue",
      amount: 2_000_000,
    },
    {
      id: "ob-3",
      name: "PPh 21 Withholding",
      type: "PPh 21",
      period: "Jun 2026",
      dueDate: new Date(Date.now() - 40 * 86400000).toISOString(),
      status: "filed",
    },
  ],
};

async function renderLoaded() {
  mockGetTaxOverview.mockResolvedValue(TAX_DATA);
  const utils = render(<TaxesPage />);
  await screen.findByText("PPh 25 Monthly Installment");
  return utils;
}

describe("TaxesPage", () => {
  it("renders the day masthead and token-driven surfaces (WS3 slice 5)", async () => {
    const { container } = await renderLoaded();

    // Day masthead: copper rule + Cormorant serif headline in --tx-pure.
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Tax Overview");
    expect(heading.style.fontFamily).toBe("var(--font-serif)");
    expect(heading.className).toContain("text-[var(--tx-pure)]");
    expect(
      container.querySelector(
        '[aria-hidden="true"].bg-\\[var\\(--bz-copper\\)\\]',
      ),
    ).not.toBeNull();

    // Card surfaces read theme tokens, not the old dark rgba glass.
    expect(container.innerHTML).toContain("var(--bz-elevated)");
    expect(container.innerHTML).not.toContain("rgba(30,30,35,0.7)");
    expect(container.innerHTML).not.toContain("rgba(255,255,255,0.05)");
  });

  it("maps obligation statuses to the semantic --state-* tokens", async () => {
    await renderLoaded();

    // StatusBadge tone chips: color-mix tint bg + state-token fg.
    const pendingChip = screen.getByText("Pending").closest("div");
    expect(pendingChip?.style.color).toBe("var(--state-warning)");
    expect(pendingChip?.style.background).toContain("color-mix");
    const overdueChip = screen.getByText("Overdue").closest("div");
    expect(overdueChip?.style.color).toBe("var(--state-danger)");
    const filedChip = screen.getByText("Filed").closest("div");
    expect(filedChip?.style.color).toBe("var(--state-success)");
  });

  it("colors the days-to-deadline panel with the danger state token", async () => {
    await renderLoaded();

    // daysToDeadline = 5 → ≤ 7 → --state-danger (icon + number + tint panel).
    const daysNumber = screen.getByText("5");
    expect(daysNumber.style.color).toBe("var(--state-danger)");
    const panel = daysNumber.closest("div")?.parentElement?.parentElement;
    expect(panel?.style.background).toContain("var(--state-danger) 8%");
    expect(panel?.style.borderColor).toContain("var(--state-danger) 30%");
  });

  it("renders countdown chips via the shared token-driven CountdownChip", async () => {
    await renderLoaded();

    // Both deadlines fall in the ≤7d danger window (5d future / 10d overdue).
    const chips = screen
      .getAllByText(/d left|overdue|today/)
      .filter((el) => el.style.background.includes("color-mix"));
    expect(chips.length).toBeGreaterThanOrEqual(2);
    for (const chip of chips) {
      expect(chip.style.color).toBe("var(--state-danger)");
    }
  });

  it("uses the AA daylight copper step for the help notice", async () => {
    await renderLoaded();

    const helpNotice = screen.getByText(/Need help with your taxes/);
    expect(helpNotice.style.color).toBe(
      "var(--bz-copper-text, var(--tx-secondary))",
    );
  });

  it("renders the loading skeleton without hardcoded dark surfaces", () => {
    mockGetTaxOverview.mockReturnValue(new Promise(() => {}));
    const { container } = render(<TaxesPage />);
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    expect(container.innerHTML).not.toContain("rgba(30,30,35,0.7)");
  });

  it("renders the empty state when no tax data is available", async () => {
    mockGetTaxOverview.mockResolvedValue(null);
    render(<TaxesPage />);
    expect(
      await screen.findByText("No tax data available"),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Tax Overview",
    );
  });
});
