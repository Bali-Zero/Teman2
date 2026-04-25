"use client";

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

export interface FunnelChartDatum {
  funnel: string;
  sessions: number;
  conversions: number;
}

export default function FunnelChart({ data }: { data: FunnelChartDatum[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
        <XAxis dataKey="funnel" stroke="#9ca3af" />
        <YAxis stroke="#9ca3af" />
        <Tooltip
          contentStyle={{
            background: "rgba(0,0,0,0.85)",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 8,
          }}
        />
        <Legend />
        <Bar dataKey="sessions" fill="#3b82f6" name="Sessioni" />
        <Bar dataKey="conversions" fill="#22c55e" name="Conversioni" />
      </BarChart>
    </ResponsiveContainer>
  );
}
