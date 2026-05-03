"use client";

/**
 * AdminImpersonationContext
 *
 * Session-scoped state for superuser (zero@) portal impersonation.
 * Holds the selected client id and injects it into every portal API call
 * as ?as_client=<id> via the shared api client (see lib/api/client.ts).
 *
 * The context is session-persistent (localStorage) so refreshing the page
 * keeps the same target client without re-searching.
 */

import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  useCallback,
} from "react";
import { api } from "@/lib/api";

type ImpersonationTarget = {
  id: number;
  email: string | null;
  fullName: string | null;
};

type Ctx = {
  isSuperuser: boolean;
  target: ImpersonationTarget | null;
  setTarget: (t: ImpersonationTarget | null) => void;
  loading: boolean;
};

const STORAGE_KEY = "bz_portal_impersonation_v1";

const AdminImpersonationContext = createContext<Ctx>({
  isSuperuser: false,
  target: null,
  setTarget: () => {},
  loading: true,
});

export function AdminImpersonationProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [isSuperuser, setIsSuperuser] = useState(false);
  const [target, setTargetState] = useState<ImpersonationTarget | null>(null);
  const [loading, setLoading] = useState(true);

  // Restore from localStorage on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as ImpersonationTarget;
        if (parsed && typeof parsed.id === "number") {
          setTargetState(parsed);
          // Apply to api client immediately so the first portal fetch already
          // carries as_client (otherwise the header would 422 on mount).
          api.setPortalImpersonation?.(parsed.id);
        }
      }
    } catch {
      // ignore
    }
  }, []);

  // Ask backend once whether the logged-in user is a superuser
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/portal/admin/me", {
          credentials: "include",
          headers: api.getToken()
            ? { Authorization: `Bearer ${api.getToken()}` }
            : undefined,
        });
        if (!res.ok) {
          if (!cancelled) setLoading(false);
          return;
        }
        const json = (await res.json()) as { is_superuser?: boolean };
        if (!cancelled) {
          setIsSuperuser(Boolean(json.is_superuser));
          setLoading(false);
        }
      } catch {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const setTarget = useCallback((t: ImpersonationTarget | null) => {
    setTargetState(t);
    if (t) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(t));
      api.setPortalImpersonation?.(t.id);
    } else {
      localStorage.removeItem(STORAGE_KEY);
      api.setPortalImpersonation?.(null);
    }
  }, []);

  const value = useMemo<Ctx>(
    () => ({ isSuperuser, target, setTarget, loading }),
    [isSuperuser, target, setTarget, loading],
  );

  return (
    <AdminImpersonationContext.Provider value={value}>
      {children}
    </AdminImpersonationContext.Provider>
  );
}

export function useAdminImpersonation() {
  return useContext(AdminImpersonationContext);
}
