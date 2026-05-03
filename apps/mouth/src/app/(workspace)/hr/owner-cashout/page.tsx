"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import {
  Banknote,
  ChevronRight,
  Lock,
  TrendingUp,
  Users as UsersIcon,
} from "lucide-react";

const MarginTrendChart = dynamic(
  () =>
    import("@/components/hr/OwnerCashoutCharts").then(
      (m) => m.MarginTrendChart,
    ),
  {
    ssr: false,
    loading: () => (
      <div
        className="h-full w-full animate-pulse rounded bg-zinc-800/50"
        aria-hidden="true"
      />
    ),
  },
);
const TopVisaChart = dynamic(
  () =>
    import("@/components/hr/OwnerCashoutCharts").then((m) => m.TopVisaChart),
  {
    ssr: false,
    loading: () => (
      <div
        className="h-full w-full animate-pulse rounded bg-zinc-800/50"
        aria-hidden="true"
      />
    ),
  },
);

import * as api from "@/lib/api/hr/owner-cashout";
import type {
  OwnerCashoutOverview,
  OwnerCashoutVisaType,
  OwnerCashoutWeek,
} from "@/types/owner-cashout";
import { OwnerCashoutRefreshButton } from "@/components/hr/OwnerCashoutRefreshButton";

function formatIDR(v: number): string {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(v);
}

function formatShort(v: number): string {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return String(v);
}

function KpiCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <div className="text-xs text-zinc-400 mb-1">{label}</div>
      <div className="text-2xl font-bold text-zinc-100">{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-1">{sub}</div>}
    </div>
  );
}

export default function OwnerCashoutPage() {
  const [overview, setOverview] = useState<OwnerCashoutOverview | null>(null);
  const [weeks, setWeeks] = useState<OwnerCashoutWeek[]>([]);
  const [visa, setVisa] = useState<OwnerCashoutVisaType[]>([]);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ov, wk, vt, st] = await Promise.all([
        api.getOverview(),
        api.listWeeks(),
        api.getVisaTypes(),
        api.getSyncStatus(),
      ]);
      setOverview(ov);
      setWeeks(wk.weeks);
      setVisa(vt.top);
      setLastSync(
        st.last_sync
          ? `${st.last_sync.status} · ${new Date(st.last_sync.started_at).toLocaleString("en-GB")}`
          : "never",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !overview) {
    return (
      <div className="space-y-6">
        <div className="h-8 bg-zinc-800 rounded w-64 animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 h-28 animate-pulse"
            />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-800 rounded-xl p-6 text-red-400">
        <h2 className="font-semibold mb-2">Error</h2>
        <p>{error}</p>
      </div>
    );
  }

  if (!overview) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100 flex items-center gap-2">
            <Lock size={20} className="text-amber-400" />
            Owner Cashout
          </h1>
          <div className="text-xs text-zinc-500 mt-1">
            Last sync: {lastSync}
          </div>
        </div>
        <OwnerCashoutRefreshButton onRefreshed={load} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Margin BZ Total"
          value={formatIDR(overview.kpi.margin_bz_total_idr)}
          sub={`${overview.total_weeks} weeks`}
        />
        <KpiCard
          label="Margin BZ Last Week"
          value={formatIDR(overview.kpi.margin_bz_last_week_idr)}
          sub={`${overview.kpi.practices_last_week} practices`}
        />
        <KpiCard
          label="Margin BS Total"
          value={formatIDR(overview.kpi.margin_bs_total_idr)}
        />
        <KpiCard
          label="Total Practices"
          value={String(overview.kpi.practices_total)}
        />
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp size={16} className="text-emerald-400" />
          <h2 className="text-sm font-semibold text-zinc-200">
            Margin trend (weekly)
          </h2>
        </div>
        <div style={{ width: "100%", height: 260 }}>
          <MarginTrendChart data={overview.trend} />
        </div>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Banknote size={16} className="text-emerald-400" />
          <h2 className="text-sm font-semibold text-zinc-200">
            Top visa types by MBZ
          </h2>
        </div>
        <div style={{ width: "100%", height: 260 }}>
          <TopVisaChart data={visa} />
        </div>
      </div>

      <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="flex items-center gap-2 p-5 border-b border-zinc-800">
          <UsersIcon size={16} className="text-emerald-400" />
          <h2 className="text-sm font-semibold text-zinc-200">
            Weekly breakdown
          </h2>
        </div>
        <table className="w-full text-sm">
          <thead className="text-xs text-zinc-500 uppercase border-b border-zinc-800">
            <tr>
              <th className="text-left px-4 py-3">Week</th>
              <th className="text-right px-4 py-3">Practices</th>
              <th className="text-right px-4 py-3">Total income</th>
              <th className="text-right px-4 py-3">Margin BZ</th>
              <th className="text-right px-4 py-3">Margin BS</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody className="text-zinc-300">
            {weeks.map((w) => (
              <tr
                key={w.id}
                className="border-b border-zinc-800 hover:bg-zinc-800/40"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/hr/owner-cashout/${w.id}`}
                    className="hover:text-emerald-400"
                  >
                    {new Date(w.week_start).toLocaleDateString("en-GB", {
                      day: "2-digit",
                      month: "short",
                      year: "numeric",
                    })}
                  </Link>
                </td>
                <td className="text-right px-4 py-3">{w.total_practices}</td>
                <td className="text-right px-4 py-3">
                  {formatIDR(w.total_income_idr)}
                </td>
                <td className="text-right px-4 py-3 text-emerald-400">
                  {formatIDR(w.total_margin_bz_idr)}
                </td>
                <td className="text-right px-4 py-3 text-amber-400">
                  {formatIDR(w.total_margin_bs_idr)}
                </td>
                <td className="px-4 py-3 text-zinc-600">
                  <Link href={`/hr/owner-cashout/${w.id}`}>
                    <ChevronRight size={16} />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
