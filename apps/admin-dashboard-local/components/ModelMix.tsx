"use client";

import { useEffect, useState } from "react";
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

type Row = {
  provider: string;
  input_tokens: number;
  output_tokens: number;
  call_count: number;
};

export default function ModelMix() {
  const [rows, setRows] = useState<Row[]>([]);
  useEffect(() => {
    fetch("/api/llm-costs/model-mix")
      .then((r) => r.json())
      .then((data) => setRows(data.rows ?? []));
  }, []);

  const data = rows.map((r) => ({
    name: r.provider,
    value: Number(r.input_tokens),
  }));
  const colors = [
    "#60a5fa",
    "#f59e0b",
    "#34d399",
    "#f87171",
    "#a78bfa",
    "#fb7185",
    "#38bdf8",
  ];

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h2 className="mb-2 text-sm font-semibold text-slate-200">
        Input tokens by provider (last 7d)
      </h2>
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius={90}
            label
          >
            {data.map((_, i) => (
              <Cell key={i} fill={colors[i % colors.length]} />
            ))}
          </Pie>
          <Legend />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155" }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
