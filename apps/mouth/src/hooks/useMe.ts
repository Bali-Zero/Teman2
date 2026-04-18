"use client";

import useSWR, { type SWRResponse } from "swr";
import { api } from "@/lib/api";
import { UserProfile } from "@/lib/schemas/settings";

/**
 * SWR hook for `GET /api/auth/profile`.
 *
 * Fetches the authenticated user's profile from the BE and validates the
 * response with Zod. Schema drift surfaces as SWR errors rather than
 * partial UI (callers should render a fallback on `error`).
 *
 * The BE endpoint lives at
 * `apps/backend-rag/backend/app/routers/auth.py:435` (`get_profile`) and
 * returns the unified `UserProfile` model (see schemas/settings.ts).
 *
 * Endpoint requires auth; a 401 triggers the ApiClient's built-in
 * redirect-to-login flow, so we don't handle it here.
 */
export function useMe(): SWRResponse<UserProfile, Error> {
  return useSWR<UserProfile, Error>(
    ["auth-profile"],
    async () => {
      const raw = await api.get<unknown>("/api/auth/profile");
      return UserProfile.parse(raw);
    },
    {
      revalidateOnFocus: true,
      dedupingInterval: 10_000,
      shouldRetryOnError: (err: { status?: number } | Error) => {
        const status = (err as { status?: number })?.status ?? 0;
        // Don't retry auth failures; do retry 5xx.
        return status >= 500;
      },
    },
  );
}
