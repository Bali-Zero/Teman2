"use client";

import { getExactSnapshotPrice } from "@/lib/pricing-snapshot";

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
