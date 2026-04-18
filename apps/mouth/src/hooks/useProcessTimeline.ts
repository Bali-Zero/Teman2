"use client";

import useSWR, { type SWRResponse } from "swr";
import { api } from "@/lib/api";
import {
  ProcessTimelineResponse,
  type ProcessTimelineData,
} from "@/lib/schemas/process";

/**
 * SWR hook for `GET /api/portal/process/{practiceId}/timeline`.
 *
 * Fetches the raw envelope `{ success, data }` via `api.get` (so that Zod can
 * validate `success` too) and returns the parsed inner `data`. Responses that
 * don't match the schema, or carry `success: false`, surface as SWR errors
 * rather than silently producing partial UI.
 *
 * Pass `null` / `undefined` for `practiceId` to skip fetching (e.g. while the
 * parent is still resolving the practice ID).
 */
export function useProcessTimeline(
  practiceId: string | number | null | undefined,
): SWRResponse<ProcessTimelineData, Error> {
  return useSWR<ProcessTimelineData, Error>(
    practiceId != null && practiceId !== ""
      ? ["portal-process-timeline", String(practiceId)]
      : null,
    async ([, id]: [string, string]) => {
      const raw = await api.get<unknown>(
        `/api/portal/process/${encodeURIComponent(id)}/timeline`,
      );
      const parsed = ProcessTimelineResponse.parse(raw);
      if (!parsed.success) {
        throw new Error("Timeline response not successful");
      }
      return parsed.data;
    },
    {
      revalidateOnFocus: true,
      dedupingInterval: 2000,
      shouldRetryOnError: (err: { status?: number } | Error) => {
        const status = (err as { status?: number })?.status ?? 0;
        return status >= 500;
      },
    },
  );
}
