import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mockGetCompanyDetail, mockToastError } = vi.hoisted(() => ({
  mockGetCompanyDetail: vi.fn(),
  mockToastError: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    portal: {
      getCompanyDetail: mockGetCompanyDetail,
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
  useParams: () => ({ id: "42" }),
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
}));

import CompanyDetailPage from "./page";

const COMPANY = {
  id: 42,
  name: "PT Example Nusantara",
  type: "PT PMA",
  status: "active" as const,
  isPrimary: true,
  address: "JALAN TEST 1, KELURAHAN X, KECAMATAN Y, KABUPATEN BADUNG, BALI",
  nib: "9120107642215",
  npwp: "01.234.567.8-901.000",
  aktaNo: "AHU-TEST-01",
  aktaDate: "2020-03-15",
  skNumber: "SK-TEST-01",
  authorizedCapital: "Rp 10B",
  directors: ["Test Director"],
  shareholders: [{ name: "Test Shareholder", pct: 100 }],
  documents: [{ id: "doc1", name: "Akta.pdf" }],
  licenses: [
    {
      id: "l1",
      name: "NIB License",
      status: "active" as const,
      expiryDate: "2027-01-01",
      daysRemaining: 400,
    },
    {
      id: "l2",
      name: "Environment Permit",
      status: "expiring" as const,
      expiryDate: "2026-08-01",
      daysRemaining: 45,
    },
  ],
};

async function renderLoaded() {
  mockGetCompanyDetail.mockResolvedValue(COMPANY);
  const utils = render(<CompanyDetailPage />);
  await screen.findByRole("heading", {
    level: 1,
    name: /PT Example Nusantara/,
  });
  return utils;
}

describe("CompanyDetailPage (WS3 day pass)", () => {
  it("renders the editorial hero with token-driven text", async () => {
    await renderLoaded();

    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading.className).toContain("text-[var(--kbli-text-primary)]");

    // Eyebrow reads the AA copper small-text step, not the dark-theme accent.
    const eyebrow = screen.getByText("Company Profile");
    expect(eyebrow.className).toContain("--bz-copper-text");
  });

  it("renders license cards on the theme surface with shared StatusBadge states", async () => {
    const { container } = await renderLoaded();

    // License section renders (licenses are below the fold — lazy chunk).
    const nibLicense = await screen.findByText("NIB License");
    const card = nibLicense.closest("div")?.parentElement
      ?.parentElement as HTMLElement;
    expect(card.style.background).toBe("var(--bz-card)");
    expect(card.style.borderColor).toBe("var(--bz-border)");
    expect(container.innerHTML).not.toContain("rgba(30,30,35,0.7)");

    // Statuses reuse the shared StatusBadge on --state-* tokens
    // (active → success, expiring → warning). "Active" also appears as a
    // hero StatusChip, so scope the query to the license card.
    const activeBadge = within(card).getByText("Active").closest("div");
    expect(activeBadge?.style.color).toBe("var(--state-success)");
    expect(activeBadge?.style.background).toContain("color-mix");
    const expiringBadge = screen.getByText("Expiring").closest("div");
    expect(expiringBadge?.style.color).toBe("var(--state-warning)");
  });

  it("renders hero status chips as hairline state-tone pills (no tint fills)", async () => {
    await renderLoaded();

    // Chips sit directly on paper, where a 12% tint fill sinks success/
    // warning fg below 4.5:1 — hairline border + bare state fg instead.
    const activeChip = screen.getByText("Active", {
      selector: "span.uppercase",
    });
    expect(activeChip.style.color).toBe("var(--state-success)");
    expect(activeChip.style.border).toContain("color-mix");
    expect(activeChip.style.background).toBe("");

    const typeChip = screen.getByText("PT PMA", { selector: "span.uppercase" });
    expect(typeChip.style.color).toBe(
      "var(--bz-copper-text, var(--tx-secondary))",
    );
  });

  it("drain guard: no hardcoded hex colors anywhere in the page output", async () => {
    const { container } = await renderLoaded();
    // Wait for the lazy sections so the guard covers the full tree.
    await screen.findByText("NIB License");
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it("renders the not-found empty state for a missing company", async () => {
    mockGetCompanyDetail.mockResolvedValue(null);
    render(<CompanyDetailPage />);
    expect(await screen.findByText("Company not found")).toBeInTheDocument();
  });

  it("shows a toast when loading fails", async () => {
    mockGetCompanyDetail.mockRejectedValue(new Error("boom"));
    render(<CompanyDetailPage />);
    await screen
      .findByText("Company not found", {}, { timeout: 3000 })
      .catch(() => null);
    expect(mockToastError).toHaveBeenCalledWith(
      "Failed to load company details",
      "Please try again later",
    );
  });
});
