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

  it("shows the legacy PDF recap as excluded, with the delta", async () => {
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
    const strip = await screen.findByText(/Legacy PDF recap/);
    expect(strip).toHaveTextContent("Rp 3.000.000");
    expect(strip).toHaveTextContent("not included");
    // July ledger = 3.250.000, PDF = 3.000.000 → delta 250.000
    expect(strip).toHaveTextContent("Rp 250.000");
    // And the headline total still counts the ledger only.
    expect(screen.getAllByText("Rp 4.250.000").length).toBeGreaterThan(0);
  });

  it("scopes the legacy recap to the member filter, so the delta stays honest", async () => {
    // Ledger July: Surya 2.500.000 + Adit 750.000. PDF July: Surya 2.000.000 +
    // Adit 750.000. Filtered to Adit, the delta must be 0 — NOT 750.000 minus
    // the all-members PDF total of 2.750.000.
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
          employee_name: "ADIT",
          employee_id: 1,
          bonus_month: 7,
          bonus_year: 2026,
          total_amount_idr: 750_000,
          task_count: 3,
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
    const user = userEvent.setup();
    render(<BonusesPage />);
    await screen.findByText(/Legacy PDF recap/);
    await user.selectOptions(screen.getByLabelText("Filter by member"), "id:1");
    const strip = await screen.findByText(/Legacy PDF recap/);
    expect(strip).toHaveTextContent("Rp 750.000");
    expect(strip).toHaveTextContent("Rp 0");
    expect(strip).not.toHaveTextContent("Rp 2.750.000");
  });

  it("suppresses the legacy recap under a status filter — the sides stop being comparable", async () => {
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
      ],
      count: 1,
    });
    const user = userEvent.setup();
    render(<BonusesPage />);
    await screen.findByText(/Legacy PDF recap/);
    await user.selectOptions(
      screen.getByLabelText("Filter by status"),
      "pending",
    );
    await waitFor(() =>
      expect(screen.queryByText(/Legacy PDF recap/)).not.toBeInTheDocument(),
    );
  });

  it("hides the reconciliation strip when the endpoint rejects (non-admin)", async () => {
    hrApiMock.listBonusHistorical.mockRejectedValue(new Error("403"));
    render(<BonusesPage />);
    await screen.findByText("July 2026");
    expect(screen.queryByText(/Legacy PDF recap/)).not.toBeInTheDocument();
  });

  it("renders the empty state when there are no bonuses", async () => {
    hrApiMock.listBonuses.mockResolvedValue({ bonuses: [], count: 0 });
    render(<BonusesPage />);
    expect(
      await screen.findByText(/No bonuses for this selection/),
    ).toBeInTheDocument();
  });
});
