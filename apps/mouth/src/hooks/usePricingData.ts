"use client";

import {
  getExactSnapshotPrice,
  getTierSetFloorPrice,
} from "@/lib/pricing-snapshot";

interface PricingResult {
  price: string | null;
  isLoading: boolean;
  isError: boolean;
}

/**
 * Resolve an exact PricingTool row from the generated, parity-tested snapshot.
 * A missing category/key or a non-scalar IDR amount abstains with `null`.
 */
export function usePricingData(
  serviceKey: string | null,
  category: string | null = null,
): PricingResult {
  return {
    price:
      serviceKey && category
        ? getExactSnapshotPrice(category, serviceKey)
        : null,
    isLoading: false,
    isError: false,
  };
}

/**
 * Resolve the catalogue's lowest IDR figure across a set of tier keys in one
 * category — for a package that spans several catalogue tiers instead of
 * mapping onto one exact SKU. Missing category/keys abstains with `null`.
 */
export function useTierFloorPricingData(
  category: string | null,
  tierKeys: string[] | null,
): PricingResult {
  return {
    price:
      category && tierKeys && tierKeys.length > 0
        ? getTierSetFloorPrice(category, tierKeys)
        : null,
    isLoading: false,
    isError: false,
  };
}
