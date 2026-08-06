import fs from "fs";
import path from "path";
import { describe, expect, it } from "vitest";

import {
  getExactSnapshotPrice,
  getPricingSnapshotEntry,
} from "./pricing-snapshot";

const REPO_ROOT = path.resolve(__dirname, "../../../..");
const CANONICAL = path.join(
  REPO_ROOT,
  "apps/backend-rag/backend/data/bali_zero_official_prices_2026.json",
);
const GENERATED = path.join(REPO_ROOT, "apps/mouth/data/bali-zero-prices.json");

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
    ).toBe(106);
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
});
