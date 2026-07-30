import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mockGetVisaStatus, mockToastError } = vi.hoisted(() => ({
  mockGetVisaStatus: vi.fn(),
  mockToastError: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    portal: {
      getVisaStatus: mockGetVisaStatus,
    },
  },
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ error: mockToastError }),
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn() },
}));

import VisaPage from "./page";

function visaFixture(daysRemaining: number) {
  return {
    current: {
      type: "KITAS Investor",
      status: "active" as const,
      issueDate: "2025-01-15",
      expiryDate: "2027-01-15",
      daysRemaining,
      permitNumber: "IMM-TEST-0001",
      sponsor: "PT Example Sponsor",
    },
    documents: [
      {
        id: "d1",
        name: "Passport Scan",
        type: "passport",
        category: "identity",
        status: "verified" as const,
        uploadDate: "2025-01-10",
        size: "1.2 MB",
      },
      {
        id: "d2",
        name: "Sponsor Letter",
        type: "letter",
        category: "legal",
        status: "expired" as const,
        uploadDate: "2024-06-01",
        size: "320 KB",
      },
    ],
    history: [
      {
        id: "h1",
        type: "VITAS",
        period: "2024 — 2025",
        status: "completed" as const,
      },
      {
        id: "h2",
        type: "KITAS Work",
        period: "2023 — 2024",
        status: "expired" as const,
      },
    ],
  };
}

async function renderLoaded(daysRemaining = 200) {
  mockGetVisaStatus.mockResolvedValue(visaFixture(daysRemaining));
  const utils = render(<VisaPage />);
  await screen.findByText("KITAS Investor");
  return utils;
}

describe("VisaPage (WS3 day pass)", () => {
  it("renders the day masthead: copper rule + Cormorant serif in --tx-pure", async () => {
    const { container } = await renderLoaded();

    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Immigration Status");
    expect(heading.style.fontFamily).toBe("var(--font-serif)");
    expect(heading.className).toContain("text-[var(--tx-pure)]");
    expect(
      container.querySelector(
        '[aria-hidden="true"].bg-\\[var\\(--bz-copper\\)\\]',
      ),
    ).not.toBeNull();
  });

  it("renders cards on theme surfaces, not the dark rgba glass", async () => {
    const { container } = await renderLoaded();

    const currentVisa = screen
      .getByText("Current Visa")
      .closest("section") as HTMLElement;
    expect(currentVisa.style.background).toBe("var(--bz-card)");
    expect(currentVisa.style.borderColor).toBe("var(--bz-border)");
    expect(container.innerHTML).not.toContain("rgba(30,30,35,0.7)");
    expect(container.innerHTML).not.toContain("rgba(255,255,255,0.05)");
  });

  it("maps statuses to the semantic --state-* tokens", async () => {
    await renderLoaded(200);

    // Visa status pill → shared StatusBadge (active → success).
    const activeBadge = screen.getByText("Active").closest("div");
    expect(activeBadge?.style.color).toBe("var(--state-success)");
    expect(activeBadge?.style.background).toContain("color-mix");

    // Expiry chip on the card: >60d → success tint (AA-verified on cards).
    const expiryChip = screen.getByText(/200d left/);
    expect(expiryChip.style.color).toBe("var(--state-success)");
    expect(expiryChip.style.background).toContain("color-mix");

    // History chips sit inside --glass-rim wells, where a 12% tint fill
    // sinks success/warning fg below 4.5:1 — hairline border + bare state
    // fg instead (no fill).
    const completedChip = screen.getByText("completed");
    expect(completedChip.style.color).toBe("var(--state-success)");
    expect(completedChip.style.border).toContain("color-mix");
    expect(completedChip.style.background).toBe("");
    // "expired" appears on both a document chip and a history chip — both
    // must read the danger token.
    for (const expiredChip of screen.getAllByText("expired")) {
      expect(expiredChip.style.color).toBe("var(--state-danger)");
    }

    // Document status chips: same well pattern (verified → success,
    // expired → danger).
    const verifiedChip = screen.getByText("verified");
    expect(verifiedChip.style.color).toBe("var(--state-success)");
    expect(verifiedChip.style.border).toContain("color-mix");
  });

  it("reads the days-remaining banner from state tokens (valid → success)", async () => {
    const { container } = await renderLoaded(200);

    const banner = screen.getByText("days remaining").closest("div")
      ?.parentElement?.parentElement as HTMLElement;
    expect(banner.style.background).toContain("var(--state-success)");
    expect(banner.style.borderColor).toContain("var(--state-success)");
    expect(container.innerHTML).not.toContain("rgba(16,185,129");
    expect(container.innerHTML).not.toContain("rgba(239,68,68");
  });

  it("flags the renewal alert in danger tones when <= 60 days remain", async () => {
    await renderLoaded(30);

    const chip = screen.getByText(/30d left/);
    expect(chip.style.color).toBe("var(--state-warning)");

    const banner = screen.getByText("days remaining").closest("div")
      ?.parentElement?.parentElement as HTMLElement;
    expect(banner.style.background).toContain("var(--state-danger)");
    expect(banner.className).toContain("animate-pulse");
    expect(
      screen.getByText(/expires in less than 2 months/),
    ).toBeInTheDocument();
  });

  it("drain guard: no hardcoded hex colors anywhere in the page output", async () => {
    const { container } = await renderLoaded();
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it("renders the shared empty state when no visa info exists", async () => {
    mockGetVisaStatus.mockResolvedValue(null);
    render(<VisaPage />);
    expect(await screen.findByText("No visa information")).toBeInTheDocument();
  });

  it("treats the superuser client-selection response as a neutral state", async () => {
    mockGetVisaStatus.mockRejectedValue(
      new Error("Superuser: select a client via ?as_client=<id>"),
    );
    render(<VisaPage />);

    expect(
      await screen.findByText("Select a client to view visa information"),
    ).toBeInTheDocument();
    expect(mockToastError).not.toHaveBeenCalled();
  });

  it("shows a toast when loading fails", async () => {
    mockGetVisaStatus.mockRejectedValue(new Error("boom"));
    render(<VisaPage />);
    await screen.findByRole("heading", { level: 1 });
    expect(mockToastError).toHaveBeenCalledWith(
      "Failed to load visa information",
      "Please try again later",
      expect.objectContaining({
        label: expect.any(String),
        onClick: expect.any(Function),
      }),
    );
  });
});
