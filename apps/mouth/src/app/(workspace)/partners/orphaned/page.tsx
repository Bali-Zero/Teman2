"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  User,
  CheckSquare,
  Square,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import { api } from "@/lib/api";
import * as partnersApi from "@/lib/api/partners/partners";
import type { Partner } from "@/lib/api/partners/partners";
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
      router.replace("/partners");
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
      logger.error(
        "Failed to load orphaned partners",
        { component: "OrphanedPartnersPage" },
        err as Error,
      );
      setError("Failed to load orphaned partners.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOrphaned();
  }, [loadOrphaned]);

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
      toastSuccess(
        `${result.updated_count} partner${result.updated_count !== 1 ? "s" : ""} reassigned`,
      );
      await loadOrphaned();
      setTargetAssignee("");
    } catch (err) {
      logger.error(
        "Bulk reassign failed",
        { component: "OrphanedPartnersPage" },
        err as Error,
      );
      toastError("Bulk reassign failed. Please try again.");
    } finally {
      setIsReassigning(false);
    }
  };

  const allSelected =
    partners.length > 0 && selectedIds.size === partners.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/partners">
          <Button
            variant="ghost"
            size="sm"
            className="text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)]"
          >
            <ArrowLeft size={16} className="mr-1" />
            Partners
          </Button>
        </Link>
        <div>
          <h1 className="text-xl font-bold text-[var(--bz-text-1)]">
            Orphaned Partners
          </h1>
          <p className="text-sm text-[var(--bz-text-3)]">
            Partners without an assigned team member
          </p>
        </div>
      </div>

      {/* Bulk Reassign Toolbar */}
      {partners.length > 0 && (
        <div className="border rounded-xl p-4 space-y-3" style={PANEL}>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm text-[var(--bz-text-2)]">
              {selectedIds.size > 0
                ? `${selectedIds.size} selected`
                : "Select partners to reassign"}
            </span>
            <select
              value={targetAssignee}
              onChange={(e) => setTargetAssignee(e.target.value)}
              className="px-3 py-2 border rounded-lg text-sm focus:outline-none focus:border-[var(--bz-accent)]"
              style={INPUT_STYLE}
            >
              <option value="">Select assignee…</option>
              {teamMemberOptions.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
            <Button
              onClick={handleBulkReassign}
              disabled={
                isReassigning ||
                selectedIds.size === 0 ||
                !targetAssignee ||
                !reasonText.trim()
              }
              className="bg-[var(--bz-accent)] hover:bg-[var(--bz-accent-hover)] text-[var(--bz-on-warm)]"
              size="sm"
            >
              {isReassigning ? (
                <>
                  <Loader2 size={14} className="animate-spin mr-1" />{" "}
                  Reassigning…
                </>
              ) : (
                `Reassign ${selectedIds.size > 0 ? selectedIds.size : ""} Partner${selectedIds.size !== 1 ? "s" : ""}`
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={loadOrphaned}
              className="text-[var(--bz-text-2)]"
            >
              <RefreshCw size={14} />
            </Button>
          </div>
          <div>
            <textarea
              value={reasonText}
              onChange={(e) => {
                setReasonText(e.target.value);
                if (e.target.value.trim()) setReasonError("");
              }}
              placeholder="Reason for reassignment (required)…"
              rows={2}
              className="w-full px-3 py-2 border rounded-lg text-sm placeholder:text-[var(--bz-text-3)] focus:outline-none focus:border-[var(--bz-accent)] resize-none"
              style={{
                ...INPUT_STYLE,
                ...(reasonError ? { borderColor: "var(--state-danger)" } : {}),
              }}
            />
            {reasonError && (
              <p className="text-xs text-[var(--state-danger)] mt-1">
                {reasonError}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Content */}
      {isLoading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 size={32} className="animate-spin text-[var(--bz-accent)]" />
        </div>
      ) : error ? (
        <div className="flex items-center gap-3 p-4 bg-[var(--state-danger)]/10 border border-[var(--state-danger)]/30 rounded-xl text-[var(--state-danger)]">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      ) : partners.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <User size={48} className="text-[var(--bz-text-3)]" />
          <p className="text-[var(--bz-text-2)]">
            No orphaned partners — all partners are assigned
          </p>
        </div>
      ) : (
        <div className="border rounded-xl overflow-hidden" style={PANEL}>
          <table className="w-full">
            <thead>
              <tr className="border-b border-[var(--bz-border)]">
                <th className="px-4 py-3 w-10">
                  <button
                    onClick={toggleAll}
                    className="text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)]"
                  >
                    {allSelected ? (
                      <CheckSquare
                        size={16}
                        className="text-[var(--bz-accent)]"
                      />
                    ) : (
                      <Square size={16} />
                    )}
                  </button>
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
                  Partner
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase hidden md:table-cell">
                  Email
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
                  Status
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase hidden md:table-cell">
                  Created
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--bz-border)]">
              {partners.map((partner) => (
                <tr
                  key={partner.id}
                  className={`transition-colors ${selectedIds.has(partner.id) ? "bg-[var(--surface-selected)]" : "hover:bg-[var(--bz-glass-rim)]"}`}
                >
                  <td className="px-4 py-3">
                    <button
                      onClick={() => toggleSelect(partner.id)}
                      className="text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)]"
                    >
                      {selectedIds.has(partner.id) ? (
                        <CheckSquare
                          size={16}
                          className="text-[var(--bz-accent)]"
                        />
                      ) : (
                        <Square size={16} />
                      )}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-sm font-medium text-[var(--bz-text-1)]">
                      {partner.full_name}
                    </div>
                    {partner.company_name && (
                      <div className="text-xs text-[var(--bz-text-3)]">
                        {partner.company_name}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell text-sm text-[var(--bz-text-2)]">
                    {partner.email}
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-[var(--state-warning)]/10 text-[var(--state-warning)] capitalize">
                      {partner.onboarding_status.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 hidden md:table-cell text-sm text-[var(--bz-text-3)]">
                    {new Date(partner.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => router.push(`/partners/${partner.id}`)}
                      className="text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)]"
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
