import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { act, render, screen, fireEvent } from "@testing-library/react";
import type { ProcessTimelineData } from "@/lib/schemas/process";

const { mockUseProcessTimeline } = vi.hoisted(() => ({
  mockUseProcessTimeline: vi.fn(),
}));

vi.mock("@/hooks/useProcessTimeline", () => ({
  useProcessTimeline: (practiceId: string) =>
    mockUseProcessTimeline(practiceId),
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));

import PracticeDetailPage from "./page";

function makeData(
  overrides: Partial<ProcessTimelineData> = {},
): ProcessTimelineData {
  return {
    practice_id: 603,
    practice_name: "KITAS Investor",
    practice_category: "VISA",
    current_status: "on_process",
    assigned_to: null,
    steps: [
      {
        status: "inquiry",
        label: "Inquiry",
        completed: true,
        is_current: false,
        changed_at: "2026-06-01T09:00:00Z",
        changed_by: "team",
      },
      {
        status: "on_process",
        label: "On Process",
        completed: false,
        is_current: true,
        changed_at: "2026-07-10T09:00:00Z",
        changed_by: "team",
      },
    ],
    ...overrides,
  };
}

// The page calls React `use(params)`, so it suspends on first mount: render
// inside an awaited act() + Suspense boundary so the resolved promise
// unrolls and the page content commits.
async function renderPage(overrides: Partial<ProcessTimelineData> = {}) {
  mockUseProcessTimeline.mockReturnValue({
    data: makeData(overrides),
    error: undefined,
    isLoading: false,
    mutate: vi.fn(),
  });
  await act(async () => {
    render(
      <React.Suspense fallback={null}>
        <PracticeDetailPage params={Promise.resolve({ practiceId: "603" })} />
      </React.Suspense>,
    );
  });
}

describe("PracticeDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the practice name in the Day serif masthead", async () => {
    await renderPage();
    const heading = screen.getByRole("heading", {
      level: 1,
      name: "KITAS Investor",
    });
    expect(heading).toHaveStyle({ fontFamily: "var(--font-serif)" });
    expect(heading.className).toContain("text-[var(--tx-pure)]");
    // Category reads copper-text with the slice-1 fallback
    expect(screen.getByText("VISA").className).toContain(
      "text-[var(--bz-copper-text,var(--tx-secondary))]",
    );
  });

  it("links back to the process list with the copper-text accent", async () => {
    await renderPage();
    const back = screen.getByRole("link", { name: /all practices/i });
    expect(back).toHaveAttribute("href", "/portal/process");
    expect(back.className).toContain(
      "text-[var(--bz-copper-text,var(--tx-secondary))]",
    );
  });

  it("drives timeline step badges from semantic --state-* tokens", async () => {
    await renderPage();
    // on_process → --state-info (was raw #d4845a / --bz-accent)
    const badge = screen.getAllByLabelText("Status: On Process")[0];
    expect(badge.style.color).toContain("--state-info");
    // completed inquiry step → neutral text-tertiary token
    const inquiryBadge = screen.getAllByLabelText("Status: Inquiry")[0];
    expect(inquiryBadge.style.color).toContain("--text-tertiary");
  });

  it("shows the blocked CTA with --state-danger styling when cancelled", async () => {
    await renderPage({
      current_status: "cancelled",
      assigned_to: "legal team",
    });
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/Practice blocked: legal team\./i);
    const icon = alert.querySelector("svg");
    expect(icon).toHaveStyle({ color: "var(--state-danger)" });
  });

  it("renders the error state with a working retry", async () => {
    const mutate = vi.fn();
    mockUseProcessTimeline.mockReturnValue({
      data: undefined,
      error: new Error("boom"),
      isLoading: false,
      mutate,
    });
    await act(async () => {
      render(
        <React.Suspense fallback={null}>
          <PracticeDetailPage params={Promise.resolve({ practiceId: "603" })} />
        </React.Suspense>,
      );
    });
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/Unable to load the timeline/i);
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(mutate).toHaveBeenCalledTimes(1);
  });

  it("renders the loading skeleton while fetching", async () => {
    mockUseProcessTimeline.mockReturnValue({
      data: undefined,
      error: undefined,
      isLoading: true,
      mutate: vi.fn(),
    });
    await act(async () => {
      render(
        <React.Suspense fallback={null}>
          <PracticeDetailPage params={Promise.resolve({ practiceId: "603" })} />
        </React.Suspense>,
      );
    });
    expect(screen.getByLabelText("Loading timeline")).toBeInTheDocument();
  });
});
