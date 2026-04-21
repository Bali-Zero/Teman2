"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Handshake,
  Search,
  Filter,
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
import * as partnersApi from "@/lib/api/partners/partners";
import type { Partner, PartnerFilters } from "@/lib/api/partners/partners";
import { useTeamMemberOptions } from "@/hooks/useTeamMembers";

// Status badge styles — CRIT-8: aligned to backend PartnerStatus enum
const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  pending_approval: { bg: "bg-amber-500/20", text: "text-amber-400", label: "Pending Approval" },
  active: { bg: "bg-green-500/20", text: "text-green-400", label: "Active" },
  inactive: { bg: "bg-gray-500/20", text: "text-gray-400", label: "Inactive" },
};

const TIER_STYLES: Record<string, { bg: string; text: string }> = {
  bronze: { bg: "bg-orange-900/30", text: "text-orange-400" },
  silver: { bg: "bg-zinc-700/50", text: "text-zinc-300" },
  gold: { bg: "bg-yellow-900/30", text: "text-yellow-400" },
  platinum: { bg: "bg-blue-900/30", text: "text-blue-300" },
};

function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] || { bg: "bg-gray-500/20", text: "text-gray-400", label: status };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${style.bg} ${style.text}`}>
      {style.label || status}
    </span>
  );
}

function TierBadge({ tier }: { tier: string }) {
  const style = TIER_STYLES[tier] || { bg: "bg-gray-500/20", text: "text-gray-400" };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize ${style.bg} ${style.text}`}>
      {tier}
    </span>
  );
}

export default function PartnersPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { error: toastError } = useToast();
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
      logger.error("Failed to load partners", { component: "PartnersPage" }, err as Error);
      setError("Failed to load partners. Please try again.");
      toastError("Failed to load partners");
    } finally {
      setIsLoading(false);
    }
  }, [toastError]);

  useEffect(() => {
    loadPartners(filters);
  }, [filters, loadPartners]);

  const handleFilterChange = (key: keyof PartnerFilters, value: string | boolean) => {
    if (key === "assigned_to" && value === "__orphaned__") {
      setFilters((prev) => ({ ...prev, assigned_to: undefined, orphaned: true, page: 1 }));
    } else if (key === "assigned_to") {
      setFilters((prev) => ({ ...prev, assigned_to: (value as string) || undefined, orphaned: false, page: 1 }));
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

  const hasActiveFilters = !!(filters.status || filters.assigned_to || filters.search || filters.orphaned);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-amber-500/10">
            <Handshake size={24} className="text-amber-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-zinc-100">Partners</h1>
            <p className="text-sm text-zinc-400">{total} partner{total !== 1 ? "s" : ""} total</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push("/partners/orphaned")}
            className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
          >
            Orphaned
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push("/partners/finance")}
            className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
          >
            Finance Queue
          </Button>
          <Button
            onClick={() => router.push("/partners/new")}
            size="sm"
            className="bg-amber-600 hover:bg-amber-700 text-white"
          >
            <Plus size={16} className="mr-1" />
            New Partner
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
        <div className="flex flex-wrap gap-3">
          {/* Search */}
          <form onSubmit={handleSearch} className="flex-1 min-w-48">
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
              <input
                type="text"
                placeholder="Search name, email..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-amber-500"
              />
            </div>
          </form>

          {/* Status filter */}
          <select
            value={filters.status || ""}
            onChange={(e) => handleFilterChange("status", e.target.value)}
            className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 focus:outline-none focus:border-amber-500"
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
            className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 focus:outline-none focus:border-amber-500"
          >
            <option value="">All assignees</option>
            <option value="__orphaned__">Unassigned</option>
            {teamMemberOptions.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>

          {/* Orphaned filter */}
          <label className="flex items-center gap-2 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg cursor-pointer">
            <input
              type="checkbox"
              checked={!!filters.orphaned}
              onChange={(e) => handleFilterChange("orphaned", e.target.checked)}
              className="rounded border-zinc-600 text-amber-500"
            />
            <span className="text-sm text-zinc-300">Orphaned only</span>
          </label>

          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={clearFilters}
              className="text-zinc-400 hover:text-zinc-200"
            >
              <X size={14} className="mr-1" />
              Clear
            </Button>
          )}

          <Button
            variant="ghost"
            size="sm"
            onClick={() => loadPartners(filters)}
            className="text-zinc-400 hover:text-zinc-200"
          >
            <RefreshCw size={14} />
          </Button>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 size={32} className="animate-spin text-amber-400" />
        </div>
      ) : error ? (
        <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      ) : partners.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <Handshake size={48} className="text-zinc-600" />
          <p className="text-zinc-400">No partners found</p>
          {hasActiveFilters && (
            <Button variant="outline" size="sm" onClick={clearFilters} className="border-zinc-700 text-zinc-300">
              Clear filters
            </Button>
          )}
        </div>
      ) : (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-900/50">
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Partner</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider hidden md:table-cell">Contact</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Status</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider hidden lg:table-cell">Tier</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider hidden lg:table-cell">Assigned To</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider hidden md:table-cell">Referrals</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {partners.map((partner) => (
                <tr
                  key={partner.id}
                  onClick={() => router.push(`/partners/${partner.id}`)}
                  className="hover:bg-zinc-800/50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-amber-500/20 flex items-center justify-center flex-shrink-0">
                        <User size={14} className="text-amber-400" />
                      </div>
                      <div>
                        <div className="text-sm font-medium text-zinc-100">{partner.full_name}</div>
                        {partner.company_name && (
                          <div className="text-xs text-zinc-500">{partner.company_name}</div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-1.5 text-xs text-zinc-400">
                        <Mail size={12} />
                        <span>{partner.email}</span>
                      </div>
                      {partner.phone && (
                        <div className="flex items-center gap-1.5 text-xs text-zinc-500">
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
                    {partner.commission_tier ? <TierBadge tier={partner.commission_tier} /> : (
                      <span className="text-xs text-zinc-600 italic">
                        {partner.default_commission_type
                          ? `${partner.default_commission_value} ${partner.default_commission_type === 'percentage' ? '%' : 'IDR'}`
                          : "—"}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 hidden lg:table-cell">
                    <span className="text-sm text-zinc-400">
                      {partner.assigned_to || <span className="text-zinc-600 italic">Unassigned</span>}
                    </span>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell">
                    <span className="text-sm text-zinc-400">{partner.referral_count ?? 0}</span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <ChevronRight size={16} className="text-zinc-600 ml-auto" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination */}
          {total > 50 && (
            <div className="px-4 py-3 border-t border-zinc-800 flex items-center justify-between">
              <span className="text-sm text-zinc-500">
                Showing {(page - 1) * 50 + 1}–{Math.min(page * 50, total)} of {total}
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
                  className="border-zinc-700 text-zinc-300"
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
                  className="border-zinc-700 text-zinc-300"
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
