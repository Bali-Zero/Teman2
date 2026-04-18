"use client";

import { useCallback, useState } from "react";
import useSWR, { type SWRResponse } from "swr";
import { api } from "@/lib/api";
import {
  isMigrationMissingMessage,
  NotificationPrefs,
  type NotificationPrefsInput,
} from "@/lib/schemas/settings";

const ENDPOINT = "/api/portal/notifications/prefs";

/**
 * Classifies a thrown error as "migration 110 missing" (BE 503) vs. a
 * normal failure. The shared ApiClient throws a plain `Error` with the
 * FastAPI `detail` as its message, so we pattern-match on that.
 */
function isMigrationMissingError(err: unknown): boolean {
  if (err instanceof Error) {
    return isMigrationMissingMessage(err.message);
  }
  return false;
}

export interface UseNotificationPrefsResult {
  /** Parsed prefs on success; `null` when migration is missing. */
  data: NotificationPrefs | null;
  /** True when the BE signalled the 503 migration-missing error. */
  migrationMissing: boolean;
  /** Any non-migration-missing error from SWR (e.g. 401, 500). */
  error: Error | undefined;
  /** SWR loading flag. */
  isLoading: boolean;
  /** Trigger a revalidation. */
  mutate: SWRResponse<NotificationPrefs | null, Error>["mutate"];
  /**
   * PUT the prefs back to the BE. Returns the updated prefs on success.
   * Throws on non-migration errors. When the BE returns 503 the hook
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
 * Schema drift surfaces as SWR `error`. The BE 503 "migration 110
 * missing" case is trapped and exposed via `migrationMissing` so the
 * portal UI can show a graceful "feature coming soon" state rather than
 * blow up with a hard error.
 *
 * Note: the GET handler itself silently returns BE defaults
 * (`_default_prefs`) on DB read failure — only PUT raises 503 — but we
 * cover both sides for safety in case that changes.
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
        if (isMigrationMissingError(err)) {
          setMigrationMissing(true);
          return null;
        }
        throw err;
      }
    },
    {
      revalidateOnFocus: true,
      dedupingInterval: 5_000,
      shouldRetryOnError: (err: { status?: number } | Error) => {
        if (isMigrationMissingError(err)) return false;
        const status = (err as { status?: number })?.status ?? 0;
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
        if (isMigrationMissingError(err)) {
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
