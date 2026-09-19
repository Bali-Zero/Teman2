// R7c restyle — new behaviour pin for the r19 ledger Tax tab.
//
// Synthetic fixtures only. The two pre-existing suites (TaxTab.consultants,
// TaxTab.healthPip) stay green untouched; this file adds the restyle-specific
// facts: lkpmHealth N/N+1 boundaries, the NPWP company-fallback provenance,
// every quarter status WORD, the "No report" placeholder, the deadline urgency
// ladder (3/4 and 7/8 boundaries), a receipt link outside any hover-gated
// container, the consultant revert path, and the disclosed AiSummaryCard drop
// (proved with an import probe, not a bare negative — if TaxTab imports the
// module again, the mock factory runs and the probe flips).
import React from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import type { Client, ClientCompanyLink } from "@/lib/api/crm/crm.types";
import type { LKPMBatchItem, LKPMReceipt } from "@/lib/api/portal/portal.types";
import { lkpmHealth } from "./TaxTab";

const YEAR = new Date().getFullYear();

const { mockUpdateClient, mockToastSuccess, mockToastError, aiSummaryProbe } =
  vi.hoisted(() => ({
    mockUpdateClient: vi.fn(),
    mockToastSuccess: vi.fn(),
    mockToastError: vi.fn(),
    aiSummaryProbe: { imported: false },
  }));

vi.mock("@/lib/api", () => ({
  api: {
    getProfile: vi.fn().mockResolvedValue({ email: "tester@example.test" }),
    crm: { updateClient: mockUpdateClient },
  },
}));

const { mockGetClientHistory, mockGetClientReceipts } = vi.hoisted(() => ({
  mockGetClientHistory: vi.fn(),
  mockGetClientReceipts: vi.fn(),
}));
vi.mock("@/lib/api/workspace/lkpm.api", () => ({
  lkpmApi: {
    getClientHistory: mockGetClientHistory,
    getClientReceipts: mockGetClientReceipts,
  },
}));

vi.mock("./AiSummaryCard", () => {
  aiSummaryProbe.imported = true;
  return { AiSummaryCard: () => <div data-testid="ai-summary-card" /> };
});

vi.mock("sonner", () => ({
  toast: {
    success: mockToastSuccess,
    error: mockToastError,
  },
}));

