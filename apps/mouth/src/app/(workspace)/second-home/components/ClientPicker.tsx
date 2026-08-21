"use client";

import React, { useEffect, useRef, useState } from "react";
import { Loader2, Search, User } from "lucide-react";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import { toError } from "@/lib/types/common";
import type { Client } from "@/lib/api/crm/crm.types";

/**
 * Client search combobox — mirrors the inline pattern in
 * `process/new/page.tsx` (no shared component exists yet for this; this is
 * a feature-local copy scoped to the second-home form).
 */
export function ClientPicker({
  selectedClient,
  onSelect,
  onClear,
}: {
  selectedClient: Client | null;
  onSelect: (client: Client) => void;
  onClear: () => void;
}) {
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<Client[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!search.trim()) {
      setResults([]);
      return;
    }
    setIsSearching(true);
    const debounce = setTimeout(async () => {
      try {
        const found = await api.crm.getClients({ search, limit: 20 });
        setResults(found);
      } catch (error) {
        logger.error(
          "Failed to search clients",
          { component: "SecondHomeClientPicker", action: "search" },
          toError(error),
        );
      } finally {
        setIsSearching(false);
      }
    }, 300);
    return () => clearTimeout(debounce);
  }, [search]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const inputClass =
    "w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 transition-all";

  if (selectedClient) {
    return (
      <div className="flex items-center justify-between p-3 rounded-lg border border-[var(--accent)]/30 bg-[var(--accent)]/10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-[var(--accent)]/20 flex items-center justify-center">
            <User className="w-4 h-4 text-[var(--accent)]" />
          </div>
          <div>
            <p className="text-sm font-medium text-[var(--foreground)]">
              {selectedClient.full_name}
            </p>
            <p className="text-xs text-[var(--foreground-muted)]">
              {selectedClient.email || "No email"}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => {
            onClear();
            setSearch("");
          }}
          className="text-xs font-medium text-[var(--accent)] hover:underline"
        >
          Change
        </button>
      </div>
    );
  }

  return (
    <div className="relative" ref={containerRef}>
      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
      <input
        type="text"
        value={search}
        aria-label="Search client"
        onChange={(e) => {
          setSearch(e.target.value);
          setShowDropdown(true);
        }}
        onFocus={() => setShowDropdown(true)}
        className={inputClass}
        placeholder="Search client by name or email..."
      />
      {isSearching && (
        <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-[var(--foreground-muted)]" />
      )}
      {showDropdown && search && (
        <div className="absolute z-10 w-full mt-1 bg-[var(--background-elevated)] border border-[var(--border)] rounded-lg shadow-lg max-h-60 overflow-y-auto">
          {results.length > 0 ? (
            results.map((client) => (
              <button
                key={client.id}
                type="button"
                onClick={() => {
                  onSelect(client);
                  setShowDropdown(false);
                }}
                className="w-full text-left px-4 py-3 hover:bg-[var(--background-secondary)] transition-colors border-b border-[var(--border)] last:border-0"
              >
                <p className="text-sm font-medium text-[var(--foreground)]">
                  {client.full_name}
                </p>
                <p className="text-xs text-[var(--foreground-muted)]">
                  {client.email || client.phone || "No contact info"}
                </p>
              </button>
            ))
          ) : (
            <div className="p-4 text-center text-sm text-[var(--foreground-muted)]">
              {isSearching ? "Searching..." : "No clients found"}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
