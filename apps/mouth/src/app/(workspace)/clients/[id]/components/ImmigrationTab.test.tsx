import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ClientDocument } from "@/lib/api/crm/crm.types";
import { ImmigrationTab, isVisaFamilyDocument } from "./ImmigrationTab";

vi.mock("./AiSummaryCard", () => ({ AiSummaryCard: () => null }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// A few cases below freeze the clock (vi.setSystemTime) to pin exact-day
// boundaries. Always restore real time afterwards — a leaked fake clock
// would desync every other `Date.now()`-based fixture in this file.
afterEach(() => {
  vi.useRealTimers();
});

describe("isVisaFamilyDocument", () => {
  it("matches kitas, kitap, visa and e-visa document types", () => {
    for (const type of ["kitas", "KITAP", "visa c1", "e-visa", "evisa"]) {
      expect(isVisaFamilyDocument({ document_type: type })).toBe(true);
    }
  });

  it("matches VOA and its e-VOA spelling (GUILT: it is a visa document)", () => {
    for (const type of ["voa", "VOA", "e-voa", "evoa"]) {
      expect(isVisaFamilyDocument({ document_type: type })).toBe(true);
    }
  });

  it("does not match a non-visa document type (INNOCENCE)", () => {
    expect(isVisaFamilyDocument({ document_type: "passport" })).toBe(false);
    expect(isVisaFamilyDocument({ document_type: "working permit" })).toBe(
      false,
    );
  });
});

const baseDoc: ClientDocument = {
  id: 1,
  client_id: 1,
  document_type: "voa",
};

const renderTab = (documents: ClientDocument[]) =>
  render(
    <ImmigrationTab
      clientId={1}
      documents={documents}
      formatDate={(d) => d}
      onAddClick={vi.fn()}
      onEditClick={vi.fn()}
      onRefresh={vi.fn()}
    />,
  );

describe("ImmigrationTab — current permit panel vs visa history (R6 restyle)", () => {
  it("shows an unexpired VOA in the current-permit panel, not only in history (GUILT)", () => {
    const futureDate = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 1,
        document_type: "voa",
        expiry_date: futureDate,
      },
    ]);

    expect(screen.getByText("Current permit")).toBeInTheDocument();
    expect(screen.queryByText("Visa history")).not.toBeInTheDocument();
  });

  it("shows an expired VOA only in the Visa history grid, not the permit panel (INNOCENCE)", () => {
    const pastDate = new Date(Date.now() - 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 2,
        document_type: "voa",
        expiry_date: pastDate,
      },
    ]);

    expect(screen.queryByText("Current permit")).not.toBeInTheDocument();
    expect(screen.getByText("Visa history")).toBeInTheDocument();
  });

  it("keeps an unexpired kitas as the current permit when a VOA is also present (existing precedence unchanged)", () => {
    const futureDate = new Date(Date.now() + 400 * 86400000)
      .toISOString()
      .slice(0, 10);
    const nearDate = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 3,
        document_type: "kitas",
        expiry_date: futureDate,
      },
      {
        ...baseDoc,
        id: 4,
        document_type: "voa",
        expiry_date: nearDate,
      },
    ]);

    // Current permit picks the document with the furthest-out expiry first
    // (existing sort order: descending expiry) — unchanged by this fix.
    expect(screen.getAllByText("kitas")).toHaveLength(1);
    expect(screen.getByText("Visa history")).toBeInTheDocument();
    expect(screen.getAllByText("voa")).toHaveLength(1);
  });

  it("never classifies a non-visa document (e.g. passport-like) as a visa", () => {
    renderTab([
      {
        ...baseDoc,
        id: 5,
        document_type: "working permit",
        document_category: "immigration",
      },
    ]);

    expect(screen.queryByText("Current permit")).not.toBeInTheDocument();
    expect(screen.queryByText("Visa history")).not.toBeInTheDocument();
    expect(screen.getByText("Working Permit")).toBeInTheDocument();
  });

  it("renders the elapsed/expiry KPIs from real issue_date + expiry_date (no invented data)", () => {
    const issueDate = new Date(Date.now() - 20 * 86400000)
      .toISOString()
      .slice(0, 10);
    const expiryDate = new Date(Date.now() + 40 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 6,
        document_type: "kitas",
        issue_date: issueDate,
        expiry_date: expiryDate,
      },
    ]);

    expect(screen.getByText("Days on this permit")).toBeInTheDocument();
    expect(screen.getByText("Days to expiry")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: /days elapsed/ }),
    ).toBeInTheDocument();
  });

  it("GUILT: omits the elapsed-days KPI and the validity track when issue_date is missing, rather than guessing it", () => {
    const futureDate = new Date(Date.now() + 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 7,
        document_type: "kitas",
        expiry_date: futureDate,
      },
    ]);

    expect(screen.getByText("Current permit")).toBeInTheDocument();
    expect(screen.queryByText("Days on this permit")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("img", { name: /days elapsed/ }),
    ).not.toBeInTheDocument();
    // The countdown itself does not need issue_date — only elapsed/total do.
    expect(screen.getByText("Days to expiry")).toBeInTheDocument();
  });

  it("Visa history shows a real document status when present, and a plain dash when it is not (no guessed status)", () => {
    const pastDate = new Date(Date.now() - 60 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 8,
        document_type: "kitas",
        expiry_date: pastDate,
        status: "verified",
      },
      {
        ...baseDoc,
        id: 9,
        document_type: "voa",
        expiry_date: pastDate,
      },
    ]);

    expect(screen.getByText("verified")).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});

