"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Handshake,
  Search,
  Plus,
  Loader2,
  AlertCircle,
  User,
  Mail,
  Phone,
  ChevronRight,
  X,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import { Money } from "@balizero/core";
import * as partnersApi from "@/lib/api/partners/partners";
import type { Partner, PartnerFilters } from "@/lib/api/partners/partners";
import { useTeamMemberOptions } from "@/hooks/useTeamMembers";

/** Dashboard panel recipe — mirrors the day/dark-aware Kita surfaces. */
const PANEL: React.CSSProperties = {
  background: "var(--bz-card)",
  borderColor: "var(--bz-border)",
};

/** Form controls on the panel surface. */
const INPUT_STYLE: React.CSSProperties = {
  background: "var(--bz-surface)",
  borderColor: "var(--bz-border)",
  color: "var(--bz-text-1)",
};

/** Inline danger strip (load error). */
const DANGER_STRIP: React.CSSProperties = {
  background: "color-mix(in srgb, var(--state-danger) 12%, transparent)",
  borderColor: "color-mix(in srgb, var(--state-danger) 30%, transparent)",
  color: "var(--state-danger)",
};

/** State-tinted chip: 12% tint fill, 30% rim, state ink (portal idiom). */
function stateChip(state: string): React.CSSProperties {
  return {
    background: `color-mix(in srgb, ${state} 12%, transparent)`,
    color: state,
    borderColor: `color-mix(in srgb, ${state} 30%, transparent)`,
  };
}

/** Neutral chip for closed/inert statuses. */
const NEUTRAL_CHIP: React.CSSProperties = {
  background: "color-mix(in srgb, var(--bz-text-pure) 6%, transparent)",
  color: "var(--bz-text-2)",
  borderColor: "var(--bz-border)",
};

// Status badge styles — CRIT-8: aligned to backend PartnerStatus enum.
// Honestly mapped: pending_approval -> warning, active -> success,
// inactive -> neutral.
const STATUS_STYLES: Record<
  string,
  { style: React.CSSProperties; label: string }
> = {
  pending_approval: {
    style: stateChip("var(--state-warning)"),
    label: "Pending Approval",
  },
  active: { style: stateChip("var(--state-success)"), label: "Active" },
  inactive: { style: NEUTRAL_CHIP, label: "Inactive" },
};

// Commission-tier identity chips (identity hues, not statuses):
// bronze -> copper accent, silver -> neutral, gold -> muted editorial gold,
// platinum -> editorial blue.
const TIER_STYLES: Record<string, React.CSSProperties> = {
  bronze: stateChip("var(--bz-accent)"),
  silver: NEUTRAL_CHIP,
  gold: stateChip("var(--accent-gold-muted)"),
  platinum: stateChip("var(--accent-blue-editorial)"),
};

function StatusBadge({ status }: { status: string }) {
  const entry = STATUS_STYLES[status] || { style: NEUTRAL_CHIP, label: status };
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium"
      style={entry.style}
    >
      {entry.label || status}
    </span>
  );
}

// P2.1: backend returns commission as a decimal string ("10.0000") — trim
// trailing zeros so the TIER fallback renders "10 %" instead of "10.0000 %".
function formatCommission(value: number | string): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return String(value);
  return parsed.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

function TierBadge({ tier }: { tier: string }) {
  const style = TIER_STYLES[tier] || NEUTRAL_CHIP;
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium capitalize"
      style={style}
    >
      {tier}
    </span>
  );
}

