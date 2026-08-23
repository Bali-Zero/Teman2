import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

import {
  getExactSnapshotPrice,
  getPricingSnapshotEntry,
} from "./pricing-snapshot";
import { SERVICES_DATA } from "@/data/services_data";

const REPO_ROOT = path.resolve(__dirname, "../../../..");
const CANONICAL = path.join(
  REPO_ROOT,
  "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json",
);
const GENERATED = path.join(REPO_ROOT, "apps/mouth/data/bali-zero-prices.json");
const SERVICE_PRICING_COMPONENT = path.join(
  REPO_ROOT,
  "apps/mouth/src/components/services/ServicePricing.tsx",
);
const DYNAMIC_JSON_LD_COMPONENT = path.join(
  REPO_ROOT,
  "apps/mouth/src/components/seo/DynamicJsonLd.tsx",
);
const PUBLIC_VISA_PRICING_CATEGORIES = [
  "single_entry_visas",
  "multiple_entry_visas",
  "kitas_permits",
  "kitap_permits",
  "other_process",
  "urgent_processing",
] as const;
const HARDCODED_SERVICE_MONEY =
  /(?:\bIDR\s*\d|\b\d[\d.,]*\s*IDR\b|\bRp\.?\s*\d)/i;

interface CanonicalRow {
  name?: string;
  price?: string;
  duration?: string;
  validity?: string;
  notes?: string;
  description_en?: string;
  icon_id?: string;
}

function projectedRow(category: string, key: string, row: CanonicalRow) {
  return {
    category,
    key,
    name: row.name ?? key,
    price: row.price ?? null,
    duration: row.duration ?? null,
    validity: row.validity ?? null,
    notes: row.notes ?? null,
    description_en: row.description_en ?? null,
    icon_id: row.icon_id ?? null,
  };
}

function canonicalRowsByCategory(
  services: Record<string, Record<string, CanonicalRow>>,
) {
  const expected: Record<
    string,
    Record<string, ReturnType<typeof projectedRow>>
  > = {};
  for (const [category, categoryPayload] of Object.entries(services)) {
    if (category === "tax_accounting") {
      for (const [blockName, block] of Object.entries(categoryPayload)) {
        const projectedCategory = `${category}.${blockName}`;
        expected[projectedCategory] = {};
        for (const [key, row] of Object.entries(
          block as unknown as Record<string, CanonicalRow>,
        )) {
          expected[projectedCategory][key] = projectedRow(
            projectedCategory,
            key,
            row,
          );
        }
      }
      continue;
    }
    expected[category] = {};
    for (const [key, row] of Object.entries(categoryPayload)) {
      expected[category][key] = projectedRow(category, key, row);
    }
  }
  return expected;
}

describe("generated PricingTool snapshot", () => {
  const canonical = JSON.parse(fs.readFileSync(CANONICAL, "utf-8"));
  const generated = JSON.parse(fs.readFileSync(GENERATED, "utf-8"));
  const selectedRows = [
    ["single_entry_visas", "C1 Tourism"],
    ["single_entry_visas", "C2 Business"],
    ["multiple_entry_visas", "D1 Tourism (1 Year)"],
    ["kitas_permits", "E33G Remote Worker (Offshore)"],
    ["kitas_permits", "Retirement (Offshore)"],
    ["company_services", "New Company (PT PMA)"],
  ] as const;

  it("keeps every exact PricingTool row in parity", () => {
    const expected = canonicalRowsByCategory(canonical.services);
    expect(generated.services_by_category).toEqual(expected);
    expect(
      Object.values(expected).reduce(
        (count, rows) => count + Object.keys(rows).length,
        0,
      ),
    ).toBe(113);
  });

  it.each(selectedRows)("keeps %s:%s in parity", (category, key) => {
    const canonicalRow = canonical.services[category][key];
    const generatedRow = getPricingSnapshotEntry(category, key);
    expect(generatedRow?.name).toBe(canonicalRow.name);
    expect(getExactSnapshotPrice(category, key)).toBe(canonicalRow.price);
  });

  it("does not fabricate unknown or obsolete service keys", () => {
    expect(
      getExactSnapshotPrice("single_entry_visas", "C317 Single Entry"),
    ).toBeNull();
    expect(getExactSnapshotPrice("missing", "C1 Tourism")).toBeNull();
  });

  it("backs every public visa service card with one exact PricingTool row", () => {
    const packages = SERVICES_DATA.visa.packages;
    const expectedIdentities = PUBLIC_VISA_PRICING_CATEGORIES.flatMap(
      (category) => {
        const rows = generated.services_by_category[category] as Record<
          string,
          { key: string; price: string | null }
        >;
        return Object.values(rows)
          .filter((row: { price: string | null }) =>
            row.price
              ? /^(?:\d+|\d{1,3}(?:\.\d{3})+)\s+IDR$/i.test(row.price)
              : false,
          )
          .map((row: { key: string }) => `${category}:${row.key}`);
      },
    );
    const actualIdentities = packages.map(
      (pkg) => `${pkg.livePriceCategory}:${pkg.livePriceKey}`,
    );

    expect(actualIdentities).toEqual(expectedIdentities);
    expect(new Set(actualIdentities).size).toBe(actualIdentities.length);
    for (const pkg of packages) {
      expect(pkg.livePriceCategory).toBeTruthy();
      expect(pkg.livePriceKey).toBeTruthy();
      expect(
        getExactSnapshotPrice(
          pkg.livePriceCategory as string,
          pkg.livePriceKey as string,
        ),
      ).not.toBeNull();
      expect(
        [pkg.price, pkg.description, ...pkg.features].join(" "),
      ).not.toMatch(HARDCODED_SERVICE_MONEY);
    }
  });

  it("never falls back from PricingTool to package price text", () => {
    const component = fs.readFileSync(SERVICE_PRICING_COMPONENT, "utf-8");
    expect(component).not.toMatch(/\bpkg\.price\b/);
    expect(component).toMatch(/return livePrice \?\? "Contact"/);

    const jsonLd = fs.readFileSync(DYNAMIC_JSON_LD_COMPONENT, "utf-8");
    expect(jsonLd).not.toMatch(/\bpkg\.price\b/);
    expect(jsonLd).toMatch(/getExactSnapshotPrice/);
  });
});
