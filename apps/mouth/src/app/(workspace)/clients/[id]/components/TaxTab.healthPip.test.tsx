// The LKPM quarter card used to signal red/yellow/green alert health with a
// literal emoji ("🔴"/"🟡"/"🟢"). Two defects: kita's
// written rule is "no red on kita" — this directory (clients/[id]/**) has a
// standing guard test that bans --state-danger outright, and every existing
// alert badge here already renders urgency as --state-warning only (see
// ClientDetailClient.tsx: "warning, never danger") — and an emoji has no
// accessible name — a screen reader announces "red circle" or nothing useful.
//
// `lkpmHealth()` is the pure decision extracted out of LkpmQuarterCard so the
// tone/label logic is testable without mounting the whole quarter-card tree.
// The render test below then proves the pip actually reaches the DOM with an
// accessible name and none of the three banned emoji code points.
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { lkpmHealth } from "./TaxTab";

vi.mock("@/lib/api", () => ({
  api: {
    getProfile: vi.fn().mockResolvedValue({ email: "tester@example.test" }),
    crm: { updateClient: vi.fn() },
  },
}));
vi.mock("./AiSummaryCard", () => ({
  AiSummaryCard: () => <div data-testid="AiSummaryCard" />,
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const YEAR = new Date().getFullYear();

const { mockGetClientHistory } = vi.hoisted(() => ({
  mockGetClientHistory: vi.fn(),
}));
vi.mock("@/lib/api/workspace/lkpm.api", () => ({
  lkpmApi: {
    getClientHistory: mockGetClientHistory,
    getClientReceipts: vi.fn().mockResolvedValue({ items: [] }),
  },
}));

const EMOJI_PATTERN = /[\u{1F534}\u{1F7E1}\u{1F7E2}]/u;

describe("lkpmHealth (pure decision)", () => {
  it("picks critical when there is one red alert, singular label", () => {
    expect(lkpmHealth({ red_alerts: 1, yellow_alerts: 0 })).toEqual({
      tone: "critical",
      label: "1 alert needs attention",
    });
  });

  it("picks critical when there are multiple red alerts, plural label", () => {
    expect(lkpmHealth({ red_alerts: 2, yellow_alerts: 0 })).toEqual({
      tone: "critical",
      label: "2 alerts need attention",
    });
  });

  it("critical wins over yellow when both are present", () => {
    expect(lkpmHealth({ red_alerts: 1, yellow_alerts: 3 })).toEqual({
      tone: "critical",
      label: "1 alert needs attention",
    });
  });

  it("picks warning with a singular label for exactly one yellow alert", () => {
    expect(lkpmHealth({ red_alerts: 0, yellow_alerts: 1 })).toEqual({
      tone: "warning",
      label: "1 warning",
    });
  });

  it("picks warning with a plural label for multiple yellow alerts", () => {
    expect(lkpmHealth({ red_alerts: 0, yellow_alerts: 4 })).toEqual({
      tone: "warning",
      label: "4 warnings",
    });
  });

  it("picks success with no alerts", () => {
    expect(lkpmHealth({ red_alerts: 0, yellow_alerts: 0 })).toEqual({
      tone: "success",
      label: "No alerts",
    });
  });
});

describe("TaxTab LKPM quarter card health pip", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetClientHistory.mockResolvedValue({
      items: [
        {
          id: 1,
          client_id: 7,
          company_name: "Acme Test PT",
          quarter: "Q1",
          year: YEAR,
          status: "draft",
          realized_total: 0,
          red_alerts: 2,
          yellow_alerts: 1,
          oss_submitted: false,
          client_approved: false,
          updated_at: "2026-01-01T00:00:00Z",
        },
        {
          id: 2,
          client_id: 7,
          company_name: "Acme Test PT",
          quarter: "Q2",
          year: YEAR,
          status: "draft",
          realized_total: 0,
          red_alerts: 0,
          yellow_alerts: 1,
          oss_submitted: false,
          client_approved: false,
          updated_at: "2026-01-01T00:00:00Z",
        },
        {
          id: 3,
          client_id: 7,
          company_name: "Acme Test PT",
          quarter: "Q3",
          year: YEAR,
          status: "draft",
          realized_total: 0,
          red_alerts: 0,
          yellow_alerts: 0,
          oss_submitted: false,
          client_approved: false,
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
  });

  it("renders an accessible pip per quarter and no emoji code points anywhere", async () => {
    const { TaxTab } = await import("./TaxTab");
    const { container } = render(
      <TaxTab
        clientId={7}
        formatDate={(d: string) => d}
        client={null}
        taxConsultants={[]}
      />,
    );

    await waitFor(() =>
      expect(
        screen.getByRole("img", { name: "2 alerts need attention" }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("img", { name: "1 warning" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "No alerts" })).toBeInTheDocument();

    expect(container.innerHTML).not.toMatch(EMOJI_PATTERN);
  });
});
