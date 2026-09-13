/**
 * "Portal Champion" challenge standing — GET /api/dashboard/portal-challenge.
 *
 * The endpoint is being built in parallel and is not deployed yet, so a 404
 * (or any other failure) must NOT break the dashboard: the queryFn swallows
 * the error and resolves `null`, which the widget reads as "nothing to show
 * yet" rather than an error banner. `retry: false` keeps a real outage from
 * hammering the endpoint every refetch tick.
 */
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api/dashboard/dashboard.api";
import type { PortalChallengeResponse } from "@/lib/api/dashboard/dashboard.api";
import { logger } from "@/lib/logger";

export const portalChallengeQueryKey = (identity: string) =>
  ["portal-challenge", identity] as const;

export function usePortalChallenge(identity: string) {
  return useQuery<PortalChallengeResponse | null>({
    queryKey: portalChallengeQueryKey(identity),
    queryFn: async () => {
      try {
        return await dashboardApi.getPortalChallenge();
      } catch (err) {
        logger.debug("Portal challenge endpoint unavailable", {
          component: "usePortalChallenge",
          action: "queryFn",
          metadata: { error: err instanceof Error ? err.message : String(err) },
        });
        return null;
      }
    },
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: false,
    enabled: Boolean(identity),
  });
}
