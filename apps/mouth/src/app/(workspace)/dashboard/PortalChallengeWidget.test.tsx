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

  it("shows 'Belum ada' and the gap to the leading contender", () => {
    render(
      <PodiumCard
        tier={1}
        threshold={20}
        prizeIdr={3_000_000}
        entries={[entry({ award_tier: null, activations: 14 })]}
      />,
    );
    expect(screen.getByText("Belum ada")).toBeInTheDocument();
    expect(screen.getByText("butuh 6 lagi")).toBeInTheDocument();
  });

  it("shows the inviting zero-state copy instead of a gap count", () => {
    render(
      <PodiumCard
        tier={3}
        threshold={10}
        prizeIdr={700_000}
        entries={[entry({ award_tier: null, activations: 0 })]}
        isZeroState
      />,
    );
    expect(screen.getByText("Ayo jadi yang pertama!")).toBeInTheDocument();
    expect(screen.queryByText(/butuh/)).not.toBeInTheDocument();
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

  it("renders the empty/zero-activation state with inviting copy, not a wall of zeros", () => {
    mockQuery(
      response({
        team_total_activations: 0,
        entries: [],
        recent_activations: [],
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    expect(screen.getByTestId("portal-challenge-widget")).toBeInTheDocument();
    expect(screen.getByText(/jadilah yang pertama/i)).toBeInTheDocument();
    expect(screen.getByText("Belum ada aktivasi tercatat")).toBeInTheDocument();
    expect(screen.getAllByText("Ayo jadi yang pertama!")).toHaveLength(3);
  });

  it("ranks alphabetically with a '–' rank marker in the zero-activation state", () => {
    mockQuery(
      response({
        team_total_activations: 0,
        entries: [
          entry({
            member: "b@x.com",
            display_name: "Budi",
            rank: 1,
            activations: 0,
            award_tier: null,
          }),
          entry({
            member: "a@x.com",
            display_name: "Ari",
            rank: 2,
            activations: 0,
            award_tier: null,
          }),
        ],
        recent_activations: [],
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const rankMarkers = screen.getAllByText("–");
    expect(rankMarkers).toHaveLength(2);
    // Alphabetical: Ari before Budi, regardless of the backend-given rank.
    const names = screen.getAllByText(/^(Ari|Budi)$/).map((n) => n.textContent);
    expect(names).toEqual(["Ari", "Budi"]);
  });

  it("renders the is_me card with rank, activations and the next-tier line", () => {
    mockQuery(
      response({
        entries: [
          entry({
            is_me: true,
            rank: 4,
            activations: 12,
            next_tier_threshold: 15,
            to_next_tier: 3,
            total_prize_idr: 0,
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const card = within(screen.getByTestId("my-position-card"));
    expect(card.getByText("Rank #4")).toBeInTheDocument();
    expect(card.getByText("12")).toBeInTheDocument();
    expect(
      card.getByText("3 lagi untuk Juara 2 — Rp 1.500.000"),
    ).toBeInTheDocument();
    // The fixed 0..20 scale always shows all three tier labels.
    expect(card.getByText("Juara 1")).toBeInTheDocument();
    expect(card.getByText("Juara 2")).toBeInTheDocument();
    expect(card.getByText("Juara 3")).toBeInTheDocument();
  });

  it("mentions the super bonus for a tax member chasing a tier", () => {
    mockQuery(
      response({
        entries: [
          entry({
            is_me: true,
            is_tax: true,
            activations: 6,
            next_tier_threshold: 10,
            to_next_tier: 4,
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const card = within(screen.getByTestId("my-position-card"));
    expect(card.getByText(/SUPER BONUS/)).toBeInTheDocument();
  });

  it("shows the placeholder position card when the viewer has no entry", () => {
    mockQuery(response({ entries: [entry({ is_me: false })] }));
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    expect(
      screen.getByText(/belum tercatat sebagai peserta/i),
    ).toBeInTheDocument();
  });

  it("tax strip: shows the super bonus branch and the tax mini-ranking", () => {
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
    expect(strip.getAllByText("Rina").length).toBeGreaterThan(0);
    expect(strip.getByText("16")).toBeInTheDocument();
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
    const strip = within(screen.getByTestId("tax-strip"));
    expect(strip.getByText(/memimpin/)).toBeInTheDocument();
    expect(strip.getByText("Rp 1.000.000")).toBeInTheDocument();
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
    const strip = within(screen.getByTestId("tax-strip"));
    expect(strip.getByText(/Belum ada anggota Tim Tax/)).toBeInTheDocument();
  });

  it("tax pill never carries the shared idiom's blue --state-info tone", () => {
    mockQuery(
      response({
        entries: [entry({ is_tax: true, display_name: "Rina" })],
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const pill = screen.getByText("Tax");
    expect(pill.closest("span")?.className).not.toContain("--state-info");
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

  it("feed marks activity from the last hour with a copper dot", () => {
    // The widget reads the real wall clock (useNow), not `generated_at` —
    // pin it so "5 min ago" / "8h ago" are stable relative to the fixture.
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-20T04:00:00Z"));
    try {
      mockQuery(
        response({
          recent_activations: [
            { display_name: "Ari", at: "2026-09-20T03:55:00Z" }, // 5 min ago
            { display_name: "Rina", at: "2026-09-19T20:00:00Z" }, // 8h ago
          ],
        }),
      );
      render(<PortalChallengeWidget identity="ari@balizero.com" />);
      const feed = within(screen.getByTestId("live-feed"));
      const items = feed
        .getAllByText(/^(Ari|Rina)$/)
        .map((el) => el.closest("li"));
      expect(items[0]?.querySelector("span[aria-hidden]")).not.toBeNull();
      expect(items[1]?.querySelector("span[aria-hidden]")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
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
