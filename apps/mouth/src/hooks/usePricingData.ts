"use client";

import useSWR from "swr";
import { PRICING_FALLBACK } from "@/components/book/book-data";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface PricingResult {
  price: string | null;
  isLoading: boolean;
  isError: boolean;
}

/**
 * Fetch a live price by SSOT service key. Pass `null` to skip the fetch
 * entirely (e.g. a package with no live pricing wired yet) — SWR treats a
 * `null` key as "don't fetch", so no network call is made and `price` is
 * always `null` in that case.
 */
export function usePricingData(serviceKey: string | null): PricingResult {
  const { data, error, isLoading } = useSWR(
    serviceKey
      ? `/api/pricing/calculate?service=${encodeURIComponent(serviceKey)}`
      : null,
    fetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      shouldRetryOnError: false,
      fallbackData: serviceKey
        ? { price: PRICING_FALLBACK[serviceKey] ?? null }
        : undefined,
    },
  );

  return {
    price:
      (serviceKey ? (data?.price ?? PRICING_FALLBACK[serviceKey]) : null) ??
      null,
    isLoading,
    isError: !!error,
  };
}
