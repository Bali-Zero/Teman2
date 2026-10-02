import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { VisaOracleTestingBanner } from "./VisaOracleTestingBanner";
import type { CampaignData } from "../intelligence/visa-oracle/testing/types";

const mocks = vi.hoisted(() => ({ load: vi.fn() }));
vi.mock("../intelligence/visa-oracle/testing/api", () => ({
  testingApi: { load: mocks.load },
}));

// 2026-10-01 03:00 WITA is still 2026-09-30 19:00 UTC: proves the Bali calendar.
const NOW = () => new Date("2026-09-30T19:00:00Z");
const TODAY = "2026-10-01";

function assignment(
  index: number,
  over: { slot?: string; day?: string; status?: "started" | "submitted" } = {},
) {
  return {
    id: `a${index}-${over.slot ?? "T02"}-${over.day ?? TODAY}`,
    slot: over.slot ?? "T02",
    day: over.day ?? TODAY,
    index,
    can_record_results: true,
    scenario: { id: "s", title: "t", focus: "f", inputs: {}, instructions: [] },
    record: over.status
      ? {
          status: over.status,
          started_at: "x",
          submitted_at: over.status === "submitted" ? "y" : null,
        }
      : null,
  };
}

function fixture(over: Record<string, unknown> = {}): CampaignData {
  return {
    campaign: {
      id: "c",
      start_date: "2026-09-30",
      end_date: "2026-10-02",
      timezone: "Asia/Makassar",
      planned: 150,
      per_day: 5,
      plan_version: "v1",
    },
    viewer: { slot: "T02", can_review: false, can_configure: false },
    assignments: [
      assignment(1, { status: "submitted" }),
      assignment(2, { status: "submitted" }),
      assignment(3, { status: "started" }),
      assignment(4),
      assignment(5),
      // Another tester's case and another day must not count.
      assignment(1, { slot: "T03", status: "submitted" }),
      assignment(1, { day: "2026-09-30", status: "submitted" }),
    ],
    ...over,
  } as unknown as CampaignData;
}

function renderBanner() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <VisaOracleTestingBanner identity="tester@example.test" now={NOW} />
    </QueryClientProvider>,
  );
}

const banner = () => screen.queryByTestId("visa-oracle-testing-banner");

describe("VisaOracleTestingBanner", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows for a slot holder with pending cases today", async () => {
    mocks.load.mockResolvedValue(fixture());
    renderBanner();
    expect(await screen.findByRole("region")).toHaveAccessibleName(
      "Pengingat Uji Visa Oracle",
    );
    expect(screen.getByText("Uji Visa Oracle — hari ini")).toBeInTheDocument();
    expect(screen.getByText(/zantara@balizero.com/)).toBeInTheDocument();
    expect(screen.getByText("2/5 kasus hari ini terkirim")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Mulai uji sekarang →" }),
    ).toHaveAttribute("href", "/intelligence/visa-oracle/testing");
  });

  it("is hidden when the viewer has no slot", async () => {
    mocks.load.mockResolvedValue(
      fixture({
        viewer: { slot: null, can_review: true, can_configure: true },
      }),
    );
    renderBanner();
    await waitFor(() => expect(mocks.load).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 20));
    expect(banner()).not.toBeInTheDocument();
  });

  it("is hidden when all of today's own cases are submitted", async () => {
    mocks.load.mockResolvedValue(
      fixture({
        assignments: [1, 2, 3, 4, 5].map((i) =>
          assignment(i, { status: "submitted" }),
        ),
      }),
    );
    renderBanner();
    await waitFor(() => expect(mocks.load).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 20));
    expect(banner()).not.toBeInTheDocument();
  });

  it("is hidden when today is outside start..end", async () => {
    mocks.load.mockResolvedValue(
      fixture({
        campaign: {
          id: "c",
          start_date: "2026-10-02",
          end_date: "2026-10-04",
          timezone: "Asia/Makassar",
          planned: 150,
          per_day: 5,
          plan_version: "v1",
        },
      }),
    );
    renderBanner();
    await waitFor(() => expect(mocks.load).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 20));
    expect(banner()).not.toBeInTheDocument();
  });

  it("is hidden on fetch error", async () => {
    mocks.load.mockRejectedValue(new Error("403"));
    renderBanner();
    await waitFor(() => expect(mocks.load).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 20));
    expect(banner()).not.toBeInTheDocument();
  });
});
