"use client";

import { useEffect, useMemo, useRef } from "react";
import { createFunnelAppTracker, type FunnelAppName } from "./funnel-app";

interface UseFunnelAppOptions {
  /** If true, fires `app_viewed` automatically on mount. Default: true. */
  trackView?: boolean;
  /** Debounce `formStarted` events — avoid flooding on fast typers. */
  formStartedDebounceMs?: number;
}

/** React hook wrapper around `createFunnelAppTracker`.
 *
 * Handles:
 *  - auto `app_viewed` on mount (once per component lifecycle)
 *  - debounced `formStarted` so a user typing field-by-field does not
 *    spam the endpoint with identical events
 */
export function useFunnelApp(
  app: FunnelAppName,
  opts: UseFunnelAppOptions = {},
) {
  const { trackView = true, formStartedDebounceMs = 1500 } = opts;
  const tracker = useMemo(() => createFunnelAppTracker(app), [app]);
  const seenFields = useRef<Set<string>>(new Set());
  const lastField = useRef<{ field: string; at: number } | null>(null);

  useEffect(() => {
    if (trackView) void tracker.viewed();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const formStarted = (field: string) => {
    const now = Date.now();
    const last = lastField.current;
    if (seenFields.current.has(field)) return;
    if (last && last.field === field && now - last.at < formStartedDebounceMs)
      return;
    seenFields.current.add(field);
    lastField.current = { field, at: now };
    void tracker.formStarted(field);
  };

  return {
    ...tracker,
    formStarted,
  };
}
