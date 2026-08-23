import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const {
  mockUsePortalBilling,
  mockGetInvoicePdfUrl,
  mockToastError,
  mockRefetch,
} = vi.hoisted(() => ({
  mockUsePortalBilling: vi.fn(),
  mockGetInvoicePdfUrl: vi.fn(),
  mockToastError: vi.fn(),
  mockRefetch: vi.fn(),
}));

vi.mock("@/hooks/usePortalBilling", () => ({
  usePortalBilling: mockUsePortalBilling,
}));

vi.mock("@/lib/api", () => ({
  api: {
    portal: {
      getInvoicePdfUrl: mockGetInvoicePdfUrl,
    },
  },
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ error: mockToastError }),
}));

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn() },
}));

import BillingPage from "./page";

const BILLING = {
  summary: {
    total_invoiced: 30_000_000,
    total_paid: 20_000_000,
    total_pending: 10_000_000,
    count: 2,
  },
  invoices: [
    {
      id: 1,
      invoice_number: "INV-2026-001",
      amount_idr: 20_000_000,
      invoice_source: "zantara",
      has_pdf: true,
      email_sent: true,
      generated_at: "2026-05-01T00:00:00Z",
      created_at: "2026-05-01T00:00:00Z",
      practice_id: 11,
      practice_name: "KITAS Investor",
      practice_category: "Immigration",
      payment_status: "paid",
    },
    {
      id: 2,
      invoice_number: "INV-2026-002",
      amount_idr: 10_000_000,
      invoice_source: "zantara",
      has_pdf: false,
      email_sent: false,
      generated_at: null,
      created_at: null,
      practice_id: 12,
      practice_name: "PT PMA Setup",
      practice_category: "Company",
      payment_status: "unpaid",
    },
  ],
};

function mockState(state: {
  data?: unknown;
  isLoading?: boolean;
  isError?: boolean;
  error?: Error | null;
}) {
  mockUsePortalBilling.mockReturnValue({
    data: state.data,
    isLoading: state.isLoading ?? false,
    isError: state.isError ?? false,
    error: state.error ?? null,
    refetch: mockRefetch,
  });
}

