import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

import { SERVICES_DATA } from "./services_data";
import {
  getExactSnapshotPrice,
  getTierSetFloorPrice,
} from "@/lib/pricing-snapshot";

const EXACT_IDR_PRICE = /^(?:\d+|\d{1,3}(?:\.\d{3})+)\s+IDR$/i;
const REPO_ROOT = path.resolve(__dirname, "../../../..");
const GENERATED = path.join(REPO_ROOT, "apps/mouth/data/bali-zero-prices.json");

/**
 * /services/tax packages must never show a catalogue price for a scope the
 * SKU does not cover (2026-09-28/29 rulings, fix-forward of #7582's gate
 * findings on LKPM / SPT Annual Company (Zero) / both BPJS cards, and of
 * #7600's gate finding that SPT Annual Company (Operational) promises
 * "Personal director filing included" while every Annual Basic Package
 * tier says "Does not include Annual Personal Tax report"). A package
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
  {
    livePriceCategory: string;
    livePriceFloorKeys: string[];
    livePriceFloorUnit?: string;
  }
> = {
  "Monthly Tax Report": {
    livePriceCategory: "tax_accounting.monthly_tax_basic",
    livePriceFloorKeys: [
      "Tier 0-50",
      "Tier 50-100",
      "Tier 100-200",
      "Tier 200+",
    ],
    livePriceFloorUnit: "month",
  },
};

// No exact SKU covers what the card promises — must keep abstaining to the
// Contact placeholder, never guess a price. (LKPM: card says quarterly, the
// only catalogue LKPM row is a stand-alone yearly report. SPT Annual Company
// (Zero): card promises company & personal filing, the SKU is the yearly
// financial report only. SPT Annual Company (Operational): card promises
// "Personal director filing included", every Annual Basic Package A-D tier
// says "Does not include Annual Personal Tax report". Both BPJS cards: card
// promises "Monthly administration", both SKUs are registration only and
// the owner has not confirmed what the 2.5M price covers.)
const TAX_PACKAGES_WITHOUT_A_PRICE = [
  "SPT Annual Company (Zero)",
  "SPT Annual Company (Operational)",
  "BPJS Health Insurance",
  "BPJS Employment Insurance",
  "LKPM Report",
];

/**
 * Lowest IDR figure the catalogue backs for `itemKeys` in `category`,
 * computed by reading + parsing the generated snapshot JSON directly — NOT
 * by calling getTierSetFloorPrice(). A test that re-derives its expectation
 * from the function under test can't catch a bug IN that function (a mutant
 * that ignores tier_range, or reads its wrong index, moves both sides of
 * the comparison together and stays green). This walks the same two candidate
 * sources (`price`, else `tier_range[0]`) independently in plain JS.
 */
function independentTierFloor(category: string, itemKeys: string[]): number {
  const raw = JSON.parse(fs.readFileSync(GENERATED, "utf-8")) as {
    services_by_category: Record<
      string,
      Record<string, { price: string | null; tier_range: string[] | null }>
    >;
  };
  const rows = raw.services_by_category[category];
  expect(
    rows,
    `category ${category} missing from generated snapshot`,
  ).toBeDefined();
  const amounts: number[] = [];
  for (const key of itemKeys) {
    const row = rows[key];
    expect(
      row,
      `key ${category}:${key} missing from generated snapshot`,
    ).toBeDefined();
    const candidate = row.price?.trim() || row.tier_range?.[0]?.trim() || null;
    if (!candidate) continue;
    expect(candidate).toMatch(EXACT_IDR_PRICE);
    amounts.push(Number(candidate.replace(/\D/g, "")));
  }
  expect(amounts.length, `no priced tier in ${category}`).toBeGreaterThan(0);
  return Math.min(...amounts);
}

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
    '%s pins its tier set and exposes the INDEPENDENTLY-COMPUTED catalogue floor as "from X"',
    (name, identity) => {
      const pkg = taxPackages.find((p) => p.name === name);
      expect(pkg).toBeDefined();
      expect(pkg?.livePriceKey).toBeUndefined();
      expect(pkg?.livePriceCategory).toBe(identity.livePriceCategory);
      expect(pkg?.livePriceFloorKeys).toEqual(identity.livePriceFloorKeys);
      expect(pkg?.livePriceFloorUnit).toBe(identity.livePriceFloorUnit);

      // Ground truth: parsed straight out of the JSON file, never through
      // getTierSetFloorPrice — see independentTierFloor()'s docstring.
      const expectedAmount = independentTierFloor(
        identity.livePriceCategory,
        identity.livePriceFloorKeys,
      );

      const floor = getTierSetFloorPrice(
        identity.livePriceCategory,
        identity.livePriceFloorKeys,
      );
      expect(floor).not.toBeNull();
      expect(floor as string).toMatch(EXACT_IDR_PRICE);
      expect(Number((floor as string).replace(/\D/g, ""))).toBe(expectedAmount);
    },
  );

  it("Monthly Tax Report's floor is the catalogue's 1.800.000 IDR (Tier 0-50's tier_range low bound)", () => {
    // Pins the specific number, not just "some minimum" — a red canary if
    // the catalogue row this depends on ever moves without anyone noticing.
    const floor = getTierSetFloorPrice("tax_accounting.monthly_tax_basic", [
      "Tier 0-50",
      "Tier 50-100",
      "Tier 100-200",
      "Tier 200+",
    ]);
    expect(floor).toBe("1.800.000 IDR");
  });

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