function mkReport(overrides: Partial<LKPMBatchItem> = {}): LKPMBatchItem {
  return {
    id: 1,
    client_id: 7,
    company_name: "Acme Test PT",
    quarter: "Q1",
    year: YEAR,
    status: "draft",
    realized_total: 0,
    red_alerts: 0,
    yellow_alerts: 0,
    oss_submitted: false,
    client_approved: false,
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const COMPANY_LINK: ClientCompanyLink = {
  link_id: 1,
  company_id: 2,
  company_name: "Acme Test PT",
  company_type: "PT PMA",
  role: "shareholder",
  is_primary: true,
  status: "active",
  npwp_company: "11.222.333.4-555.000",
  nib: "9120107642219",
};

beforeEach(() => {
  vi.clearAllMocks();
  mockGetClientHistory.mockResolvedValue({ items: [] });
  mockGetClientReceipts.mockResolvedValue({ items: [] });
  mockUpdateClient.mockResolvedValue({});
});

describe("lkpmHealth boundaries — N and N+1 must land on different levels", () => {
  it("0 red + 0 yellow is success, 1 red flips to critical", () => {
    expect(lkpmHealth({ red_alerts: 0, yellow_alerts: 0 })).toEqual({
      tone: "success",
      label: "No alerts",
    });
    expect(lkpmHealth({ red_alerts: 1, yellow_alerts: 0 })).toEqual({
      tone: "critical",
      label: "1 alert needs attention",
    });
  });

  it("0 yellow is success, 1 yellow flips to warning", () => {
    expect(lkpmHealth({ red_alerts: 0, yellow_alerts: 0 })).toEqual({
      tone: "success",
      label: "No alerts",
    });
    expect(lkpmHealth({ red_alerts: 0, yellow_alerts: 1 })).toEqual({
      tone: "warning",
      label: "1 warning",
    });
  });

  it("1 red + 1 yellow is critical — red wins over yellow", () => {
    expect(lkpmHealth({ red_alerts: 1, yellow_alerts: 1 })).toEqual({
      tone: "critical",
      label: "1 alert needs attention",
    });
  });
});

describe("Tax identity — NPWP/NIB provenance", () => {
  it("company fallback shows the value, the words 'via company' and the company name", async () => {
    const { TaxTab } = await import("./TaxTab");
    render(
      <TaxTab
        clientId={7}
        formatDate={(d: string) => d}
        client={null}
        companyLinks={[COMPANY_LINK]}
        taxConsultants={[]}
      />,
    );

    expect(await screen.findByText("11.222.333.4-555.000")).toBeInTheDocument();
    // Both NPWP and NIB fall back, each with its own "via company · …" line.
    expect(screen.getAllByText(/via company/).length).toBe(2);
    expect(screen.getAllByText(/via company · Acme Test PT/).length).toBe(2);
    // NIB falls back the same way.
    expect(screen.getByText("9120107642219")).toBeInTheDocument();
  });

  it("the client's own NPWP and NIB win over the company's", async () => {
    const { TaxTab } = await import("./TaxTab");
    const client = {
      npwp: "99.888.777.6-555.000",
      nib: "9120107000111",
    } as unknown as Client;
    render(
      <TaxTab
        clientId={7}
        formatDate={(d: string) => d}
        client={client}
        companyLinks={[COMPANY_LINK]}
        taxConsultants={[]}
      />,
    );

    expect(await screen.findByText("99.888.777.6-555.000")).toBeInTheDocument();
    expect(screen.getByText("9120107000111")).toBeInTheDocument();
    // The company's own numbers must not appear — the fallback is suppressed.
    expect(screen.queryByText("11.222.333.4-555.000")).not.toBeInTheDocument();
    expect(screen.queryByText("9120107642219")).not.toBeInTheDocument();
  });

  it("neither value nor fallback renders the words 'Not registered'", async () => {
    const { TaxTab } = await import("./TaxTab");
    render(
      <TaxTab
        clientId={7}
        formatDate={(d: string) => d}
        client={null}
        taxConsultants={[]}
      />,
    );

    expect((await screen.findAllByText("Not registered")).length).toBe(2);
  });
});

describe("LKPM quarter rows", () => {
  it("each quarter status renders its WORD — Draft, Validated, Approved, Submitted", async () => {
    mockGetClientHistory.mockResolvedValue({
      items: [
        mkReport({ id: 1, quarter: "Q1", status: "draft" }),
        mkReport({ id: 2, quarter: "Q2", status: "validated" }),
        mkReport({ id: 3, quarter: "Q3", status: "approved" }),
        mkReport({
          id: 4,
          quarter: "Q4",
          status: "draft",
          oss_submitted: true,
        }),
      ],
    });
    const { TaxTab } = await import("./TaxTab");
    render(
      <TaxTab
        clientId={7}
        formatDate={(d: string) => d}
        client={null}
        taxConsultants={[]}
      />,
    );

    const q1 = await screen.findByTestId("lkpm-row-Q1");
    expect(within(q1).getByText("Draft")).toBeInTheDocument();
    expect(
      within(screen.getByTestId("lkpm-row-Q2")).getByText("Validated"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("lkpm-row-Q3")).getByText("Approved"),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("lkpm-row-Q4")).getByText("Submitted"),
    ).toBeInTheDocument();
    // The LKPM header carries the selected year.
    expect(screen.getByRole("heading", { name: /LKPM/ })).toHaveTextContent(
      String(YEAR),
    );
  });

  it("a quarter with no report renders the 'No report' placeholder", async () => {
    mockGetClientHistory.mockResolvedValue({
      items: [mkReport({ id: 1, quarter: "Q1" })],
    });
    const { TaxTab } = await import("./TaxTab");
    render(
      <TaxTab
        clientId={7}
        formatDate={(d: string) => d}
        client={null}
        taxConsultants={[]}
      />,
    );

    expect(await screen.findByTestId("lkpm-row-Q2-empty")).toHaveTextContent(
      "No report",
    );
    // Quarters with a report never show the placeholder.
    expect(screen.queryByTestId("lkpm-row-Q1-empty")).not.toBeInTheDocument();
  });

  it("no LKPM data at all still renders the static Q1-Q4 placeholders", async () => {
    const { TaxTab } = await import("./TaxTab");
    render(
      <TaxTab
        clientId={7}
        formatDate={(d: string) => d}
        client={null}
        taxConsultants={[]}
      />,
    );

    for (const q of ["Q1", "Q2", "Q3", "Q4"]) {
      expect(
        await screen.findByTestId(`lkpm-row-${q}-empty`),
      ).toHaveTextContent("No report");
    }
  });

  it("deadline urgency: 3 is semibold warning, 4 is warning, 8 is calm, overdue has a word", async () => {
    mockGetClientHistory.mockResolvedValue({
      items: [
        mkReport({ id: 1, quarter: "Q1", days_to_deadline: 3 }),
        mkReport({ id: 2, quarter: "Q2", days_to_deadline: 4 }),
        mkReport({ id: 3, quarter: "Q3", days_to_deadline: 8 }),
        mkReport({ id: 4, quarter: "Q4", days_to_deadline: -1 }),
      ],
    });
    const { TaxTab } = await import("./TaxTab");
    render(
      <TaxTab
        clientId={7}
        formatDate={(d: string) => d}
        client={null}
        taxConsultants={[]}
      />,
    );

    const q1 = within(await screen.findByTestId("lkpm-row-Q1")).getByText(
      "Due in 3 days",
    );
    expect(q1.style.color).toBe("var(--state-warning)");
    expect(q1.className).toContain("font-semibold");

    const q2 = within(screen.getByTestId("lkpm-row-Q2")).getByText(
      "Due in 4 days",
    );
    expect(q2.style.color).toBe("var(--state-warning)");
    expect(q2.className).not.toContain("font-semibold");

    const q3 = within(screen.getByTestId("lkpm-row-Q3")).getByText(
      "Due in 8 days",
    );
    expect(q3.style.color).toBe("var(--tx-secondary)");

    const q4 = within(screen.getByTestId("lkpm-row-Q4")).getByText(
      "Overdue by 1 day",
    );
    expect(q4.style.color).toBe("var(--state-warning)");
    expect(q4.className).toContain("font-semibold");
  });

  it("a submitted quarter has no deadline cell and keeps its Open link", async () => {
    mockGetClientHistory.mockResolvedValue({
      items: [mkReport({ id: 9, quarter: "Q1", oss_submitted: true })],
    });
    const { TaxTab } = await import("./TaxTab");
    render(
      <TaxTab
        clientId={7}
        formatDate={(d: string) => d}
        client={null}
        taxConsultants={[]}
      />,
    );

    const q1 = await screen.findByTestId("lkpm-row-Q1");
    expect(within(q1).queryByText(/Due in|Overdue/)).not.toBeInTheDocument();
    expect(within(q1).getByRole("link", { name: "Open" })).toHaveAttribute(
      "href",
      "/lkpm/9",
    );
  });
});

describe("OSS tanda terima receipts", () => {
  const RECEIPT: LKPMReceipt = {
    id: 5,
    lkpm_report_id: 1,
    nomor_laporan: "LAP-0001",
    nomor_kegiatan_usaha: "NU-901",
    kbli_code: "56101",
    kegiatan_usaha_desc: "Restaurant",
    stage: "PRODUKSI",
    oss_status: "Disetujui",
    lokasi: "Badung",
    tanggal_diterima: "2026-07-09",
    nama_perusahaan_oss: null,
    file_drive_url: "https://drive.example.test/receipt-5",
    file_name: "receipt-5.pdf",
    quarter: "Q2",
    year: YEAR,
    company_name: "Acme Test PT",
  };

  it("the receipt Open link is reachable and not inside a hover-gated container", async () => {
    mockGetClientReceipts.mockResolvedValue({ items: [RECEIPT] });
    const { TaxTab } = await import("./TaxTab");
    render(
      <TaxTab
        clientId={7}
        formatDate={(d: string) => d}
        client={null}
        taxConsultants={[]}
      />,
    );

    const link = await screen.findByRole("link", { name: "Open" });
    expect(link).toHaveAttribute(
      "href",
      "https://drive.example.test/receipt-5",
    );
    // The R6 defect: controls that lived in HairlineRow's hover-gated
    // `actions` slot vanished under (hover:none). Walk every ancestor and
    // prove none carries the hiding classes.
    let el: HTMLElement | null = link;
    while (el) {
      expect(el.className).not.toMatch(/opacity-0/);
      expect(el.className).not.toMatch(/\[@media\(hover:none\)\]:hidden/);
      el = el.parentElement;
    }
  });

  it("the OSS receipt carries the perusahaan-usaha number visibly, not as a tooltip", async () => {
    mockGetClientReceipts.mockResolvedValue({ items: [RECEIPT] });
    const { TaxTab } = await import("./TaxTab");
    const { container } = render(
      <TaxTab
        clientId={7}
        formatDate={(d: string) => d}
        client={null}
        taxConsultants={[]}
      />,
    );

    expect(await screen.findByText("NU-901")).toBeInTheDocument();
    expect(container.querySelector("[title]")).toBeNull();
  });

  it("the section is hidden when there are no receipts", async () => {
    const { TaxTab } = await import("./TaxTab");
    render(
      <TaxTab
        clientId={7}
        formatDate={(d: string) => d}
        client={null}
        taxConsultants={[]}
      />,
    );

    await waitFor(() =>
      expect(screen.getByTestId("lkpm-row-Q1-empty")).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("heading", { name: /OSS tanda terima/ }),
    ).not.toBeInTheDocument();
  });
});

describe("Tax consultant save and revert", () => {
  it("reverts the select to its previous value and toasts an error when the save fails", async () => {
    const user = userEvent.setup();
    mockUpdateClient.mockRejectedValue(new Error("network down"));
    const { TaxTab } = await import("./TaxTab");
    const client = {
      tax_consultant: "alpha.tax@example.test",
    } as unknown as Client;
    render(
      <TaxTab
        clientId={7}
        formatDate={(d: string) => d}
        client={client}
        taxConsultants={[
          { value: "alpha.tax@example.test", label: "Alpha" },
          { value: "beta.tax@example.test", label: "Beta" },
        ]}
      />,
    );

    const select = (await screen.findByLabelText(
      "Tax Consultant",
    )) as HTMLSelectElement;
    expect(select.value).toBe("alpha.tax@example.test");

    await user.selectOptions(select, "beta.tax@example.test");
    await waitFor(() => expect(mockUpdateClient).toHaveBeenCalled());
    await waitFor(() =>
      expect(mockToastError).toHaveBeenCalledWith(
        "Failed to update tax consultant",
        { description: "network down" },
      ),
    );
    // The optimistic value is rolled back — the select shows the old value.
    expect(select.value).toBe("alpha.tax@example.test");
  });
});

describe("AiSummaryCard removal (v3 drops the per-tab card)", () => {
  it("TaxTab no longer imports or renders AiSummaryCard", async () => {
    const { TaxTab } = await import("./TaxTab");
    render(
      <TaxTab
        clientId={7}
        formatDate={(d: string) => d}
        client={null}
        taxConsultants={[]}
      />,
    );

    await screen.findByRole("heading", { name: "Tax identity" });
    expect(screen.queryByTestId("ai-summary-card")).not.toBeInTheDocument();
    // The probe: the mocked module's factory sets this flag the moment
    // anything imports it. A bare negative on an unrendered id could never
    // fail; the import probe can.
    expect(aiSummaryProbe.imported).toBe(false);
  });
});
