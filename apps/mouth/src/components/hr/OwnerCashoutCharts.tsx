"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

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

interface TrendPoint {
  week_start: string;
  margin_bz: number;
  margin_bs: number;
}

export function MarginTrendChart({ data }: { data: TrendPoint[] }) {
  return (
    <ResponsiveContainer>
      <LineChart data={data}>
        <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
        <XAxis dataKey="week_start" stroke="#71717a" fontSize={11} />
        <YAxis stroke="#71717a" fontSize={11} tickFormatter={formatShort} />
        <Tooltip
          contentStyle={{ background: "#18181b", border: "1px solid #27272a" }}
          formatter={(v: number) => formatIDR(v)}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="margin_bz"
          stroke="#34d399"
          name="Margin BZ"
          strokeWidth={2}
        />
        <Line
          type="monotone"
          dataKey="margin_bs"
          stroke="#fbbf24"
          name="Margin BS"
          strokeWidth={2}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

interface VisaPoint {
  process: string;
  margin_bz_total_idr: number;
}

export function TopVisaChart({ data }: { data: VisaPoint[] }) {
  return (
    <ResponsiveContainer>
      <BarChart data={data} layout="vertical">
        <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
        <XAxis
          type="number"
          stroke="#71717a"
          fontSize={11}
          tickFormatter={formatShort}
        />
        <YAxis
          type="category"
          dataKey="process"
          stroke="#71717a"
          fontSize={11}
          width={130}
        />
        <Tooltip
          contentStyle={{ background: "#18181b", border: "1px solid #27272a" }}
          formatter={(v: number) => formatIDR(v)}
        />
        <Bar dataKey="margin_bz_total_idr" fill="#34d399" name="MBZ" />
      </BarChart>
    </ResponsiveContainer>
  );
}
