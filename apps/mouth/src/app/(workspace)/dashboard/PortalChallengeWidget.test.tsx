import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import {
  PortalChallengeWidget,
  PodiumCard,
  countdownParts,
  relativeMinutes,
} from "./PortalChallengeWidget";
import { usePortalChallenge } from "./_lib/usePortalChallenge";
import type {
  PortalChallengeEntry,
  PortalChallengeResponse,
} from "@/lib/api/dashboard/dashboard.api";

vi.mock("./_lib/usePortalChallenge", () => ({
  usePortalChallenge: vi.fn(),
}));

const mockedHook = vi.mocked(usePortalChallenge);

function entry(over: Partial<PortalChallengeEntry> = {}): PortalChallengeEntry {
  return {
    member: "ari@balizero.com",
    display_name: "Ari",
    department: "Setup",
    is_tax: false,
    is_me: false,
    rank: 1,
    activations: 22,
    invited: 30,
    last_activation_at: "2026-09-14T01:00:00Z",
    award_tier: 1,
    prize_idr: 3_000_000,
    tax_bonus_idr: 0,
    total_prize_idr: 3_000_000,
    next_tier_threshold: null,
    to_next_tier: null,
    ...over,
  };
}

function response(
  over: Partial<PortalChallengeResponse> = {},
): PortalChallengeResponse {
  return {
    status: "live",
    window_start: "2026-09-14T00:00:00+08:00",
    window_end: "2026-09-30T00:00:00+08:00",
    timezone: "Asia/Makassar",
    generated_at: "2026-09-20T04:00:00Z",
    tiers: [
      { tier: 1, threshold: 20, prize_idr: 3_000_000 },
      { tier: 2, threshold: 15, prize_idr: 1_500_000 },
      { tier: 3, threshold: 10, prize_idr: 700_000 },
    ],
    tax_rules: {
      podium_super_bonus_idr: 1_500_000,
      best_tax_fallback_idr: 1_000_000,
      best_tax_fallback_threshold: 10,
    },
    team_total_activations: 40,
    entries: [entry()],
    recent_activations: [{ display_name: "Ari", at: "2026-09-20T03:55:00Z" }],
    ...over,
  };
}

function mockQuery(data: PortalChallengeResponse | null, isLoading = false) {
  mockedHook.mockReturnValue({
    data,
    isLoading,
  } as unknown as ReturnType<typeof usePortalChallenge>);
}

describe("countdownParts", () => {
  it("splits remaining time into days/hours/minutes", () => {
    const now = new Date("2026-09-20T00:00:00Z").getTime();
    const target = "2026-09-22T06:30:00Z";
    expect(countdownParts(target, now)).toEqual({
      remaining: 2 * 24 * 60 * 60 * 1000 + 6 * 60 * 60 * 1000 + 30 * 60 * 1000,
      days: 2,
      hours: 6,
      minutes: 30,
    });
  });

  it("clamps to zero once the target has passed", () => {
    const now = new Date("2026-09-30T01:00:00Z").getTime();
    expect(countdownParts("2026-09-29T00:00:00Z", now)).toMatchObject({
      remaining: 0,
      days: 0,
      hours: 0,
      minutes: 0,
    });
  });
});

describe("relativeMinutes", () => {
  it("formats sub-minute as 'baru saja'", () => {
    const now = new Date("2026-09-20T03:55:30Z").getTime();
    expect(relativeMinutes("2026-09-20T03:55:00Z", now)).toBe("baru saja");
  });

  it("formats minutes and hours", () => {
    const now = new Date("2026-09-20T04:00:00Z").getTime();
    expect(relativeMinutes("2026-09-20T03:55:00Z", now)).toBe("5 menit lalu");
    expect(relativeMinutes("2026-09-20T01:00:00Z", now)).toBe("3 jam lalu");
  });
});

describe("PodiumCard", () => {
  it("shows the current holder and their activations", () => {
    render(
      <PodiumCard
        tier={1}
        threshold={20}
        prizeIdr={3_000_000}
        entries={[
          entry({ award_tier: 1, display_name: "Ari", activations: 22 }),
        ]}
      />,
    );
    expect(screen.getByText("Rp 3.000.000")).toBeInTheDocument();
    expect(screen.getByText("Ari")).toBeInTheDocument();
    expect(screen.getByText("22")).toBeInTheDocument();
  });

  it("shows 'belum ada' and the gap to the leading contender", () => {
    render(
      <PodiumCard
        tier={1}
        threshold={20}
        prizeIdr={3_000_000}
        entries={[entry({ award_tier: null, activations: 14 })]}
      />,
    );
    expect(screen.getByText("belum ada")).toBeInTheDocument();
    expect(screen.getByText("kurang 6")).toBeInTheDocument();
  });
});

