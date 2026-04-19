"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Row = { endpoint: string; call_count: number; total_cost_usd: number };

export default function TopEndpoints() {
  const [rows, setRows] = useState<Row[]>([]);
  useEffect(() => {
    fetch("/api/llm-costs/top-endpoints")
      .then((r) => r.json())
      .then((data) => setRows(data.rows ?? []));
  }, []);

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h2 className="mb-2 text-sm font-semibold text-slate-200">
        Top 10 endpoints by cost (last 7d)
      </h2>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={rows} layout="vertical" margin={{ left: 120 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis type="number" stroke="#64748b" tick={{ fontSize: 11 }} />
          <YAxis
            dataKey="endpoint"
            type="category"
            stroke="#64748b"
            tick={{ fontSize: 11 }}
            width={120}
          />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155" }}
          />
          <Bar dataKey="total_cost_usd" fill="#60a5fa" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
