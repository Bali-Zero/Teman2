'use client';

import useSWR from 'swr';
import { PRICING_FALLBACK } from '@/components/book/book-data';

const fetcher = (url: string) => fetch(url).then((r) => r.json());

interface PricingResult {
  price: string | null;
  isLoading: boolean;
  isError: boolean;
}

export function usePricingData(serviceKey: string): PricingResult {
  const { data, error, isLoading } = useSWR(
    `/api/pricing/calculate?service=${encodeURIComponent(serviceKey)}`,
    fetcher,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      shouldRetryOnError: false,
      fallbackData: { price: PRICING_FALLBACK[serviceKey] ?? null },
    }
  );

  return {
    price: data?.price ?? PRICING_FALLBACK[serviceKey] ?? null,
    isLoading,
    isError: !!error,
  };
}
