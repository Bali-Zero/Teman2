import pricingSnapshot from "../../data/bali-zero-prices.json";
import type { PricingItem } from "@/types/pricing";

export interface PricingSnapshotEntry {
  category: string;
  key: string;
  name: string;
  price: string | null;
  duration: string | null;
  validity: string | null;
  notes: string | null;
  description_en: string | null;
  icon_id: string | null;
  /** [low, high] IDR range for a tier the catalogue prices as a band rather
   *  than a single figure (e.g. a "from" tier). Null everywhere else. Same
   *  shape as PricingItem["tier_range"] (apps/mouth/src/types/pricing.ts). */
  tier_range: PricingItem["tier_range"];
}

interface PricingSnapshot {
  services_by_category: Record<string, Record<string, PricingSnapshotEntry>>;
}

// The raw JSON module's inferred array literal type does not always narrow
// to the [string, string] tuple PricingSnapshotEntry declares (some
// tier_range values are null, some are 2-element arrays) — go through
// `unknown` rather than widen the public field back to string[].
const snapshot = pricingSnapshot as unknown as PricingSnapshot;
const EXACT_IDR_PRICE = /^(?:\d+|\d{1,3}(?:\.\d{3})+)\s+IDR$/i;

export function getPricingSnapshotEntry(
  category: string,
  itemKey: string,
): PricingSnapshotEntry | undefined {
  return snapshot.services_by_category[category]?.[itemKey];
}

export function getExactPricingSnapshotEntries(
  category: string,
): PricingSnapshotEntry[] {
  const rows = snapshot.services_by_category[category];
  if (!rows) return [];
  return Object.values(rows).filter(
    (row) => row.price !== null && EXACT_IDR_PRICE.test(row.price.trim()),
  );
}

export function getExactSnapshotPrice(
  category: string,
  itemKey: string,
): string | null {
  const price = getPricingSnapshotEntry(category, itemKey)?.price?.trim();
  return price && EXACT_IDR_PRICE.test(price) ? price : null;
}

function parseIdrAmount(price: string): number {
  return Number(price.replace(/[^\d]/g, ""));
}

/**
 * Lowest IDR figure the catalogue backs for any of `itemKeys` in `category` —
 * a tier's exact price if it has one, otherwise the low end of its
 * `tier_range` band. Used for a package that shows "from X" because it spans
 * several catalogue tiers rather than mapping onto one exact SKU. Returns
 * null (never a guess) when no key resolves to a numeric floor.
 */
export function getTierSetFloorPrice(
  category: string,
  itemKeys: string[],
): string | null {
  let floor: { amount: number; price: string } | null = null;
  for (const itemKey of itemKeys) {
    const entry = getPricingSnapshotEntry(category, itemKey);
    if (!entry) continue;
    const rangeLow = entry.tier_range?.[0]?.trim();
    const candidate =
      entry.price && EXACT_IDR_PRICE.test(entry.price.trim())
        ? entry.price.trim()
        : rangeLow && EXACT_IDR_PRICE.test(rangeLow)
          ? rangeLow
          : null;
    if (!candidate) continue;
    const amount = parseIdrAmount(candidate);
    if (!floor || amount < floor.amount) {
      floor = { amount, price: candidate };
    }
  }
  return floor?.price ?? null;
}
