import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { mockGetMe } = vi.hoisted(() => ({ mockGetMe: vi.fn() }));

vi.mock("@/lib/api/partners/partners", () => ({
  getMe: mockGetMe,
}));

import PartnerProfilePage from "./page";

const PARTNER = {
  id: "p1",
  full_name: "Made Example",
  email: "made@example.com",
  phone: "+6281200000000",
  whatsapp: "6281200000000",
  nationality: "Indonesian",
  entity_type: "individual",
  company_name: null,
  work_role: "Consultant",
  onboarding_status: "active",
  commission_tier: "silver",
  tax_withholding_category: "pph21",
  npwp: "01.234.567.8-901.000",
  pdp_consent_at: "2026-01-15T00:00:00Z",
  payment_method: "bank_transfer",
  bank_name: "BCA",
  bank_account_holder: "Made Example",
  bank_account_number: "1234567890",
};

async function renderLoaded(partner = PARTNER) {
  mockGetMe.mockResolvedValue(partner);
  const utils = render(<PartnerProfilePage />);
  await screen.findByText("My Profile");
  return utils;
}

describe("PartnerProfilePage (WS3 day pass)", () => {
  beforeEach(() => {
    mockGetMe.mockReset();
  });

  it("renders the day masthead: copper rule + serif headline in --tx-pure", async () => {
    const { container } = await renderLoaded();

    expect(
      container.querySelector(".bg-\\[var\\(--bz-copper\\)\\]"),
    ).not.toBeNull();
    const h1 = screen.getByText("My Profile");
    expect(h1.className).toContain("text-[var(--tx-pure)]");
    expect(h1.style.fontFamily).toBe("var(--font-serif)");
  });

  it("sections sit on --bz-card with the concept panel shadow", async () => {
    const { container } = await renderLoaded();

    const cards = container.querySelectorAll(".rounded-xl.border.p-6");
    expect(cards.length).toBe(3);
    for (const card of cards) {
      expect((card as HTMLElement).style.background).toBe("var(--bz-card)");
      expect((card as HTMLElement).style.boxShadow).toContain(
        "rgba(22, 33, 58, 0.07)",
      );
    }
  });

  it("onboarding status renders the shared StatusBadge (active → success)", async () => {
    await renderLoaded();

    const chip = screen.getByText("Active");
    expect(chip.style.color).toBe("var(--state-success)");
    expect(chip.style.background).toContain("var(--state-success)");
  });

  it("inactive partners get the danger tone", async () => {
    await renderLoaded({ ...PARTNER, onboarding_status: "inactive" });

    const chip = screen.getByText("Inactive");
    expect(chip.style.color).toBe("var(--state-danger)");
  });

  it("support mailto reads --bz-copper-text (AA small text)", async () => {
    await renderLoaded();

    const link = screen.getByRole("link", { name: "zantara@balizero.com" });
    expect(link.className).toContain("text-[var(--bz-copper-text)]");
  });

  it("drain guard: no dark-glass utilities or amber links remain", async () => {
    const { container } = await renderLoaded();
    const html = container.innerHTML;

    expect(html).not.toContain("bg-white/5");
    expect(html).not.toContain("border-white/10");
    expect(html).not.toContain("text-amber-400");
    expect(html).not.toContain("text-white");
    expect(html).not.toContain("text-gray-");
  });

  it("shows a safe outage state and retries the profile request", async () => {
    mockGetMe
      .mockRejectedValueOnce(new Error("private database detail"))
      .mockResolvedValueOnce(PARTNER);
    render(<PartnerProfilePage />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Profile is temporarily unavailable");
    expect(alert).not.toHaveTextContent("private database detail");

    fireEvent.click(screen.getByRole("button", { name: "Try Again" }));
    expect(await screen.findByText("My Profile")).toBeInTheDocument();
    expect(mockGetMe).toHaveBeenCalledTimes(2);
  });
});
