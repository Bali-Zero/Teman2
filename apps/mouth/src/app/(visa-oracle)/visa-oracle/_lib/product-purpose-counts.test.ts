import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { CATEGORY_TO_PURPOSE } from "./fact-mapper";
import { tierForProductCode, isSelfService } from "./product-tier-map";
import { CATEGORY_KEYS } from "./tree";
import {
  SNAPSHOT_PACK_SEQUENCE,
  TOTAL_CATALOGUE_PRODUCTS,
  productBreakdownForCategory,
} from "./product-purpose-counts";

/**
 * Freshness tripwire: reads the REAL signed pack file directly (not a
 * fixture, not a mock) and re-derives every count `product-purpose-counts.ts`
 * hardcodes, on BOTH axes — how many products are tagged for a purpose, AND
 * how many of those are self-service (T1/T2) vs consultant-routed (T3) per
 * the real `PRODUCT_TIER_MAP`. If the active pack ever rotates to a new
 * sequence, or a product's tier changes (e.g. a T3 product cured into a
 * priced T1/T2 one), this goes red rather than silently drifting stale.
 */
const PACK_PATH = path.resolve(
  __dirname,
  "../../../../../../../apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-013.signed.json",
);

interface PackProduct {
  product_code: string;
  covered_purposes: readonly string[];
}

interface SignedPack {
  payload: {
    sequence: number;
    products: readonly PackProduct[];
  };
}

function loadPack(): SignedPack {
  return JSON.parse(readFileSync(PACK_PATH, "utf-8")) as SignedPack;
}

describe("product-purpose-counts", () => {
  it("is pinned to the pack sequence it claims", () => {
    const pack = loadPack();
    expect(pack.payload.sequence).toBe(SNAPSHOT_PACK_SEQUENCE);
  });

  it("TOTAL_CATALOGUE_PRODUCTS matches the real catalogue size", () => {
    const pack = loadPack();
    expect(pack.payload.products.length).toBe(TOTAL_CATALOGUE_PRODUCTS);
  });

  it("every total is real-derived from the pack's purpose tags, not invented", () => {
    const pack = loadPack();
    for (const category of CATEGORY_KEYS) {
      const purpose = CATEGORY_TO_PURPOSE[category];
      const expectedTotal =
        purpose === undefined
          ? null
          : pack.payload.products.filter((product) =>
              product.covered_purposes.includes(purpose),
            ).length;
      const breakdown = productBreakdownForCategory(category);
      if (expectedTotal === null) {
        expect(breakdown).toBeNull();
      } else {
        expect(breakdown?.total).toBe(expectedTotal);
      }
    }
  });

  it("every selfService count is real-derived from the pack + PRODUCT_TIER_MAP, not invented — this is the axis the 2026-08-25 correction added", () => {
    const pack = loadPack();
    for (const category of CATEGORY_KEYS) {
      const purpose = CATEGORY_TO_PURPOSE[category];
      if (purpose === undefined) continue;
      const taggedProducts = pack.payload.products.filter((product) =>
        product.covered_purposes.includes(purpose),
      );
      const expectedSelfService = taggedProducts.filter((product) => {
        const tier = tierForProductCode(product.product_code);
        return tier !== undefined && isSelfService(tier);
      }).length;
      const breakdown = productBreakdownForCategory(category);
      expect(breakdown?.selfService).toBe(expectedSelfService);
      expect(breakdown?.consultantRouted).toBe(
        taggedProducts.length - expectedSelfService,
      );
    }
  });

  it("diaspora has no engine purpose and therefore no breakdown at all", () => {
    expect("diaspora" in CATEGORY_TO_PURPOSE).toBe(false);
    expect(productBreakdownForCategory("diaspora")).toBeNull();
  });

  it("reproduces the specific EMPLOYMENT and STUDY figures from the 2026-08-25 measurement", () => {
    expect(productBreakdownForCategory("work")).toEqual({
      total: 5,
      selfService: 1,
      consultantRouted: 4,
    });
    expect(productBreakdownForCategory("study")).toEqual({
      total: 5,
      selfService: 2,
      consultantRouted: 3,
    });
  });

  it("every countable category's numbers are internally consistent integers", () => {
    for (const category of CATEGORY_KEYS) {
      const breakdown = productBreakdownForCategory(category);
      if (breakdown === null) continue;
      expect(Number.isInteger(breakdown.total)).toBe(true);
      expect(Number.isInteger(breakdown.selfService)).toBe(true);
      expect(breakdown.selfService).toBeGreaterThanOrEqual(0);
      expect(breakdown.consultantRouted).toBeGreaterThanOrEqual(0);
      expect(breakdown.selfService + breakdown.consultantRouted).toBe(
        breakdown.total,
      );
      expect(breakdown.total).toBeGreaterThan(0);
      expect(breakdown.total).toBeLessThanOrEqual(TOTAL_CATALOGUE_PRODUCTS);
    }
  });
});