export default function PartnersPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  // useToast returns a fresh object on every render; stash the error fn in a
  // ref so loadPartners can stay referentially stable. Without this, the
  // `[filters, loadPartners]` useEffect re-fires every render and the table
  // re-renders continuously (visually "vibrates").
  const { error: toastError } = useToast();
  const toastErrorRef = useRef(toastError);
  useEffect(() => {
    toastErrorRef.current = toastError;
  }, [toastError]);
  const { options: teamMemberOptions } = useTeamMemberOptions();

  const [partners, setPartners] = useState<Partner[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const [filters, setFilters] = useState<PartnerFilters>({
    status: searchParams?.get("status") || "",
    assigned_to: searchParams?.get("assigned_to") || "",
    search: searchParams?.get("search") || "",
    orphaned: searchParams?.get("orphaned") === "true",
    page: 1,
    page_size: 50,
  });

  const [searchInput, setSearchInput] = useState(filters.search || "");

  const loadPartners = useCallback(async (currentFilters: PartnerFilters) => {
    setIsLoading(true);
    setError(null);
    try {
      const cleanFilters: PartnerFilters = {
        ...currentFilters,
        status: currentFilters.status || undefined,
        assigned_to: currentFilters.assigned_to || undefined,
        search: currentFilters.search || undefined,
        orphaned: currentFilters.orphaned || undefined,
      };
      const data = await partnersApi.listPartners(cleanFilters);
      setPartners(data.partners);
      setTotal(data.total);
    } catch (err) {
      logger.error(
        "Failed to load partners",
        { component: "PartnersPage" },
        err as Error,
      );
      setError("Failed to load partners. Please try again.");
      toastErrorRef.current("Failed to load partners");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPartners(filters);
  }, [filters, loadPartners]);

  const handleFilterChange = (
    key: keyof PartnerFilters,
    value: string | boolean,
  ) => {
    if (key === "assigned_to" && value === "__orphaned__") {
      setFilters((prev) => ({
        ...prev,
        assigned_to: undefined,
        orphaned: true,
        page: 1,
      }));
    } else if (key === "assigned_to") {
      setFilters((prev) => ({
        ...prev,
        assigned_to: (value as string) || undefined,
        orphaned: false,
        page: 1,
      }));
    } else {
      setFilters((prev) => ({ ...prev, [key]: value, page: 1 }));
    }
    setPage(1);
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    handleFilterChange("search", searchInput);
  };

  const clearFilters = () => {
    setSearchInput("");
    setFilters({ page: 1, page_size: 50 });
    setPage(1);
  };

  const hasActiveFilters = !!(
    filters.status ||
    filters.assigned_to ||
    filters.search ||
    filters.orphaned
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-[var(--bz-accent-subtle)]">
            <Handshake size={24} className="text-[var(--bz-accent)]" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--bz-text-1)]">
              Partners
            </h1>
            <p className="text-sm text-[var(--bz-text-2)]">
              {total} partner{total !== 1 ? "s" : ""} total
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Variant defaults are already token-driven (outline = --border,
              default = copper --accent) — no per-button color overrides. */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push("/partners/orphaned")}
          >
            Orphaned
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push("/partners/finance")}
          >
            Finance Queue
          </Button>
          <Button onClick={() => router.push("/partners/new")} size="sm">
            <Plus size={16} className="mr-1" />
            New Partner
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="border rounded-xl p-4" style={PANEL}>
        <div className="flex flex-wrap gap-3">
          {/* Search */}
          <form onSubmit={handleSearch} className="flex-1 min-w-48">
            <div className="relative">
              <Search
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--bz-text-3)]"
              />
              <input
                type="text"
                placeholder="Search name, email..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="w-full pl-9 pr-3 py-2 border rounded-lg text-sm placeholder:text-[var(--bz-text-3)] focus:outline-none focus:border-[var(--bz-accent)]"
                style={INPUT_STYLE}
              />
            </div>
          </form>

          {/* Status filter */}
          <select
            value={filters.status || ""}
            onChange={(e) => handleFilterChange("status", e.target.value)}
            className="px-3 py-2 border rounded-lg text-sm focus:outline-none focus:border-[var(--bz-accent)]"
            style={INPUT_STYLE}
          >
            <option value="">All statuses</option>
            {/* CRIT-8: aligned to backend PartnerStatus enum */}
            <option value="pending_approval">Pending Approval</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>

          {/* Assigned to filter */}
          <select
            value={filters.assigned_to || ""}
            onChange={(e) => handleFilterChange("assigned_to", e.target.value)}
            className="px-3 py-2 border rounded-lg text-sm focus:outline-none focus:border-[var(--bz-accent)]"
            style={INPUT_STYLE}
          >
            <option value="">All assignees</option>
            <option value="__orphaned__">Unassigned</option>
            {teamMemberOptions.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>

          {/* Orphaned filter */}
          <label
            className="flex items-center gap-2 px-3 py-2 border rounded-lg cursor-pointer"
            style={INPUT_STYLE}
          >
            <input
              type="checkbox"
              checked={!!filters.orphaned}
              onChange={(e) => handleFilterChange("orphaned", e.target.checked)}
              className="rounded border-[var(--bz-border-hover)] text-[var(--bz-accent)]"
            />
            <span className="text-sm text-[var(--bz-text-1)]">
              Orphaned only
            </span>
          </label>

          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={clearFilters}
              className="text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)]"
            >
              <X size={14} className="mr-1" />
              Clear
            </Button>
          )}

          <Button
            variant="ghost"
            size="sm"
            onClick={() => loadPartners(filters)}
            className="text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)]"
          >
            <RefreshCw size={14} />
          </Button>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 size={32} className="animate-spin text-[var(--bz-accent)]" />
        </div>
      ) : error ? (
        <div
          className="flex items-center gap-3 p-4 border rounded-xl"
          style={DANGER_STRIP}
        >
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      ) : partners.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <Handshake size={48} className="text-[var(--bz-text-3)]" />
          <p className="text-[var(--bz-text-2)]">No partners found</p>
          {hasActiveFilters && (
            <Button variant="outline" size="sm" onClick={clearFilters}>
              Clear filters
            </Button>
          )}
        </div>
      ) : (
        <div className="border rounded-xl overflow-hidden" style={PANEL}>
          <table className="w-full">
            <thead>
              <tr className="border-b border-[var(--bz-border)]">
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase tracking-wider">
                  Partner
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase tracking-wider hidden md:table-cell">
                  Contact
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase tracking-wider">
                  Status
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase tracking-wider hidden lg:table-cell">
                  Tier
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase tracking-wider hidden lg:table-cell">
                  Assigned To
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase tracking-wider hidden md:table-cell">
                  Referrals
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--bz-border)]">
              {partners.map((partner) => (
                <tr
                  key={partner.id}
                  onClick={() => router.push(`/partners/${partner.id}`)}
                  className="hover:bg-[var(--bz-glass-rim)] cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-[var(--bz-accent-muted)] flex items-center justify-center flex-shrink-0">
                        <User size={14} className="text-[var(--bz-accent)]" />
                      </div>
                      <div>
                        <div className="text-sm font-medium text-[var(--bz-text-1)]">
                          {partner.full_name}
                        </div>
                        {partner.company_name && (
                          <div className="text-xs text-[var(--bz-text-3)]">
                            {partner.company_name}
                          </div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-1.5 text-xs text-[var(--bz-text-2)]">
                        <Mail size={12} />
                        <span>{partner.email}</span>
                      </div>
                      {partner.phone && (
                        <div className="flex items-center gap-1.5 text-xs text-[var(--bz-text-3)]">
                          <Phone size={12} />
                          <span>{partner.phone}</span>
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={partner.onboarding_status} />
                  </td>
                  <td className="px-4 py-3 hidden lg:table-cell">
                    {/* CRIT-8: commission_tier is optional; backend uses default_commission_type + value */}
                    {partner.commission_tier ? (
                      <TierBadge tier={partner.commission_tier} />
                    ) : (
                      <span className="text-xs text-[var(--bz-text-3)] italic">
                        {partner.default_commission_type &&
                        partner.default_commission_value != null ? (
                          partner.default_commission_type === "percentage" ? (
                            `${formatCommission(partner.default_commission_value)} %`
                          ) : (
                            <Money
                              value={Number(partner.default_commission_value)}
                            />
                          )
                        ) : (
                          "—"
                        )}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 hidden lg:table-cell">
                    <span className="text-sm text-[var(--bz-text-2)]">
                      {partner.assigned_to || (
                        <span className="text-[var(--bz-text-3)] italic">
                          Unassigned
                        </span>
                      )}
                    </span>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    <span className="text-sm text-[var(--bz-text-2)]">
                      {partner.referral_count ?? 0}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <ChevronRight
                      size={16}
                      className="text-[var(--bz-text-3)] ml-auto"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination */}
          {total > 50 && (
            <div className="px-4 py-3 border-t border-[var(--bz-border)] flex items-center justify-between">
              <span className="text-sm text-[var(--bz-text-3)]">
                Showing {(page - 1) * 50 + 1}–{Math.min(page * 50, total)} of{" "}
                {total}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 1}
                  onClick={() => {
                    const newPage = page - 1;
                    setPage(newPage);
                    setFilters((prev) => ({ ...prev, page: newPage }));
                  }}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page * 50 >= total}
                  onClick={() => {
                    const newPage = page + 1;
                    setPage(newPage);
                    setFilters((prev) => ({ ...prev, page: newPage }));
                  }}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
