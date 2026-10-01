import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  VisaOracleTestingGuideOverlay,
  guideDismissKey,
} from "./VisaOracleTestingGuideOverlay";
import type { CampaignData } from "../intelligence/visa-oracle/testing/types";

const mocks = vi.hoisted(() => ({ load: vi.fn(), pathname: "/dashboard" }));
vi.mock("../intelligence/visa-oracle/testing/api", () => ({
  testingApi: { load: mocks.load },
}));
vi.mock("next/navigation", () => ({ usePathname: () => mocks.pathname }));

const T0 = new Date("2026-09-30T19:00:00Z"); // 2026-10-01 03:00 WITA
const TODAY = "2026-10-01";

function assignment(index: number, status?: "started" | "submitted") {
  return {
    id: `a${index}`,
    slot: "T02",
    day: TODAY,
    index,
    can_record_results: true,
    scenario: { id: "s", title: "t", focus: "f", inputs: {}, instructions: [] },
    record: status
      ? {
          status,
          started_at: "x",
          submitted_at: status === "submitted" ? "y" : null,
        }
      : null,
  };
}

function fixture(opts: { slot?: string | null; allDone?: boolean } = {}) {
  const slot = opts.slot === undefined ? "T02" : opts.slot;
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
    viewer: { slot, can_review: false, can_configure: false },
    assignments: [1, 2, 3, 4, 5].map((i) =>
      assignment(
        i,
        opts.allDone ? "submitted" : i <= 2 ? "submitted" : undefined,
      ),
    ),
  } as unknown as CampaignData;
}

function mount(now: () => Date = () => T0) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <VisaOracleTestingGuideOverlay identity="tester@example.test" now={now} />
    </QueryClientProvider>,
  );
}

describe("VisaOracleTestingGuideOverlay", () => {
  beforeEach(() => {
    mocks.load.mockReset();
    mocks.pathname = "/dashboard";
    window.sessionStorage.clear();
  });

  it("shows for a slot holder with pending cases and links to the testing page", async () => {
    mocks.load.mockResolvedValue(fixture());
    mount();
    const dialog = await screen.findByRole("dialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(screen.getByText("Panduan Uji Visa Oracle")).toBeTruthy();
    expect(screen.getByText(/Hari ini: 2\/5 kasus terkirim\./)).toBeTruthy();
    const link = screen.getByRole("link", { name: /Mulai uji sekarang/ });
    expect(link.getAttribute("href")).toBe("/intelligence/visa-oracle/testing");
    await waitFor(() => expect(document.activeElement).toBe(link));
    fireEvent.click(link);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("is hidden on the testing page", async () => {
    mocks.pathname = "/intelligence/visa-oracle/testing";
    mocks.load.mockResolvedValue(fixture());
    mount();
    await waitFor(() => expect(mocks.load).toHaveBeenCalled());
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("is hidden when the viewer has no slot", async () => {
    mocks.load.mockResolvedValue(fixture({ slot: null }));
    mount();
    await waitFor(() => expect(mocks.load).toHaveBeenCalled());
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("is hidden when all of today's cases are submitted", async () => {
    mocks.load.mockResolvedValue(fixture({ allDone: true }));
    mount();
    await waitFor(() => expect(mocks.load).toHaveBeenCalled());
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("Nanti hides it for 30 minutes, then it shows again", async () => {
    mocks.load.mockResolvedValue(fixture());
    const first = mount();
    fireEvent.click(await screen.findByRole("button", { name: "Nanti" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(window.sessionStorage.getItem(guideDismissKey(TODAY))).toBe(
      String(T0.getTime()),
    );
    first.unmount();

    const at = (min: number) => () => new Date(T0.getTime() + min * 60_000);
    const second = mount(at(29));
    await waitFor(() => expect(mocks.load).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("dialog")).toBeNull();
    second.unmount();

    mount(at(31));
    expect(await screen.findByRole("dialog")).toBeTruthy();
  });

  it("is hidden on fetch error", async () => {
    mocks.load.mockRejectedValue(new Error("boom"));
    mount();
    await waitFor(() => expect(mocks.load).toHaveBeenCalled());
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("Escape dismisses it", async () => {
    mocks.load.mockResolvedValue(fixture());
    mount();
    await screen.findByRole("dialog");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(
      window.sessionStorage.getItem(guideDismissKey(TODAY)),
    ).not.toBeNull();
  });
});
