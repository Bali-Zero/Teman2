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
        className="h-full w-full animate-pulse rounded bg-[var(--bz-glass-rim)]"
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
        className="h-full w-full animate-pulse rounded bg-[var(--bz-glass-rim)]"
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
import { Money } from "@balizero/core";

function formatShort(v: number): string {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return String(v);
}

/** Dashboard panel recipe — mirrors the operative-dark kita surfaces. */
const PANEL: React.CSSProperties = {
  background: "rgba(35,35,40,0.65)",
  borderColor: "var(--bz-border)",
};

function KpiCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
}) {
  return (
    <div className="border rounded-xl p-5" style={PANEL}>
      <div className="text-xs text-[var(--bz-text-2)] mb-1">{label}</div>
      <div className="text-2xl font-bold text-[var(--bz-text-1)]">{value}</div>
      {sub && <div className="text-xs text-[var(--bz-text-3)] mt-1">{sub}</div>}
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
        <div className="h-8 bg-[var(--bz-glass-rim)] rounded w-64 animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="border rounded-xl p-5 h-28 animate-pulse"
              style={PANEL}
            />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-[var(--state-danger)]/10 border border-[var(--state-danger)]/30 rounded-xl p-6 text-[var(--state-danger)]">
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
          <h1 className="text-2xl font-bold text-[var(--bz-text-1)] flex items-center gap-2">
            <Lock size={20} className="text-[var(--bz-accent)]" />
            Owner Cashout
          </h1>
          <div className="text-xs text-[var(--bz-text-3)] mt-1">
            Last sync: {lastSync}
          </div>
        </div>
        <OwnerCashoutRefreshButton onRefreshed={load} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Margin BZ Total"
          value={<Money value={overview.kpi.margin_bz_total_idr} />}
          sub={`${overview.total_weeks} weeks`}
        />
        <KpiCard
          label="Margin BZ Last Week"
          value={<Money value={overview.kpi.margin_bz_last_week_idr} />}
          sub={`${overview.kpi.practices_last_week} practices`}
        />
        <KpiCard
          label="Margin BS Total"
          value={<Money value={overview.kpi.margin_bs_total_idr} />}
        />
        <KpiCard
          label="Total Practices"
          value={String(overview.kpi.practices_total)}
        />
      </div>

      <div className="border rounded-xl p-5" style={PANEL}>
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp size={16} className="text-[var(--state-success)]" />
          <h2 className="text-sm font-semibold text-[var(--bz-text-1)]">
            Margin trend (weekly)
          </h2>
        </div>
        <div style={{ width: "100%", height: 260 }}>
          <MarginTrendChart data={overview.trend} />
        </div>
      </div>

      <div className="border rounded-xl p-5" style={PANEL}>
        <div className="flex items-center gap-2 mb-4">
          <Banknote size={16} className="text-[var(--state-success)]" />
          <h2 className="text-sm font-semibold text-[var(--bz-text-1)]">
            Top visa types by MBZ
          </h2>
        </div>
        <div style={{ width: "100%", height: 260 }}>
          <TopVisaChart data={visa} />
        </div>
      </div>

      <div className="border rounded-xl overflow-hidden" style={PANEL}>
        <div className="flex items-center gap-2 p-5 border-b border-[var(--bz-border)]">
          <UsersIcon size={16} className="text-[var(--state-success)]" />
          <h2 className="text-sm font-semibold text-[var(--bz-text-1)]">
            Weekly breakdown
          </h2>
        </div>
        <table className="w-full text-sm">
          <thead className="text-xs text-[var(--bz-text-3)] uppercase border-b border-[var(--bz-border)]">
            <tr>
              <th className="text-left px-4 py-3">Week</th>
              <th className="text-right px-4 py-3">Practices</th>
              <th className="text-right px-4 py-3">Total income</th>
              <th className="text-right px-4 py-3">Margin BZ</th>
              <th className="text-right px-4 py-3">Margin BS</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody className="text-[var(--bz-text-1)]">
            {weeks.map((w) => (
              <tr
                key={w.id}
                className="border-b border-[var(--bz-border)] hover:bg-[var(--bz-glass-rim)]"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/hr/owner-cashout/${w.id}`}
                    className="hover:text-[var(--state-success)]"
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
                  <Money value={w.total_income_idr} />
                </td>
                <td className="text-right px-4 py-3 text-[var(--state-success)]">
                  <Money value={w.total_margin_bz_idr} />
                </td>
                <td className="text-right px-4 py-3 text-[var(--state-warning)]">
                  <Money value={w.total_margin_bs_idr} />
                </td>
                <td className="px-4 py-3 text-[var(--bz-text-3)]">
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
