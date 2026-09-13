import { render, screen, within } from "@testing-library/react";
import ComplianceRetainerPage, { metadata } from "./page";

/**
 * Unlisted compliance retainer page (2026-09-11). Pins two contracts:
 *  - the five compliance_retainers SSOT entries render as name + price,
 *    sourced from `getExactPricingSnapshotEntries` (never a hardcoded
 *    literal in the page) — the pricing source is mocked here so the test
 *    is a contract test against the page's rendering, not a re-assertion
 *    of the committed snapshot file;
 *  - the page stays out of search results (robots index:false/follow:false)
 *    until the owner asks for it to be listed.
 */

const COMPLIANCE_ENTRIES = [
  {
    category: "compliance_retainers",
    key: "compliance_takeover",
    name: "Compliance Takeover",
    price: "9.500.000 IDR",
    duration: "",
    validity: "",
    notes: "USD reference: 600. Historical clean-up is quoted separately.",
    description_en:
      "One-off compliance takeover for a foreign-owned company (PT PMA).",
    icon_id: "consultant-update",
  },
  {
    category: "compliance_retainers",
    key: "compliance_core_retainer_monthly",
    name: "Compliance Core Retainer (Monthly)",
    price: "9.500.000 IDR",
    duration: "",
    validity: "monthly",
    notes: "USD reference: 600 per month.",
    description_en: "Monthly compliance retainer for a PT PMA.",
    icon_id: "tax-monthly",
  },
  {
    category: "compliance_retainers",
    key: "compliance_employer_retainer_monthly",
    name: "Compliance Employer Retainer (Monthly)",
    price: "19.000.000 IDR",
    duration: "",
    validity: "monthly",
    notes: "USD reference: 1,200 per month.",
    description_en:
      "Core retainer plus payroll compliance for up to 15 employees.",
    icon_id: "consultant-bpjs-tk",
  },
  {
    category: "compliance_retainers",
    key: "pse_registration_fixed",
    name: "PSE Registration (Fixed Fee)",
    price: "19.000.000 IDR",
    duration: "",
    validity: "",
    notes:
      "USD reference: 1,200. Ongoing liaison is a separate monthly service.",
    description_en: "Electronic System Operator (PSE) registration.",
    icon_id: "consultant-efin",
  },
  {
    category: "compliance_retainers",
    key: "pmse_vat_assessment",
    name: "PMSE VAT Assessment",
    price: "14.000.000 IDR",
    duration: "",
    validity: "",
    notes: "USD reference: 900.",
    description_en:
      "Fixed-fee assessment of the foreign digital-trade (PMSE) VAT threshold.",
    icon_id: "tax-annual",
  },
];

const getEntriesMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/pricing-snapshot", () => ({
  getExactPricingSnapshotEntries: getEntriesMock,
}));

describe("ComplianceRetainerPage", () => {
  beforeEach(() => {
    getEntriesMock.mockReset();
    getEntriesMock.mockReturnValue(COMPLIANCE_ENTRIES);
  });

  it("renders all five compliance retainer packages with their SSOT price string", () => {
    render(<ComplianceRetainerPage />);

    const cards = screen.getAllByTestId("compliance-price-card");
    expect(cards).toHaveLength(5);

    for (const entry of COMPLIANCE_ENTRIES) {
      const card = cards.find((c) => within(c).queryByText(entry.name));
      expect(card).toBeDefined();
      expect(
        within(card as HTMLElement).getByText(entry.price),
      ).toBeInTheDocument();
    }
  });

  it("calls the pricing source with the compliance_retainers category, never a literal price", () => {
    render(<ComplianceRetainerPage />);
    expect(getEntriesMock).toHaveBeenCalledWith("compliance_retainers");
  });

  it("keeps robots index:false and follow:false (unlisted, owner review pending)", () => {
    expect(metadata.robots).toEqual({ index: false, follow: false });
  });
});
