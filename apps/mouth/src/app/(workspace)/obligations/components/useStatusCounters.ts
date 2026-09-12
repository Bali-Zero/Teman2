"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

import {
  COUNTER_STATUSES,
  type CounterStatus,
  type ObligationListOut,
} from "./types";

export type StatusCounts = Partial<Record<CounterStatus, number>>;

/**
 * Per-status row counts for the current client filter.
 *
 * The list endpoint already returns `total` for whatever filter it is given,
 * so one `limit=1` read per status is the whole implementation — no new
 * backend route, and the four reads go out in parallel. `clientId` is the
 * trimmed client filter ("" = all clients); `refreshTick` is bumped by the
 * page after a generate / approve / reject so the strip follows the register.
 */
export function useStatusCounters(
  clientId: string,
  refreshTick: number,
): { counts: StatusCounts; loading: boolean } {
  const [counts, setCounts] = useState<StatusCounts>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    void (async () => {
      const results = await Promise.all(
        COUNTER_STATUSES.map(async (status) => {
          const params = new URLSearchParams();
          if (clientId) params.set("client_id", clientId);
          params.set("status", status);
          params.set("limit", "1");
          params.set("offset", "0");
          try {
            const res = await api.get<ObligationListOut>(
              `/api/compliance/obligations?${params.toString()}`,
            );
            return [status, res?.total ?? 0] as const;
          } catch (e) {
            logger.error(
              "obligations status counter failed",
              {
                component: "ObligationsPage",
                action: "statusCounter",
                metadata: { status },
              },
              e instanceof Error ? e : new Error(String(e)),
            );
            return null;
          }
        }),
      );
      if (cancelled) return;
      const next: StatusCounts = {};
      for (const pair of results) {
        if (pair) next[pair[0]] = pair[1];
      }
      setCounts(next);
      setLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [clientId, refreshTick]);

  return { counts, loading };
}
