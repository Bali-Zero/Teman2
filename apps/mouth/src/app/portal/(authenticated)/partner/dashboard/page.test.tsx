import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mockGetMe, mockGetMyReferrals, mockGetMyCommissions } = vi.hoisted(
  () => ({
    mockGetMe: vi.fn(),
    mockGetMyReferrals: vi.fn(),
    mockGetMyCommissions: vi.fn(),
  }),
);

vi.mock("@/lib/api/partners/partners", () => ({
  getMe: mockGetMe,
  getMyReferrals: mockGetMyReferrals,
  getMyCommissions: mockGetMyCommissions,
}));

import PartnerDashboardPage from "./page";

const PARTNER = {
  id: "p1",
  full_name: "Made Example",
  email: "made@example.com",
  onboarding_status: "active",
};

const REFERRALS = [
  {
    id: "r1",
    client_display: "Client A",
    service_type: "KITAS",
    process_status: "processing",
    status: "active",
    referred_at: "2026-07-01T00:00:00Z",
    created_at: "2026-07-01T00:00:00Z",
  },
];

const COMMISSIONS = [
  {
    id: "c1",
    status: "paid",
    net_amount: 1_500_000,
    gross_amount: 2_000_000,
    withholding_amount: 500_000,
    created_at: "2026-07-10T00:00:00Z",
    paid_at: "2026-07-15T00:00:00Z",
  },
  {
    id: "c2",
    status: "accrued",
    net_amount: 750_000,
    gross_amount: 1_000_000,
    withholding_amount: 250_000,
    created_at: "2026-07-20T00:00:00Z",
    paid_at: null,
  },
];

async function renderLoaded() {
  mockGetMe.mockResolvedValue(PARTNER);
  mockGetMyReferrals.mockResolvedValue(REFERRALS);
  mockGetMyCommissions.mockResolvedValue(COMMISSIONS);
  const utils = render(<PartnerDashboardPage />);
  await screen.findByText("Partner Dashboard");
  return utils;
}

describe("PartnerDashboardPage (WS3 day pass)", () => {
  it("renders the day masthead: copper rule + serif headline in --tx-pure", async () => {
    const { container } = await renderLoaded();

    const rule = container.querySelector(".bg-\\[var\\(--bz-copper\\)\\]");
    expect(rule).not.toBeNull();

    const h1 = screen.getByText("Partner Dashboard");
    expect(h1.className).toContain("text-[var(--tx-pure)]");
    expect(h1.style.fontFamily).toBe("var(--font-serif)");

    expect(screen.getByText(/Welcome, Made Example/).className).toContain(
      "text-[var(--tx-secondary)]",
    );
  });

  it("stat cards sit on --bz-card with the concept panel shadow and token text", async () => {
    const { container } = await renderLoaded();

    const cards = container.querySelectorAll(".grid .rounded-xl.border");
    expect(cards.length).toBe(3);
    for (const card of cards) {
      expect((card as HTMLElement).style.background).toBe("var(--bz-card)");
      expect((card as HTMLElement).style.borderColor).toBe("var(--bz-border)");
      expect((card as HTMLElement).style.boxShadow).toContain(
        "rgba(22, 33, 58, 0.07)",
      );
    }

    // Totals from the mocked data sources: paid 1.5M, pending (accrued) 750k.
    expect(screen.getByText("Total Earned")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("Referral Count")).toBeInTheDocument();
  });

  it("commission rows render the shared StatusBadge on --state-* tokens", async () => {
    await renderLoaded();

    const paidChip = screen.getByText("Paid");
    expect(paidChip.style.color).toBe("var(--state-success)");
    expect(paidChip.style.background).toContain("var(--state-success)");

    const accruedChip = screen.getByText("Accrued");
    expect(accruedChip.style.color).toBe("var(--state-warning)");
  });

  it("drain guard: no dark-glass utilities remain", async () => {
    const { container } = await renderLoaded();
    const html = container.innerHTML;

    expect(html).not.toContain("text-white");
    expect(html).not.toContain("bg-white/5");
    expect(html).not.toContain("bg-white/10");
    expect(html).not.toContain("border-white/10");
    expect(html).not.toContain("divide-white/10");
    expect(html).not.toContain("text-gray-");
  });

  it("error state reads --state-danger", async () => {
    mockGetMe.mockRejectedValue(new Error("boom"));
    mockGetMyReferrals.mockResolvedValue([]);
    mockGetMyCommissions.mockResolvedValue([]);

    render(<PartnerDashboardPage />);
    const err = await screen.findByText(/Error: boom/);
    expect(err.style.color).toBe("var(--state-danger)");
  });
});
