"use client";

import { useEffect, useState } from "react";
import {
  getMyCommissions,
  type PartnerCommission,
  type CommissionStatus,
} from "@/lib/api/partners/partners";

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

function fmt(n: number | undefined | null): string {
  if (n == null) return "—";
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(n);
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
  const [commissions, setCommissions] = useState<PartnerCommission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<CommissionStatus | "all">("all");

  useEffect(() => {
    getMyCommissions()
      .then((data) => setCommissions(Array.isArray(data) ? data : []))
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : String(e))
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6">Loading...</div>;
  if (error) return <div className="p-6 text-red-500">Error: {error}</div>;

  const filtered =
    activeFilter === "all"
      ? commissions
      : commissions.filter((c) => c.status === activeFilter);

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-semibold text-white">My Commissions</h1>

      {/* Status filter chips */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setActiveFilter("all")}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
            activeFilter === "all"
              ? "bg-amber-600 text-white"
              : "bg-white/10 text-gray-300 hover:bg-white/20"
          }`}
        >
          All ({commissions.length})
        </button>
        {ALL_CHIP_STATUSES.map((s) => {
          const count = commissions.filter((c) => c.status === s).length;
          return (
            <button
              key={s}
              onClick={() => setActiveFilter(s)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                activeFilter === s
                  ? "bg-amber-600 text-white"
                  : "bg-white/10 text-gray-300 hover:bg-white/20"
              }`}
            >
              {STATUS_LABELS[s] ?? s} ({count})
            </button>
          );
        })}
      </div>

      {filtered.length === 0 ? (
        <p className="text-gray-400 text-sm">No commissions match this filter.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left border border-white/10 rounded-lg">
            <thead className="bg-white/5 text-gray-400">
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
            <tbody className="divide-y divide-white/10">
              {filtered.map((c) => (
                <tr key={c.id} className="text-gray-200 hover:bg-white/5">
                  <td className="px-4 py-2">{fmtDate(c.created_at)}</td>
                  <td className="px-4 py-2">{c.practice_type_name ?? c.client_name ?? "—"}</td>
                  <td className="px-4 py-2">{fmt(c.gross_amount)}</td>
                  <td className="px-4 py-2">{fmt(c.withholding_amount)}</td>
                  <td className="px-4 py-2">{fmt(c.net_amount)}</td>
                  <td className="px-4 py-2">
                    <span className="px-2 py-0.5 rounded-full text-xs bg-white/10">
                      {STATUS_LABELS[c.status] ?? c.status}
                    </span>
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
