import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { ApiError } from "@/lib/api/error-handler";

const mocks = vi.hoisted(() => ({
  approveLKPMDraft: vi.fn(),
  getLKPMDraft: vi.fn(),
  loggerError: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ quarter: "Q2" }),
  useRouter: () => ({ push: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams("year=2026"),
}));

vi.mock("@/lib/api", () => ({
  api: {
    portal: {
      getLKPMDraft: mocks.getLKPMDraft,
      approveLKPMDraft: mocks.approveLKPMDraft,
    },
  },
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({
    error: mocks.toastError,
    success: mocks.toastSuccess,
  }),
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: mocks.loggerError },
}));

import LKPMReviewPage from "./page";
import LKPMQuarterError from "./error";

const VALIDATED_DRAFT = {
  id: 22,
  client_id: 42,
  company_id: 7,
  quarter: "Q2",
  year: 2026,
  status: "validated",
  realized: {
    equipment_domestic: 1000000,
    equipment_import: 0,
    building_domestic: 0,
    building_import: 0,
    vehicle_domestic: 0,
    vehicle_import: 0,
    land: 0,
    working_capital: 250000,
    other: 0,
    total_domestic: 1250000,
    total_import: 0,
    grand_total: 1250000,
  },
  cumulative: {
    equipment_domestic: 1000000,
    equipment_import: 0,
    building_domestic: 0,
    building_import: 0,
    vehicle_domestic: 0,
    vehicle_import: 0,
    land: 0,
    working_capital: 250000,
    other: 0,
    total_domestic: 1250000,
    total_import: 0,
    grand_total: 1250000,
  },
  employment: { tki: 3, tka: 1, total: 4 },
  quarterly_revenue: 5000000,
  annual_revenue: 20000000,
  narrative_obstacles: null,
  narrative_plans: null,
  validation_alerts: [],
  client_approved: false,
  client_approved_at: null,
  oss_submitted: false,
  oss_submitted_at: null,
  oss_receipt_number: null,
  data_source: "manual",
  has_ai_categorized_items: false,
  ai_categorized_count: 0,
  created_at: null,
  updated_at: null,
};

describe("LKPM quarter page (day edition)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getLKPMDraft.mockResolvedValue(VALIDATED_DRAFT);
    mocks.approveLKPMDraft.mockResolvedValue({ success: true });
  });

  it("renders the error state with --state-danger tokens", () => {
    const { container } = render(
      <LKPMQuarterError error={new Error("boom")} reset={() => {}} />,
    );
    const html = container.innerHTML;
    expect(html).toContain("var(--state-danger)");
    expect(html).not.toContain("--neon-rose");
  });

  it("distinguishes a failed read from a verified missing draft and recovers", async () => {
    mocks.getLKPMDraft
      .mockRejectedValueOnce(new Error("synthetic private transport detail"))
      .mockResolvedValueOnce(VALIDATED_DRAFT);

    render(<LKPMReviewPage />);

    expect(
      await screen.findByRole("heading", { name: "Unable to load LKPM draft" }),
    ).toBeVisible();
    expect(screen.queryByText(/No draft found for/)).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(
      "synthetic private transport detail",
    );

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(
      await screen.findByRole("heading", { name: "Q2 2026 — LKPM Draft" }),
    ).toBeVisible();
    expect(mocks.getLKPMDraft).toHaveBeenCalledTimes(2);
  });

  it("shows the empty contract only after a verified 404", async () => {
    mocks.getLKPMDraft.mockRejectedValue(
      new ApiError("private not-found detail", 404),
    );

    render(<LKPMReviewPage />);

    expect(
      await screen.findByText("No draft found for Q2 2026."),
    ).toBeVisible();
    expect(
      screen.queryByRole("heading", { name: "Unable to load LKPM draft" }),
    ).not.toBeInTheDocument();
    expect(mocks.toastError).not.toHaveBeenCalled();
  });

  it("approves a validated draft through the owned mutation", async () => {
    render(<LKPMReviewPage />);

    fireEvent.click(
      await screen.findByRole("button", { name: "Approve Draft" }),
    );

    await waitFor(() => {
      expect(mocks.approveLKPMDraft).toHaveBeenCalledWith(22);
    });
    expect(
      await screen.findByText(
        "This report has been approved. Your team will submit it to OSS.",
      ),
    ).toBeVisible();
  });

  it("keeps the page free of dark-era raw hexes (drain guard)", () => {
    const raw = readFileSync(join(__dirname, "page.tsx"), "utf8");
    // Comments may document what was drained; judge only code lines.
    const src = raw
      .split("\n")
      .filter(
        (l) =>
          !l.trimStart().startsWith("*") && !l.trimStart().startsWith("//"),
      )
      .join("\n");
    for (const forbidden of [
      "#f87171", // token-lint-ok: drain-guard assertion string, not a color use
      "#fbbf24", // token-lint-ok: drain-guard assertion string, not a color use
      "#34d399", // token-lint-ok: drain-guard assertion string, not a color use
      "rgba(244,63,94",
      "rgba(245,158,11",
      "--neon-rose",
    ]) {
      expect(src.includes(forbidden), `found ${forbidden}`).toBe(false);
    }
  });
});
