"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Row = { day: string; provider: string; cost_usd: number };

export default function CostTimeline() {
  const [rows, setRows] = useState<Row[]>([]);
  useEffect(() => {
    fetch("/api/llm-costs/timeline")
      .then((r) => r.json())
      .then((data) => setRows(data.rows ?? []));
  }, []);

  // Pivot to wide format: one object per day, keys = providers.
  const byDay = new Map<string, Record<string, number | string>>();
  const providers = new Set<string>();
  for (const r of rows) {
    const day = typeof r.day === "string" ? r.day.slice(0, 10) : String(r.day);
    if (!byDay.has(day)) byDay.set(day, { day });
    byDay.get(day)![r.provider] = Number(r.cost_usd);
    providers.add(r.provider);
  }
  const data = Array.from(byDay.values()).sort((a, b) =>
    String(a.day).localeCompare(String(b.day)),
  );
  const providerList = Array.from(providers);
  const colors = [
    "#60a5fa",
    "#f59e0b",
    "#34d399",
    "#f87171",
    "#a78bfa",
    "#fb7185",
  ];

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h2 className="mb-2 text-sm font-semibold text-slate-200">
        Daily cost (30d, stacked by provider)
      </h2>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="day" stroke="#64748b" tick={{ fontSize: 11 }} />
          <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155" }}
          />
          <Legend />
          {providerList.map((p, i) => (
            <Bar key={p} dataKey={p} stackId="a" fill={colors[i % colors.length]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
