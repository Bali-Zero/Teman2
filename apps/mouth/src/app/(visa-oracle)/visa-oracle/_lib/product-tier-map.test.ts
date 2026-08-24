import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  PRODUCT_TIER_MAP,
  isSelfService,
  tierForProductCode,
} from "./product-tier-map";

/**
 * Freshness tripwire: re-derives T1/T2/T3 membership from the REAL signed
 * pack, using TIER-MAP.md's own stated rule ("No pricing_key => the
 * product cannot be sold self-service at all => T3 by construction") to
 * distinguish T3 from T1/T2. It cannot re-derive the T1/T2 SPLIT itself —
 * that half is the owner's business judgement, not something the pack
 * encodes — so this test only asserts the T3 boundary and total coverage,
 * not which of T1/T2 each non-T3 product landed in.
 */
const PACK_PATH = path.resolve(
  __dirname,
  "../../../../../../../apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-013.signed.json",
);

interface PackProduct {
  product_code: string;
  pricing_key: unknown;
}

interface SignedPack {
  payload: { products: readonly PackProduct[] };
}

function loadPack(): SignedPack {
  return JSON.parse(readFileSync(PACK_PATH, "utf-8")) as SignedPack;
}

describe("product-tier-map", () => {
  it("covers every product code in the real pack, exactly once", () => {
    const pack = loadPack();
    const packCodes = pack.payload.products.map((p) => p.product_code).sort();
    const mapCodes = Object.keys(PRODUCT_TIER_MAP).sort();
    expect(mapCodes).toEqual(packCodes);
  });

  it("T3 membership matches the pack's own pricing_key rule exactly", () => {
    const pack = loadPack();
    for (const product of pack.payload.products) {
      const tier = tierForProductCode(product.product_code);
      expect(tier).toBeDefined();
      const hasPricingKey = product.pricing_key !== null;
      if (tier === "T3") {
        expect(hasPricingKey).toBe(false);
      } else {
        expect(hasPricingKey).toBe(true);
      }
    }
  });

  it("has exactly 7 T1, 19 T2, 12 T3 — TIER-MAP.md's own counts", () => {
    const counts = { T1: 0, T2: 0, T3: 0 };
    for (const tier of Object.values(PRODUCT_TIER_MAP)) counts[tier] += 1;
    expect(counts).toEqual({ T1: 7, T2: 19, T3: 12 });
  });

  it("isSelfService is true for T1/T2 and false for T3", () => {
    expect(isSelfService("T1")).toBe(true);
    expect(isSelfService("T2")).toBe(true);
    expect(isSelfService("T3")).toBe(false);
  });
});
