"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";

/**
 * FASE 5 — soft-delete / restore actions for portal vault documents.
 *
 *   - DELETE /api/portal/documents/{id}            → soft-delete (recoverable)
 *   - POST   /api/portal/documents/{id}/restore    → restore
 *
 * Both endpoints return `{ success, message, data }`. We surface only the
 * in-flight id (for per-row spinners/disabling) and the last error message;
 * the caller revalidates the SWR list on success via the `onMutated` callback.
 */
export function useVaultDocumentActions(onMutated?: () => void) {
  const [pendingId, setPendingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const remove = useCallback(
    async (id: number): Promise<boolean> => {
      setPendingId(id);
      setError(null);
      try {
        await api.delete<unknown>(`/api/portal/documents/${id}`);
        onMutated?.();
        return true;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to remove document");
        return false;
      } finally {
        setPendingId(null);
      }
    },
    [onMutated],
  );

  const restore = useCallback(
    async (id: number): Promise<boolean> => {
      setPendingId(id);
      setError(null);
      try {
        await api.post<unknown>(`/api/portal/documents/${id}/restore`);
        onMutated?.();
        return true;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to restore document");
        return false;
      } finally {
        setPendingId(null);
      }
    },
    [onMutated],
  );

  return { remove, restore, pendingId, error };
}
