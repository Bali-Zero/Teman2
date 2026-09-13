"use client";

/**
 * GARUDA VOA — staff practice list.
 *
 * SAETTA-VOA W-VOA-V3 (2026-09-13): concept-F "RAPI" presentation pass, the
 * same one shipped on the client portal. PRESENTATION ONLY — the profile
 * probe, the admin/assigned narrowing, the abort-on-change load and the staff
 * API contract are byte-for-byte the behaviour that was here before.
 *
 * The table stays a table: staff scan five columns and the semantics are worth
 * keeping. What changes is the dressing — copper rule + Fraunces masthead,
 * eyebrow column heads, hairlines instead of a filled card, copper numerals,
 * and the seven states as OUTLINED pills in the four R19 meanings. No filled
 * state row, and no red: see r19.tsx.
 */

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { FilterSelect } from "@balizero/core";
import { Loader2, FolderKanban } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { logger } from "@/lib/logger";
import { toError } from "@/lib/types/common";
import { listStaffPractices } from "./api-client";
import {
  CARD,
  EYEBROW,
  FOCUS,
  Masthead,
  Notice,
  PracticeStatePill,
  SERIF,
  pad2,
} from "./r19";
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

const FILTER_SELECT_CLASS =
  "h-11 rounded border border-[var(--bz-border-hover)] bg-[var(--bz-surface)] text-sm text-[var(--tx-pure)] focus-visible:ring-2 focus-visible:ring-[var(--bz-copper)]";

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
    <div className="space-y-9">
      <Masthead
        eyebrow="GARUDA VOA · staff"
        title="Practices"
        subtitle="Review, block, submit and deliver visa-on-arrival practices"
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <FilterSelect
          id="garuda-voa-state-filter"
          label="State"
          value={stateFilter}
          onChange={setStateFilter}
          selectClassName={FILTER_SELECT_CLASS}
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
            selectClassName={FILTER_SELECT_CLASS}
          >
            <option value="all">All staff</option>
            <option value="me">My work</option>
          </FilterSelect>
        )}
      </div>

      {loadError && <Notice role="alert">{loadError}</Notice>}

      {isLoading ? (
        <div
          className="flex h-40 items-center justify-center"
          data-testid="loading-skeleton"
        >
          <Loader2 className="h-6 w-6 animate-spin text-[var(--bz-copper)]" />
        </div>
      ) : rows.length === 0 ? (
        <div
          className={cn(
            CARD,
            "flex flex-col items-center justify-center gap-2 px-6 py-12",
          )}
        >
          <FolderKanban
            className="h-7 w-7 text-[var(--tx-secondary)] opacity-40"
            aria-hidden="true"
          />
          <p
            className="text-[20px] leading-[1.14] text-[var(--tx-pure)]"
            style={SERIF}
          >
            No practices
          </p>
          <p className="text-[13px] text-[var(--tx-secondary)]">
            Nothing matches this filter yet.
          </p>
        </div>
      ) : (
        <div className={cn(CARD, "overflow-x-auto")}>
          <table className="w-full text-sm">
            <caption className="sr-only">
              GARUDA VOA staff practices, newest activity first
            </caption>
            <thead>
              <tr className={cn("border-b border-[var(--bz-border)]", EYEBROW)}>
                <th
                  scope="col"
                  className="w-[42px] px-3 py-3 text-left md:w-[52px] md:px-4"
                >
                  #
                </th>
                <th scope="col" className="px-3 py-3 text-left md:px-4">
                  Practice
                </th>
                <th
                  scope="col"
                  className="hidden px-3 py-3 text-left md:table-cell md:px-4"
                >
                  Order
                </th>
                <th scope="col" className="px-3 py-3 text-left md:px-4">
                  State
                </th>
                <th
                  scope="col"
                  className="hidden px-3 py-3 text-left md:table-cell md:px-4"
                >
                  Assigned to
                </th>
                <th
                  scope="col"
                  className="hidden px-3 py-3 text-left md:table-cell md:px-4"
                >
                  Updated
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((practice, index) => {
                const shortDate = formatDate(practice.updated_at);
                return (
                  <tr
                    key={practice.practice_id}
                    className={cn(
                      "cursor-pointer border-b border-[var(--bz-border)] transition-colors last:border-0 hover:bg-[var(--bz-card-hover)]",
                      FOCUS,
                    )}
                    tabIndex={0}
                    onClick={() =>
                      router.push(`/garuda-voa/${practice.practice_id}`)
                    }
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        router.push(`/garuda-voa/${practice.practice_id}`);
                      }
                    }}
                    data-testid={`garuda-voa-row-${practice.practice_id}`}
                  >
                    <td
                      className="px-3 py-3.5 text-[20px] leading-none tabular-nums text-[var(--bz-copper-text)] md:px-4"
                      style={SERIF}
                    >
                      {pad2(index + 1)}
                    </td>
                    <td className="px-3 py-3.5 font-mono text-xs text-[var(--tx-pure)] md:px-4">
                      {practice.practice_id}
                      {/* Below md the three columns to the right are hidden
                        rather than pushed off the edge of a 390px screen —
                        their content moves here, under the id. */}
                      <span className="mt-1 block font-sans text-[11px] text-[var(--tx-secondary)] md:hidden">
                        {practice.assigned_to
                          ? practice.assigned_to.split("@")[0]
                          : "Unassigned"}{" "}
                        · <span className="tabular-nums">{shortDate}</span>
                      </span>
                    </td>
                    <td className="hidden px-3 py-3.5 md:px-4 font-mono text-xs text-[var(--tx-secondary)] md:table-cell">
                      {practice.order_id}
                    </td>
                    <td className="px-3 py-3.5 md:px-4">
                      <PracticeStatePill state={practice.state} />
                    </td>
                    <td className="hidden px-3 py-3.5 md:px-4 text-[var(--tx-pure)] md:table-cell">
                      {practice.assigned_to ? (
                        practice.assigned_to.split("@")[0]
                      ) : (
                        <span className="text-[var(--tx-secondary)]">
                          Unassigned
                        </span>
                      )}
                    </td>
                    <td className="hidden px-3 py-3.5 md:px-4 tabular-nums text-[var(--tx-secondary)] md:table-cell">
                      {shortDate}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
