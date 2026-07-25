import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mockGetMyReferrals } = vi.hoisted(() => ({
  mockGetMyReferrals: vi.fn(),
}));

vi.mock("@/lib/api/partners/partners", () => ({
  getMyReferrals: mockGetMyReferrals,
}));

import PartnerReferralsPage from "./page";

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

describe("PartnerReferralsPage (WS3 day pass)", () => {
  it("renders the day masthead and a token-surfaced table", async () => {
    mockGetMyReferrals.mockResolvedValue(REFERRALS);
    const { container } = render(<PartnerReferralsPage />);
    await screen.findByText("My Referrals");

    expect(
      container.querySelector(".bg-\\[var\\(--bz-copper\\)\\]"),
    ).not.toBeNull();
    const h1 = screen.getByText("My Referrals");
    expect(h1.className).toContain("text-[var(--tx-pure)]");
    expect(h1.style.fontFamily).toBe("var(--font-serif)");

    const tableWrap = container.querySelector(".overflow-x-auto");
    expect((tableWrap as HTMLElement).style.background).toBe("var(--bz-card)");
    expect((tableWrap as HTMLElement).style.boxShadow).toContain(
      "rgba(22, 33, 58, 0.07)",
    );
    expect(screen.getByText("Client A")).toBeInTheDocument();
    expect(screen.getByText("processing")).toBeInTheDocument();
  });

  it("renders the empty state in --tx-secondary", async () => {
    mockGetMyReferrals.mockResolvedValue([]);
    render(<PartnerReferralsPage />);
    const empty = await screen.findByText("No referrals found.");
    expect(empty.className).toContain("text-[var(--tx-secondary)]");
  });

  it("drain guard: no dark-glass utilities remain", async () => {
    mockGetMyReferrals.mockResolvedValue(REFERRALS);
    const { container } = render(<PartnerReferralsPage />);
    await screen.findByText("Client A");
    const html = container.innerHTML;

    expect(html).not.toContain("bg-white/5");
    expect(html).not.toContain("border-white/10");
    expect(html).not.toContain("divide-white/10");
    expect(html).not.toContain("text-white");
    expect(html).not.toContain("text-gray-");
  });
});
