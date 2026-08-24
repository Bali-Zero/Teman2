/**
 * Product code -> service tier (T1/T2/T3), transcribed verbatim from
 * `TIER-MAP.md` (owner switchboard #4, `docs/plans/2026-08-24-visa-oracle-live/`
 * on `origin/feature/visa-oracle`) — the authoritative source, built once for
 * the owner switchboard from the real signed pack. Reused here rather than
 * re-derived, the same discipline already applied to `CATEGORY_TO_PURPOSE`
 * (`fact-mapper.ts`): one authoritative map, not a parallel one this route
 * would have to keep in sync by hand.
 *
 * - **T1 — self-purchase puro.** No consultant needed.
 * - **T2 — self-purchase + consultant included.** The consultant contact is
 *   part of the price, not a fallback.
 * - **T3 — assisted-only.** `pricing_key` absent -> cannot be sold
 *   self-service at all -> T3 by construction (TIER-MAP.md's own rule),
 *   independent of how complete the product's eligibility rules are.
 *
 * `product-tier-map.test.ts` re-derives T1/T2/T3 membership from the real
 * signed pack's `pricing_key` presence and asserts it matches this map
 * exactly — the same freshness discipline as `product-purpose-counts.ts`.
 */

export type ProductTier = "T1" | "T2" | "T3";

const T1_CODES = ["A1", "B1", "C1", "C2", "C6", "D1", "D2"] as const;

const T2_CODES = [
  "D12",
  "E23",
  "E28A",
  "E30A",
  "E30B",
  "E31A",
  "E31B",
  "E31C",
  "E31D",
  "E31E",
  "E31F",
  "E31G",
  "E31H",
  "E31J",
  "E33",
  "E33E",
  "E33F",
  "E33G",
  "BRIDGING",
] as const;

const T3_CODES = [
  "E23U",
  "E23V",
  "E28B",
  "E28C",
  "E28D",
  "E28F",
  "E33A",
  "E33B",
  "E33C",
  "E30",
  "E30E",
  "E30F",
] as const;

export const PRODUCT_TIER_MAP: Readonly<Record<string, ProductTier>> =
  Object.freeze({
    ...Object.fromEntries(T1_CODES.map((code) => [code, "T1" as const])),
    ...Object.fromEntries(T2_CODES.map((code) => [code, "T2" as const])),
    ...Object.fromEntries(T3_CODES.map((code) => [code, "T3" as const])),
  });

/** `self-service` covers T1 and T2 — a client can buy without the interview
 * dead-ending in a consultant hand-off, even though T2 always gets a
 * follow-up call. T3 is the "assisted-only" set: never sold solo. */
export function isSelfService(tier: ProductTier): boolean {
  return tier === "T1" || tier === "T2";
}

/** `undefined` for a product code this map does not (yet) cover — never
 * guessed as T1/T2/T3, since an unmapped product must not silently count
 * as either self-service or consultant-routed. */
export function tierForProductCode(
  productCode: string,
): ProductTier | undefined {
  return PRODUCT_TIER_MAP[productCode];
}
