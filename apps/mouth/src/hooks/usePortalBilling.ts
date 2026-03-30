import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { BillingResponse } from "@/lib/api/portal/portal.types";

export function usePortalBilling() {
  return useQuery<BillingResponse>({
    queryKey: ["portal", "billing"],
    queryFn: () => api.portal.getBilling(),
    staleTime: 120_000,
  });
}
