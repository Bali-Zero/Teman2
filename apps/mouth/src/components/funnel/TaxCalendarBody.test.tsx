import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { TaxCalendarBody } from "./TaxCalendarBody";

vi.mock("@/lib/analytics", () => ({
  trackTaxDashboardViewed: vi.fn(),
}));

const DEADLINES = [
  {
    id: "pph25-monthly",
    kind: "PPh" as const,
    title: "PPh 25 mensile",
    date: "2026-05-15T00:00:00Z",
    description: "Pagamento entro il 15 del mese.",
  },
  {
    id: "ppn-monthly",
    kind: "PPN" as const,
    title: "PPN SPT Masa",
    date: "2026-05-31T00:00:00Z",
    description: "SPT Masa PPN.",
  },
  {
    id: "pb1-badung",
    kind: "PB1" as const,
    title: "PB1 Badung",
    date: "2026-05-10T00:00:00Z",
    regency: "Badung",
    description: "Pajak Hotel/Restoran 10%.",
  },
  {
    id: "pb1-gianyar",
    kind: "PB1" as const,
    title: "PB1 Gianyar",
    date: "2026-05-15T00:00:00Z",
    regency: "Gianyar",
    description: "PB1 reggenza Gianyar.",
  },
];

const REGENCIES = ["Badung", "Gianyar"];

describe("TaxCalendarBody", () => {
  afterEach(() => vi.clearAllMocks());

  it("renders all 4 deadlines by default (ALL tab)", () => {
    render(<TaxCalendarBody deadlines={DEADLINES} regencies={REGENCIES} />);
    expect(screen.getByText("PPh 25 mensile")).toBeInTheDocument();
    expect(screen.getByText("PPN SPT Masa")).toBeInTheDocument();
    expect(screen.getByText("PB1 Badung")).toBeInTheDocument();
    expect(screen.getByText("PB1 Gianyar")).toBeInTheDocument();
  });

  it("filters by PPh tab — only PPh deadline shown", () => {
    render(<TaxCalendarBody deadlines={DEADLINES} regencies={REGENCIES} />);
    fireEvent.click(screen.getByRole("button", { name: "PPh" }));
    expect(screen.getByText("PPh 25 mensile")).toBeInTheDocument();
    expect(screen.queryByText("PPN SPT Masa")).not.toBeInTheDocument();
    expect(screen.queryByText("PB1 Badung")).not.toBeInTheDocument();
  });

  it("filters by PB1 tab — only PB1 deadlines shown", () => {
    render(<TaxCalendarBody deadlines={DEADLINES} regencies={REGENCIES} />);
    fireEvent.click(screen.getByRole("button", { name: "PB1" }));
    expect(screen.getByText("PB1 Badung")).toBeInTheDocument();
    expect(screen.getByText("PB1 Gianyar")).toBeInTheDocument();
    expect(screen.queryByText("PPh 25 mensile")).not.toBeInTheDocument();
  });

  it("filters by regency Badung — PB1 Gianyar hidden, non-regency deadlines visible", () => {
    render(<TaxCalendarBody deadlines={DEADLINES} regencies={REGENCIES} />);
    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "Badung" } });
    expect(screen.getByText("PB1 Badung")).toBeInTheDocument();
    // deadlines without regency are still shown (falls through filter)
    expect(screen.getByText("PPh 25 mensile")).toBeInTheDocument();
    expect(screen.queryByText("PB1 Gianyar")).not.toBeInTheDocument();
  });

  it("iCal export link points to API route + download filename", () => {
    render(<TaxCalendarBody deadlines={DEADLINES} regencies={REGENCIES} />);
    const ical = screen.getByRole("link", {
      name: /Export iCal/i,
    }) as HTMLAnchorElement;
    expect(ical.getAttribute("href")).toBe("/api/tax-calendar/ical");
    expect(ical.getAttribute("download")).toBe("bali-tax-deadlines.ics");
  });

  it("Delegate to us WA CTA present per deadline — correct WA deeplink + intent text", () => {
    // Commit a9502d4b5 renamed the CTA from "Delega a noi" → "Delegate to us"
    // as part of the tax-calendar English canonicalisation. The WA deeplink
    // query keeps the Italian "Delega%20Bali%20Zero%20SPT" intent string —
    // that's the literal text the operator searches for in WhatsApp.
    render(<TaxCalendarBody deadlines={DEADLINES} regencies={REGENCIES} />);
    const links = screen.getAllByRole("link", { name: /Delegate to us/i });
    expect(links.length).toBeGreaterThanOrEqual(4);
    expect(links[0].getAttribute("href")).toContain("wa.me/628213107363");
    expect(links[0].getAttribute("href")).toContain(
      "Delega%20Bali%20Zero%20SPT",
    );
  });
});
