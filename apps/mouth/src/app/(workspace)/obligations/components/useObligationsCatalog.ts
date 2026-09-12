"use client";

import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

import type { CatalogRuleOut } from "./types";

export interface CatalogState {
  /** rule_id -> rule. Empty until the catalog read resolves. */
  byId: Map<string, CatalogRuleOut>;
  loading: boolean;
  /** Non-null when the catalog read failed; the table then falls back to ids. */
  error: string | null;
}

/**
 * Load `GET /api/compliance/obligations/catalog` ONCE per mount.
 *
 * The catalog is process-cached server-side (`_cached_rules()`) and carries no
 * client data, so one read per screen is enough and the result is safe to hold
 * in component state. A failure is not fatal: the caller renders `rule_id`
 * unchanged, which is what the screen did before this hook existed.
 */
export function useObligationsCatalog(): CatalogState {
  const [byId, setById] = useState<Map<string, CatalogRuleOut>>(
    () => new Map(),
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // The request itself, not an "already started" boolean. `reactStrictMode` is on
  // (apps/mouth/next.config.ts), so in dev React runs setup -> cleanup -> setup:
  // a boolean guard would let the first run start the read, the cleanup discard
  // its result, and the second run bail out — leaving the catalog empty forever
  // with no second request to recover it. Holding the PROMISE means the second
  // setup re-attaches to the same in-flight read: still exactly one request,
  // and its result lands.
  const inflight = useRef<Promise<CatalogRuleOut[]> | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!inflight.current) {
      inflight.current = api.get<CatalogRuleOut[]>(
        "/api/compliance/obligations/catalog",
      );
    }
    const request = inflight.current;

    void (async () => {
      try {
        const rules = await request;
        if (cancelled) return;
        // A non-array body (an older backend, or a proxy error page) must not
        // throw inside render — degrade to ids instead.
        const list = Array.isArray(rules) ? rules : [];
        setById(new Map(list.map((rule) => [rule.id, rule])));
        setError(list.length === 0 ? "Rule catalog is empty." : null);
      } catch (e) {
        if (cancelled) return;
        logger.error(
          "obligations catalog load failed",
          { component: "ObligationsPage", action: "loadCatalog" },
          e instanceof Error ? e : new Error(String(e)),
        );
        setError("Could not load the rule catalog — showing rule ids.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return { byId, loading, error };
}
