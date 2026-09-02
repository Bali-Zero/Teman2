"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ListPageHeader, FilterSelect } from "@balizero/core";
import { Loader2, FolderKanban } from "lucide-react";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import { toError } from "@/lib/types/common";
import { listStaffPractices } from "./api-client";
import type { StaffPracticeListRow, PracticeState } from "./types";

const STATE_OPTIONS: PracticeState[] = [
  "Received",
  "In review",
  "Blocked",
  "Submitted",
  "Approved",
  "Rejected",
  "Delivered",
];

// Same badge palette family as the customer tracker (orders/OrderTracker.tsx)
// — staff and customer surfaces read the same seven-state vocabulary and
// must never drift into two different color stories for one state.
const STATE_BADGE_STYLE: Record<PracticeState, React.CSSProperties> = {
  Received: {
    background: "var(--surface-raised)",
    color: "var(--bz-text-2)",
  },
  "In review": {
    background: "color-mix(in srgb, var(--state-info) 15%, transparent)",
    color: "var(--state-info)",
  },
  Blocked: {
    background: "color-mix(in srgb, var(--state-warning) 15%, transparent)",
    color: "var(--state-warning)",
  },
  Submitted: {
    background: "color-mix(in srgb, var(--state-info) 15%, transparent)",
    color: "var(--state-info)",
  },
  Approved: {
    background: "color-mix(in srgb, var(--state-success) 15%, transparent)",
    color: "var(--state-success)",
  },
  Rejected: {
    background: "color-mix(in srgb, var(--state-danger) 15%, transparent)",
    color: "var(--state-danger)",
  },
  Delivered: {
    background: "color-mix(in srgb, var(--state-success) 20%, transparent)",
    color: "var(--state-success)",
  },
};

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-GB", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function GarudaVoaStaffListPage() {
  const router = useRouter();
  const [isAdmin, setIsAdmin] = useState(false);
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [practices, setPractices] = useState<StaffPracticeListRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [stateFilter, setStateFilter] = useState<string>("");
  // Non-admin team members only ever see their own assigned work (server
  // enforces this regardless — see api-client.ts); admins default to "all"
  // but can still narrow to "me".
  const [assignedFilter, setAssignedFilter] = useState<"me" | "all">("all");

  useEffect(() => {
    api
      .getProfile()
      .then(() => {
        setIsAdmin(api.isAdmin());
      })
      .catch((err: unknown) => {
        logger.error(
          "[GarudaVoaStaff] Failed to load user profile",
          {},
          err instanceof Error ? err : new Error(String(err)),
        );
      })
      .finally(() => setProfileLoaded(true));
  }, []);

  useEffect(() => {
    if (!profileLoaded) return;
    const controller = new AbortController();
    const load = async () => {
      setIsLoading(true);
      setLoadError(null);
      try {
        const response = await listStaffPractices({
          state: stateFilter || undefined,
          assigned: isAdmin ? assignedFilter : "me",
          signal: controller.signal,
        });
        setPractices(response.items);
      } catch (error) {
        if (controller.signal.aborted) return;
        logger.error(
          "[GarudaVoaStaff] Failed to load practices",
          { component: "GarudaVoaStaffList", action: "loadPractices" },
          toError(error),
        );
        setLoadError("Failed to load GARUDA VOA practices.");
      } finally {
        if (!controller.signal.aborted) setIsLoading(false);
      }
    };
    load();
    return () => controller.abort();
  }, [profileLoaded, isAdmin, stateFilter, assignedFilter]);

  const rows = useMemo(() => practices, [practices]);

  return (
    <div className="space-y-6">
      <ListPageHeader
        title="GARUDA VOA — Staff practices"
        subtitle="Review, block, submit and deliver visa-on-arrival practices"
      />

      <div className="flex flex-col sm:flex-row gap-3">
        <FilterSelect
          id="garuda-voa-state-filter"
          label="State"
          value={stateFilter}
          onChange={setStateFilter}
          selectClassName="border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-1)] focus:ring-2 focus:ring-[var(--bz-accent)]/50"
        >
          <option value="">All states</option>
          {STATE_OPTIONS.map((state) => (
            <option key={state} value={state}>
              {state}
            </option>
          ))}
        </FilterSelect>
        {isAdmin && (
          <FilterSelect
            id="garuda-voa-assigned-filter"
            label="Assigned"
            value={assignedFilter}
            onChange={(v) => setAssignedFilter(v === "me" ? "me" : "all")}
            selectClassName="border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-1)] focus:ring-2 focus:ring-[var(--bz-accent)]/50"
          >
            <option value="all">All staff</option>
            <option value="me">My work</option>
          </FilterSelect>
        )}
      </div>

      {loadError && (
        <div
          className="rounded-lg p-4 text-sm"
          style={{
            background:
              "color-mix(in srgb, var(--state-danger) 10%, transparent)",
            color: "var(--state-danger)",
          }}
          role="alert"
        >
          {loadError}
        </div>
      )}

      {isLoading ? (
        <div
          className="flex items-center justify-center h-40"
          data-testid="loading-skeleton"
        >
          <Loader2 className="w-6 h-6 animate-spin text-[var(--bz-accent)]" />
        </div>
      ) : rows.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-32 border border-dashed border-[var(--bz-border)] rounded-lg bg-[var(--bz-card)]/30">
          <FolderKanban className="w-8 h-8 text-[var(--bz-text-2)] opacity-20 mb-2" />
          <p className="text-xs text-[var(--bz-text-2)]">No practices</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-[var(--bz-border)] bg-[var(--bz-card)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-[var(--bz-text-2)] border-b border-[var(--bz-border)]">
                <th className="px-4 py-3">Practice</th>
                <th className="px-4 py-3">Order</th>
                <th className="px-4 py-3">State</th>
                <th className="px-4 py-3">Assigned to</th>
                <th className="px-4 py-3">Updated</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((practice) => (
                <tr
                  key={practice.practice_id}
                  className="border-b border-[var(--bz-border)] last:border-0 cursor-pointer hover:bg-[var(--bz-card-hover)] transition-colors"
                  onClick={() =>
                    router.push(`/garuda-voa/${practice.practice_id}`)
                  }
                  data-testid={`garuda-voa-row-${practice.practice_id}`}
                >
                  <td className="px-4 py-3 font-mono text-xs text-[var(--bz-text-1)]">
                    {practice.practice_id}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-[var(--bz-text-2)]">
                    {practice.order_id}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium"
                      style={STATE_BADGE_STYLE[practice.state]}
                    >
                      {practice.state}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[var(--bz-text-1)]">
                    {practice.assigned_to
                      ? practice.assigned_to.split("@")[0]
                      : "Unassigned"}
                  </td>
                  <td className="px-4 py-3 text-[var(--bz-text-2)]">
                    {formatDate(practice.updated_at)}
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
