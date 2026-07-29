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
  buildMonthlyReconciliation,
  formatBonusDate,
  groupBonusesByMonth,
  UNDATED_KEY,
  witaMonthKey,
  type MonthAggregate,
} from "@/lib/hr/bonus-aggregation";
import { Money } from "@balizero/core";

/** Dashboard panel recipe — mirrors the day/dark-aware Kita surfaces. */
const PANEL: React.CSSProperties = {
  background: "var(--bz-card)",
  borderColor: "var(--bz-border)",
};

/** Bonus-status chip, honestly mapped to --state-* (12% tint + 30% rim). */
const statusStyles: Record<string, React.CSSProperties> = {
  pending: {
    background: "color-mix(in srgb, var(--state-warning) 12%, transparent)",
    color: "var(--state-warning)",
    borderColor: "color-mix(in srgb, var(--state-warning) 30%, transparent)",
  },
  approved: {
    background: "color-mix(in srgb, var(--state-info) 12%, transparent)",
    color: "var(--state-info)",
    borderColor: "color-mix(in srgb, var(--state-info) 30%, transparent)",
  },
  paid: {
    background: "color-mix(in srgb, var(--state-success) 12%, transparent)",
    color: "var(--state-success)",
    borderColor: "color-mix(in srgb, var(--state-success) 30%, transparent)",
  },
  rejected: {
    background: "color-mix(in srgb, var(--state-danger) 12%, transparent)",
    color: "var(--state-danger)",
    borderColor: "color-mix(in srgb, var(--state-danger) 30%, transparent)",
  },
  reversed: {
    background: "color-mix(in srgb, var(--bz-text-pure) 6%, transparent)",
    color: "var(--bz-text-2)",
    borderColor: "var(--bz-border)",
  },
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

  /**
   * The reconciliation verdict is a property of the WHOLE month, computed once
   * from the UNFILTERED ledger + PDF. It must never be recomputed from a
   * filtered slice: filtering to one member drops the very members whose
   * absence defines the incompleteness, which would flip a PDF-authoritative
   * month to "ledger authoritative" and headline the wrong (smaller) number.
   * Filters below change only what is DISPLAYED, never this verdict.
   */
  const reconByMonth = useMemo(
    () => buildMonthlyReconciliation(bonuses, historical),
    [bonuses, historical],
  );

  /** WITA month keys that have at least one ledger row in the UNFILTERED data. */
  const ledgerMonthKeys = useMemo(() => {
    const set = new Set<string>();
    for (const b of bonuses) set.add(witaMonthKey(b.awarded_at));
    return set;
  }, [bonuses]);

  // ─── Filter options (derived from the unfiltered payload) ───────────

  const years = useMemo(() => {
    const set = new Set<string>();
    for (const m of groupBonusesByMonth(bonuses)) {
      if (m.key !== UNDATED_KEY) set.add(m.key.slice(0, 4));
    }
    // Include years that exist only in the PDF recap — otherwise a PDF-only
    // month's year could show under "All years" yet not be selectable.
    for (const key of reconByMonth.keys()) set.add(key.slice(0, 4));
    return [...set].sort().reverse();
  }, [bonuses, reconByMonth]);

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

  const filtersNarrowView = status !== ALL || member !== ALL;

  /**
   * Months to render = the filtered ledger months UNION any month that has a
   * PDF verdict but NO ledger rows AT ALL (a month the ledger never captured).
   * "No ledger rows at all" is judged against the UNFILTERED ledger
   * (`ledgerMonthKeys`), never the filtered view — otherwise a real ledger
   * month that a status/member filter emptied would be mislabeled "PDF recap
   * only". A real ledger month with no rows in the current filter simply does
   * not render (a narrow filter legitimately hides it); it is never relabeled.
   * Year is a legitimate scope; status/member never hide a whole-month verdict.
   */
  const displayMonths = useMemo<MonthAggregate[]>(() => {
    const present = new Set(months.map((m) => m.key));
    const extras: MonthAggregate[] = [];
    for (const recon of reconByMonth.values()) {
      if (present.has(recon.monthKey)) continue;
      if (ledgerMonthKeys.has(recon.monthKey)) continue; // real ledger month, just filtered out
      if (year !== ALL && !recon.monthKey.startsWith(year)) continue;
      extras.push({
        key: recon.monthKey,
        label: recon.monthLabel,
        count: 0,
        memberCount: 0,
        total: 0,
        pendingTotal: 0,
        approvedTotal: 0,
        members: [],
      });
    }
    return [...months, ...extras].sort((a, b) => {
      if (a.key === UNDATED_KEY) return 1;
      if (b.key === UNDATED_KEY) return -1;
      return b.key.localeCompare(a.key);
    });
  }, [months, reconByMonth, ledgerMonthKeys, year]);

  // Newest month starts expanded, the rest collapsed — DERIVED, not set by an
  // effect: an effect would paint one frame with everything closed and only
  // then expand. An explicit toggle writes a boolean and always wins.
  const newestMonthKey = displayMonths.length > 0 ? displayMonths[0].key : null;

  if (loading) {
    return (
      <div className="space-y-4">
        <h1
          className="text-2xl font-bold"
          style={{ color: "var(--bz-text-1)" }}
        >
          Bonuses
        </h1>
        <div className="animate-pulse space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 rounded-lg" style={PANEL} />
          ))}
        </div>
      </div>
    );
  }

  const selectCls = "border rounded-lg px-2 py-1.5 text-sm";
  const selectStyle: React.CSSProperties = {
    background: "var(--bz-surface)",
    borderColor: "var(--bz-border)",
    color: "var(--bz-text-1)",
  };

  const kpis: { label: string; value: React.ReactNode }[] = [
    { label: "Total", value: <Money value={grandTotal} /> },
    { label: "Pending", value: <Money value={grandPending} /> },
    { label: "Months", value: months.length },
    { label: "Bonuses", value: filtered.length },
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1
          className="text-2xl font-bold"
          style={{ color: "var(--bz-text-1)" }}
        >
          Bonuses
        </h1>
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Filter by year"
            value={year}
            onChange={(e) => setYear(e.target.value)}
            className={selectCls}
            style={selectStyle}
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
            style={selectStyle}
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
            style={selectStyle}
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
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--bz-surface)] text-[var(--bz-text-1)] hover:bg-[var(--surface-raised)] text-sm transition-colors disabled:opacity-40"
          >
            <Download size={14} />
            CSV
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {kpis.map((kpi) => (
          <div key={kpi.label} className="border rounded-xl p-3" style={PANEL}>
            <div
              className="text-xs uppercase tracking-wide"
              style={{ color: "var(--bz-text-2)" }}
            >
              {kpi.label}
            </div>
            <div
              className="text-lg font-semibold mt-0.5"
              style={{ color: "var(--bz-text-1)" }}
            >
              {kpi.value}
            </div>
          </div>
        ))}
      </div>

      {displayMonths.length === 0 ? (
        <div
          className="border rounded-xl p-8 text-center"
          style={{ ...PANEL, color: "var(--bz-text-2)" }}
        >
          <Gift size={20} className="mx-auto mb-2 opacity-50" />
          No bonuses for this selection. Bonuses are created automatically when
          practices are completed.
        </div>
      ) : (
        <>
          {/* ─── Total per member, across the selected months ─────────── */}
          {memberTotals.length > 0 && (
            <section
              className="border rounded-xl overflow-hidden"
              style={PANEL}
            >
              <div
                className="px-4 py-3 border-b"
                style={{ borderColor: "var(--bz-border)" }}
              >
                <h2
                  className="text-sm font-semibold"
                  style={{ color: "var(--bz-text-1)" }}
                >
                  Total per member
                </h2>
                <p
                  className="text-xs mt-0.5"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  Across every month in the current selection.
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr
                      className="text-xs uppercase tracking-wide"
                      style={{ color: "var(--bz-text-2)" }}
                    >
                      <th className="text-left font-medium px-4 py-2">
                        Member
                      </th>
                      <th className="text-right font-medium px-4 py-2">
                        Months
                      </th>
                      <th className="text-right font-medium px-4 py-2">
                        Bonuses
                      </th>
                      <th className="text-right font-medium px-4 py-2">
                        Pending
                      </th>
                      <th className="text-right font-medium px-4 py-2">
                        Approved
                      </th>
                      <th className="text-right font-medium px-4 py-2">
                        Total
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {memberTotals.map((m) => (
                      <tr
                        key={m.memberKey}
                        className="border-t"
                        style={{
                          borderColor:
                            "color-mix(in srgb, var(--bz-border) 70%, transparent)",
                          color: "var(--bz-text-1)",
                        }}
                      >
                        <td
                          className="px-4 py-2"
                          style={{ color: "var(--bz-text-1)" }}
                        >
                          {m.employeeName}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums">
                          {m.monthCount}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums">
                          {m.count}
                        </td>
                        <td className="px-4 py-2 text-right">
                          {m.byStatus.pending ? (
                            <Money
                              value={m.byStatus.pending}
                              style={{ color: "var(--state-warning)" }}
                            />
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="px-4 py-2 text-right">
                          {m.byStatus.approved ? (
                            <Money value={m.byStatus.approved} />
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="px-4 py-2 text-right font-semibold">
                          <Money
                            value={m.total}
                            style={{ color: "var(--bz-accent)" }}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr
                      className="border-t font-semibold"
                      style={{
                        borderColor: "var(--bz-border-hover)",
                        color: "var(--bz-text-1)",
                      }}
                    >
                      <td className="px-4 py-2">All members</td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {months.length}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {filtered.length}
                      </td>
                      <td className="px-4 py-2 text-right">
                        {grandPending ? (
                          <Money
                            value={grandPending}
                            style={{ color: "var(--state-warning)" }}
                          />
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <Money value={grandApproved} />
                      </td>
                      <td className="px-4 py-2 text-right">
                        <Money
                          value={grandTotal}
                          style={{ color: "var(--bz-accent)" }}
                        />
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </section>
          )}

          {/* ─── Month by month → member by member ────────────────────── */}
          <div className="space-y-3">
            {displayMonths.map((month) => {
              const isOpen =
                openMonths[month.key] ?? month.key === newestMonthKey;
              // Global, filter-independent verdict for the whole month.
              const recon = reconByMonth.get(month.key) ?? null;
              // "PDF only" = the ledger never captured this month at all (judged
              // on the UNFILTERED ledger), NOT merely "no rows in this filter".
              const pdfOnly = recon != null && !ledgerMonthKeys.has(month.key);
              return (
                <section
                  key={month.key || "undated"}
                  className="border rounded-xl overflow-hidden"
                  style={PANEL}
                >
                  <button
                    onClick={() =>
                      setOpenMonths((p) => ({ ...p, [month.key]: !isOpen }))
                    }
                    aria-expanded={isOpen}
                    className="w-full flex items-center justify-between gap-3 px-4 py-3 hover:bg-[var(--surface-raised)] transition-colors text-left"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      {isOpen ? (
                        <ChevronDown
                          size={16}
                          className="shrink-0"
                          style={{ color: "var(--bz-text-2)" }}
                        />
                      ) : (
                        <ChevronRight
                          size={16}
                          className="shrink-0"
                          style={{ color: "var(--bz-text-2)" }}
                        />
                      )}
                      <span
                        className="font-semibold"
                        style={{ color: "var(--bz-text-1)" }}
                      >
                        {month.label}
                      </span>
                      <span
                        className="text-xs truncate"
                        style={{ color: "var(--bz-text-2)" }}
                      >
                        {pdfOnly ? (
                          "PDF recap only — not yet in the ledger"
                        ) : (
                          <>
                            {month.memberCount} member
                            {month.memberCount === 1 ? "" : "s"} · {month.count}{" "}
                            bonus
                            {month.count === 1 ? "" : "es"}
                          </>
                        )}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      {month.pendingTotal > 0 && (
                        <span className="text-xs px-2 py-0.5 rounded-full border bg-[color-mix(in_srgb,var(--state-warning)_12%,transparent)] text-[var(--state-warning)] border-[color-mix(in_srgb,var(--state-warning)_30%,transparent)]">
                          <Money value={month.pendingTotal} /> pending
                        </span>
                      )}
                      {pdfOnly && recon && !recon.pdfTotalReliable ? (
                        // A PDF-only month with an unreadable amount headlines
                        // "—", NOT the understated total — showing it would
                        // contradict the strip and imply a wrong pay figure.
                        <span
                          className="text-base font-semibold"
                          style={{ color: "var(--bz-accent)" }}
                        >
                          —
                        </span>
                      ) : (
                        <Money
                          value={
                            pdfOnly && recon ? recon.pdfTotal : month.total
                          }
                          className="text-base font-semibold"
                          style={{ color: "var(--bz-accent)" }}
                        />
                      )}
                    </div>
                  </button>

                  {isOpen && (
                    <div
                      className="border-t"
                      style={{ borderColor: "var(--bz-border)" }}
                    >
                      {recon &&
                        (recon.ledgerAuthoritative ? (
                          <div
                            className="flex items-start gap-2 px-4 py-2.5 border-b text-xs"
                            style={{
                              background: "var(--bz-glass-rim)",
                              borderColor:
                                "color-mix(in srgb, var(--bz-border) 70%, transparent)",
                              color: "var(--bz-text-2)",
                            }}
                          >
                            <AlertTriangle
                              size={14}
                              className="mt-0.5 shrink-0"
                            />
                            <span>
                              No PDF-only paid members detected for this month,
                              so per the ruling the{" "}
                              <strong>ledger is authoritative</strong>. A
                              pre-system PDF recap (
                              <strong className="tabular-nums">
                                <Money value={recon.pdfTotal} />
                              </strong>
                              , {recon.pdfTasks} tasks —{" "}
                              {recon.sources.join(", ")}) is shown for
                              reference, <strong>not summed</strong>{" "}
                              (whole-month ledger{" "}
                              <Money value={recon.ledgerTotal} />, delta{" "}
                              <Money
                                value={recon.ledgerTotal - recon.pdfTotal}
                              />
                              ).
                              {filtersNarrowView && (
                                <>
                                  {" "}
                                  This verdict is for the whole month; the rows
                                  below are filtered.
                                </>
                              )}
                            </span>
                          </div>
                        ) : (
                          <div
                            className="flex items-start gap-2 px-4 py-2.5 border-b text-xs"
                            style={{
                              background:
                                "color-mix(in srgb, var(--state-warning) 10%, transparent)",
                              borderColor:
                                "color-mix(in srgb, var(--state-warning) 30%, transparent)",
                              color:
                                "color-mix(in srgb, var(--state-warning) 40%, var(--bz-text-pure))",
                            }}
                          >
                            <AlertTriangle
                              size={14}
                              className="mt-0.5 shrink-0"
                            />
                            <span>
                              <strong>Ledger incomplete for this month.</strong>{" "}
                              {recon.missingPaidMembers > 0 && (
                                <>
                                  {recon.missingPaidMembers} member
                                  {recon.missingPaidMembers === 1
                                    ? ""
                                    : "s"}{" "}
                                  the PDF paid{" "}
                                  {recon.missingPaidMembers === 1
                                    ? "has"
                                    : "have"}{" "}
                                  no ledger rows.{" "}
                                </>
                              )}
                              {recon.unresolvedPaidRecords > 0 && (
                                <>
                                  {recon.unresolvedPaidRecords} PDF payment
                                  {recon.unresolvedPaidRecords === 1
                                    ? ""
                                    : "s"}{" "}
                                  could not be matched to a member — verify
                                  manually.{" "}
                                </>
                              )}
                              {recon.pdfTotalReliable ? (
                                <>
                                  The pre-system PDF list (
                                  <strong className="tabular-nums">
                                    <Money value={recon.pdfTotal} />
                                  </strong>
                                  , {recon.pdfTasks} tasks —{" "}
                                  {recon.sources.join(", ")}) is the{" "}
                                  <strong>authoritative record</strong>; the
                                  ledger (
                                  <Money value={recon.ledgerTotal} />) is a
                                  partial backfill —{" "}
                                  <strong>
                                    use the PDF total for this month
                                  </strong>{" "}
                                  until the ledger is backfilled. Not summed.
                                </>
                              ) : (
                                <>
                                  The pre-system PDF list (
                                  {recon.sources.join(", ")}) is the{" "}
                                  <strong>authoritative record</strong>, but at
                                  least one PDF amount could not be read, so{" "}
                                  <strong>
                                    the PDF total shown is incomplete
                                  </strong>{" "}
                                  — do not pay from it;{" "}
                                  <strong>
                                    verify the source PDF manually
                                  </strong>
                                  .
                                </>
                              )}
                              {filtersNarrowView && (
                                <>
                                  {" "}
                                  This verdict is for the whole month; the rows
                                  below are filtered.
                                </>
                              )}
                            </span>
                          </div>
                        ))}

                      {month.members.map((m) => {
                        const mKey = `${month.key}|${m.memberKey}`;
                        const mOpen = openMembers[mKey] ?? false;
                        return (
                          <div
                            key={m.memberKey}
                            className="border-b last:border-b-0"
                            style={{
                              borderColor:
                                "color-mix(in srgb, var(--bz-border) 70%, transparent)",
                            }}
                          >
                            <button
                              onClick={() =>
                                setOpenMembers((p) => ({
                                  ...p,
                                  [mKey]: !mOpen,
                                }))
                              }
                              aria-expanded={mOpen}
                              className="w-full flex items-center justify-between gap-3 px-4 py-2.5 pl-9 hover:bg-[var(--surface-raised)] transition-colors text-left"
                            >
                              <div className="flex items-center gap-2 min-w-0">
                                {mOpen ? (
                                  <ChevronDown
                                    size={14}
                                    className="shrink-0"
                                    style={{ color: "var(--bz-text-3)" }}
                                  />
                                ) : (
                                  <ChevronRight
                                    size={14}
                                    className="shrink-0"
                                    style={{ color: "var(--bz-text-3)" }}
                                  />
                                )}
                                <span
                                  className="truncate"
                                  style={{ color: "var(--bz-text-1)" }}
                                >
                                  {m.employeeName}
                                </span>
                                <span
                                  className="text-xs"
                                  style={{ color: "var(--bz-text-2)" }}
                                >
                                  {m.count} bonus{m.count === 1 ? "" : "es"}
                                </span>
                              </div>
                              <div className="flex items-center gap-3 shrink-0 text-sm">
                                {m.byStatus.pending > 0 && (
                                  <span className="text-xs">
                                    <Money
                                      value={m.byStatus.pending}
                                      style={{ color: "var(--state-warning)" }}
                                    />{" "}
                                    <span
                                      style={{ color: "var(--state-warning)" }}
                                    >
                                      pending
                                    </span>
                                  </span>
                                )}
                                <Money
                                  value={m.total}
                                  className="font-semibold"
                                  style={{ color: "var(--bz-text-1)" }}
                                />
                              </div>
                            </button>

                            {mOpen && (
                              <ul
                                style={{
                                  background:
                                    "color-mix(in srgb, var(--surface-deep) 40%, transparent)",
                                }}
                              >
                                {m.bonuses.map((bonus) => (
                                  <li
                                    key={bonus.id}
                                    className="flex items-center justify-between gap-3 px-4 py-2 pl-14 border-t"
                                    style={{
                                      borderColor:
                                        "color-mix(in srgb, var(--bz-border) 50%, transparent)",
                                    }}
                                  >
                                    <div className="min-w-0">
                                      <div className="flex items-center gap-2">
                                        <span
                                          className="text-sm"
                                          style={{ color: "var(--bz-text-1)" }}
                                        >
                                          {bonus.practice_type_code?.replace(
                                            /_/g,
                                            " ",
                                          )}
                                        </span>
                                        <span
                                          className="text-[10px] px-1.5 py-0.5 rounded-full border"
                                          style={
                                            statusStyles[bonus.status] ??
                                            statusStyles.reversed
                                          }
                                        >
                                          {bonus.status}
                                        </span>
                                      </div>
                                      <div
                                        className="text-xs mt-0.5 truncate"
                                        style={{ color: "var(--bz-text-2)" }}
                                      >
                                        {formatBonusDate(bonus.awarded_at)}
                                        {bonus.client_name &&
                                          ` — ${bonus.client_name}`}
                                      </div>
                                    </div>
                                    <div className="flex items-center gap-3 shrink-0">
                                      <Money
                                        value={Number(bonus.amount_idr) || 0}
                                        className="text-sm"
                                        style={{ color: "var(--bz-text-1)" }}
                                      />
                                      {bonus.status === "pending" && (
                                        <button
                                          onClick={() =>
                                            handleApprove(bonus.id)
                                          }
                                          className="flex items-center gap-1 px-2 py-1 rounded-lg bg-[color-mix(in_srgb,var(--state-success)_12%,transparent)] text-[var(--state-success)] hover:bg-[color-mix(in_srgb,var(--state-success)_20%,transparent)] text-xs transition-colors"
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
