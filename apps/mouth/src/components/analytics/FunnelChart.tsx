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
        <XAxis dataKey="funnel" stroke="var(--bz-text-2)" />
        <YAxis stroke="var(--bz-text-2)" />
        <Tooltip
          contentStyle={{
            background: "rgba(0,0,0,0.85)",
            border: "1px solid var(--bz-border)",
            borderRadius: 8,
          }}
        />
        <Legend />
        <Bar dataKey="sessions" fill="var(--bz-chart-1)" name="Sessioni" />
        <Bar
          dataKey="conversions"
          fill="var(--bz-chart-2)"
          name="Conversioni"
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