describe("ImmigrationTab — Start Renewal CTA (R6 repair P0-1)", () => {
  it("GUILT: the permit panel shows Start Renewal for a kitas expiring in 45 days", () => {
    const soon = new Date(Date.now() + 45 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 20, document_type: "kitas", expiry_date: soon },
    ]);

    expect(
      screen.getByRole("button", { name: /start renewal/i }),
    ).toBeInTheDocument();
  });

  it("INNOCENCE: the permit panel shows no Start Renewal for a kitas expiring in 200 days", () => {
    const far = new Date(Date.now() + 200 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 21, document_type: "kitas", expiry_date: far },
    ]);

    expect(
      screen.queryByRole("button", { name: /start renewal/i }),
    ).not.toBeInTheDocument();
  });

  it("GUILT: an expired kitas in Visa history still offers Start Renewal", () => {
    const current = new Date(Date.now() + 400 * 86400000)
      .toISOString()
      .slice(0, 10);
    const expired = new Date(Date.now() - 10 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 22, document_type: "kitas", expiry_date: current },
      { ...baseDoc, id: 23, document_type: "kitas", expiry_date: expired },
    ]);

    expect(screen.getByText("Visa history")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /start renewal for kitas/i }),
    ).toBeInTheDocument();
  });

  it("BOUNDARY: shows Start Renewal at exactly 90 days out", () => {
    const now = new Date("2026-01-01T00:00:00.000Z");
    vi.setSystemTime(now);
    const expiryDate = new Date(now.getTime() + 90 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 24, document_type: "kitas", expiry_date: expiryDate },
    ]);

    expect(
      screen.getByRole("button", { name: /start renewal/i }),
    ).toBeInTheDocument();
  });

  it("BOUNDARY: hides Start Renewal at 91 days out — the threshold did not move", () => {
    const now = new Date("2026-01-01T00:00:00.000Z");
    vi.setSystemTime(now);
    const expiryDate = new Date(now.getTime() + 91 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 25, document_type: "kitas", expiry_date: expiryDate },
    ]);

    expect(
      screen.queryByRole("button", { name: /start renewal/i }),
    ).not.toBeInTheDocument();
  });
});

describe("ImmigrationTab — 'Days to expiry' never flips sign (R6 repair P0-2)", () => {
  it("GUILT: a permit expired 10 days ago (still in the 30-day grace) reads 'Days past expiry', never 'Days to expiry'", () => {
    const pastExpiry = new Date(Date.now() - 10 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 30,
        document_type: "kitas",
        expiry_date: pastExpiry,
      },
    ]);

    expect(screen.getByText("Current permit")).toBeInTheDocument();
    expect(screen.getByText("Days past expiry")).toBeInTheDocument();
    expect(screen.queryByText("Days to expiry")).not.toBeInTheDocument();
  });

  it("INNOCENCE: a permit expiring in 10 days still reads 'Days to expiry'", () => {
    const futureExpiry = new Date(Date.now() + 10 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 31,
        document_type: "kitas",
        expiry_date: futureExpiry,
      },
    ]);

    expect(screen.getByText("Days to expiry")).toBeInTheDocument();
    expect(screen.queryByText("Days past expiry")).not.toBeInTheDocument();
  });
});

describe("ImmigrationTab — 30-day grace boundary (R6 repair P1-6)", () => {
  it("BOUNDARY: a visa expired 29 days ago still shows in the permit panel (inside grace)", () => {
    const withinGrace = new Date(Date.now() - 29 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      { ...baseDoc, id: 40, document_type: "kitas", expiry_date: withinGrace },
    ]);

    expect(screen.getByText("Current permit")).toBeInTheDocument();
    expect(screen.queryByText("Visa history")).not.toBeInTheDocument();
  });

  it("BOUNDARY: a visa expired 31 days ago falls out of the panel and into Visa history", () => {
    const outsideGrace = new Date(Date.now() - 31 * 86400000)
      .toISOString()
      .slice(0, 10);
    renderTab([
      {
        ...baseDoc,
        id: 41,
        document_type: "kitas",
        expiry_date: outsideGrace,
      },
    ]);

    expect(screen.queryByText("Current permit")).not.toBeInTheDocument();
    expect(screen.getByText("Visa history")).toBeInTheDocument();
  });
});
