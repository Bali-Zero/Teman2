import { describe, expect, it } from "vitest";

import { SERVICES_DATA } from "./services_data";
import {
  getExactSnapshotPrice,
  getTierSetFloorPrice,
} from "@/lib/pricing-snapshot";

const EXACT_IDR_PRICE = /^(?:\d+|\d{1,3}(?:\.\d{3})+)\s+IDR$/i;

/**
 * /services/tax packages must never show a catalogue price for a scope the
 * SKU does not cover (2026-09-28 ruling, fix-forward of #7582's gate
 * findings on LKPM / SPT Annual Company (Zero) / both BPJS cards). A package
 * shows a price ONLY when:
 *  - an exact SKU covers exactly what the card promises (livePriceKey), or
 *  - the card is explicitly a tiered "from" package whose floor comes from
 *    the catalogue's tier set (livePriceFloorKeys), never a hardcoded number.
 * Everything else abstains to the Contact placeholder.
 */

// Exact 1:1 SKU — key/category pinned so a swap to a different (even
// same-priced) SKU goes red, not just "some SKU is set".
const TAX_PACKAGES_WITH_EXACT_SKU: Record<
  string,
  { livePriceKey: string; livePriceCategory: string }
> = {
  "NPWP Personal + Coretax": {
    livePriceKey: "NPWP Personal + Coretax Activation",
    livePriceCategory: "consultant_services",
  },
  "NPWPD Corporate": {
    livePriceKey: "NPWPD Registration",
    livePriceCategory: "consultant_services",
  },
  "SPT Annual Personal": {
    livePriceKey: "Annual Tax Personal",
    livePriceCategory: "tax_accounting.annual_standalone",
  },
};

// Tiered "from" packages — no exact SKU, but a pinned tier set whose
// catalogue floor the card must expose, never a hardcoded literal.
const TAX_PACKAGES_WITH_TIER_FLOOR: Record<
  string,
  { livePriceCategory: string; livePriceFloorKeys: string[] }
> = {
  "SPT Annual Company (Operational)": {
    livePriceCategory: "tax_accounting.annual_basic_packages",
    livePriceFloorKeys: ["Package A", "Package B", "Package C", "Package D"],
  },
  "Monthly Tax Report": {
    livePriceCategory: "tax_accounting.monthly_tax_basic",
    livePriceFloorKeys: [
      "Tier 0-50",
      "Tier 50-100",
      "Tier 100-200",
      "Tier 200+",
    ],
  },
};

// No exact SKU covers what the card promises — must keep abstaining to the
// Contact placeholder, never guess a price. (LKPM: card says quarterly, the
// only catalogue LKPM row is a stand-alone yearly report. SPT Annual Company
// (Zero): card promises company & personal filing, the SKU is the yearly
// financial report only. Both BPJS cards: card promises "Monthly
// administration", both SKUs are registration only and the owner has not
// confirmed what the 2.5M price covers.)
const TAX_PACKAGES_WITHOUT_A_PRICE = [
  "SPT Annual Company (Zero)",
  "BPJS Health Insurance",
  "BPJS Employment Insurance",
  "LKPM Report",
];

describe("/services/tax packages resolve exact catalogue prices", () => {
  const taxPackages = SERVICES_DATA.tax.packages;

  it.each(Object.entries(TAX_PACKAGES_WITH_EXACT_SKU))(
    "%s pins its SKU identity and resolves to a numeric IDR price",
    (name, identity) => {
      const pkg = taxPackages.find((p) => p.name === name);
      expect(pkg).toBeDefined();
      expect(pkg?.livePriceKey).toBe(identity.livePriceKey);
      expect(pkg?.livePriceCategory).toBe(identity.livePriceCategory);
      expect(pkg?.livePriceFloorKeys).toBeUndefined();

      const price = getExactSnapshotPrice(
        identity.livePriceCategory,
        identity.livePriceKey,
      );
      expect(price).not.toBeNull();
      expect(price as string).toMatch(EXACT_IDR_PRICE);
    },
  );

  it.each(Object.entries(TAX_PACKAGES_WITH_TIER_FLOOR))(
    '%s pins its tier set and exposes the catalogue floor as "from X"',
    (name, identity) => {
      const pkg = taxPackages.find((p) => p.name === name);
      expect(pkg).toBeDefined();
      expect(pkg?.livePriceKey).toBeUndefined();
      expect(pkg?.livePriceCategory).toBe(identity.livePriceCategory);
      expect(pkg?.livePriceFloorKeys).toEqual(identity.livePriceFloorKeys);

      const floor = getTierSetFloorPrice(
        identity.livePriceCategory,
        identity.livePriceFloorKeys,
      );
      expect(floor).not.toBeNull();
      expect(floor as string).toMatch(EXACT_IDR_PRICE);

      // The floor must be the true minimum across the pinned tier set, not
      // just any priced tier — computed independently here so a mutant that
      // picks the wrong tier (or a higher one) goes red.
      const amounts = identity.livePriceFloorKeys
        .map((key) => getTierSetFloorPrice(identity.livePriceCategory, [key]))
        .filter((p): p is string => p !== null)
        .map((p) => Number(p.replace(/\D/g, "")));
      expect(amounts.length).toBeGreaterThan(0);
      expect(Number((floor as string).replace(/\D/g, ""))).toBe(
        Math.min(...amounts),
      );
    },
  );

  it.each(TAX_PACKAGES_WITHOUT_A_PRICE)(
    "%s has no exact SKU or tier floor and stays on the placeholder",
    (name) => {
      const pkg = taxPackages.find((p) => p.name === name);
      expect(pkg).toBeDefined();
      expect(pkg?.livePriceKey).toBeUndefined();
      expect(pkg?.livePriceCategory).toBeUndefined();
      expect(pkg?.livePriceFloorKeys).toBeUndefined();
    },
  );

  it("covers every /services/tax package exactly once", () => {
    const covered = [
      ...Object.keys(TAX_PACKAGES_WITH_EXACT_SKU),
      ...Object.keys(TAX_PACKAGES_WITH_TIER_FLOOR),
      ...TAX_PACKAGES_WITHOUT_A_PRICE,
    ];
    expect(covered.sort()).toEqual(taxPackages.map((p) => p.name).sort());
  });

  it("never hardcodes a monetary figure on a tax package", () => {
    const HARDCODED_MONEY = /(?:\bIDR\s*\d|\b\d[\d.,]*\s*IDR\b|\bRp\.?\s*\d)/i;
    for (const pkg of taxPackages) {
      expect([pkg.description, ...pkg.features].join(" ")).not.toMatch(
        HARDCODED_MONEY,
      );
    }
  });

  it("NPWPD Corporate's card says the SKU is billed per location", () => {
    const pkg = taxPackages.find((p) => p.name === "NPWPD Corporate");
    expect(pkg?.features.join(" ")).toMatch(/per location/i);
  });
});
