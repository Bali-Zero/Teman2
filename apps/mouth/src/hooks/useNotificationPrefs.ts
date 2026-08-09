"use client";

import { useCallback, useState } from "react";
import useSWR, { type SWRResponse } from "swr";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/api/error-handler";
import {
  NotificationPrefs,
  type NotificationPrefsInput,
} from "@/lib/schemas/settings";

const ENDPOINT = "/api/portal/notifications/prefs";

/**
 * Classifies the endpoint's client-safe unavailable response by HTTP status.
 * Never infer backend schema state from error text: those implementation
 * details do not belong in the browser contract.
 */
function isTemporarilyUnavailableError(err: unknown): boolean {
  return err instanceof ApiError && err.statusCode === 503;
}

export interface UseNotificationPrefsResult {
  /** Parsed prefs on success; `null` while the endpoint is unavailable. */
  data: NotificationPrefs | null;
  /** True when the endpoint is temporarily unavailable (HTTP 503). */
  migrationMissing: boolean;
  /** Any non-availability error from SWR (e.g. 401, 500). */
  error: Error | undefined;
  /** SWR loading flag. */
  isLoading: boolean;
  /** Trigger a revalidation. */
  mutate: SWRResponse<NotificationPrefs | null, Error>["mutate"];
  /**
   * PUT the prefs back to the BE. Returns the updated prefs on success.
   * Throws on non-availability errors. When the BE returns 503 the hook
   * swallows it, flips `migrationMissing = true`, and returns `null`.
   */
  updatePrefs: (
    payload: NotificationPrefsInput,
  ) => Promise<NotificationPrefs | null>;
  /** True while `updatePrefs` is in flight. */
  isUpdating: boolean;
}

/**
 * SWR hook for `GET /api/portal/notifications/prefs` + PUT mutator.
 *
 * Endpoint lives at
 * `apps/backend-rag/backend/app/routers/portal_notification_prefs.py`.
 *
 * A client-safe HTTP 503 is trapped and exposed via the legacy
 * `migrationMissing` flag so existing consumers can render an unavailable
 * state without exposing backend details or fake preference values.
 */
export function useNotificationPrefs(): UseNotificationPrefsResult {
  const [isUpdating, setIsUpdating] = useState(false);
  const [migrationMissing, setMigrationMissing] = useState(false);

  const swr = useSWR<NotificationPrefs | null, Error>(
    ["portal-notification-prefs"],
    async () => {
      try {
        const raw = await api.get<unknown>(ENDPOINT);
        setMigrationMissing(false);
        return NotificationPrefs.parse(raw);
      } catch (err) {
        if (isTemporarilyUnavailableError(err)) {
          setMigrationMissing(true);
          return null;
        }
        throw err;
      }
    },
    {
      revalidateOnFocus: true,
      dedupingInterval: 5_000,
      shouldRetryOnError: (err: Error) => {
        if (isTemporarilyUnavailableError(err)) return false;
        const status = (err as { statusCode?: number })?.statusCode ?? 0;
        return status >= 500;
      },
    },
  );

  const updatePrefs = useCallback(
    async (
      payload: NotificationPrefsInput,
    ): Promise<NotificationPrefs | null> => {
      setIsUpdating(true);
      try {
        const raw = await api.put<unknown>(ENDPOINT, payload);
        const parsed = NotificationPrefs.parse(raw);
        setMigrationMissing(false);
        await swr.mutate(parsed, { revalidate: false });
        return parsed;
      } catch (err) {
        if (isTemporarilyUnavailableError(err)) {
          setMigrationMissing(true);
          await swr.mutate(null, { revalidate: false });
          return null;
        }
        throw err;
      } finally {
        setIsUpdating(false);
      }
    },
    [swr],
  );

  return {
    data: swr.data ?? null,
    migrationMissing,
    error: swr.error,
    isLoading: swr.isLoading,
    mutate: swr.mutate,
    updatePrefs,
    isUpdating,
  };
}
