import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BonusesPage from "./page";

const hrApiMock = vi.hoisted(() => ({
  listBonuses: vi.fn(),
  listBonusHistorical: vi.fn(),
  approveBonus: vi.fn(),
}));

vi.mock("@/lib/api/hr/hr", () => hrApiMock);

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

function bonus(over: Record<string, unknown> & { id: number }) {
  return {
    practice_id: 0,
    employee_id: 1,
    payroll_period_id: null,
    bonus_rate_id: null,
    practice_type_code: "visa_b211",
    amount_idr: 100_000,
    status: "approved",
    awarded_at: "2026-07-10T02:00:00.000Z",
    awarded_by: null,
    approved_by: null,
    approved_at: null,
    employee_name: "Surya",
    employee_email: "surya@balizero.com",
    practice_status: "completed",
    client_name: null,
    notes: null,
    ...over,
  };
}

/** Two members, two months — the shape accounting actually reads. */
const BONUSES = [
  bonus({
    id: 1,
    employee_id: 3,
    employee_name: "Surya",
    amount_idr: 2_000_000,
  }),
  bonus({
    id: 2,
    employee_id: 3,
    employee_name: "Surya",
    amount_idr: 500_000,
    status: "pending",
  }),
  bonus({ id: 3, employee_id: 1, employee_name: "Adit", amount_idr: 750_000 }),
  bonus({
    id: 4,
    employee_id: 1,
    employee_name: "Adit",
    amount_idr: 1_000_000,
    awarded_at: "2026-06-10T02:00:00.000Z",
  }),
];

beforeEach(() => {
  vi.clearAllMocks();
  hrApiMock.listBonuses.mockResolvedValue({
    bonuses: BONUSES,
    count: BONUSES.length,
  });
  hrApiMock.listBonusHistorical.mockResolvedValue({ records: [], count: 0 });
});

