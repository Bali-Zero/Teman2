import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mockGetCompanies, mockToastError, mockPush } = vi.hoisted(() => ({
  mockGetCompanies: vi.fn(),
  mockToastError: vi.fn(),
  mockPush: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    portal: {
      getCompanies: mockGetCompanies,
    },
  },
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ error: mockToastError }),
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn() },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

import CompaniesPage from "./page";

const COMPANIES = [
  {
    id: 11,
    company_id: 22,
    name: "PT Example Nusantara",
    type: "PT PMA",
    status: "active" as const,
    isPrimary: true,
    nib: "9120107642215",
    kbli: "56101,47911",
    directors: ["A", "B"],
    licenses: [
      {
        id: "l1",
        name: "NIB",
        status: "expired" as const,
        expiryDate: "2026-01-01",
      },
    ],
    compliance: [
      {
        id: "c1",
        name: "LKPM Q2",
        dueDate: "2026-07-01",
        status: "overdue" as const,
      },
    ],
  },
  {
    id: 12,
    company_id: 23,
    name: "CV Contoh Kedua",
    type: "CV",
    status: "pending" as const,
    isPrimary: false,
    compliance: [
      {
        id: "c2",
        name: "LKPM Q3",
        dueDate: "2026-10-01",
        status: "completed" as const,
      },
    ],
  },
];

async function renderLoaded() {
  mockGetCompanies.mockResolvedValue(COMPANIES);
  const utils = render(<CompaniesPage />);
  await screen.findByText("PT Example Nusantara");
  return utils;
}

describe("CompaniesPage (WS3 day pass)", () => {
  it("renders the day masthead: copper rule + Cormorant serif in --tx-pure", async () => {
    const { container } = await renderLoaded();

    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Your Companies");
    expect(heading.style.fontFamily).toBe("var(--font-serif)");
    expect(heading.className).toContain("text-[var(--tx-pure)]");
    expect(
      container.querySelector(
        '[aria-hidden="true"].bg-\\[var\\(--bz-copper\\)\\]',
      ),
    ).not.toBeNull();
  });

  it("renders company cards on theme surfaces with state-token statuses", async () => {
    const { container } = await renderLoaded();

    // Card surface reads tokens, not the old dark glass.
    const card = screen.getByRole("button", {
      name: "View PT Example Nusantara details",
    });
    expect(card.style.background).toBe("var(--bz-card)");
    expect(card.style.borderColor).toBe("var(--bz-border)");
    expect(container.innerHTML).not.toContain("rgba(30,30,35,0.7)");
    expect(container.innerHTML).not.toContain("rgba(255,255,255,0.05)");

    // StatusBadge for the company status (active → success, pending → warning).
    const activeBadge = screen.getByText("Active").closest("div");
    expect(activeBadge?.style.color).toBe("var(--state-success)");
    const pendingBadge = screen.getByText("Pending").closest("div");
    expect(pendingBadge?.style.color).toBe("var(--state-warning)");

    // Compliance roll-up renders the shared StatusBadge (overdue → danger).
    const overdueBadge = screen.getByText("Overdue").closest("div");
    expect(overdueBadge?.style.color).toBe("var(--state-danger)");
    expect(overdueBadge?.style.background).toContain("color-mix");

    // License icon reads the danger state token (expired license present).
    const licenseCount = screen.getByText(/1 license/);
    const icon = licenseCount.querySelector("svg");
    expect(icon?.getAttribute("style")).toContain("var(--state-danger)");
  });

  it("renders identifier chips with token-driven hairline patterns", async () => {
    await renderLoaded();

    // NIB chip: glass-rim well + token border, no hardcoded rgba.
    const nibChip = screen.getByText(/NIB 9120107642215/);
    expect(nibChip.style.background).toBe("var(--glass-rim)");
    expect(nibChip.style.border).toContain("var(--bz-border)");

    // KBLI chip: hairline copper border + AA copper text (no tint fill —
    // a 12% copper tint fails AA on both themes, slice-6 finding).
    const kbliChip = screen.getByText(/KBLI 56101/);
    expect(kbliChip.style.color).toBe(
      "var(--bz-copper-text, var(--tx-secondary))",
    );
    expect(kbliChip.style.border).toContain("color-mix");
    expect(kbliChip.style.background).toBe("");
  });

  it("drain guard: no hardcoded hex colors anywhere in the page output", async () => {
    const { container } = await renderLoaded();
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it("routes to the company detail using company_id over the relation id", async () => {
    await renderLoaded();
    screen
      .getByRole("button", { name: "View PT Example Nusantara details" })
      .click();
    expect(mockPush).toHaveBeenCalledWith("/portal/company/22");
  });

  it("renders the empty state when there are no companies", async () => {
    mockGetCompanies.mockResolvedValue([]);
    render(<CompaniesPage />);
    expect(await screen.findByText("No companies yet")).toBeInTheDocument();
  });

  it("shows a toast and keeps the shell quiet when loading fails", async () => {
    mockGetCompanies.mockRejectedValue(new Error("boom"));
    render(<CompaniesPage />);
    await screen.findByRole("heading", { level: 1 });
    expect(mockToastError).toHaveBeenCalledWith(
      "Failed to load companies",
      "Please try again later",
    );
  });
});