describe("BillingPage", () => {
  it("renders the day masthead, token-driven summary cards and invoice rows (WS3)", () => {
    mockState({ data: BILLING });
    const { container } = render(<BillingPage />);

    // Day masthead: copper rule + Cormorant serif headline in --tx-pure.
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Billing");
    expect(heading.style.fontFamily).toBe("var(--font-serif)");
    expect(heading.className).toContain("text-[var(--tx-pure)]");
    expect(
      container.querySelector(
        '[aria-hidden="true"].bg-\\[var\\(--bz-copper\\)\\]',
      ),
    ).not.toBeNull();

    // Summary amounts render via <Money> (tabular-nums) with state tokens:
    // paid → --state-success, outstanding > 0 → --state-warning.
    // (The same amounts also appear as invoice-row totals, without color.)
    const paidAmount = screen
      .getAllByText("Rp 20.000.000")
      .find((el) => el.style.color !== "");
    expect(paidAmount?.style.fontVariantNumeric).toBe("tabular-nums");
    expect(paidAmount?.style.color).toBe("var(--state-success)");
    const outstandingAmount = screen
      .getAllByText("Rp 10.000.000")
      .find((el) => el.style.color !== "");
    expect(outstandingAmount?.style.color).toBe("var(--state-warning)");

    // Invoice rows: token surfaces, invoice numbers, status badges reading
    // the semantic --state-* tokens (paid → success, unpaid → warning).
    // `overdue` is never a real payment_status here: the backend's payment
    // vocabulary is a closed set {unpaid, partial, paid} (crm_practices.py
    // PAYMENT_STATUS_VALUES) and no invoice due-date data exists to derive
    // an "overdue" state from — `overdue` is only ever emitted for deadline
    // states elsewhere in the portal (dashboard mixin), not billing.
    expect(screen.getByText("INV-2026-001")).toBeInTheDocument();
    expect(screen.getByText("INV-2026-002")).toBeInTheDocument();
    // ("Paid" also appears as a summary-card label, so pick the badge by
    // its token-driven inline style.)
    const paidBadge = screen
      .getAllByText("Paid")
      .map((el) => el.closest("div"))
      .find((el) => el?.style.background.includes("color-mix"));
    expect(paidBadge?.style.color).toBe("var(--state-success)");
    const unpaidBadge = screen.getByText("Unpaid").closest("div");
    expect(unpaidBadge?.style.color).toBe("var(--state-warning)");

    // Card surfaces read theme tokens, not the old dark rgba glass.
    expect(container.innerHTML).toContain("var(--bz-card)");
    expect(container.innerHTML).not.toContain("rgba(30,30,35,0.7)");
    expect(container.innerHTML).not.toContain("rgba(255,255,255,0.05)");

    // Help notice: small copper text uses the AA daylight step with the
    // slice-2 fallback pattern.
    const helpNotice = screen.getByText(/For payment inquiries/);
    expect(helpNotice.style.color).toBe(
      "var(--bz-copper-text, var(--tx-secondary))",
    );

    // Download action only on invoices with a PDF.
    expect(
      screen.getByRole("button", { name: "Download invoice INV-2026-001" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Download invoice INV-2026-002" }),
    ).toBeNull();

    // Drain guard: no hardcoded hex colors anywhere in the page output.
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });

  it("downloads through a same-origin anchor after resolving the proxy URL", async () => {
    mockState({ data: BILLING });
    mockGetInvoicePdfUrl.mockResolvedValue({
      download_url: "/api/portal/billing/1/pdf",
    });
    let clickedLink: HTMLAnchorElement | undefined;
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        clickedLink = this;
      });
    render(<BillingPage />);

    fireEvent.click(
      screen.getByRole("button", { name: "Download invoice INV-2026-001" }),
    );

    await waitFor(() => expect(clickSpy).toHaveBeenCalledOnce());
    expect(mockGetInvoicePdfUrl).toHaveBeenCalledWith(1);
    expect(clickedLink?.getAttribute("href")).toBe("/api/portal/billing/1/pdf");
    expect(clickedLink?.download).toBe("INV-2026-001.pdf");
    expect(clickedLink?.rel).toBe("noopener noreferrer");
    expect(clickedLink?.isConnected).toBe(false);
    clickSpy.mockRestore();
  });

  it("keeps zero outstanding on the success state color", () => {
    mockState({
      data: {
        summary: {
          total_invoiced: 5_000_000,
          total_paid: 5_000_000,
          total_pending: 0,
          count: 1,
        },
        invoices: [],
      },
    });
    render(<BillingPage />);
    const outstanding = screen.getByText("Rp 0");
    expect(outstanding.style.color).toBe("var(--state-success)");
  });

  it("renders the loading skeleton without hardcoded dark surfaces", () => {
    mockState({ isLoading: true });
    const { container } = render(<BillingPage />);
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
    expect(container.innerHTML).not.toContain("rgba(30,30,35,0.7)");
  });

  it("keeps failures client-safe and retries the real billing query", () => {
    mockState({ isError: true, error: new Error("boom") });
    render(<BillingPage />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Billing",
    );
    expect(
      screen.getByRole("heading", { name: "Unable to load billing" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("boom")).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "We could not verify your invoices. Check your connection and try again.",
      ),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(mockRefetch).toHaveBeenCalledOnce();
  });

  // The operator's lifecycle is unpaid -> partial -> paid. STATUS_MAP knew only
  // "paid" and "pending", so both "unpaid" and "partial" fell through to the
  // `?? STATUS_MAP.none` fallback and the client saw a grey "None" badge on a
  // bill they had partly settled.
  it("names the operator's real payment states instead of falling back to None", () => {
    mockState({
      data: {
        summary: {
          total_invoiced: 10_000_000,
          total_paid: 4_000_000,
          total_pending: 6_000_000,
          count: 2,
        },
        invoices: [
          { ...BILLING.invoices[0], id: 3, payment_status: "partial" },
          { ...BILLING.invoices[1], id: 4, payment_status: "unpaid" },
        ],
      },
    });
    render(<BillingPage />);

    expect(screen.getByText("Partially paid")).toBeInTheDocument();
    expect(screen.getByText("Unpaid")).toBeInTheDocument();
    expect(screen.queryByText("None")).not.toBeInTheDocument();
  });

  it("renders the empty state when there are no invoices", () => {
    mockState({
      data: {
        summary: {
          total_invoiced: 0,
          total_paid: 0,
          total_pending: 0,
          count: 0,
        },
        invoices: [],
      },
    });
    render(<BillingPage />);
    expect(screen.getByText("No invoices yet")).toBeInTheDocument();
  });
});