describe("PortalChallengeWidget", () => {
  beforeEach(() => {
    mockedHook.mockReset();
  });

  it("renders nothing when there is no authenticated identity", () => {
    mockQuery(response());
    const { container } = render(<PortalChallengeWidget identity="" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a quiet placeholder on 404 / error (hook resolves null)", () => {
    mockQuery(null);
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    expect(
      screen.getByText(/Portal Champion akan tampil di sini/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("portal-challenge-widget"),
    ).not.toBeInTheDocument();
  });

  it("renders the empty/zero state when no one has activated yet", () => {
    mockQuery(
      response({
        team_total_activations: 0,
        entries: [],
        recent_activations: [],
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    expect(screen.getByTestId("portal-challenge-widget")).toBeInTheDocument();
    expect(screen.getByText("Belum ada aktivasi tercatat")).toBeInTheDocument();
    expect(screen.getByText(/0 klien aktivasi/)).toBeInTheDocument();
  });

  it("renders the is_me card with rank, activations and progress", () => {
    mockQuery(
      response({
        entries: [
          entry({
            is_me: true,
            rank: 4,
            activations: 12,
            next_tier_threshold: 15,
            to_next_tier: 3,
            total_prize_idr: 700_000,
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const card = within(screen.getByTestId("my-position-card"));
    expect(card.getByText("Rank #4")).toBeInTheDocument();
    expect(card.getByText("3 lagi menuju 15 aktivasi")).toBeInTheDocument();
    expect(card.getByText("Rp 700.000")).toBeInTheDocument();
  });

  it("shows the placeholder position card when the viewer has no entry", () => {
    mockQuery(response({ entries: [entry({ is_me: false })] }));
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    expect(
      screen.getByText(/belum tercatat sebagai peserta/i),
    ).toBeInTheDocument();
  });

  it("tax strip: shows the super bonus branch when a tax member is on the podium", () => {
    mockQuery(
      response({
        entries: [
          entry({
            is_tax: true,
            award_tier: 2,
            display_name: "Rina",
            activations: 16,
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const strip = within(screen.getByTestId("tax-strip"));
    expect(strip.getByText(/SUPER BONUS/)).toBeInTheDocument();
    expect(strip.getByText("Rp 1.500.000")).toBeInTheDocument();
  });

  it("tax strip: shows the best-tax fallback branch below the podium threshold", () => {
    mockQuery(
      response({
        entries: [
          entry({
            is_tax: true,
            award_tier: null,
            display_name: "Rina",
            activations: 11,
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    expect(screen.getByText(/memimpin/)).toBeInTheDocument();
    expect(screen.getByText("Rp 1.000.000")).toBeInTheDocument();
  });

  it("tax strip: shows the not-yet-eligible branch under the fallback threshold", () => {
    mockQuery(
      response({
        entries: [
          entry({
            is_tax: true,
            award_tier: null,
            display_name: "Rina",
            activations: 4,
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    expect(screen.getByText(/Belum ada anggota Tim Tax/)).toBeInTheDocument();
  });

  it("ranking list expands beyond the first five rows on demand", () => {
    const entries = Array.from({ length: 7 }, (_, i) =>
      entry({
        member: `m${i}@balizero.com`,
        display_name: `Member ${i}`,
        rank: i + 1,
        award_tier: null,
      }),
    );
    mockQuery(response({ entries }));
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    expect(screen.queryByText("Member 6")).not.toBeInTheDocument();
    const toggle = screen.getByRole("button", { name: /lihat semua/i });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Member 6")).toBeInTheDocument();
  });

  it("opens and closes the rules drawer", () => {
    mockQuery(response());
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const open = screen.getByRole("button", { name: /aturan/i });
    fireEvent.click(open);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /tutup$/i }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows a loading skeleton while the query is in flight", () => {
    mockQuery(undefined as unknown as PortalChallengeResponse, true);
    const { container } = render(
      <PortalChallengeWidget identity="ari@balizero.com" />,
    );
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(
      0,
    );
  });
});