describe("BonusesPage", () => {
  it("shows the grand total of every bonus in the payload", async () => {
    render(<BonusesPage />);
    // 2.000.000 + 500.000 + 750.000 + 1.000.000
    await waitFor(() =>
      expect(screen.getAllByText("Rp 4.250.000").length).toBeGreaterThan(0),
    );
  });

  it("splits the ledger into months, newest first", async () => {
    render(<BonusesPage />);
    await screen.findByText("July 2026");
    const headings = screen.getAllByRole("button", { name: /2026/ });
    expect(headings[0]).toHaveTextContent("July 2026");
    expect(headings[1]).toHaveTextContent("June 2026");
  });

  it("totals each member inside the month — the number accounting needs", async () => {
    render(<BonusesPage />);
    const july = await screen.findByRole("button", { name: /July 2026/ });
    // Newest month is expanded by default.
    expect(july).toHaveAttribute("aria-expanded", "true");

    // Surya in July = 2.000.000 + 500.000 pending
    const suryaRow = await screen.findByRole("button", {
      name: /Surya.*2 bonuses/,
    });
    expect(suryaRow).toHaveTextContent("Rp 2.500.000");
    expect(suryaRow).toHaveTextContent("Rp 500.000 pending");
  });

  it("gives a per-member all-time total across months", async () => {
    render(<BonusesPage />);
    const table = await screen.findByRole("table");
    const aditRow = within(table)
      .getAllByRole("row")
      .find((r) => r.textContent?.startsWith("Adit"));
    // 750.000 (July) + 1.000.000 (June) over 2 months
    expect(aditRow).toHaveTextContent("Rp 1.750.000");
    expect(aditRow).toHaveTextContent("2");
  });

  it("month totals and per-member totals agree on the grand total", async () => {
    render(<BonusesPage />);
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row");
    const footer = rows[rows.length - 1];
    expect(footer).toHaveTextContent("Rp 4.250.000");
  });

  it("expands a member to reveal the individual bonus rows", async () => {
    const user = userEvent.setup();
    render(<BonusesPage />);
    const suryaRow = await screen.findByRole("button", {
      name: /Surya.*2 bonuses/,
    });
    await user.click(suryaRow);
    await waitFor(() =>
      expect(screen.getAllByText("visa b211").length).toBeGreaterThan(0),
    );
  });

  it("filters to a single member without leaking the others", async () => {
    const user = userEvent.setup();
    render(<BonusesPage />);
    await screen.findByText("July 2026");
    await user.selectOptions(screen.getByLabelText("Filter by member"), "id:1");
    // The member <select> still lists every name — scope the leak check to the
    // per-member summary table, which must now hold Adit alone.
    await waitFor(() => {
      const rows = within(screen.getByRole("table")).getAllByRole("row");
      expect(rows.some((r) => r.textContent?.includes("Surya"))).toBe(false);
    });
    expect(screen.getAllByText("Rp 1.750.000").length).toBeGreaterThan(0);
  });

  it("when every paid member is in the ledger, the ledger wins and the PDF is a reference snapshot", async () => {
    hrApiMock.listBonusHistorical.mockResolvedValue({
      records: [
        {
          id: 1,
          employee_name: "SURYA",
          employee_id: 3,
          bonus_month: 7,
          bonus_year: 2026,
          total_amount_idr: 3_000_000,
          task_count: 13,
          source_pdf: "LIST BONUS JULY 2026.pdf",
          accounting_total_data: null,
          accounting_not_paid: null,
          accounting_paid: null,
          imported_at: "2026-08-01T00:00:00.000Z",
          notes: null,
        },
      ],
      count: 1,
    });
    render(<BonusesPage />);
    // Surya (id 3) is in the July ledger → ledger authoritative, PDF snapshot.
    const strip = await screen.findByText(/pre-system PDF recap/);
    expect(strip).toHaveTextContent("Rp 3.000.000");
    expect(strip).toHaveTextContent("ledger is authoritative");
    expect(strip).toHaveTextContent("not summed");
    // July ledger = 3.250.000, PDF = 3.000.000 → delta 250.000
    expect(strip).toHaveTextContent("Rp 250.000");
    // And the headline total still counts the ledger only.
    expect(screen.getAllByText("Rp 4.250.000").length).toBeGreaterThan(0);
  });

  it("when the PDF paid a member the ledger never captured, the PDF is authoritative and the ledger is flagged incomplete", async () => {
    // Vino (id 99) was paid 1.500.000 in the PDF but has zero July ledger rows —
    // the ledger was not yet capturing him. The strip must flip to PDF-wins.
    hrApiMock.listBonusHistorical.mockResolvedValue({
      records: [
        {
          id: 1,
          employee_name: "SURYA",
          employee_id: 3,
          bonus_month: 7,
          bonus_year: 2026,
          total_amount_idr: 2_000_000,
          task_count: 8,
          source_pdf: "LIST BONUS JULY 2026.pdf",
          accounting_total_data: null,
          accounting_not_paid: null,
          accounting_paid: null,
          imported_at: "2026-08-01T00:00:00.000Z",
          notes: null,
        },
        {
          id: 2,
          employee_name: "VINO",
          employee_id: 99,
          bonus_month: 7,
          bonus_year: 2026,
          total_amount_idr: 1_500_000,
          task_count: 5,
          source_pdf: "LIST BONUS JULY 2026.pdf",
          accounting_total_data: null,
          accounting_not_paid: null,
          accounting_paid: null,
          imported_at: "2026-08-01T00:00:00.000Z",
          notes: null,
        },
      ],
      count: 2,
    });
    render(<BonusesPage />);
    const strip = await screen.findByText(/pre-system PDF list/);
    expect(strip).toHaveTextContent("Ledger incomplete");
    expect(strip).toHaveTextContent("1 member the PDF");
    expect(strip).toHaveTextContent("authoritative record");
    expect(strip).toHaveTextContent("use the PDF total");
    // pdfTotal = 2.000.000 + 1.500.000 = 3.500.000
    expect(strip).toHaveTextContent("Rp 3.500.000");
    // ledger figure for July is still shown as the partial backfill.
    expect(strip).toHaveTextContent("Rp 3.250.000");
    // The headline still sums the ledger only — the strip does not mutate it.
    expect(screen.getAllByText("Rp 4.250.000").length).toBeGreaterThan(0);
  });

  // The verdict is a whole-month property. Filtering the view must never flip
  // it (that would headline the wrong, smaller number) nor hide it.
  const julyPdfAuthoritative = {
    records: [
      {
        id: 1,
        employee_name: "SURYA",
        employee_id: 3,
        bonus_month: 7,
        bonus_year: 2026,
        total_amount_idr: 2_000_000,
        task_count: 8,
        source_pdf: "recap.pdf",
        accounting_total_data: null,
        accounting_not_paid: null,
        accounting_paid: null,
        imported_at: "2026-08-01T00:00:00.000Z",
        notes: null,
      },
      {
        id: 2,
        employee_name: "VINO",
        employee_id: 99, // paid by the PDF, absent from the ledger
        bonus_month: 7,
        bonus_year: 2026,
        total_amount_idr: 1_500_000,
        task_count: 5,
        source_pdf: "recap.pdf",
        accounting_total_data: null,
        accounting_not_paid: null,
        accounting_paid: null,
        imported_at: "2026-08-01T00:00:00.000Z",
        notes: null,
      },
    ],
    count: 2,
  };

  it("a member filter does NOT flip a PDF-authoritative month to ledger-authoritative", async () => {
    hrApiMock.listBonusHistorical.mockResolvedValue(julyPdfAuthoritative);
    const user = userEvent.setup();
    render(<BonusesPage />);
    await screen.findByText(/pre-system PDF list/);
    // Filter to Surya (id 3) — who IS in the ledger. Before the fix this
    // dropped Vino from the input and flipped the verdict to "ledger wins".
    await user.selectOptions(screen.getByLabelText("Filter by member"), "id:3");
    const strip = await screen.findByText(/pre-system PDF list/);
    expect(strip).toHaveTextContent("Ledger incomplete");
    expect(strip).toHaveTextContent("authoritative record");
    // Whole-month PDF total, NOT Surya's filtered 2.000.000.
    expect(strip).toHaveTextContent("Rp 3.500.000");
    expect(strip).toHaveTextContent("verdict is for the whole month");
  });

  it("a status filter does NOT hide the whole-month verdict", async () => {
    hrApiMock.listBonusHistorical.mockResolvedValue(julyPdfAuthoritative);
    const user = userEvent.setup();
    render(<BonusesPage />);
    await screen.findByText(/pre-system PDF list/);
    await user.selectOptions(
      screen.getByLabelText("Filter by status"),
      "pending",
    );
    const strip = await screen.findByText(/pre-system PDF list/);
    expect(strip).toHaveTextContent("Ledger incomplete");
    expect(strip).toHaveTextContent("Rp 3.500.000");
    expect(strip).toHaveTextContent("verdict is for the whole month");
  });

  it("renders a PDF-only month (no ledger rows) instead of silently hiding it", async () => {
    // May 2026 exists only in the PDF — the ledger never captured it.
    hrApiMock.listBonusHistorical.mockResolvedValue({
      records: [
        {
          id: 1,
          employee_name: "VINO",
          employee_id: 99,
          bonus_month: 5,
          bonus_year: 2026,
          total_amount_idr: 2_000_000,
          task_count: 6,
          source_pdf: "LIST BONUS MAY 2026.pdf",
          accounting_total_data: null,
          accounting_not_paid: null,
          accounting_paid: null,
          imported_at: "2026-06-01T00:00:00.000Z",
          notes: null,
        },
      ],
      count: 1,
    });
    const user = userEvent.setup();
    render(<BonusesPage />);
    const mayHeader = await screen.findByRole("button", { name: /May 2026/ });
    expect(mayHeader).toHaveTextContent(
      "PDF recap only — not yet in the ledger",
    );
    await user.click(mayHeader);
    const strip = await screen.findByText(/pre-system PDF list/);
    expect(strip).toHaveTextContent("Ledger incomplete");
    expect(strip).toHaveTextContent("Rp 2.000.000");
  });

  it("does NOT relabel a real ledger month as 'PDF recap only' when a filter empties it", async () => {
    // July HAS ledger rows and a PDF verdict. Filtering to a status with zero
    // July rows must not turn the real month into a synthetic PDF-only card.
    hrApiMock.listBonusHistorical.mockResolvedValue(julyPdfAuthoritative);
    const user = userEvent.setup();
    render(<BonusesPage />);
    await screen.findByText(/pre-system PDF list/);
    await user.selectOptions(
      screen.getByLabelText("Filter by status"),
      "rejected", // no July bonus is rejected → July has no rows in this view
    );
    // The filter empties the view — confirm it took effect, then confirm the
    // real month was NOT resurrected as a fake "PDF recap only" card.
    await screen.findByText(/No bonuses for this selection/);
    expect(screen.queryByText(/PDF recap only/)).not.toBeInTheDocument();
  });

  it("refuses to issue a pay instruction when a PDF amount is unreadable", async () => {
    hrApiMock.listBonusHistorical.mockResolvedValue({
      records: [
        {
          id: 1,
          employee_name: "SURYA",
          employee_id: 3,
          bonus_month: 7,
          bonus_year: 2026,
          total_amount_idr: 2_000_000,
          task_count: 8,
          source_pdf: "recap.pdf",
          accounting_total_data: null,
          accounting_not_paid: null,
          accounting_paid: null,
          imported_at: "2026-08-01T00:00:00.000Z",
          notes: null,
        },
        {
          id: 2,
          employee_name: "VINO",
          employee_id: 99,
          bonus_month: 7,
          bonus_year: 2026,
          total_amount_idr: "500,000" as unknown as number, // unreadable
          task_count: 5,
          source_pdf: "recap.pdf",
          accounting_total_data: null,
          accounting_not_paid: null,
          accounting_paid: null,
          imported_at: "2026-08-01T00:00:00.000Z",
          notes: null,
        },
      ],
      count: 2,
    });
    render(<BonusesPage />);
    const strip = await screen.findByText(/pre-system PDF list/);
    expect(strip).toHaveTextContent("PDF total shown is incomplete");
    expect(strip).toHaveTextContent("verify the source PDF manually");
    expect(strip).not.toHaveTextContent("use the PDF total for this month");
  });

  it("a PDF-only month with an unreadable amount headlines '—', not the understated total", async () => {
    hrApiMock.listBonusHistorical.mockResolvedValue({
      records: [
        {
          id: 1,
          employee_name: "VINO",
          employee_id: 99,
          bonus_month: 5,
          bonus_year: 2026,
          total_amount_idr: 2_000_000,
          task_count: 6,
          source_pdf: "LIST BONUS MAY 2026.pdf",
          accounting_total_data: null,
          accounting_not_paid: null,
          accounting_paid: null,
          imported_at: "2026-06-01T00:00:00.000Z",
          notes: null,
        },
        {
          id: 2,
          employee_name: "ARI",
          employee_id: 2,
          bonus_month: 5,
          bonus_year: 2026,
          total_amount_idr: "1,000,000" as unknown as number, // unreadable
          task_count: 3,
          source_pdf: "LIST BONUS MAY 2026.pdf",
          accounting_total_data: null,
          accounting_not_paid: null,
          accounting_paid: null,
          imported_at: "2026-06-01T00:00:00.000Z",
          notes: null,
        },
      ],
      count: 2,
    });
    render(<BonusesPage />);
    const mayHeader = await screen.findByRole("button", { name: /May 2026/ });
    // The parseable 2.000.000 is an understatement of the true total — the
    // header must not present it as the month figure.
    expect(mayHeader).not.toHaveTextContent("Rp 2.000.000");
    expect(mayHeader).toHaveTextContent("—");
  });

  it("hides the reconciliation strip when the endpoint rejects (non-admin)", async () => {
    hrApiMock.listBonusHistorical.mockRejectedValue(new Error("403"));
    render(<BonusesPage />);
    await screen.findByText("July 2026");
    expect(screen.queryByText(/pre-system PDF/)).not.toBeInTheDocument();
  });

  it("renders the empty state when there are no bonuses", async () => {
    hrApiMock.listBonuses.mockResolvedValue({ bonuses: [], count: 0 });
    render(<BonusesPage />);
    expect(
      await screen.findByText(/No bonuses for this selection/),
    ).toBeInTheDocument();
  });
});
