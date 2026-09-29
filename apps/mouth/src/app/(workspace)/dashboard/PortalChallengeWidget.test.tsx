import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { rosterBySlug } from "@/data/team-roster";
import {
  PortalChallengeWidget,
  PodiumCard,
  countdownParts,
  relativeMinutes,
} from "./PortalChallengeWidget";
import { usePortalChallenge } from "./_lib/usePortalChallenge";
import type {
  PortalChallengeAsyaMission,
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

  it("leads with the race and keeps rules and prize details collapsed below it", () => {
    mockQuery(response());
    render(<PortalChallengeWidget identity="fixture" />);
    const arena = screen.getByTestId("champion-arena");
    const details = screen
      .getByText("Hadiah, posisi saya & aturan")
      .closest("details")!;
    expect(details.open).toBe(false);
    expect(
      arena.compareDocumentPosition(details) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    expect(details).toContainElement(screen.getByTestId("podium-tier-1"));
  });

  it("selects a contender and shows the points needed to pass the next rival", () => {
    mockQuery(
      response({
        entries: [
          entry({ member: "leader", display_name: "Leader", activations: 23 }),
          entry({
            member: "chaser",
            display_name: "Chaser",
            activations: 20,
            rank: 2,
            award_tier: 2,
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="fixture" />);
    const arena = within(screen.getByTestId("champion-arena"));
    fireEvent.click(
      arena.getByRole("button", { name: "Lihat peluang Chaser" }),
    );
    expect(
      screen.getByText("4 poin untuk melewati Leader."),
    ).toBeInTheDocument();
    expect(arena.getByLabelText("Lihat peluang peserta lain")).toHaveValue(
      "chaser",
    );
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
    // The feed card never disappears — it shows a quiet empty line instead.
    const feed = within(screen.getByTestId("live-feed"));
    expect(feed.getByText(/Belum ada aktivitas/i)).toBeInTheDocument();
  });

  it("shows a '–' rank instead of a lying Rank #N when the viewer has 0 activations", () => {
    mockQuery(
      response({
        entries: [
          entry({
            is_me: true,
            rank: 1,
            activations: 0,
            award_tier: null,
            next_tier_threshold: 10,
            to_next_tier: 10,
            total_prize_idr: 0,
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const card = within(screen.getByTestId("my-position-card"));
    expect(card.getByText("Rank –")).toBeInTheDocument();
    expect(card.queryByText("Rank #1")).not.toBeInTheDocument();
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
    const names = within(screen.getByTestId("champion-ranking"))
      .getAllByText(/^(Ari|Budi)$/)
      .map((n) => n.textContent);
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
    const ranking = within(screen.getByTestId("champion-ranking"));
    expect(ranking.queryByText("Member 6")).not.toBeInTheDocument();
    const toggle = screen.getByRole("button", { name: /lihat semua/i });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(ranking.getByText("Member 6")).toBeInTheDocument();
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

describe("Champion hero", () => {
  beforeEach(() => {
    mockedHook.mockReset();
  });

  /** 20 synthetic contenders, dense-ranked: podium 46/34/33, ties, 4 on zero. */
  function field(): PortalChallengeEntry[] {
    const scores = [
      46, 34, 33, 20, 18, 16, 15, 12, 11, 10, 9, 8, 8, 7, 6, 6, 0, 0, 0, 0,
    ];
    return scores.map((activations, index) =>
      entry({
        member: `contender-${index + 1}`,
        display_name: `Contender ${index + 1}`,
        rank: new Set(scores.filter((s) => s > activations)).size + 1,
        activations,
        award_tier: null,
        avatar_url: null,
      }),
    );
  }

  it("merges title, one team total, countdown and the race into one panel", () => {
    mockQuery(response({ team_total_activations: 150, entries: field() }));
    render(<PortalChallengeWidget identity="fixture" />);
    const arena = within(screen.getByTestId("champion-arena"));
    expect(
      arena.getByRole("heading", { name: "Portal Champion" }),
    ).toBeInTheDocument();
    expect(arena.getByText("Berakhir dalam")).toBeInTheDocument();
    expect(screen.getAllByText("150")).toHaveLength(1);
    expect(
      screen.getAllByRole("heading", { name: "Portal Champion" }),
    ).toHaveLength(1);
  });

  it("puts the target beside the podium and keeps 20 contenders in one compact picker", () => {
    mockQuery(response({ team_total_activations: 150, entries: field() }));
    render(<PortalChallengeWidget identity="fixture" />);
    const arena = within(screen.getByTestId("champion-arena"));
    // Only the three podium cards are buttons — no wall of 20 pills.
    expect(arena.getAllByRole("button")).toHaveLength(3);
    const picker = arena.getByRole("combobox", {
      name: "Lihat peluang peserta lain",
    });
    expect(within(picker).getAllByRole("option")).toHaveLength(20);
    expect(screen.getByTestId("champion-target")).toContainElement(picker);
  });

  it("rank 3 on 33 below rank 2 on 34 needs 2 points to overtake", () => {
    mockQuery(response({ team_total_activations: 150, entries: field() }));
    render(<PortalChallengeWidget identity="fixture" />);
    const target = within(screen.getByTestId("champion-target"));
    fireEvent.change(target.getByLabelText("Lihat peluang peserta lain"), {
      target: { value: "contender-3" },
    });
    expect(
      target.getByText("2 poin untuk melewati Contender 2."),
    ).toBeInTheDocument();
    expect(target.getByText("Peringkat #3 · 33 poin")).toBeInTheDocument();
    expect(
      within(screen.getByTestId("champion-arena")).getByRole("button", {
        name: "Lihat peluang Contender 3",
      }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("a tie is not a rival: the tied contender chases the next higher score", () => {
    mockQuery(response({ team_total_activations: 150, entries: field() }));
    render(<PortalChallengeWidget identity="fixture" />);
    const target = within(screen.getByTestId("champion-target"));
    fireEvent.change(target.getByLabelText("Lihat peluang peserta lain"), {
      target: { value: "contender-13" },
    });
    expect(
      target.getByText("2 poin untuk melewati Contender 11."),
    ).toBeInTheDocument();
  });

  it("gives a 0-point contender no rank and the first-point prompt", () => {
    mockQuery(
      response({
        team_total_activations: 0,
        entries: [
          entry({
            member: "a",
            display_name: "Contender A",
            activations: 0,
            award_tier: null,
          }),
          entry({
            member: "b",
            display_name: "Contender B",
            activations: 0,
            award_tier: null,
          }),
        ],
        recent_activations: [],
      }),
    );
    render(<PortalChallengeWidget identity="fixture" />);
    const arena = within(screen.getByTestId("champion-arena"));
    expect(arena.queryAllByRole("button")).toHaveLength(0);
    const target = within(screen.getByTestId("champion-target"));
    expect(
      target.getByText("Jadilah pencetak poin pertama."),
    ).toBeInTheDocument();
    expect(target.getByText("Peringkat – · 0 poin")).toBeInTheDocument();
  });

  it("frames approved staff photos on the face and keeps other sources uncropped", () => {
    mockQuery(
      response({
        entries: [
          entry({
            member: "a",
            display_name: "Contender A",
            avatar_url: "/static/team/ari.jpg",
          }),
          entry({
            member: "b",
            display_name: "Contender B",
            rank: 2,
            activations: 20,
            award_tier: 2,
            avatar_url: "/static/team/unlisted.jpg",
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="fixture" />);
    const arena = within(screen.getByTestId("champion-arena"));
    const [framed] = arena.getAllByRole("img", { name: "Contender A" });
    expect(framed.style.objectPosition).toBe("50% 34%");
    expect(framed.style.transform).toBe(
      "translate(50%, 50%) scale(2.45) translate(-50%, -34%)",
    );
    const [plain] = arena.getAllByRole("img", { name: "Contender B" });
    expect(plain.style.transform).toBe("");
  });

  it("renders the backend's superseded Krisna avatar from the approved, face-framed file", () => {
    const approved = String(rosterBySlug("krisna")?.photo);
    expect(approved).toBe("/static/team/krisna-20260927.jpg");
    expect(
      existsSync(join(__dirname, "..", "..", "..", "..", "public", approved)),
    ).toBe(true);
    mockQuery(
      response({
        entries: [
          entry({
            member: "a",
            display_name: "Contender A",
            // What team_members.avatar still holds in production.
            avatar_url: "/static/team/krisna.jpg",
          }),
          entry({
            member: "b",
            display_name: "Contender B",
            rank: 2,
            activations: 20,
            award_tier: 2,
            avatar_url: approved,
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="fixture" />);
    const arena = within(screen.getByTestId("champion-arena"));
    for (const name of ["Contender A", "Contender B"]) {
      for (const portrait of arena.getAllByRole("img", { name })) {
        expect(portrait.tagName).toBe("IMG");
        expect(portrait.getAttribute("src")).toBe(approved);
        expect(portrait.style.transform).toBe(
          "translate(50%, 50%) scale(2.45) translate(-55%, -33%)",
        );
      }
    }
  });

  it("aliases only the exact legacy path and keeps the initials fallback", () => {
    mockQuery(
      response({
        entries: [
          entry({
            member: "a",
            display_name: "Contender A",
            avatar_url: "/static/team/krisna.jpg",
          }),
          entry({
            member: "b",
            display_name: "Contender B",
            rank: 2,
            activations: 20,
            award_tier: 2,
            avatar_url: "https://cdn.invalid/static/team/krisna.jpg",
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="fixture" />);
    const arena = within(screen.getByTestId("champion-arena"));
    expect(
      arena
        .getAllByRole("img", { name: "Contender B" })
        .map((node) => node.tagName),
    ).not.toContain("IMG");
    const podium = within(
      arena.getByRole("button", { name: "Lihat peluang Contender A" }),
    );
    fireEvent.error(podium.getByRole("img", { name: "Contender A" }));
    expect(podium.getByText("CA")).toBeInTheDocument();
  });

  it("falls back to initials when a podium photo fails to load", () => {
    mockQuery(
      response({
        entries: [
          entry({
            member: "a",
            display_name: "Contender A",
            avatar_url: "/static/team/ari.jpg",
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="fixture" />);
    const podium = within(
      within(screen.getByTestId("champion-arena")).getByRole("button", {
        name: "Lihat peluang Contender A",
      }),
    );
    fireEvent.error(podium.getByRole("img", { name: "Contender A" }));
    expect(podium.getByText("CA")).toBeInTheDocument();
  });
});

describe("Round 2 «Lascia o raddoppia»", () => {
  beforeEach(() => {
    mockedHook.mockReset();
  });

  /** A round-2 payload — tiers empty, rank prizes/scoring/september/asya_mission present. */
  function round2Response(
    over: Partial<PortalChallengeResponse> = {},
  ): PortalChallengeResponse {
    return response({
      round: 2,
      campaign: "Lascia o raddoppia",
      window_start: "2026-09-30T00:00:00+08:00",
      window_end: "2026-10-30T00:00:00+08:00",
      tiers: [],
      rank_prizes: [
        { rank: 1, prize_idr: 6_000_000 },
        { rank: 2, prize_idr: 3_500_000 },
        { rank: 3, prize_idr: 2_000_000 },
        { rank: 4, prize_idr: 1_000_000 },
        { rank: 5, prize_idr: 700_000 },
      ],
      scoring: {
        registration: 1,
        first_document: 3,
        unanswered_request: -2,
        unreviewed_document: -1,
        response_working_hours: 3,
        review_working_hours: 9.5,
        service_hours: "Senin–Jumat 09.00–18.30 WITA",
      },
      team_total_points: 63,
      entries: [
        entry({
          member: "adit@balizero.com",
          display_name: "Adit",
          is_me: true,
          rank: 1,
          activations: 2,
          points: 23,
          carry_points: 23,
          registrations: 0,
          document_bonuses: 0,
          unanswered_requests: 0,
          unreviewed_documents: 0,
          penalty_points: 0,
          september_choice: "carry",
          last_event_at: "2026-09-20T00:00:00Z",
          award_tier: null,
          prize_idr: 6_000_000,
          total_prize_idr: 6_000_000,
        }),
      ],
      recent_activations: [],
      recent_events: [
        {
          kind: "registration",
          display_name: "Adit",
          points: 1,
          at: "2026-09-30T01:00:00Z",
        },
      ],
      september: {
        status: "closed",
        window_start: "2026-09-14T00:00:00+08:00",
        window_end: "2026-09-30T00:00:00+08:00",
        team_total_activations: 160,
        entries: [
          {
            member: "ari.firda",
            display_name: "Ari Firda",
            avatar_url: null,
            is_tax: false,
            rank: 1,
            activations: 25,
            invited: 30,
            award_tier: 1,
            prize_idr: 3_000_000,
            tax_bonus_idr: 0,
            total_prize_idr: 3_000_000,
            september_choice: "prize",
          },
        ],
      },
      asya_mission: {
        member: "asya",
        display_name: "Asya Nadia",
        avatar_url: null,
        target_points: 60,
        prize_idr: 1_000_000,
        bonus_points: 3,
        mission_bonuses: 5,
        unanswered_requests: 1,
        unreviewed_documents: 0,
        penalty_points: 2,
        points: 13,
        reached: false,
        is_me: false,
      },
      ...over,
    });
  }

  it("shows the campaign eyebrow and races on team points instead of activations", () => {
    mockQuery(round2Response());
    render(<PortalChallengeWidget identity="fixture" />);
    const arena = within(screen.getByTestId("champion-arena"));
    expect(arena.getByText(/lascia o raddoppia/i)).toBeInTheDocument();
    expect(arena.getByText(/30 sep.*29 okt 2026.*wita/i)).toBeInTheDocument();
    expect(screen.getAllByText("63")).toHaveLength(1);
    expect(arena.getByText("poin tim")).toBeInTheDocument();
  });

  it("renders all five prizes in order, holder points, a tie, and never a 0-point winner", () => {
    mockQuery(
      round2Response({
        entries: [
          entry({
            member: "a",
            display_name: "Adit",
            rank: 1,
            points: 30,
            last_event_at: "2026-10-01T00:00:00Z",
          }),
          entry({
            member: "b",
            display_name: "Budi",
            rank: 2,
            points: 20,
            last_event_at: "2026-10-01T00:00:00Z",
          }),
          entry({
            member: "c",
            display_name: "Citra",
            rank: 2,
            points: 20,
            last_event_at: "2026-10-01T00:00:00Z",
          }),
          // Shares rank 5 by dense-rank tie-break, but 0 points — the
          // backend already ships prize_idr: 0 for it; it must never show
          // as the rank-5 winner.
          entry({
            member: "d",
            display_name: "Dedi",
            rank: 5,
            points: 0,
            last_event_at: null,
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="fixture" />);
    expect(screen.getByTestId("rank-prize-list")).toBeInTheDocument();
    // formatIDR's "Rp" separator is a non-breaking space — normalize before
    // substring-matching raw textContent (unlike getByText, .textContent
    // isn't whitespace-normalized).
    const norm = (s: string | null) => (s ?? "").replace(/\s+/g, " ");
    const rows = [1, 2, 3, 4, 5].map((rank) =>
      screen.getByTestId(`rank-prize-${rank}`),
    );
    expect(norm(rows[0].textContent)).toContain("Rp 6.000.000");
    expect(norm(rows[1].textContent)).toContain("Rp 3.500.000");
    expect(norm(rows[2].textContent)).toContain("Rp 2.000.000");
    expect(norm(rows[3].textContent)).toContain("Rp 1.000.000");
    expect(norm(rows[4].textContent)).toContain("Rp 700.000");

    expect(within(rows[0]).getByText("Adit")).toBeInTheDocument();
    expect(rows[0].textContent).toContain("30 poin");

    // Tied rank 2: both holders listed, shared prize, shared points.
    expect(rows[1].textContent).toContain("Budi, Citra");
    expect(rows[1].textContent).toContain("20 poin");

    // Ranks 3/4 have no candidate at all.
    expect(rows[2].textContent).toContain("Belum ada");
    expect(rows[3].textContent).toContain("Belum ada");

    // Rank 5's only candidate has 0 points — shown as vacant, not as Dedi.
    expect(rows[4].textContent).toContain("Belum ada");
    expect(rows[4].textContent).not.toContain("Dedi");

    expect(screen.queryByTestId("podium-tier-1")).not.toBeInTheDocument();
  });

  it("shows each prize slot's minimum score, from the payload when present", () => {
    mockQuery(
      round2Response({
        rank_prizes: [
          { rank: 1, prize_idr: 6_000_000, min_points: 111 },
          { rank: 2, prize_idr: 3_500_000, min_points: 80 },
        ],
      }),
    );
    render(<PortalChallengeWidget identity="fixture" />);
    expect(screen.getByTestId("rank-prize-1").textContent).toContain(
      "min 111 poin",
    );
    expect(screen.getByTestId("rank-prize-2").textContent).toContain(
      "min 80 poin",
    );
  });

  it("falls back to the ruled minimums when min_points is absent", () => {
    mockQuery(round2Response());
    render(<PortalChallengeWidget identity="fixture" />);
    const mins = [100, 80, 60, 30, 20];
    mins.forEach((m, i) => {
      expect(screen.getByTestId(`rank-prize-${i + 1}`).textContent).toContain(
        `min ${m} poin`,
      );
    });
  });

  it("assigns prize-list holders by prize_slot when the payload carries it", () => {
    mockQuery(
      round2Response({
        entries: [
          entry({
            member: "adit",
            display_name: "Adit",
            rank: 1,
            points: 23,
            prize_slot: 5,
            prize_idr: 700_000,
            total_prize_idr: 700_000,
            last_event_at: "2026-10-01T00:00:00Z",
          }),
          entry({
            member: "z",
            display_name: "Zed",
            rank: 2,
            points: 10,
            prize_slot: null,
            last_event_at: "2026-10-01T00:00:00Z",
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="fixture" />);
    const first = screen.getByTestId("rank-prize-1");
    expect(first.textContent).toContain("Belum ada");
    expect(first.textContent).not.toContain("Adit");
    const fifth = screen.getByTestId("rank-prize-5");
    expect(fifth.textContent).toContain("Adit");
    expect(fifth.textContent).not.toContain("Zed");
    expect(screen.getByTestId("rank-prize-2").textContent).not.toContain("Zed");
  });

  it("falls back to rank matching when no entry carries prize_slot", () => {
    mockQuery(
      round2Response({
        entries: [
          entry({
            member: "adit",
            display_name: "Adit",
            rank: 1,
            points: 23,
            last_event_at: "2026-10-01T00:00:00Z",
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="fixture" />);
    expect(screen.getByTestId("rank-prize-1").textContent).toContain("Adit");
  });

  it("notes the prize slot when it differs from the rank", () => {
    mockQuery(
      round2Response({
        entries: [
          entry({
            member: "a",
            display_name: "Anna",
            rank: 1,
            points: 85,
            prize_slot: 2,
            last_event_at: "2026-10-01T00:00:00Z",
          }),
          entry({
            member: "b",
            display_name: "Budi",
            rank: 2,
            points: 70,
            prize_slot: 2,
            last_event_at: "2026-10-01T00:00:00Z",
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="fixture" />);
    const ranking = screen.getByTestId("champion-ranking");
    expect(ranking.textContent).toContain("hadiah posisi 2");
    expect(ranking.textContent?.match(/hadiah posisi/g)).toHaveLength(1);
  });

  it("tells an ineligible September prize-taker which rank they need", () => {
    mockQuery(
      round2Response({
        entries: [
          entry({
            member: "s",
            display_name: "Surya",
            rank: 3,
            points: 65,
            september_rank: 1,
            prize_slot: null,
            last_event_at: "2026-10-01T00:00:00Z",
          }),
          entry({
            member: "k",
            display_name: "Krisna",
            rank: 1,
            points: 120,
            september_rank: 2,
            prize_slot: 1,
            last_event_at: "2026-10-01T00:00:00Z",
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="fixture" />);
    const ranking = screen.getByTestId("champion-ranking");
    expect(ranking.textContent).toContain("perlu posisi ≤ 1");
    expect(ranking.textContent).not.toContain("perlu posisi ≤ 2");
  });

  it("explains thresholds, slide-down and the prize-taker rule in the rules drawer", () => {
    mockQuery(round2Response());
    render(<PortalChallengeWidget identity="fixture" />);
    fireEvent.click(screen.getByRole("button", { name: /aturan/i }));
    const dialog = screen.getByRole("dialog");
    const t = (dialog.textContent ?? "").replace(/\s+/g, " ");
    expect(t).toContain("minimal 100 poin");
    expect(t).toContain("80");
    expect(t).toContain("turun ke posisi hadiah yang bisa dicapai");
    expect(t).toMatch(/pemenang hadiah September/i);
    expect(t).not.toContain("(5 posisi)");
  });

  it("shows the round 2 breakdown chips and the September-prize note", () => {
    mockQuery(
      round2Response({
        entries: [
          entry({
            is_me: true,
            rank: 2,
            points: 5,
            carry_points: 0,
            registrations: 2,
            document_bonuses: 1,
            unanswered_requests: 1,
            unreviewed_documents: 3,
            penalty_points: 5,
            september_choice: "prize",
            last_event_at: "2026-10-01T00:00:00Z",
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const card = screen.getByTestId("my-position-card");
    expect(within(card).getByText("Rank #2")).toBeInTheDocument();
    expect(within(card).getByText("5")).toBeInTheDocument();
    expect(card.textContent).toMatch(/hadiah september diambil/i);
    expect(card.textContent).toContain("Bawa dari September");
    expect(card.textContent).toContain("+2");
    expect(card.textContent).toContain("registrasi");
    expect(card.textContent).toContain("+3");
    expect(card.textContent).toContain("dokumen pertama");
    expect(card.textContent).toContain("-2");
    expect(card.textContent).toContain("permintaan tak terjawab");
    expect(card.textContent).toContain("-3");
    expect(card.textContent).toContain("dokumen belum ditinjau");
  });

  it("ranking rows itemise every scoring component so the row adds up to the total", () => {
    mockQuery(
      round2Response({
        entries: [
          entry({
            member: "a",
            display_name: "A",
            rank: 1,
            points: 23 + 4 + 6 - 5,
            carry_points: 23,
            september_choice: "carry",
            registrations: 4,
            document_bonuses: 2,
            unanswered_requests: 2,
            unreviewed_documents: 1,
            penalty_points: 5,
            last_event_at: "2026-10-01T00:00:00Z",
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const row = screen.getByTestId("champion-breakdown-a");
    const t = row.textContent ?? "";
    // order: carry, reg, dok (3 per bonus), requests (2 each), docs (1 each)
    const order = ["+23", "+4 reg", "+6 dok", "−4", "−1"].map((x) =>
      t.indexOf(x),
    );
    expect(order.every((i) => i >= 0)).toBe(true);
    expect([...order].sort((x, y) => x - y)).toEqual(order);
    expect(t).toContain("Sep");
    expect(t).toContain("permintaan");
    expect(t).toContain("dokumen");
    const ranking = screen.getByTestId("champion-ranking");
    expect(within(ranking).getByText("28")).toBeInTheDocument();
  });

  it("a September prize-taker row shows 0 carry with the prize marker", () => {
    mockQuery(
      round2Response({
        entries: [
          entry({
            member: "s",
            display_name: "Surya",
            rank: 2,
            points: 3,
            carry_points: 0,
            september_choice: "prize",
            registrations: 0,
            document_bonuses: 1,
            unanswered_requests: 0,
            unreviewed_documents: 0,
            penalty_points: 0,
            last_event_at: "2026-10-01T00:00:00Z",
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const t = screen.getByTestId("champion-breakdown-s").textContent ?? "";
    expect(t).toContain("Sep 0");
    expect(t).toContain("hadiah diambil");
    expect(t).toContain("+3 dok");
  });

  it("round 2 lists every entry with no top-5 collapse", () => {
    mockQuery(
      round2Response({
        entries: Array.from({ length: 6 }, (_, i) =>
          entry({
            member: `m${i}`,
            display_name: `Member${i}`,
            rank: i + 1,
            points: 10 - i,
            september_choice: "carry",
            last_event_at: "2026-10-01T00:00:00Z",
          }),
        ),
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const ranking = within(screen.getByTestId("champion-ranking"));
    expect(ranking.getByText("Member5")).toBeInTheDocument();
    expect(ranking.queryByText("Lihat semua")).toBeNull();
  });

  it("shows a '–' rank in the ranking list for a member with no R2 event", () => {
    mockQuery(
      round2Response({
        entries: [
          entry({
            member: "untouched",
            display_name: "Untouched",
            rank: 9,
            points: 0,
            last_event_at: null,
          }),
        ],
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const ranking = within(screen.getByTestId("champion-ranking"));
    expect(ranking.getByText("–")).toBeInTheDocument();
  });

  it("live feed renders recent_events with Indonesian labels and signed points", () => {
    mockQuery(
      round2Response({
        recent_events: [
          {
            kind: "registration",
            display_name: "Adit",
            points: 1,
            at: "2026-09-30T01:00:00Z",
          },
          {
            kind: "unanswered_request",
            display_name: "Rina",
            points: -2,
            at: "2026-09-30T00:30:00Z",
          },
        ],
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const feed = within(screen.getByTestId("live-feed"));
    expect(feed.getByText("Registrasi selesai")).toBeInTheDocument();
    expect(feed.getByText("Permintaan tak terjawab")).toBeInTheDocument();
    expect(feed.getByText("+1")).toBeInTheDocument();
    expect(feed.getByText("-2")).toBeInTheDocument();
  });

  it("shows the Asya mission card with the prize, target, and breakdown", () => {
    mockQuery(round2Response());
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const mission = screen.getByTestId("asya-mission-card");
    const norm = (s: string | null) => (s ?? "").replace(/\s+/g, " ");
    expect(within(mission).getByText("Asya Nadia")).toBeInTheDocument();
    expect(within(mission).getByText("13/60")).toBeInTheDocument();
    expect(norm(mission.textContent)).toMatch(
      /target 60 poin — hadiah rp 1\.000\.000/i,
    );
    expect(mission.textContent).toContain("+15");
    expect(mission.textContent).toContain("-2");
  });

  function asyaMission(
    over: Partial<PortalChallengeAsyaMission> = {},
  ): PortalChallengeAsyaMission {
    return {
      member: "asya",
      display_name: "Asya Nadia",
      avatar_url: null,
      target_points: 60,
      prize_idr: 1_000_000,
      bonus_points: 3,
      mission_bonuses: 5,
      unanswered_requests: 0,
      unreviewed_documents: 0,
      penalty_points: 0,
      points: 0,
      reached: false,
      is_me: false,
      ...over,
    };
  }

  it("Misi Asya is not reached at 59/60", () => {
    mockQuery(
      round2Response({
        asya_mission: asyaMission({ points: 59, reached: false }),
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const mission = within(screen.getByTestId("asya-mission-card"));
    expect(mission.getByText("59/60")).toBeInTheDocument();
    expect(mission.queryByText("Tercapai")).not.toBeInTheDocument();
    expect(mission.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "98",
    );
  });

  it("Misi Asya is reached at 60/60, progress bar at exactly 100%", () => {
    mockQuery(
      round2Response({
        asya_mission: asyaMission({ points: 60, reached: true }),
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const mission = within(screen.getByTestId("asya-mission-card"));
    expect(mission.getByText("Tercapai")).toBeInTheDocument();
    const bar = mission.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "100");
    expect((bar.firstElementChild as HTMLElement).style.width).toBe("100%");
  });

  it("Misi Asya's progress bar stays capped at 100% when points exceed the target", () => {
    mockQuery(
      round2Response({
        asya_mission: asyaMission({ points: 90, reached: true }),
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const mission = within(screen.getByTestId("asya-mission-card"));
    const bar = mission.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "100");
    expect((bar.firstElementChild as HTMLElement).style.width).toBe("100%");
  });

  it("Hasil September discloses the frozen ranking, prize per row, and both choice labels", () => {
    mockQuery(
      round2Response({
        september: {
          status: "closed",
          window_start: "2026-09-14T00:00:00+08:00",
          window_end: "2026-09-30T00:00:00+08:00",
          team_total_activations: 160,
          entries: [
            {
              member: "ari.firda",
              display_name: "Ari Firda",
              avatar_url: null,
              is_tax: false,
              rank: 1,
              activations: 25,
              invited: 30,
              award_tier: 1,
              prize_idr: 3_000_000,
              tax_bonus_idr: 0,
              total_prize_idr: 3_000_000,
              september_choice: "prize",
            },
            {
              member: "surya",
              display_name: "Surya",
              avatar_url: null,
              is_tax: false,
              rank: 2,
              activations: 20,
              invited: 25,
              award_tier: 2,
              prize_idr: 1_500_000,
              tax_bonus_idr: 0,
              total_prize_idr: 1_500_000,
              september_choice: "prize",
            },
            {
              member: "krisna",
              display_name: "Krisna",
              avatar_url: null,
              is_tax: false,
              rank: 3,
              activations: 15,
              invited: 20,
              award_tier: 3,
              prize_idr: 700_000,
              tax_bonus_idr: 0,
              total_prize_idr: 700_000,
              september_choice: "carry",
            },
          ],
        },
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const norm = (s: string | null) => (s ?? "").replace(/\s+/g, " ");

    // Disclosure starts closed, same idiom as "Hadiah, posisi saya & aturan".
    const details = screen.getByText("Hasil September").closest("details")!;
    expect(details.open).toBe(false);
    fireEvent.click(screen.getByText("Hasil September"));
    expect(details.open).toBe(true);

    const region = screen.getByTestId("september-results");
    const section = within(region);

    // Frozen order — ari.firda, surya, krisna (rank order, unchanged by R2).
    const names = section
      .getAllByText(/^#\d+ (Ari Firda|Surya|Krisna)$/)
      .map((el) => el.textContent);
    expect(names).toEqual(["#1 Ari Firda", "#2 Surya", "#3 Krisna"]);

    const rows = region.querySelectorAll("li");
    expect(norm(rows[0]!.textContent)).toContain("Rp 3.000.000");
    expect(norm(rows[1]!.textContent)).toContain("Rp 1.500.000");
    expect(norm(rows[2]!.textContent)).toContain("Rp 700.000");

    // Both choice labels appear (Ari Firda + Surya "prize", Krisna "carry").
    expect(section.getAllByText("Ambil hadiah")).toHaveLength(2);
    expect(section.getByText("Bawa poin ke Oktober")).toBeInTheDocument();
  });

  it("hides the Tim Tax strip in round 2", () => {
    mockQuery(
      round2Response({
        entries: [entry({ is_tax: true, is_me: true, points: 10 })],
      }),
    );
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    expect(screen.queryByTestId("tax-strip")).not.toBeInTheDocument();
  });

  it("round 2 with tiers: [] never renders the (round-1-only) tier scale", () => {
    mockQuery(round2Response({ tiers: [] }));
    expect(() =>
      render(<PortalChallengeWidget identity="ari@balizero.com" />),
    ).not.toThrow();
  });

  it("PositionScale guards Math.max on an empty tiers array with a sane 0-width bar (round 1)", () => {
    // Round 1 is the path that actually calls PositionScale — an empty
    // tiers array here used to feed Math.max(...[]) === -Infinity.
    mockQuery(response({ tiers: [], entries: [entry({ is_me: true })] }));
    render(<PortalChallengeWidget identity="ari@balizero.com" />);
    const card = within(screen.getByTestId("my-position-card"));
    const bar = card.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "0");
    expect((bar.firstElementChild as HTMLElement).style.width).toBe("0%");
  });
});
