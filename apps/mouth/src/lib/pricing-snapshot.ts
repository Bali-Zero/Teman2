import pricingSnapshot from "../../data/bali-zero-prices.json";

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
}

interface PricingSnapshot {
  services_by_category: Record<string, Record<string, PricingSnapshotEntry>>;
}

const snapshot = pricingSnapshot as PricingSnapshot;
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
