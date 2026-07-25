import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mockGetMyCommissions } = vi.hoisted(() => ({
  mockGetMyCommissions: vi.fn(),
}));

vi.mock("@/lib/api/partners/partners", () => ({
  getMyCommissions: mockGetMyCommissions,
}));

import PartnerCommissionsPage from "./page";

const COMMISSIONS = [
  {
    id: "c1",
    status: "paid",
    practice_type_name: "KITAS New",
    net_amount: 1_500_000,
    gross_amount: 2_000_000,
    withholding_amount: 500_000,
    created_at: "2026-07-10T00:00:00Z",
    paid_at: "2026-07-15T00:00:00Z",
  },
  {
    id: "c2",
    status: "accrued",
    practice_type_name: "Company Setup",
    net_amount: 750_000,
    gross_amount: 1_000_000,
    withholding_amount: 250_000,
    created_at: "2026-07-20T00:00:00Z",
    paid_at: null,
  },
];

async function renderLoaded() {
  mockGetMyCommissions.mockResolvedValue(COMMISSIONS);
  const utils = render(<PartnerCommissionsPage />);
  await screen.findByText("My Commissions");
  return utils;
}

describe("PartnerCommissionsPage (WS3 day pass)", () => {
  it("renders the day masthead: copper rule + serif headline in --tx-pure", async () => {
    const { container } = await renderLoaded();

    expect(
      container.querySelector(".bg-\\[var\\(--bz-copper\\)\\]"),
    ).not.toBeNull();
    const h1 = screen.getByText("My Commissions");
    expect(h1.className).toContain("text-[var(--tx-pure)]");
    expect(h1.style.fontFamily).toBe("var(--font-serif)");
  });

  it("active filter chip uses the darker copper step + --bz-on-warm (AA pair)", async () => {
    await renderLoaded();

    const allChip = screen.getByRole("button", { name: /All \(2\)/ });
    expect(allChip.style.background).toBe("var(--bz-copper-text)");
    expect(allChip.style.color).toBe("var(--bz-on-warm)");

    const idleChip = screen.getByRole("button", { name: /Accrued \(1\)/ });
    expect(idleChip.style.background).toBe("var(--bz-card)");
    expect(idleChip.style.color).toBe("var(--tx-secondary)");
  });

  it("clicking a chip filters the ledger rows", async () => {
    await renderLoaded();

    fireEvent.click(screen.getByRole("button", { name: /Accrued \(1\)/ }));
    expect(screen.queryByText("KITAS New")).not.toBeInTheDocument();
    expect(screen.getByText("Company Setup")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /All \(2\)/ }));
    expect(screen.getByText("KITAS New")).toBeInTheDocument();
  });

  it("status cells render the shared StatusBadge on --state-* tokens", async () => {
    await renderLoaded();

    expect(screen.getByText("Paid").style.color).toBe("var(--state-success)");
    expect(screen.getByText("Accrued").style.color).toBe(
      "var(--state-warning)",
    );
  });

  it("drain guard: no amber chips or dark-glass utilities remain", async () => {
    const { container } = await renderLoaded();
    const html = container.innerHTML;

    expect(html).not.toContain("bg-amber-600");
    expect(html).not.toContain("bg-white/10");
    expect(html).not.toContain("bg-white/5");
    expect(html).not.toContain("border-white/10");
    expect(html).not.toContain("text-white");
    expect(html).not.toContain("text-gray-");
  });
});
