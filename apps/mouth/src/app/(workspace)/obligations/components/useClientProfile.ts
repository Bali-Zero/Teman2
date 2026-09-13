"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

import { describeError } from "./describe-error";
import type { ProfileOut } from "./types";

export interface ClientProfileState {
  data: ProfileOut | null;
  loading: boolean;
  error: string | null;
  /** Re-read the profile from the server; used after a successful save. */
  reload: () => Promise<void>;
}

/**
 * Load `GET /api/compliance/obligations/profile/{clientId}` for the client the
 * register is filtered to.
 *
 * `clientId` is the trimmed client filter; "" means no client is selected and
 * nothing is read. The response carries client data (the company's compliance
 * attributes), so like `useClientNames` it stays in component state for the
 * life of the tab: never logged, never persisted, never forwarded.
 */
export function useClientProfile(clientId: string): ClientProfileState {
  const [data, setData] = useState<ProfileOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Sequence number of the newest read. A response whose number is no longer
  // current is DROPPED: two reads can be open at once (the mount read and the
  // reload a save triggers), and applying them in arrival order would let an
  // older profile overwrite a newer one.
  const latest = useRef(0);

  const load = useCallback(async (): Promise<void> => {
    if (!clientId) {
      setData(null);
      setError(null);
      setLoading(false);
      return;
    }
    const mine = ++latest.current;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<ProfileOut>(
        `/api/compliance/obligations/profile/${clientId}`,
      );
      if (mine !== latest.current) return;
      setData(res);
    } catch (e) {
      if (mine !== latest.current) return;
      // The thrown error is NOT passed to the log sink: its message comes from a
      // client-record read (same reason as useClientNames).
      logger.warn("obligations client profile load failed", {
        component: "ObligationsPage",
        action: "loadClientProfile",
        metadata: { client_id: clientId },
      });
      setData(null);
      setError(describeError(e, "Could not load the client profile."));
    } finally {
      if (mine === latest.current) setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    void load();
  }, [load]);

  return { data, loading, error, reload: load };
}
