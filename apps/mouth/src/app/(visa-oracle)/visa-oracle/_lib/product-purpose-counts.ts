/**
 * Real, pack-sourced product counts per wizard category — the honest
 * version of "the path visibly narrowing from 38 products to theirs"
 * (MANDATE.md §1, "magia decisionale").
 *
 * This is NOT an eligibility computation and must never be read as one: it
 * counts how many of the 38 catalogued visa products are tagged for the
 * SAME purpose the wizard's `category` question feeds into
 * `intent.purposes` — `CATEGORY_TO_PURPOSE` in `fact-mapper.ts`, the exact
 * mapping that already decides what fact gets submitted to the engine.
 * That mapping is imported and used to gate which categories get a number
 * at all, rather than duplicating its judgment here.
 *
 * `diaspora` is the one wizard category with no entry in
 * `CATEGORY_TO_PURPOSE` at all (that file's own comment: "Diaspora is
 * intentionally represented only by request_category") — so it gets no
 * count here either.
 *
 * **The count DECOMPOSES rather than shrinks (2026-08-25 correction from a
 * cross-family measurement).** A flat "N of 38 serve your situation" over-
 * promises: on `EMPLOYMENT` the pack tags 5 products, but only 1
 * (`E23`) is actually sellable self-service today — the other 4
 * (`E33A`, `E33B`, `E23U`, `E23V`) have no `pricing_key` at all and are
 * `T3` ("assisted-only") by `TIER-MAP.md`'s own construction rule. A flat
 * "1 of 38" instead throws away four real routes that DO exist, just
 * through a consultant. The honest shape is both numbers together: total
 * tagged, and how many of those are self-service (T1/T2) vs
 * consultant-routed (T3) — via `PRODUCT_TIER_MAP` (`product-tier-map.ts`,
 * itself transcribed from the owner-authoritative `TIER-MAP.md` rather
 * than re-derived here, same discipline as `CATEGORY_TO_PURPOSE`).
 *
 * **Divergence found and reported, not silently resolved**: a raw
 * "has at least one rule that can produce a decision" count (the
 * `TIER-MAP.md`-adjacent "29 of 38 have >=1 ELIGIBILITY rule" figure) is
 * NOT the same boundary as `PRODUCT_TIER_MAP`'s T3 test (pricing_key
 * presence) — `TIER-MAP.md` itself notes 3 of its 12 T3 products DO carry
 * an eligibility rule despite having no price. On `STUDY` this is visible
 * concretely: `E30`, `E30E`, `E30F` are exactly those 3 products —
 * tagged `STUDY`, each with SOME rule, none with a price. A count keyed on
 * "has a rule" would report STUDY as 5-of-5 self-service; the tier map
 * (correctly, for a "can the client actually buy this" display) reports
 * 2-of-5. This module uses the tier map's boundary throughout, because
 * that is the question this counter is actually answering for a visitor.
 *
 * The counts are a static snapshot of `rulepack-prod-013.signed.json`
 * (PRODUCTION, sequence 13). Pinned, not computed at build or run time —
 * this Next.js route has no filesystem access to the backend's signed-pack
 * directory. `product-purpose-counts.test.ts` re-derives every number
 * directly from that same file (purpose tagging AND tier split) and
 * additionally asserts `payload.sequence` is still 13 — if the active pack
 * rotates to a new sequence, or V1's per-product cure work moves a product
 * out of T3, that test goes red rather than this display silently serving
 * stale numbers.
 */
import { CATEGORY_TO_PURPOSE } from "./fact-mapper";
import type { CategoryKey } from "./tree";

/** The pinned pack this snapshot was taken from — asserted, not assumed,
 * by `product-purpose-counts.test.ts`. */
export const SNAPSHOT_PACK_SEQUENCE = 13;

/** `payload.products.length` in the pinned pack — the true catalogue size,
 * the honest anchor for any "38" language (never a hardcoded belief). */
export const TOTAL_CATALOGUE_PRODUCTS = 38;

export interface ProductPurposeBreakdown {
  /** All catalogue products tagged with this category's purpose. */
  total: number;
  /** Of `total`, how many are T1/T2 — a client can buy without the
   * interview dead-ending in a consultant hand-off. */
  selfService: number;
  /** `total - selfService` — T3, assisted-only, never invented: always
   * derived, never a second hardcoded number that could drift from
   * `total`. */
  consultantRouted: number;
}

/**
 * `{ total, selfService }` per wizard category — `selfService` counted
 * against `PRODUCT_TIER_MAP` (T1 ∪ T2). Only present for categories
 * `CATEGORY_TO_PURPOSE` itself covers — see module doc for why `diaspora`
 * has no entry. Individually commented so a reviewer can see the exact
 * pack purpose tag and tier split each pair traces to.
 */
const PRODUCT_PURPOSE_BREAKDOWN: Readonly<
  Partial<Record<CategoryKey, { total: number; selfService: number }>>
> = {
  tourism: { total: 13, selfService: 10 }, // "TOURISM": 3 T3
  business: { total: 6, selfService: 4 }, // "BUSINESS_MEETINGS": 2 T3
  work: { total: 5, selfService: 1 }, // "EMPLOYMENT": 4 T3 (E33A, E33B, E23U, E23V)
  invest: { total: 9, selfService: 3 }, // "INVESTMENT": 6 T3 (E28B/C/D/F, E33B, E33C)
  remote: { total: 1, selfService: 1 }, // "REMOTE_WORK": 0 T3
  family: { total: 19, selfService: 16 }, // "FAMILY": 3 T3
  retirement: { total: 2, selfService: 2 }, // "RETIREMENT": 0 T3
  study: { total: 5, selfService: 2 }, // "STUDY": 3 T3 (E30, E30E, E30F)
  other: { total: 2, selfService: 2 }, // "OTHER": 0 T3
  // diaspora: deliberately absent — see module doc.
};

/**
 * Returns the real, pack-and-tier-sourced product breakdown for a wizard
 * category, or `null` when the category has no corresponding engine
 * purpose to count against. The `null` boundary is LIVE — derived from
 * whether `CATEGORY_TO_PURPOSE` (the real fact-submission mapping) covers
 * this category — never a second, independently-maintained list of which
 * categories are "countable".
 */
export function productBreakdownForCategory(
  category: CategoryKey,
): ProductPurposeBreakdown | null {
  if (!(category in CATEGORY_TO_PURPOSE)) return null;
  const entry = PRODUCT_PURPOSE_BREAKDOWN[category];
  if (entry === undefined) return null;
  return {
    total: entry.total,
    selfService: entry.selfService,
    consultantRouted: entry.total - entry.selfService,
  };
}
