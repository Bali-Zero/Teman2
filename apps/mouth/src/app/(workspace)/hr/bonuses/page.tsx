"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Download,
  Gift,
} from "lucide-react";
import { toast } from "sonner";
import * as hrApi from "@/lib/api/hr/hr";
import type { Bonus, BonusHistoricalRecord } from "@/types/hr";
import {
  aggregateByMember,
  bonusesToCsv,
  formatBonusDate,
  groupBonusesByMonth,
  reconcileMonthHistorical,
  UNDATED_KEY,
  witaMonthKey,
} from "@/lib/hr/bonus-aggregation";
import { formatIDR } from "@balizero/core/utils";

const statusColors: Record<string, string> = {
  pending: "bg-amber-500/10 text-amber-400 border-amber-500/30",
  approved: "bg-blue-500/10 text-blue-400 border-blue-500/30",
  paid: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
  rejected: "bg-red-500/10 text-red-400 border-red-500/30",
  reversed: "bg-zinc-500/10 text-zinc-400 border-zinc-500/30",
};

const ALL = "all";

function memberKeyOf(b: Bonus): string {
  return b.employee_id != null
    ? `id:${b.employee_id}`
    : `email:${b.employee_email || b.employee_name || "unknown"}`;
}

function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function BonusesPage() {
  const [bonuses, setBonuses] = useState<Bonus[]>([]);
  const [historical, setHistorical] = useState<BonusHistoricalRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [year, setYear] = useState<string>(ALL);
  const [status, setStatus] = useState<string>(ALL);
  const [member, setMember] = useState<string>(ALL);
  const [openMonths, setOpenMonths] = useState<Record<string, boolean>>({});
  const [openMembers, setOpenMembers] = useState<Record<string, boolean>>({});

  useEffect(() => {
    async function load() {
      try {
        const data = await hrApi.listBonuses();
        setBonuses(data.bonuses || []);
      } catch {
        /* keep the page usable — the empty state covers it */
      }
      try {
        // HR-admin only. Team members get a 403 and the reconciliation strip
        // simply stays hidden for them.
        const hist = await hrApi.listBonusHistorical();
        setHistorical(hist.records || []);
      } catch {
        setHistorical([]);
      }
      setLoading(false);
    }
    load();
  }, []);

  const handleApprove = async (id: number) => {
    try {
      await hrApi.approveBonus(id);
      setBonuses((prev) =>
        prev.map((b) => (b.id === id ? { ...b, status: "approved" } : b)),
      );
      toast.success("Bonus approved");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to approve bonus",
      );
    }
  };

  // ─── Filter options (derived from the unfiltered payload) ───────────

  const years = useMemo(() => {
    const set = new Set<string>();
    for (const m of groupBonusesByMonth(bonuses)) {
      if (m.key !== UNDATED_KEY) set.add(m.key.slice(0, 4));
    }
    return [...set].sort().reverse();
  }, [bonuses]);

  const members = useMemo(
    () =>
      aggregateByMember(bonuses).map((m) => ({
        key: m.memberKey,
        name: m.employeeName,
      })),
    [bonuses],
  );

  // ─── Filtered aggregation ───────────────────────────────────────────

  const filtered = useMemo(
    () =>
      bonuses.filter((b) => {
        if (status !== ALL && b.status !== status) return false;
        // Year is read off the WITA month key, so the filter and the month
        // buckets always agree on rows near a month/year boundary.
        if (year !== ALL && !witaMonthKey(b.awarded_at).startsWith(year))
          return false;
        if (member !== ALL && memberKeyOf(b) !== member) return false;
        return true;
      }),
    [bonuses, status, year, member],
  );

  const months = useMemo(() => groupBonusesByMonth(filtered), [filtered]);
  const memberTotals = useMemo(() => aggregateByMember(filtered), [filtered]);

  const grandTotal = months.reduce((s, m) => s + m.total, 0);
  const grandPending = months.reduce((s, m) => s + m.pendingTotal, 0);
  const grandApproved = memberTotals.reduce(
    (s, m) => s + m.byStatus.approved,
    0,
  );

  /**
   * Pre-system PDF recap records grouped by month key, scoped to the SAME
   * selection as the ledger they are compared against — otherwise the delta
   * would subtract an all-members PDF total from a single-member ledger total
   * and read as a phantom shortfall. A status filter has no counterpart in the
   * PDF recaps (they carry no status), so it makes the two sides
   * non-comparable and suppresses the strip entirely.
   */
  const historicalRecordsByMonth = useMemo(() => {
    const map = new Map<string, BonusHistoricalRecord[]>();
    if (status !== ALL) return map;
    const scoped =
      member === ALL
        ? historical
        : historical.filter(
            (r) => r.employee_id != null && `id:${r.employee_id}` === member,
          );
    for (const r of scoped) {
      const key = `${r.bonus_year}-${String(r.bonus_month).padStart(2, "0")}`;
      const arr = map.get(key) ?? [];
      arr.push(r);
      map.set(key, arr);
    }
    return map;
  }, [historical, member, status]);

  // Newest month starts expanded, the rest collapsed — DERIVED, not set by an
  // effect: an effect would paint one frame with everything closed and only
  // then expand. An explicit toggle writes a boolean and always wins.
  const newestMonthKey = months.length > 0 ? months[0].key : null;

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-zinc-100">Bonuses</h1>
        <div className="animate-pulse space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 bg-zinc-900 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  const selectCls =
    "bg-zinc-900 border border-zinc-800 rounded-lg px-2 py-1.5 text-sm text-zinc-300";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-zinc-100">Bonuses</h1>
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Filter by year"
            value={year}
            onChange={(e) => setYear(e.target.value)}
            className={selectCls}
          >
            <option value={ALL}>All years</option>
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter by status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className={selectCls}
          >
            <option value={ALL}>All statuses</option>
            {["pending", "approved", "paid", "rejected", "reversed"].map(
              (s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ),
            )}
          </select>
          <select
            aria-label="Filter by member"
            value={member}
            onChange={(e) => setMember(e.target.value)}
            className={selectCls}
          >
            <option value={ALL}>All members</option>
            {members.map((m) => (
              <option key={m.key} value={m.key}>
                {m.name}
              </option>
            ))}
          </select>
          <button
            onClick={() =>
              downloadCsv(
                `bali-zero-bonuses-${year === ALL ? "all" : year}.csv`,
                bonusesToCsv(months),
              )
            }
            disabled={months.length === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 text-zinc-300 hover:bg-zinc-700 text-sm transition-colors disabled:opacity-40"
          >
            <Download size={14} />
            CSV
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Total", value: formatIDR(grandTotal) },
          { label: "Pending", value: formatIDR(grandPending) },
          { label: "Months", value: String(months.length) },
          { label: "Bonuses", value: String(filtered.length) },
        ].map((kpi) => (
          <div
            key={kpi.label}
            className="bg-zinc-900 border border-zinc-800 rounded-xl p-3"
          >
            <div className="text-xs uppercase tracking-wide text-zinc-500">
              {kpi.label}
            </div>
            <div className="text-lg font-semibold text-zinc-100 mt-0.5">
              {kpi.value}
            </div>
          </div>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center text-zinc-500">
          <Gift size={20} className="mx-auto mb-2 opacity-50" />
          No bonuses for this selection. Bonuses are created automatically when
          practices are completed.
        </div>
      ) : (
        <>
          {/* ─── Total per member, across the selected months ─────────── */}
          <section className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-zinc-800">
              <h2 className="text-sm font-semibold text-zinc-200">
                Total per member
              </h2>
              <p className="text-xs text-zinc-500 mt-0.5">
                Across every month in the current selection.
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs uppercase tracking-wide text-zinc-500">
                    <th className="text-left font-medium px-4 py-2">Member</th>
                    <th className="text-right font-medium px-4 py-2">Months</th>
                    <th className="text-right font-medium px-4 py-2">
                      Bonuses
                    </th>
                    <th className="text-right font-medium px-4 py-2">
                      Pending
                    </th>
                    <th className="text-right font-medium px-4 py-2">
                      Approved
                    </th>
                    <th className="text-right font-medium px-4 py-2">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {memberTotals.map((m) => (
                    <tr
                      key={m.memberKey}
                      className="border-t border-zinc-800/70 text-zinc-300"
                    >
                      <td className="px-4 py-2 text-zinc-200">
                        {m.employeeName}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {m.monthCount}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {m.count}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-amber-400">
                        {m.byStatus.pending
                          ? formatIDR(m.byStatus.pending)
                          : "—"}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {m.byStatus.approved
                          ? formatIDR(m.byStatus.approved)
                          : "—"}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums font-semibold text-[var(--bz-accent)]">
                        {formatIDR(m.total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-zinc-700 text-zinc-200 font-semibold">
                    <td className="px-4 py-2">All members</td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {months.length}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {filtered.length}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-amber-400">
                      {grandPending ? formatIDR(grandPending) : "—"}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {formatIDR(grandApproved)}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-[var(--bz-accent)]">
                      {formatIDR(grandTotal)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </section>

          {/* ─── Month by month → member by member ────────────────────── */}
          <div className="space-y-3">
            {months.map((month) => {
              const isOpen =
                openMonths[month.key] ?? month.key === newestMonthKey;
              const recon = reconcileMonthHistorical(
                month,
                historicalRecordsByMonth.get(month.key) ?? [],
              );
              return (
                <section
                  key={month.key || "undated"}
                  className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden"
                >
                  <button
                    onClick={() =>
                      setOpenMonths((p) => ({ ...p, [month.key]: !isOpen }))
                    }
                    aria-expanded={isOpen}
                    className="w-full flex items-center justify-between gap-3 px-4 py-3 hover:bg-zinc-800/40 transition-colors text-left"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      {isOpen ? (
                        <ChevronDown
                          size={16}
                          className="text-zinc-500 shrink-0"
                        />
                      ) : (
                        <ChevronRight
                          size={16}
                          className="text-zinc-500 shrink-0"
                        />
                      )}
                      <span className="font-semibold text-zinc-100">
                        {month.label}
                      </span>
                      <span className="text-xs text-zinc-500 truncate">
                        {month.memberCount} member
                        {month.memberCount === 1 ? "" : "s"} · {month.count}{" "}
                        bonus
                        {month.count === 1 ? "" : "es"}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      {month.pendingTotal > 0 && (
                        <span className="text-xs px-2 py-0.5 rounded-full border bg-amber-500/10 text-amber-400 border-amber-500/30">
                          {formatIDR(month.pendingTotal)} pending
                        </span>
                      )}
                      <span className="text-base font-semibold text-[var(--bz-accent)] tabular-nums">
                        {formatIDR(month.total)}
                      </span>
                    </div>
                  </button>

                  {isOpen && (
                    <div className="border-t border-zinc-800">
                      {recon &&
                        (recon.ledgerAuthoritative ? (
                          <div className="flex items-start gap-2 px-4 py-2.5 bg-zinc-500/5 border-b border-zinc-700/40 text-xs text-zinc-400">
                            <AlertTriangle
                              size={14}
                              className="mt-0.5 shrink-0"
                            />
                            <span>
                              A pre-system PDF recap exists for this month (
                              <strong className="tabular-nums">
                                {formatIDR(recon.pdfTotal)}
                              </strong>
                              , {recon.pdfTasks} tasks —{" "}
                              {recon.sources.join(", ")}). The{" "}
                              <strong>ledger is authoritative</strong> here; the
                              recap is a historical snapshot shown for
                              reference, <strong>not summed</strong> into the
                              totals above (delta{" "}
                              <span className="tabular-nums">
                                {formatIDR(month.total - recon.pdfTotal)}
                              </span>
                              ).
                            </span>
                          </div>
                        ) : (
                          <div className="flex items-start gap-2 px-4 py-2.5 bg-amber-500/10 border-b border-amber-500/30 text-xs text-amber-200/90">
                            <AlertTriangle
                              size={14}
                              className="mt-0.5 shrink-0"
                            />
                            <span>
                              <strong>Ledger incomplete for this month.</strong>{" "}
                              {recon.missingPaidMembers} member
                              {recon.missingPaidMembers === 1 ? "" : "s"} the
                              PDF paid have no ledger rows — the pre-system PDF
                              list (
                              <strong className="tabular-nums">
                                {formatIDR(recon.pdfTotal)}
                              </strong>
                              , {recon.pdfTasks} tasks —{" "}
                              {recon.sources.join(", ")}) is the{" "}
                              <strong>authoritative record</strong>. The ledger
                              figures above (
                              <span className="tabular-nums">
                                {formatIDR(recon.ledgerTotal)}
                              </span>
                              ) are a partial backfill —{" "}
                              <strong>use the PDF total for this month</strong>{" "}
                              until the ledger is backfilled. Not summed.
                            </span>
                          </div>
                        ))}

                      {month.members.map((m) => {
                        const mKey = `${month.key}|${m.memberKey}`;
                        const mOpen = openMembers[mKey] ?? false;
                        return (
                          <div
                            key={m.memberKey}
                            className="border-b border-zinc-800/70 last:border-b-0"
                          >
                            <button
                              onClick={() =>
                                setOpenMembers((p) => ({
                                  ...p,
                                  [mKey]: !mOpen,
                                }))
                              }
                              aria-expanded={mOpen}
                              className="w-full flex items-center justify-between gap-3 px-4 py-2.5 pl-9 hover:bg-zinc-800/30 transition-colors text-left"
                            >
                              <div className="flex items-center gap-2 min-w-0">
                                {mOpen ? (
                                  <ChevronDown
                                    size={14}
                                    className="text-zinc-600 shrink-0"
                                  />
                                ) : (
                                  <ChevronRight
                                    size={14}
                                    className="text-zinc-600 shrink-0"
                                  />
                                )}
                                <span className="text-zinc-200 truncate">
                                  {m.employeeName}
                                </span>
                                <span className="text-xs text-zinc-500">
                                  {m.count} bonus{m.count === 1 ? "" : "es"}
                                </span>
                              </div>
                              <div className="flex items-center gap-3 shrink-0 text-sm">
                                {m.byStatus.pending > 0 && (
                                  <span className="text-xs text-amber-400 tabular-nums">
                                    {formatIDR(m.byStatus.pending)} pending
                                  </span>
                                )}
                                <span className="font-semibold text-zinc-100 tabular-nums">
                                  {formatIDR(m.total)}
                                </span>
                              </div>
                            </button>

                            {mOpen && (
                              <ul className="bg-zinc-950/40">
                                {m.bonuses.map((bonus) => (
                                  <li
                                    key={bonus.id}
                                    className="flex items-center justify-between gap-3 px-4 py-2 pl-14 border-t border-zinc-800/50"
                                  >
                                    <div className="min-w-0">
                                      <div className="flex items-center gap-2">
                                        <span className="text-sm text-zinc-300">
                                          {bonus.practice_type_code?.replace(
                                            /_/g,
                                            " ",
                                          )}
                                        </span>
                                        <span
                                          className={`text-[10px] px-1.5 py-0.5 rounded-full border ${statusColors[bonus.status] || ""}`}
                                        >
                                          {bonus.status}
                                        </span>
                                      </div>
                                      <div className="text-xs text-zinc-500 mt-0.5 truncate">
                                        {formatBonusDate(bonus.awarded_at)}
                                        {bonus.client_name &&
                                          ` — ${bonus.client_name}`}
                                      </div>
                                    </div>
                                    <div className="flex items-center gap-3 shrink-0">
                                      <span className="text-sm text-zinc-200 tabular-nums">
                                        {formatIDR(
                                          Number(bonus.amount_idr) || 0,
                                        )}
                                      </span>
                                      {bonus.status === "pending" && (
                                        <button
                                          onClick={() =>
                                            handleApprove(bonus.id)
                                          }
                                          className="flex items-center gap-1 px-2 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 text-xs transition-colors"
                                        >
                                          <CheckCircle size={12} />
                                          Approve
                                        </button>
                                      )}
                                    </div>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </section>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
