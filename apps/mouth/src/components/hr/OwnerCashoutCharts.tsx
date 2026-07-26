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

import { formatIDR } from "@balizero/core/utils";

function formatShort(v: number): string {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return String(v);
}

function formatTooltipIDR(v: unknown): string {
  const amount =
    typeof v === "number" ? v : Number.parseFloat(String(v ?? "0"));
  return formatIDR(Number.isFinite(amount) ? amount : 0);
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
        <CartesianGrid stroke="var(--bz-border)" strokeDasharray="3 3" />
        <XAxis
          dataKey="week_start"
          stroke="var(--bz-text-muted)"
          fontSize={11}
        />
        <YAxis
          stroke="var(--bz-text-muted)"
          fontSize={11}
          tickFormatter={formatShort}
        />
        <Tooltip
          contentStyle={{
            background: "var(--bz-bg-elevated)",
            border: "1px solid var(--bz-border)",
          }}
          formatter={formatTooltipIDR}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="margin_bz"
          stroke="var(--bz-chart-2)"
          name="Margin BZ"
          strokeWidth={2}
        />
        <Line
          type="monotone"
          dataKey="margin_bs"
          stroke="var(--bz-chart-3)"
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
        <CartesianGrid stroke="var(--bz-border)" strokeDasharray="3 3" />
        <XAxis
          type="number"
          stroke="var(--bz-text-muted)"
          fontSize={11}
          tickFormatter={formatShort}
        />
        <YAxis
          type="category"
          dataKey="process"
          stroke="var(--bz-text-muted)"
          fontSize={11}
          width={130}
        />
        <Tooltip
          contentStyle={{
            background: "var(--bz-bg-elevated)",
            border: "1px solid var(--bz-border)",
          }}
          formatter={formatTooltipIDR}
        />
        <Bar
          dataKey="margin_bz_total_idr"
          fill="var(--bz-chart-2)"
          name="MBZ"
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
