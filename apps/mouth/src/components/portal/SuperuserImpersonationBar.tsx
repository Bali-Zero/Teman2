"use client";

/**
 * SuperuserImpersonationBar
 *
 * Visible only when the authenticated user is a superuser (zero@balizero.com
 * by default — see backend SUPERUSER_EMAILS). Lets them search for a client
 * and "enter" their portal view. Active impersonation shows a pill with the
 * selected client and a close button to restore the superuser's own view.
 */

import React, { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { api } from "@/lib/api";
import { useAdminImpersonation } from "@/contexts/AdminImpersonationContext";

type Suggestion = {
  id: number;
  email: string | null;
  full_name: string | null;
};

const SEARCH_DEBOUNCE_MS = 200;

async function searchClients(q: string): Promise<Suggestion[]> {
  const params = new URLSearchParams({ q, limit: "10" });
  const res = await fetch(`/api/portal/admin/clients/search?${params}`, {
    credentials: "include",
    headers: api.getToken()
      ? { Authorization: `Bearer ${api.getToken()}` }
      : undefined,
  });
  if (!res.ok) return [];
  const json = (await res.json()) as { items?: Suggestion[] };
  return json.items ?? [];
}

export function SuperuserImpersonationBar() {
  const { isSuperuser, target, setTarget } = useAdminImpersonation();
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!isSuperuser) return;
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!query || query.length < 2) {
      setSuggestions([]);
      return;
    }
    setLoading(true);
    timerRef.current = setTimeout(async () => {
      const items = await searchClients(query);
      setSuggestions(items);
      setLoading(false);
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [query, isSuperuser]);

  if (!isSuperuser) return null;

  // Active impersonation pill
  if (target) {
    const label = target.fullName || target.email || `Client #${target.id}`;
    return (
      <div className="flex items-center gap-2">
        <span
          className="flex items-center gap-1.5 px-2 py-1 rounded-full text-[11px] font-semibold uppercase tracking-wider bg-[var(--bz-copper)]/20 text-[var(--bz-copper)] border border-[var(--bz-copper)]/40"
          title={target.email ?? ""}
        >
          Viewing as: {label}
          <button
            onClick={() => {
              setTarget(null);
              // Force a reload so all cached portal data is re-fetched
              window.location.reload();
            }}
            aria-label="Stop impersonating"
            className="hover:bg-[var(--bz-copper)]/30 rounded-full p-0.5 transition-colors"
          >
            <X className="w-3 h-3" />
          </button>
        </span>
      </div>
    );
  }

  // Search input
  return (
    <div className="relative">
      <input
        type="text"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setIsOpen(true);
        }}
        onFocus={() => setIsOpen(true)}
        onBlur={() => {
          // Delay so onClick on a suggestion fires before we close
          setTimeout(() => setIsOpen(false), 120);
        }}
        placeholder="Search client to impersonate…"
        className="w-56 md:w-72 bg-[rgba(255,255,255,0.05)] border border-[var(--glass-rim)] rounded-lg px-3 py-1.5 text-sm text-[var(--tx-pure)] placeholder:text-[var(--tx-secondary)]/60 focus:outline-none focus:border-[var(--bz-copper)]/60"
      />
      {isOpen && (query.length >= 2 || loading) && (
        <div className="absolute top-full mt-1 right-0 left-0 z-40 max-h-80 overflow-y-auto rounded-lg border border-[var(--glass-rim)] bg-[rgba(29,39,59,0.95)] backdrop-blur-[24px] shadow-xl">
          {loading && (
            <div className="px-3 py-2 text-xs text-[var(--tx-secondary)]">
              Searching…
            </div>
          )}
          {!loading && suggestions.length === 0 && query.length >= 2 && (
            <div className="px-3 py-2 text-xs text-[var(--tx-secondary)]">
              No match
            </div>
          )}
          {suggestions.map((s) => (
            <button
              key={s.id}
              onClick={() => {
                setTarget({
                  id: s.id,
                  email: s.email,
                  fullName: s.full_name,
                });
                setQuery("");
                setSuggestions([]);
                setIsOpen(false);
                // Reload so fresh data loads with as_client
                window.location.reload();
              }}
              className="w-full text-left px-3 py-2 text-sm hover:bg-[var(--background-elevated)] border-b border-[var(--glass-rim)] last:border-b-0"
            >
              <div className="font-medium text-[var(--tx-pure)]">
                {s.full_name || `Client #${s.id}`}
              </div>
              {s.email && (
                <div className="text-[11px] text-[var(--tx-secondary)]">
                  {s.email}
                </div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
