"use client";

/**
 * Partner Commissions — full commission ledger with status filters.
 *
 * WS3 final slice (GARUDA Day Edition, 2026-07-26): day-theme token
 * alignment. Masthead = copper rule + serif (--font-serif) in --tx-pure;
 * filter chips: active = darker copper step --bz-copper-text with
 * theme-aware --bz-on-warm fg (5.70:1 light; 6.74:1 dark — the base
 * copper step with white would be 4.37:1, below the 4.5:1 floor);
 * inactive = --bz-card hairline.
 * Status cells render the shared StatusBadge on --state-* AA tokens
 * (was bg-white/10 neutral pill for every state). No hardcoded hexes.
 */

import { useCallback, useEffect, useState } from "react";
import { formatIDR } from "@balizero/core/utils";
import { StatusBadge } from "@/components/portal/StatusBadge";
import {
  getMyCommissions,
  type PartnerSelfCommission,
  type CommissionStatus,
} from "@/lib/api/partners/partners";
import { PartnerLoadError } from "../PartnerLoadError";

const STATUS_LABELS: Record<string, string> = {
  accrued: "Accrued",
  approved: "Approved",
  paid: "Paid",
  clawback_pending: "Clawback Pending",
  pending_approval: "Pending Approval",
  ready_to_pay: "Ready to Pay",
  offset_applied: "Offset Applied",
  waived: "Waived",
  repaid: "Repaid",
  clawed_back: "Clawed Back",
};

const ALL_CHIP_STATUSES: CommissionStatus[] = [
  "accrued",
  "approved",
  "paid",
  "clawback_pending",
  "pending_approval",
];

// Active chip: darker copper step + theme-aware on-warm fg (AA both themes,
// see header comment). Was bg-amber-600 + text-white.
const CHIP_ACTIVE_STYLE = {
  background: "var(--bz-copper-text)",
  color: "var(--bz-on-warm)",
} as const;

// Inactive chip: white card + hairline + secondary text. Was
// bg-white/10 + text-gray-300 + hover:bg-white/20.
const CHIP_IDLE_STYLE = {
  background: "var(--bz-card)",
  borderColor: "var(--bz-border)",
  color: "var(--tx-secondary)",
} as const;

function fmt(n: number | undefined | null): string {
  if (n == null) return "—";
  return formatIDR(n);
}

function fmtDate(s: string | undefined | null): string {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("id-ID", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function PartnerCommissionsPage() {
  const [commissions, setCommissions] = useState<PartnerSelfCommission[]>([]);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [activeFilter, setActiveFilter] = useState<CommissionStatus | "all">(
    "all",
  );

  const load = useCallback(async () => {
    setLoading(true);
    setUnavailable(false);
    try {
      const data = await getMyCommissions();
      if (!Array.isArray(data)) throw new Error("Invalid commissions response");
      setCommissions(data);
    } catch {
      setCommissions([]);
      setUnavailable(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading)
    return <div className="p-6 text-[var(--tx-secondary)]">Loading...</div>;
  if (unavailable)
    return (
      <PartnerLoadError
        title="Commissions are temporarily unavailable"
        onRetry={load}
      />
    );

  const filtered =
    activeFilter === "all"
      ? commissions
      : commissions.filter((c) => c.status === activeFilter);

  const chipStyle = (active: boolean) =>
    active ? CHIP_ACTIVE_STYLE : CHIP_IDLE_STYLE;

  return (
    <div className="p-6 space-y-6">
      {/* Day masthead: copper rule + Cormorant serif headline per concept */}
      <section>
        <div
          aria-hidden="true"
          className="w-14 h-[3px] rounded-sm mb-4 bg-[var(--bz-copper)]"
        />
        <h1
          className="text-2xl font-semibold tracking-tight text-[var(--tx-pure)]"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          My Commissions
        </h1>
      </section>

      {/* Status filter chips */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setActiveFilter("all")}
          className="px-3 py-1 rounded-full text-xs font-medium border transition-colors"
          style={chipStyle(activeFilter === "all")}
        >
          All ({commissions.length})
        </button>
        {ALL_CHIP_STATUSES.map((s) => {
          const count = commissions.filter((c) => c.status === s).length;
          return (
            <button
              key={s}
              onClick={() => setActiveFilter(s)}
              className="px-3 py-1 rounded-full text-xs font-medium border transition-colors"
              style={chipStyle(activeFilter === s)}
            >
              {STATUS_LABELS[s] ?? s} ({count})
            </button>
          );
        })}
      </div>

      {filtered.length === 0 ? (
        <p className="text-[var(--tx-secondary)] text-sm">
          No commissions match this filter.
        </p>
      ) : (
        <div
          className="overflow-x-auto rounded-xl border"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
            boxShadow: "0 14px 34px rgba(22, 33, 58, 0.07)",
          }}
        >
          <table className="w-full text-sm text-left">
            <thead className="text-[var(--tx-secondary)]">
              <tr>
                <th className="px-4 py-2">Accrued At</th>
                <th className="px-4 py-2">Process</th>
                <th className="px-4 py-2">Gross (IDR)</th>
                <th className="px-4 py-2">Withholding (IDR)</th>
                <th className="px-4 py-2">Net (IDR)</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Paid At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--bz-border)]">
              {filtered.map((c) => (
                <tr
                  key={c.id}
                  className="text-[var(--tx-primary)] hover:bg-[var(--bz-card-hover)]"
                >
                  <td className="px-4 py-2">{fmtDate(c.created_at)}</td>
                  <td className="px-4 py-2">
                    {c.practice_type_name ?? c.client_name ?? "—"}
                  </td>
                  <td className="px-4 py-2">{fmt(c.gross_amount_idr)}</td>
                  <td className="px-4 py-2">{fmt(c.withholding_amount_idr)}</td>
                  <td className="px-4 py-2">{fmt(c.net_amount_idr)}</td>
                  <td className="px-4 py-2">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-4 py-2">{fmtDate(c.paid_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
