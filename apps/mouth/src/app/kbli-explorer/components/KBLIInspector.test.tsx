import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import type { KBLIDetail } from "@/lib/api/kbli.api";
import KBLIInspector, {
  getRelatedRequirementGroups,
  getPmaBadge,
  getRiskBadge,
  getRiskLevel,
} from "./KBLIInspector";

const GAP_PMA = {
  pma_status: "TERBUKA",
  pma_max_asing: 100,
  pma_cap_special: false,
  pma_cap_verified: false,
  pma_verification_status: "declared_gap",
  pma_official_basis: null,
  pma_source_vintage: null,
};

describe("getPmaBadge", () => {
  it("GUILT: never renders raw TERBUKA/100 without the full evidence tuple", () => {
    const badge = getPmaBadge(GAP_PMA);
    expect(badge.label).toBe("PMA Not Verified");
    expect(badge.className).toContain("badge-neutral");
    expect(badge.label).not.toMatch(/open|100/i);
  });

  it("INNOCENCE: preserves a located verdict with locator and vintage", () => {
    expect(
      getPmaBadge({
        ...GAP_PMA,
        pma_status: "TERBATAS",
        pma_max_asing: 49,
        pma_cap_verified: true,
        pma_verification_status: "located",
        pma_official_basis: "Perpres 49/2021 Lampiran III entry 3",
        pma_source_vintage: "2021-05-25",
      }).label,
    ).toBe("Restricted - Conditions Apply");
  });

  it("GUILT: a located closed verdict still exposes a missing cap", () => {
    const badge = getPmaBadge({
      ...GAP_PMA,
      pma_status: "TERTUTUP",
      pma_max_asing: null,
      pma_verification_status: "located",
      pma_official_basis: "Perpres 49/2021 Lampiran III entry 3",
      pma_source_vintage: "2021-05-25",
    });

    expect(badge.label).toBe(
      "Closed to Foreign Investment · ownership cap not verified",
    );
    expect(badge.className).toContain("badge-error");
  });
});

// Zero decision 2026-07-17: an undefined/unclassified KBLI risk must surface as
// an honest "Not Classified" gap, NEVER the old false-reassuring "low"/"Low Risk"
// default. A cured false-friend code (per_skala detached) has no risk basis.
// Guilt + innocence corpus per scar #3 (a guard must not fire on legit neighbours).

describe("getRiskLevel", () => {
  it("INNOCENCE: real Indonesian risk tiers still map correctly", () => {
    expect(getRiskLevel("Tinggi")).toBe("high");
    expect(getRiskLevel("Menengah Tinggi")).toBe("medium-high");
    expect(getRiskLevel("Menengah")).toBe("medium");
    expect(getRiskLevel("Menengah Rendah")).toBe("medium-low");
    expect(getRiskLevel("Rendah")).toBe("low");
    // English aliases the router/licenses can emit.
    expect(getRiskLevel("High")).toBe("high");
    expect(getRiskLevel("Low")).toBe("low");
  });

  it("GUILT: undefined risk returns 'not-classified', never 'low'", () => {
    expect(getRiskLevel("Not classified")).toBe("not-classified");
    expect(getRiskLevel("")).toBe("not-classified");
    expect(getRiskLevel("Unknown")).toBe("not-classified");
    // A value matching no known tier is a gap, not a low reading.
    expect(getRiskLevel("¯\\_(ツ)_/¯")).toBe("not-classified");
  });
});

describe("getRiskBadge", () => {
  it("INNOCENCE: real risk tiers keep their labels", () => {
    expect(getRiskBadge("Rendah").label).toBe("Low Risk");
    expect(getRiskBadge("Tinggi").label).toBe("High Risk");
    expect(getRiskBadge("Menengah Tinggi").label).toBe("Medium-High Risk");
    expect(getRiskBadge("Menengah Rendah").label).toBe("Medium-Low Risk");
  });

  it("GUILT: undefined risk is neutral 'Not Classified', not 'Low Risk'", () => {
    const badge = getRiskBadge("Not classified");
    expect(badge.label).toBe("Not Classified");
    expect(badge.className).toContain("badge-neutral");
    expect(badge.label).not.toMatch(/low/i);
    expect(getRiskBadge("").label).toBe("Not Classified");
    expect(getRiskBadge("Unknown").label).toBe("Not Classified");
  });
});

describe("related requirements", () => {
  it("GUILT: renders reclassified obligations separately and never labels them permits", () => {
    const data: KBLIDetail = {
      code: "56101",
      title: "Restaurant",
      description: "Restaurant activity",
      ...GAP_PMA,
      licensing_status: "VERIFIED",
      sector: "Accommodation and food service",
      risk_profile: "Menengah Rendah",
      licenses: [],
      related_codes: [],
      related_requirements: {
        costs: ["Minimum investment threshold: IDR 10 billion"],
        documents: ["Business plan"],
      },
    };

    render(<KBLIInspector data={data} isLoading={false} />);

    expect(
      screen.getByRole("heading", {
        name: "Related Requirements (Not Permits)",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Minimum investment threshold: IDR 10 billion/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Business plan/)).toBeInTheDocument();
    expect(screen.queryByText("Required Licenses")).toBeNull();
  });

  it("INNOCENCE: omits empty categories and gives unknown categories an honest label", () => {
    expect(
      getRelatedRequirementGroups({
        costs: [],
        sector_approval: ["Sector authority review"],
      }),
    ).toEqual([
      {
        key: "sector_approval",
        label: "Sector Approval",
        items: ["Sector authority review"],
      },
    ]);
  });
});
