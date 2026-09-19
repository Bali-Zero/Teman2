/** Company ledger behaviour — synthetic fixtures only, no client data. */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CompanyTab } from "./CompanyTab";
import type { ClientCompanyLink, ClientProfile } from "@/lib/api/crm/crm.types";

const {
  mockGetClientCompanies,
  mockGetCompany,
  mockSearchCompanyByName,
  mockPost,
} = vi.hoisted(() => ({
  mockGetClientCompanies: vi.fn(),
  mockGetCompany: vi.fn().mockResolvedValue({ associates: [], documents: [] }),
  mockSearchCompanyByName: vi.fn().mockResolvedValue(null),
  mockPost: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    crm: {
      getClientCompanies: mockGetClientCompanies,
      getCompany: mockGetCompany,
      searchCompanyByName: mockSearchCompanyByName,
      getCompanyDocuments: vi.fn().mockResolvedValue([]),
    },
    post: mockPost,
  },
}));

vi.mock("@/lib/logger", () => ({ logger: { error: vi.fn() } }));

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}));

// Stubbed so the "no per-tab AI card" assertions can fail: the real card
// carries no test id, so without this a restored card would stay invisible.
vi.mock("./AiSummaryCard", () => ({
  AiSummaryCard: () => <div data-testid="AiSummaryCard" />,
}));

vi.mock("@/hooks/useOcrPolling", () => ({
  useOcrPolling: () => ({ ocrPolling: false, pollOcrStatus: vi.fn() }),
}));

const CLIENT = {
  id: 412,
  full_name: "Client A",
  company_name: undefined,
} as unknown as ClientProfile["client"];

function link(overrides: Partial<ClientCompanyLink> = {}): ClientCompanyLink {
  return {
    link_id: 1,
    company_id: 90,
    company_name: "PT Synthetic Studio",
    company_type: "PT",
    role: "director",
    is_primary: true,
    status: "active",
    company_status: "active",
    nib: "9120000000001",
    npwp_company: "84.221.907.4-901.000",
    kbli_code: "70209",
    kbli_description: "Other Management Consulting Activities",
    registered_address: "Jl. Synthetic No. 1",
    city: "Denpasar",
    province: "Bali",
    ...overrides,
  } as ClientCompanyLink;
}

const renderTab = () =>
  render(
    <CompanyTab
      clientId={412}
      client={CLIENT}
      documents={[]}
      formatDate={(d: string) => `formatted:${d}`}
      onRefresh={() => Promise.resolve()}
    />,
  );

afterEach(() => vi.clearAllMocks());
beforeEach(() => {
  mockGetCompany.mockResolvedValue({ associates: [], documents: [] });
  mockSearchCompanyByName.mockResolvedValue(null);
});

