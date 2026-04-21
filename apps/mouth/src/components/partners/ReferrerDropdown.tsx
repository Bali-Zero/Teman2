"use client";

import React, { useEffect, useState } from "react";
import { Loader2, Handshake } from "lucide-react";
import * as partnersApi from "@/lib/api/partners/partners";
import type { Partner } from "@/lib/api/partners/partners";

interface ReferrerDropdownProps {
  // CRIT-8: partner IDs are UUID strings
  value: string | null;
  onChange: (partnerId: string | null) => void;
  className?: string;
  disabled?: boolean;
  placeholder?: string;
}

/**
 * ReferrerDropdown — select an active partner as referrer for a process/practice.
 * Fetches active partners scoped by the caller's role (team members see only
 * partners assigned to them; admins see all active partners).
 */
export function ReferrerDropdown({
  value,
  onChange,
  className = "",
  disabled = false,
  placeholder = "No referrer",
}: ReferrerDropdownProps) {
  const [partners, setPartners] = useState<Partner[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await partnersApi.listActivePartnersDropdown();
        if (!cancelled) {
          setPartners(
            [...data.partners].sort((a, b) =>
              a.full_name.localeCompare(b.full_name),
            ),
          );
        }
      } catch {
        if (!cancelled) setError("Failed to load partners");
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  if (isLoading) {
    return (
      <div className={`flex items-center gap-2 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg ${className}`}>
        <Loader2 size={14} className="animate-spin text-zinc-500" />
        <span className="text-sm text-zinc-500">Loading partners…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`px-3 py-2 bg-zinc-800 border border-red-700/50 rounded-lg ${className}`}>
        <span className="text-sm text-red-400">{error}</span>
      </div>
    );
  }

  return (
    <div className={`relative ${className}`}>
      <Handshake
        size={14}
        className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none"
      />
      <select
        value={value ?? ""}
        onChange={(e) => {
          const v = e.target.value;
          // CRIT-8: partner IDs are UUID strings — no Number() conversion
          onChange(v === "" ? null : v);
        }}
        disabled={disabled}
        className="w-full pl-8 pr-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 focus:outline-none focus:border-amber-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <option value="">{placeholder}</option>
        {partners.map((p) => (
          <option key={p.id} value={p.id}>
            {/* CRIT-8: commission_tier is optional; use default_commission_value as fallback */}
            {p.full_name}{p.commission_tier ? ` (${p.commission_tier})` : p.default_commission_value ? ` (${p.default_commission_value}${p.default_commission_type === 'percentage' ? '%' : ' IDR'})` : ''}
          </option>
        ))}
      </select>
    </div>
  );
}

export default ReferrerDropdown;
