import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mockApiGet, mockToastError } = vi.hoisted(() => ({
  mockApiGet: vi.fn(),
  mockToastError: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: { get: mockApiGet },
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ error: mockToastError }),
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn() },
}));

import LKPMPage from "./page";

const HISTORY = [
  {
    id: 1,
    quarter: "Q2",
    year: 2026,
    status: "validated",
    realized_total: 1_000_000_000,
    oss_submitted: false,
    client_approved: false,
    days_to_deadline: 20,
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-01T00:00:00Z",
  },
  {
    id: 2,
    quarter: "Q1",
    year: 2026,
    status: "submitted",
    realized_total: 2_000_000_000,
    oss_submitted: true,
    oss_receipt_number: "RCP-2026-001",
    client_approved: true,
    days_to_deadline: null,
    created_at: "2026-03-01T00:00:00Z",
    updated_at: "2026-03-01T00:00:00Z",
  },
];

const DEADLINES = [
  {
    quarter: "Q3",
    year: 2026,
    deadline: new Date(Date.now() + 41 * 86400000).toISOString(),
    days_remaining: 41,
    is_overdue: false,
  },
];

const RECEIPTS = [
  {
    id: 1,
    lkpm_report_id: 2,
    nomor_laporan: "LP-2026-001",
    nomor_kegiatan_usaha: "NKU-1",
    kbli_code: "56101",
    kegiatan_usaha_desc: null,
    stage: "PRODUKSI",
    oss_status: "Disetujui",
    lokasi: null,
    tanggal_diterima: "2026-04-10",
    nama_perusahaan_oss: null,
    file_drive_id: null,
    file_drive_url: "https://example.com/receipt.pdf",
    file_name: null,
    quarter: "Q1",
    year: 2026,
    company_name: "PT Example",
  },
];

function mockEndpoints() {
  mockApiGet.mockImplementation((url: string) => {
    if (url === "/api/v1/lkpm/history/me")
      return Promise.resolve({ success: true, items: HISTORY });
    if (url === "/api/v1/lkpm/deadlines")
      return Promise.resolve({ success: true, deadlines: DEADLINES });
    if (url === "/api/v1/lkpm/receipts/me")
      return Promise.resolve({ success: true, items: RECEIPTS });
    return Promise.reject(new Error(`unexpected ${url}`));
  });
}

async function renderLoaded() {
  mockEndpoints();
  const utils = render(<LKPMPage />);
  await screen.findByText("Perlu persetujuan Anda");
  return utils;
}

describe("LKPMPage (list)", () => {
  it("renders the day masthead and token-driven surfaces (WS3 slice 5)", async () => {
    const { container } = await renderLoaded();

    // Day masthead: copper rule + Cormorant serif headline in --tx-pure.
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("LKPM Reports");
    expect(heading.style.fontFamily).toBe("var(--font-serif)");
    expect(heading.className).toContain("text-[var(--tx-pure)]");
    expect(
      container.querySelector(
        '[aria-hidden="true"].bg-\\[var\\(--bz-copper\\)\\]',
      ),
    ).not.toBeNull();

    // Card surfaces read theme tokens, not the old dark rgba glass.
    expect(container.innerHTML).toContain("var(--bz-elevated)");
    expect(container.innerHTML).not.toContain("rgba(30,30,35,0.7)");
    expect(container.innerHTML).not.toContain("rgba(255,255,255,0.05)");

    // Drain guard: no hardcoded hex colors anywhere in the page output.
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it("maps the 3-state report indicator to the semantic --state-* tokens", async () => {
    await renderLoaded();

    // Orange: validated, awaiting client approval → warning.
    const orangeLabel = screen.getByText("Perlu persetujuan Anda");
    expect(orangeLabel.style.color).toBe("var(--state-warning)");
    // Green: submitted to OSS → success.
    const greenLabel = screen.getByText("Sudah dilapor ke OSS");
    expect(greenLabel.style.color).toBe("var(--state-success)");
    expect(screen.getByText("No. RCP-2026-001")).toBeInTheDocument();
    // Accent borders are color-mix tints of the same state tokens.
    // (label span → status row → title col → header row → card)
    const orangeCard =
      orangeLabel.closest("div")?.parentElement?.parentElement?.parentElement;
    expect(orangeCard?.style.borderColor).toContain("var(--state-warning)");
    const greenCard =
      greenLabel.closest("div")?.parentElement?.parentElement?.parentElement;
    expect(greenCard?.style.borderColor).toContain("var(--state-success)");
  });

  it("colors the next-deadline panel with the success state token", async () => {
    await renderLoaded();

    // days_remaining = 41 → > 30 → --state-success (icon + tint panel).
    const deadlineText = screen.getByText(/41 days remaining/);
    const panel = deadlineText.closest("div")?.parentElement;
    expect(panel?.style.background).toContain("var(--state-success) 8%");
    expect(panel?.style.borderColor).toContain("var(--state-success) 30%");
  });

  it("renders OSS receipt statuses and copper accents with tokens", async () => {
    await renderLoaded();

    // Approved receipt status → --state-success.
    const statusCell = screen.getByText(/Disetujui/);
    expect(statusCell.style.color).toBe("var(--state-success)");
    // Period group header: small copper text on the AA daylight step.
    // ("Q1 2026" also appears as a report-card title, so pick the styled one.)
    const periodHeader = screen
      .getAllByText("Q1 2026")
      .find((el) => el.style.color !== "");
    expect(periodHeader?.style.color).toBe(
      "var(--bz-copper-text, var(--tx-secondary))",
    );
    // Receipt count summary: approved count in --state-success.
    expect(screen.getByText("1 approved").style.color).toBe(
      "var(--state-success)",
    );
    // PDF link: small copper text on the AA daylight step.
    expect(screen.getByText("Open").style.color).toBe(
      "var(--bz-copper-text, var(--tx-secondary))",
    );
  });

  it("renders the loading skeleton without hardcoded dark surfaces", () => {
    mockApiGet.mockReturnValue(new Promise(() => {}));
    const { container } = render(<LKPMPage />);
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    expect(container.innerHTML).not.toContain("rgba(30,30,35,0.7)");
    expect(container.innerHTML).not.toContain("rgba(255,255,255,0.05)");
  });
});
