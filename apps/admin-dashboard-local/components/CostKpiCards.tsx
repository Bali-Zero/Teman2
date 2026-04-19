"use client";

import { useEffect, useState } from "react";

type Kpi = {
  today_usd: number;
  last_7d_usd: number;
  last_30d_usd: number;
};

export default function CostKpiCards() {
  const [kpi, setKpi] = useState<Kpi | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/llm-costs/kpi")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText))))
      .then(setKpi)
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) return <div className="text-red-400">KPI error: {err}</div>;
  if (!kpi) return <div className="text-slate-400">Loading KPI…</div>;

  const fmt = (v: number) => `$${Number(v).toFixed(2)}`;

  return (
    <div className="grid grid-cols-3 gap-4">
      <Card label="Today" value={fmt(kpi.today_usd)} />
      <Card label="Last 7 days" value={fmt(kpi.last_7d_usd)} />
      <Card label="Last 30 days" value={fmt(kpi.last_30d_usd)} />
    </div>
  );
}

function Card({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="text-xs uppercase tracking-wider text-slate-400">{label}</div>
      <div className="mt-2 text-3xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}
