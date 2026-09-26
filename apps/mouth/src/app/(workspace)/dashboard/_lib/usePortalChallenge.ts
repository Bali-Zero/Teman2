/**
 * "Portal Champion" challenge standing — GET /api/dashboard/portal-challenge.
 *
 * The endpoint is being built in parallel and is not deployed yet, so a 404
 * (or any other failure) must NOT break the dashboard: the queryFn swallows
 * the error and resolves `null`, which the widget reads as "nothing to show
 * yet" rather than an error banner. `retry: false` keeps a real outage from
 * hammering the endpoint every refetch tick.
 *
 * A thrown error is not the only way this endpoint can be "not really
 * there" yet: a 200 with an unrelated/placeholder body (an API mock/stub
 * that answers every unmatched route with `{success:true,data:{}}`, or a
 * future contract change) is JSON that parses fine but is not a
 * PortalChallengeResponse — the widget then reads `data.entries` etc. as
 * undefined and crashes render instead of degrading. `isPortalChallengeResponse`
 * validates the minimal shape the widget actually touches BEFORE handing it
 * to the widget, so a malformed 200 degrades exactly like a 404 does.
 */
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api/dashboard/dashboard.api";
import type { PortalChallengeResponse } from "@/lib/api/dashboard/dashboard.api";
import { logger } from "@/lib/logger";

export const portalChallengeQueryKey = (identity: string) =>
  ["portal-challenge", identity] as const;

function isPortalChallengeResponse(
  value: unknown,
): value is PortalChallengeResponse {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.status === "string" &&
    typeof v.team_total_activations === "number" &&
    Array.isArray(v.entries) &&
    Array.isArray(v.tiers) &&
    Array.isArray(v.recent_activations) &&
    typeof v.tax_rules === "object" &&
    v.tax_rules !== null
  );
}

export function usePortalChallenge(identity: string) {
  return useQuery<PortalChallengeResponse | null>({
    queryKey: portalChallengeQueryKey(identity),
    queryFn: async () => {
      try {
        const response = await dashboardApi.getPortalChallenge();
        if (!isPortalChallengeResponse(response)) {
          logger.debug(
            "Portal challenge endpoint returned an unexpected shape",
            {
              component: "usePortalChallenge",
              action: "queryFn",
            },
          );
          return null;
        }
        return response;
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
    refetchOnWindowFocus: true,
    retry: false,
    enabled: Boolean(identity),
  });
}
