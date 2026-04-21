"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2, AlertCircle, User, CheckSquare, Square, RefreshCw } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import { api } from "@/lib/api";
import * as partnersApi from "@/lib/api/partners/partners";
import type { Partner } from "@/lib/api/partners/partners";
import { useTeamMemberOptions } from "@/hooks/useTeamMembers";

export default function OrphanedPartnersPage() {
  const router = useRouter();
  const { success: toastSuccess, error: toastError } = useToast();
  const { options: teamMemberOptions } = useTeamMemberOptions();

  const [partners, setPartners] = useState<Partner[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // CRIT-8: partner IDs are UUID strings
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [targetAssignee, setTargetAssignee] = useState("");
  const [reasonText, setReasonText] = useState("");
  const [reasonError, setReasonError] = useState("");
  const [isReassigning, setIsReassigning] = useState(false);

  // Admin gate — redirect non-admin users back to partners list
  useEffect(() => {
    if (!api.isAdmin?.()) {
      router.replace('/partners');
    }
  }, [router]);

  const loadOrphaned = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setSelectedIds(new Set());
    try {
      const data = await partnersApi.listOrphanedPartners();
      setPartners(data.partners);
    } catch (err) {
      logger.error("Failed to load orphaned partners", { component: "OrphanedPartnersPage" }, err as Error);
      setError("Failed to load orphaned partners.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadOrphaned(); }, [loadOrphaned]);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === partners.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(partners.map((p) => p.id)));
    }
  };

  const handleBulkReassign = async () => {
    if (!targetAssignee) {
      toastError("Please select a team member to reassign to");
      return;
    }
    if (selectedIds.size === 0) {
      toastError("Please select at least one partner");
      return;
    }
    if (!reasonText.trim()) {
      setReasonError("Reason is required for reassignment");
      return;
    }
    setReasonError("");

    setIsReassigning(true);
    try {
      const result = await partnersApi.bulkReassign({
        partner_ids: Array.from(selectedIds),
        new_user_id: targetAssignee,
        reason: reasonText.trim(),
      });
      toastSuccess(`${result.updated_count} partner${result.updated_count !== 1 ? "s" : ""} reassigned`);
      await loadOrphaned();
      setTargetAssignee("");
    } catch (err) {
      logger.error("Bulk reassign failed", { component: "OrphanedPartnersPage" }, err as Error);
      toastError("Bulk reassign failed. Please try again.");
    } finally {
      setIsReassigning(false);
    }
  };

  const allSelected = partners.length > 0 && selectedIds.size === partners.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/partners">
          <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-zinc-200">
            <ArrowLeft size={16} className="mr-1" />
            Partners
          </Button>
        </Link>
        <div>
          <h1 className="text-xl font-bold text-zinc-100">Orphaned Partners</h1>
          <p className="text-sm text-zinc-500">Partners without an assigned team member</p>
        </div>
      </div>

      {/* Bulk Reassign Toolbar */}
      {partners.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm text-zinc-400">
              {selectedIds.size > 0 ? `${selectedIds.size} selected` : "Select partners to reassign"}
            </span>
            <select
              value={targetAssignee}
              onChange={(e) => setTargetAssignee(e.target.value)}
              className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 focus:outline-none focus:border-amber-500"
            >
              <option value="">Select assignee…</option>
              {teamMemberOptions.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
            <Button
              onClick={handleBulkReassign}
              disabled={isReassigning || selectedIds.size === 0 || !targetAssignee || !reasonText.trim()}
              className="bg-amber-600 hover:bg-amber-700 text-white"
              size="sm"
            >
              {isReassigning ? (
                <><Loader2 size={14} className="animate-spin mr-1" /> Reassigning…</>
              ) : (
                `Reassign ${selectedIds.size > 0 ? selectedIds.size : ""} Partner${selectedIds.size !== 1 ? "s" : ""}`
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={loadOrphaned}
              className="text-zinc-400"
            >
              <RefreshCw size={14} />
            </Button>
          </div>
          <div>
            <textarea
              value={reasonText}
              onChange={(e) => { setReasonText(e.target.value); if (e.target.value.trim()) setReasonError(""); }}
              placeholder="Reason for reassignment (required)…"
              rows={2}
              className={`w-full px-3 py-2 bg-zinc-800 border rounded-lg text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-amber-500 resize-none ${reasonError ? "border-red-500" : "border-zinc-700"}`}
            />
            {reasonError && <p className="text-xs text-red-400 mt-1">{reasonError}</p>}
          </div>
        </div>
      )}

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
          <User size={48} className="text-zinc-600" />
          <p className="text-zinc-400">No orphaned partners — all partners are assigned</p>
        </div>
      ) : (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="px-4 py-3 w-10">
                  <button onClick={toggleAll} className="text-zinc-400 hover:text-zinc-200">
                    {allSelected ? <CheckSquare size={16} className="text-amber-400" /> : <Square size={16} />}
                  </button>
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">Partner</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase hidden md:table-cell">Email</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">Status</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase hidden md:table-cell">Created</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {partners.map((partner) => (
                <tr
                  key={partner.id}
                  className={`transition-colors ${selectedIds.has(partner.id) ? "bg-amber-500/5" : "hover:bg-zinc-800/30"}`}
                >
                  <td className="px-4 py-3">
                    <button onClick={() => toggleSelect(partner.id)} className="text-zinc-400 hover:text-zinc-200">
                      {selectedIds.has(partner.id)
                        ? <CheckSquare size={16} className="text-amber-400" />
                        : <Square size={16} />}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-sm font-medium text-zinc-100">{partner.full_name}</div>
                    {partner.company_name && <div className="text-xs text-zinc-500">{partner.company_name}</div>}
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell text-sm text-zinc-400">{partner.email}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-500/20 text-amber-400 capitalize">
                      {partner.onboarding_status.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell text-sm text-zinc-500">
                    {new Date(partner.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => router.push(`/partners/${partner.id}`)}
                      className="text-zinc-400 hover:text-zinc-200"
                    >
                      View
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
