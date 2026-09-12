"use client";

import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

/** The one field this screen needs from the CRM client read. */
interface ClientNameRead {
  id: number;
  full_name?: string | null;
}

/**
 * Resolve `client_id` -> display name for the ids currently on screen.
 *
 * Read: `GET /api/crm/clients/{client_id}` (`crm_clients.py`, one row plus a
 * lateral last-interaction join) — the lightest per-client read that returns
 * `full_name`. Its gate is `verify_client_access(..., allow_assigned=True)`,
 * and `is_crm_admin` short-circuits it to allowed, so any session that already
 * passed this screen's own admin gate can resolve every id it sees.
 *
 * PII boundary: a resolved name lives in this hook's state for the life of the
 * browser tab and nowhere else. It is never logged (failures log the id only),
 * never sent anywhere, and never persisted. An id that fails to resolve is
 * remembered as attempted so the screen does not retry it on every render; the
 * caller falls back to the id, which is what the table showed before.
 */
export function useClientNames(clientIds: number[]): Record<number, string> {
  const [names, setNames] = useState<Record<number, string>>({});
  // Ids already fetched (resolved OR failed). Cache key = client id.
  const attempted = useRef<Set<number>>(new Set());

  // Stable dependency: the sorted unique id list as a string, so an unchanged
  // page of rows does not re-run the effect on every parent render.
  const key = Array.from(new Set(clientIds))
    .sort((a, b) => a - b)
    .join(",");

  useEffect(() => {
    const ids = key
      .split(",")
      .filter(Boolean)
      .map(Number)
      .filter((id) => Number.isInteger(id) && id > 0)
      .filter((id) => !attempted.current.has(id));
    if (ids.length === 0) return;
    ids.forEach((id) => attempted.current.add(id));

    // No `cancelled` guard, deliberately. The merge below is per id and
    // idempotent, so a late response can never be stale: there is no ordering
    // hazard to protect against. A guard would be actively harmful — the rows
    // change (a page turn, a filter) while a read is in flight, React runs the
    // cleanup, the result gets dropped, and the id stays in `attempted`, so
    // those names would never load again for the life of the tab.
    void (async () => {
      const resolved = await Promise.all(
        ids.map(async (id) => {
          try {
            const client = await api.get<ClientNameRead>(
              `/api/crm/clients/${id}`,
            );
            const name = (client?.full_name ?? "").trim();
            return name ? ([id, name] as const) : null;
          } catch {
            // Deliberately NOT passing the thrown error: its message comes from
            // a client-record read and must not reach the log sink.
            logger.warn(
              "client name resolution failed; falling back to the id",
              {
                component: "ObligationsPage",
                action: "resolveClientName",
                metadata: { client_id: id },
              },
            );
            return null;
          }
        }),
      );
      const found = resolved.filter((pair): pair is readonly [number, string] =>
        Boolean(pair),
      );
      if (found.length === 0) return;
      setNames((prev) => {
        const next = { ...prev };
        for (const [id, name] of found) next[id] = name;
        return next;
      });
    })();
  }, [key]);

  return names;
}