describe("CompanyTab — r19 kv-grid ledger", () => {
  it("empty state: no company, no company name, no docs — r19 EmptyState sentence, no dashed box, no AiSummaryCard", async () => {
    mockGetClientCompanies.mockResolvedValueOnce([]);
    render(
      <CompanyTab
        clientId={412}
        client={{ ...CLIENT, company_name: undefined }}
        documents={[]}
        formatDate={(d: string) => d}
        onRefresh={() => Promise.resolve()}
      />,
    );
    expect(
      await screen.findByText("No company linked yet."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add company" }),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("AiSummaryCard")).not.toBeInTheDocument();
  });

  it("GUILT: company_type 'PT' renders through companyType.ts as 'PT (local / PMDN)', not the raw string (PR 6827 gap)", async () => {
    mockGetClientCompanies.mockResolvedValueOnce([
      link({ company_type: "PT" }),
    ]);
    renderTab();
    expect(await screen.findByText("PT (local / PMDN)")).toBeInTheDocument();
    // The raw, unmapped string must not appear as its own cell value.
    expect(screen.queryByText("PT", { exact: true })).not.toBeInTheDocument();
  });

  it("GUILT: a legacy alias (PMDN) normalises to the same canonical label", async () => {
    mockGetClientCompanies.mockResolvedValueOnce([
      link({ company_type: "PMDN" }),
    ]);
    renderTab();
    expect(await screen.findByText("PT (local / PMDN)")).toBeInTheDocument();
  });

  it("company identity kv-grid shows legal name, NIB, NPWP, KBLI and address from real fields", async () => {
    mockGetClientCompanies.mockResolvedValueOnce([link()]);
    renderTab();
    expect(await screen.findByText("PT Synthetic Studio")).toBeInTheDocument();
    expect(screen.getByText("9120000000001")).toBeInTheDocument();
    expect(screen.getByText("84.221.907.4-901.000")).toBeInTheDocument();
    // "70209" and its description appear twice by design: once as the
    // at-a-glance identity kv-item, once as the full row in Business
    // activities (parity items 35-37 — both old facts kept, not merged).
    expect(screen.getAllByText("70209").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Other Management Consulting Activities").length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("Jl. Synthetic No. 1")).toBeInTheDocument();
    expect(screen.queryByTestId("AiSummaryCard")).not.toBeInTheDocument();
  });

  it("identity glosses survive the restyle: NIB and NPWP expansions, and the Indonesian entity-type expansion on a legacy spelling", async () => {
    mockGetClientCompanies.mockResolvedValueOnce([
      link({ company_type: "PT_PMA" }),
    ]);
    renderTab();
    expect(
      await screen.findByText("Nomor Induk Berusaha · OSS registered"),
    ).toBeInTheDocument();
    expect(screen.getByText("Tax Identification Number")).toBeInTheDocument();
    expect(screen.getByText("PT PMA")).toBeInTheDocument();
    expect(screen.getByText("Penanaman Modal Asing")).toBeInTheDocument();
  });

  it("INNOCENCE: an entity type with no known expansion shows no gloss", async () => {
    mockGetClientCompanies.mockResolvedValueOnce([
      link({ company_type: "PT" }),
    ]);
    renderTab();
    await screen.findByText("PT (local / PMDN)");
    expect(screen.queryByText("Penanaman Modal Asing")).not.toBeInTheDocument();
  });

  it("INNOCENCE: 'Edit company' icon button is reachable when a company is linked", async () => {
    mockGetClientCompanies.mockResolvedValueOnce([link()]);
    renderTab();
    expect(
      await screen.findByRole("button", { name: "Edit company" }),
    ).toBeInTheDocument();
  });

  it("GUILT: 'Edit company' button is absent when there is no linked company_id", async () => {
    mockGetClientCompanies.mockResolvedValueOnce([]);
    render(
      <CompanyTab
        clientId={412}
        client={{ ...CLIENT, company_name: "Unlinked Co" }}
        documents={[]}
        formatDate={(d: string) => d}
        onRefresh={() => Promise.resolve()}
      />,
    );
    await screen.findByText("Unlinked Co");
    expect(
      screen.queryByRole("button", { name: "Edit company" }),
    ).not.toBeInTheDocument();
  });

  it("the NIB copy action writes to the clipboard and confirms", async () => {
    // fireEvent, not userEvent: userEvent.setup() installs its OWN clipboard
    // stub on navigator.clipboard, shadowing the vi.fn() from test/setup.tsx
    // that this assertion needs to inspect.
    mockGetClientCompanies.mockResolvedValueOnce([link()]);
    renderTab();
    const copyBtn = await screen.findByRole("button", { name: "Copy NIB" });
    fireEvent.click(copyBtn);
    await waitFor(() =>
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        "9120000000001",
      ),
    );
  });

  it("GUILT (gap closed): company_status 'dissolved' now renders its real word — the old chip rendered nothing for this value", async () => {
    mockGetClientCompanies.mockResolvedValueOnce([
      link({ company_status: "dissolved" }),
    ]);
    renderTab();
    expect(await screen.findByText("Dissolved")).toBeInTheDocument();
  });

  it("shareholders & officers: role and ownership stay visible without a colour-coded well", async () => {
    mockGetClientCompanies.mockResolvedValueOnce([link()]);
    mockGetCompany.mockResolvedValueOnce({
      associates: [
        {
          client_name: "Shareholder One",
          role: "director",
          ownership_percentage: 60,
          shares_count: 600,
        },
        {
          client_name: "Shareholder Two",
          role: "commissioner",
          ownership_percentage: 40,
          shares_count: 400,
        },
      ],
      documents: [],
    });
    renderTab();
    expect(await screen.findByText("Shareholder One")).toBeInTheDocument();
    expect(screen.getByText("director")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getByText("Shareholder Two")).toBeInTheDocument();
    expect(screen.getByText("40%")).toBeInTheDocument();
  });

  it("GUILT: OCR shareholders' ownership is a share of the company's shares_count, not of the OCR'd rows", async () => {
    mockGetClientCompanies.mockResolvedValueOnce([
      link({
        shares_count: 10000,
        custom_fields: {
          shareholders: [
            { name: "Holder A", role: "Director", shares: 4000 },
            { name: "Holder B", role: "Commissioner", shares: 4000 },
          ],
        },
      }),
    ]);
    renderTab();
    expect(await screen.findByText("Holder A")).toBeInTheDocument();
    expect(screen.getAllByText("40%")).toHaveLength(2);
    // 50% is what the rows' own sum (8000) would give.
    expect(screen.queryByText("50%")).not.toBeInTheDocument();
  });

  it("INNOCENCE: with no shares_count the OCR rows' own sum is the denominator", async () => {
    mockGetClientCompanies.mockResolvedValueOnce([
      link({
        custom_fields: {
          shareholders: [
            { name: "Holder A", shares: 4000 },
            { name: "Holder B", shares: 4000 },
          ],
        },
      }),
    ]);
    renderTab();
    expect(await screen.findByText("Holder A")).toBeInTheDocument();
    expect(screen.getAllByText("50%")).toHaveLength(2);
  });

  it("boundary: the OCR list replaces the linked associates only when it is LONGER (1 vs 1 keeps the associate, 2 vs 1 switches)", async () => {
    mockGetClientCompanies.mockResolvedValueOnce([
      link({
        custom_fields: { shareholders: [{ name: "Ocr Only", shares: 100 }] },
      }),
    ]);
    const first = renderTab();
    expect(await screen.findByText("Client A")).toBeInTheDocument();
    expect(screen.queryByText("Ocr Only")).not.toBeInTheDocument();
    first.unmount();

    mockGetClientCompanies.mockResolvedValueOnce([
      link({
        custom_fields: {
          shareholders: [
            { name: "Ocr Only", shares: 100 },
            { name: "Ocr Second", shares: 100 },
          ],
        },
      }),
    ]);
    renderTab();
    expect(await screen.findByText("Ocr Only")).toBeInTheDocument();
    expect(screen.queryByText("Client A")).not.toBeInTheDocument();
  });

  it("legal timeline: incorporation date renders only through the formatDate prop, never a raw locale format", async () => {
    mockGetClientCompanies.mockResolvedValueOnce([
      link({
        akta_pendirian_no: "12",
        akta_pendirian_date: "2019-03-04",
        sk_menhumkam_no: "AHU-000",
      }),
    ]);
    renderTab();
    // Renders twice by design: the Capital & shares kv-item and the Legal
    // timeline row each show the same real incorporation date independently
    // (same duplication the old KeyNumbersColumn/LegalTimeline pair had).
    const dates = await screen.findAllByText("formatted:2019-03-04");
    expect(dates.length).toBeGreaterThan(0);
    // The old component's own `toLocaleDateString(... {month:"long"})` would
    // have produced "March" — that must never appear, since formatDate is the
    // only sanctioned date renderer (SSR hydration law).
    expect(screen.queryByText(/March/)).not.toBeInTheDocument();
  });

  it("GUILT: the NIB/OSS timeline entry shows no fabricated year — the old heuristic (skDate year + 1) is dropped, not replaced by a guess", async () => {
    mockGetClientCompanies.mockResolvedValueOnce([
      link({
        nib: "9120000000001",
        sk_menhumkam_no: "AHU-000",
        sk_menhumkam_date: "2020-01-01",
        akta_pendirian_no: undefined,
        akta_pendirian_date: undefined,
      }),
    ]);
    renderTab();
    expect(
      await screen.findByText("NIB Issued & OSS Platform Verified"),
    ).toBeInTheDocument();
    // "2021" would be the old fabricated (skDate year + 1) guess.
    expect(screen.queryByText("2021")).not.toBeInTheDocument();
  });

  it("document vault renders its fixed slots when a company is linked", async () => {
    mockGetClientCompanies.mockResolvedValueOnce([link()]);
    renderTab();
    expect(await screen.findByText("Akta Pendirian")).toBeInTheDocument();
    expect(screen.getByText("NPWP Perusahaan")).toBeInTheDocument();
    expect(screen.getByText("Rekening Koran")).toBeInTheDocument();
  });
});
