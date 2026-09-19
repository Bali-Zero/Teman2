import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ClientDocument } from "@/lib/api/crm/crm.types";
import { ImmigrationTab, isVisaFamilyDocument } from "./ImmigrationTab";

vi.mock("./AiSummaryCard", () => ({ AiSummaryCard: () => null }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

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

describe("ImmigrationTab — Actual Visa vs Previous Visas", () => {
  it("shows an unexpired VOA as the Actual Visa, not only in history (GUILT)", () => {
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

    expect(screen.getByText("Actual Visa")).toBeInTheDocument();
    expect(screen.queryByText("Previous Visas")).not.toBeInTheDocument();
  });

  it("shows an expired VOA only in Previous Visas, not as the Actual Visa (INNOCENCE)", () => {
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

    expect(screen.queryByText("Actual Visa")).not.toBeInTheDocument();
    expect(screen.getByText("Previous Visas")).toBeInTheDocument();
  });

  it("keeps an unexpired kitas as the Actual Visa when a VOA is also present (existing precedence unchanged)", () => {
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

    // Actual Visa picks the document with the furthest-out expiry first
    // (existing sort order: descending expiry) — unchanged by this fix.
    expect(screen.getAllByText("kitas")).toHaveLength(1);
    expect(screen.getByText("Previous Visas")).toBeInTheDocument();
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

    expect(screen.queryByText("Actual Visa")).not.toBeInTheDocument();
    expect(screen.queryByText("Previous Visas")).not.toBeInTheDocument();
    expect(screen.getByText("Working Permit")).toBeInTheDocument();
  });
});
