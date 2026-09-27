import { describe, expect, it } from "vitest";

import { SERVICES_DATA } from "./services_data";
import { getExactSnapshotPrice } from "@/lib/pricing-snapshot";

const EXACT_IDR_PRICE = /^(?:\d+|\d{1,3}(?:\.\d{3})+)\s+IDR$/i;

/**
 * Every /services/tax package that has an exact catalogue SKU (Lane C,
 * fase0) must resolve to a numeric IDR price — never fall back to a
 * placeholder for a package we know maps 1:1 onto a real SKU. Red on
 * origin/main: none of these packages carry a livePriceKey/livePriceCategory
 * there, so getExactSnapshotPrice(null-ish) abstains with null for all of
 * them.
 */
const TAX_PACKAGES_WITH_EXACT_SKU = [
  "NPWP Personal + Coretax",
  "NPWPD Corporate",
  "SPT Annual Personal",
  "SPT Annual Company (Zero)",
  "BPJS Health Insurance",
  "BPJS Employment Insurance",
  "LKPM Report",
];

// No exact 1:1 catalogue SKU exists for these — ambiguous among several
// catalogue rows (see comments in services_data.ts). They must keep
// abstaining, never guess a price.
const TAX_PACKAGES_WITHOUT_EXACT_SKU = [
  "SPT Annual Company (Operational)",
  "Monthly Tax Report",
];

describe("/services/tax packages resolve exact catalogue prices", () => {
  const taxPackages = SERVICES_DATA.tax.packages;

  it.each(TAX_PACKAGES_WITH_EXACT_SKU)(
    "%s resolves to a numeric IDR price",
    (name) => {
      const pkg = taxPackages.find((p) => p.name === name);
      expect(pkg).toBeDefined();
      expect(pkg?.livePriceKey).toBeTruthy();
      expect(pkg?.livePriceCategory).toBeTruthy();

      const price = getExactSnapshotPrice(
        pkg?.livePriceCategory as string,
        pkg?.livePriceKey as string,
      );
      expect(price).not.toBeNull();
      expect(price as string).toMatch(EXACT_IDR_PRICE);
    },
  );

  it.each(TAX_PACKAGES_WITHOUT_EXACT_SKU)(
    "%s has no exact SKU and stays on the placeholder",
    (name) => {
      const pkg = taxPackages.find((p) => p.name === name);
      expect(pkg).toBeDefined();
      expect(pkg?.livePriceKey).toBeUndefined();
      expect(pkg?.livePriceCategory).toBeUndefined();
    },
  );

  it("never hardcodes a monetary figure on a wired tax package", () => {
    const HARDCODED_MONEY = /(?:\bIDR\s*\d|\b\d[\d.,]*\s*IDR\b|\bRp\.?\s*\d)/i;
    for (const pkg of taxPackages) {
      expect([pkg.description, ...pkg.features].join(" ")).not.toMatch(
        HARDCODED_MONEY,
      );
    }
  });
});
