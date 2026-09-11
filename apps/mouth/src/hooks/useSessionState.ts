"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SessionState } from "@/lib/api/types/api-client.types";

export type UseSessionStateResult = SessionState | "pending";

/**
 * Cookie-primary session state for a mounted component (auth-gates-cookie-
 * primary). Every consumer that used to gate on `api.isAuthenticated()` (a
 * local-token-only, positive-only check) now asks the server instead, so a
 * cookie-only session — no local bearer token, still logged in — is
 * recognized rather than bounced to /login.
 *
 * Starts at "pending" on every render, ALWAYS — never reads the token or
 * localStorage synchronously here. Doing so would make the very first
 * render differ between server and client (SSR has no cookies to read),
 * which is exactly the hydration-mismatch class this hook exists to avoid.
 * The effect below resolves it after mount; a visitor who does carry a
 * local token still lands on "authenticated" within the same effect cycle,
 * via the fast path inside `api.hasSession()` — they just see it one tick
 * later than a (hydration-unsafe) synchronous read would have shown it.
 *
 * Cross-component dedup is `api.hasSession()`'s job (it memoizes the
 * in-flight probe): N components mounted at once still cost one fetch.
 */
export function useSessionState(): UseSessionStateResult {
  const [state, setState] = useState<UseSessionStateResult>("pending");

  useEffect(() => {
    let alive = true;
    api.hasSession().then((result) => {
      if (alive) setState(result);
    });
    return () => {
      alive = false;
    };
  }, []);

  return state;
}
