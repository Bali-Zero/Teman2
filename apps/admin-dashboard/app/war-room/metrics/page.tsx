"use client";

import { useEffect, useState } from "react";
import { error as logError } from "@/lib/logger";

type DaysWindow = 14 | 30 | 90;

interface TimelineBucket {
  day: string;
  register: string;
  post_count: number;
}

interface HeatmapCell {
  register: string;
  metric_name: string;
  avg_value: number;
  sample_count: number;
}

interface PieSlice {
  register: string;
  post_count: number;
  pct: number;
}

interface FunnelStage {
  stage: string;
  count: number;
}

interface RejectionBucket {
  reason: string;
  count: number;
}

interface CostRow {
  draft_id: string;
  topic: string;
  total_usd: number;
  by_type: Record<string, number>;
}

interface DashboardData {
  timeline: { buckets: TimelineBucket[] };
  heatmap: { cells: HeatmapCell[] };
  distribution: {
    total_posts: number;
    slices: PieSlice[];
    dominant_register: string | null;
    alert: boolean;
  };
  funnel: { stages: FunnelStage[] };
  rejections: { buckets: RejectionBucket[] };
  costs: { rows: CostRow[]; grand_total_usd: number };
}

const REGISTER_COLORS: Record<string, string> = {
  rituale: "#8B5CF6",
  analitico: "#2563EB",
  ironico: "#F59E0B",
  militante: "#DC2626",
  pedagogico: "#10B981",
  poetico: "#EC4899",
  tecnico: "#6B7280",
  unknown: "#9CA3AF",
};

function regColor(r: string): string {
  return REGISTER_COLORS[r] ?? "#9CA3AF";
}

export default function WarRoomMetricsPage() {
  const [days, setDays] = useState<DaysWindow>(30);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (w: DaysWindow) => {
    setLoading(true);
    setError(null);
    try {
      const [timeline, heatmap, distribution, funnel, rejections, costs] =
        await Promise.all([
          fetch(`/api/war-room/metrics/timeline?days=${w}`).then((r) =>
            r.json(),
          ),
          fetch(`/api/war-room/metrics/heatmap?days=${w}`).then((r) =>
            r.json(),
          ),
          fetch(`/api/war-room/metrics/distribution?days=${w}`).then((r) =>
            r.json(),
          ),
          fetch(`/api/war-room/metrics/funnel?days=${w}`).then((r) => r.json()),
          fetch(`/api/war-room/metrics/rejections?days=${w}`).then((r) =>
            r.json(),
          ),
          fetch(`/api/war-room/metrics/costs?days=${w}&limit=25`).then((r) =>
            r.json(),
          ),
        ]);
      setData({ timeline, heatmap, distribution, funnel, rejections, costs });
    } catch (e) {
      logError(String(e));
      setError("Failed to load metrics");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(days);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days]);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">War Room · Metrics</h1>
        <div className="flex items-center gap-2">
          {([14, 30, 90] as DaysWindow[]).map((w) => (
            <button
              key={w}
              onClick={() => setDays(w)}
              className={`px-3 py-1 rounded text-sm ${
                w === days
                  ? "bg-blue-600 text-white"
                  : "bg-gray-200 text-gray-700 hover:bg-gray-300"
              }`}
            >
              {w}d
            </button>
          ))}
          <button
            onClick={() => load(days)}
            className="px-3 py-1 rounded text-sm bg-gray-200 hover:bg-gray-300"
            disabled={loading}
          >
            {loading ? "…" : "↻"}
          </button>
        </div>
      </header>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 text-sm p-3 rounded">
          {error}
        </div>
      )}

      {data?.distribution?.alert && (
        <div className="bg-yellow-50 border border-yellow-300 text-yellow-900 text-sm p-3 rounded">
          ⚠ Tonal drift alert — register{" "}
          <strong>{data.distribution.dominant_register}</strong> exceeds 40% in
          the last {days} days. Consiglio hard rule may need re-tuning.
        </div>
      )}

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 bg-white border rounded p-4">
          <h2 className="text-sm font-semibold text-gray-700 mb-2">
            Posts published per day (by register)
          </h2>
          <Timeline buckets={data?.timeline?.buckets ?? []} />
        </div>
        <div className="bg-white border rounded p-4">
          <h2 className="text-sm font-semibold text-gray-700 mb-2">
            Register distribution ({days}d)
          </h2>
          <DistributionPie slices={data?.distribution?.slices ?? []} />
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border rounded p-4">
          <h2 className="text-sm font-semibold text-gray-700 mb-2">Funnel</h2>
          <Funnel stages={data?.funnel?.stages ?? []} />
        </div>
        <div className="bg-white border rounded p-4">
          <h2 className="text-sm font-semibold text-gray-700 mb-2">
            Rejections by reason
          </h2>
          <RejectionsBar buckets={data?.rejections?.buckets ?? []} />
        </div>
      </section>

      <section className="bg-white border rounded p-4">
        <h2 className="text-sm font-semibold text-gray-700 mb-2">
          Register × metric heatmap
        </h2>
        <Heatmap cells={data?.heatmap?.cells ?? []} />
      </section>

      <section className="bg-white border rounded p-4">
        <h2 className="text-sm font-semibold text-gray-700 mb-2">
          Cost per draft ({days}d) — grand total $
          {(data?.costs?.grand_total_usd ?? 0).toFixed(4)}
        </h2>
        <CostTable rows={data?.costs?.rows ?? []} />
      </section>
    </div>
  );
}

// ── Widgets ────────────────────────────────────────────────────

function Timeline({ buckets }: { buckets: TimelineBucket[] }) {
  if (buckets.length === 0) {
    return <div className="text-sm text-gray-500">No data</div>;
  }
  // Group by day, stack registers
  const days = Array.from(new Set(buckets.map((b) => b.day))).sort();
  const registers = Array.from(new Set(buckets.map((b) => b.register)));
  const map: Record<string, Record<string, number>> = {};
  for (const b of buckets) {
    map[b.day] = map[b.day] ?? {};
    map[b.day][b.register] = b.post_count;
  }
  const maxPerDay = Math.max(
    ...days.map((d) => Object.values(map[d] ?? {}).reduce((a, v) => a + v, 0)),
    1,
  );
  const W = 720;
  const H = 180;
  const padL = 32;
  const padR = 12;
  const padT = 12;
  const padB = 30;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const barW = Math.max(4, plotW / days.length - 2);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-48">
      {/* y axis line */}
      <line x1={padL} y1={padT} x2={padL} y2={H - padB} stroke="#e5e7eb" />
      <line
        x1={padL}
        y1={H - padB}
        x2={W - padR}
        y2={H - padB}
        stroke="#e5e7eb"
      />
      {days.map((d, i) => {
        const x = padL + i * (plotW / days.length) + 1;
        let stackY = H - padB;
        return (
          <g key={d}>
            {registers.map((r) => {
              const v = (map[d] ?? {})[r] ?? 0;
              if (v === 0) return null;
              const h = (v / maxPerDay) * plotH;
              stackY -= h;
              return (
                <rect
                  key={r}
                  x={x}
                  y={stackY}
                  width={barW}
                  height={h}
                  fill={regColor(r)}
                >
                  <title>{`${d} · ${r}: ${v}`}</title>
                </rect>
              );
            })}
            {i % Math.max(1, Math.floor(days.length / 6)) === 0 && (
              <text
                x={x + barW / 2}
                y={H - padB + 14}
                textAnchor="middle"
                fontSize="9"
                fill="#6b7280"
              >
                {d.slice(5)}
              </text>
            )}
          </g>
        );
      })}
      <Legend registers={registers} y={H - padB + 25} />
    </svg>
  );
}

function Legend({ registers, y }: { registers: string[]; y: number }) {
  return (
    <g>
      {registers.map((r, i) => (
        <g key={r} transform={`translate(${40 + i * 80} ${y})`}>
          <rect width="10" height="10" fill={regColor(r)} />
          <text x="14" y="9" fontSize="9" fill="#374151">
            {r}
          </text>
        </g>
      ))}
    </g>
  );
}

function DistributionPie({ slices }: { slices: PieSlice[] }) {
  if (slices.length === 0) {
    return <div className="text-sm text-gray-500">No data</div>;
  }
  const cx = 90;
  const cy = 90;
  const r = 70;
  const total = slices.reduce((a, s) => a + s.post_count, 0);
  let a0 = -Math.PI / 2;

  return (
    <div className="flex items-center gap-3">
      <svg viewBox="0 0 180 180" className="w-44 h-44">
        {slices.map((s) => {
          const frac = total > 0 ? s.post_count / total : 0;
          const a1 = a0 + frac * Math.PI * 2;
          const x0 = cx + r * Math.cos(a0);
          const y0 = cy + r * Math.sin(a0);
          const x1 = cx + r * Math.cos(a1);
          const y1 = cy + r * Math.sin(a1);
          const large = frac > 0.5 ? 1 : 0;
          const path = [
            `M ${cx} ${cy}`,
            `L ${x0.toFixed(2)} ${y0.toFixed(2)}`,
            `A ${r} ${r} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`,
            "Z",
          ].join(" ");
          const current = a0;
          a0 = a1;
          return (
            <path
              key={s.register + current}
              d={path}
              fill={regColor(s.register)}
              stroke="white"
              strokeWidth={1}
            >
              <title>{`${s.register}: ${s.post_count} (${s.pct}%)`}</title>
            </path>
          );
        })}
      </svg>
      <ul className="text-xs space-y-1">
        {slices.map((s) => (
          <li key={s.register} className="flex items-center gap-2">
            <span
              className="inline-block w-3 h-3 rounded-sm"
              style={{ background: regColor(s.register) }}
            />
            <span className="w-20">{s.register}</span>
            <span className="tabular-nums">
              {s.post_count} · {s.pct.toFixed(1)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Funnel({ stages }: { stages: FunnelStage[] }) {
  if (stages.length === 0) {
    return <div className="text-sm text-gray-500">No data</div>;
  }
  const max = Math.max(...stages.map((s) => s.count), 1);
  return (
    <ul className="space-y-2 text-sm">
      {stages.map((s) => {
        const pct = (s.count / max) * 100;
        return (
          <li key={s.stage}>
            <div className="flex justify-between mb-1">
              <span className="font-medium">{s.stage}</span>
              <span className="tabular-nums">{s.count}</span>
            </div>
            <div className="w-full bg-gray-100 h-3 rounded">
              <div
                className="bg-blue-500 h-3 rounded"
                style={{ width: `${pct}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function RejectionsBar({ buckets }: { buckets: RejectionBucket[] }) {
  if (buckets.length === 0) {
    return <div className="text-sm text-gray-500">No rejections 🎉</div>;
  }
  const max = Math.max(...buckets.map((b) => b.count), 1);
  return (
    <ul className="space-y-2 text-sm">
      {buckets.map((b) => {
        const pct = (b.count / max) * 100;
        return (
          <li key={b.reason}>
            <div className="flex justify-between mb-1">
              <span>{b.reason}</span>
              <span className="tabular-nums">{b.count}</span>
            </div>
            <div className="w-full bg-gray-100 h-3 rounded">
              <div
                className="bg-red-400 h-3 rounded"
                style={{ width: `${pct}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function Heatmap({ cells }: { cells: HeatmapCell[] }) {
  if (cells.length === 0) {
    return <div className="text-sm text-gray-500">No data</div>;
  }
  const registers = Array.from(new Set(cells.map((c) => c.register))).sort();
  const metrics = Array.from(new Set(cells.map((c) => c.metric_name))).sort();
  const map: Record<string, Record<string, HeatmapCell>> = {};
  for (const c of cells) {
    map[c.register] = map[c.register] ?? {};
    map[c.register][c.metric_name] = c;
  }
  const maxValue = Math.max(...cells.map((c) => c.avg_value), 1);

  return (
    <div className="overflow-x-auto">
      <table className="text-xs border-collapse">
        <thead>
          <tr>
            <th className="text-left p-1"></th>
            {metrics.map((m) => (
              <th key={m} className="p-1 text-left font-medium text-gray-600">
                {m}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {registers.map((r) => (
            <tr key={r}>
              <td className="p-1 pr-3 font-medium">{r}</td>
              {metrics.map((m) => {
                const c = map[r]?.[m];
                const v = c?.avg_value ?? 0;
                const intensity = Math.min(1, v / maxValue);
                const bg = `rgba(37, 99, 235, ${intensity.toFixed(2)})`;
                return (
                  <td
                    key={m}
                    className="p-1 border border-gray-100 text-center tabular-nums"
                    style={{
                      background: bg,
                      color: intensity > 0.5 ? "white" : "#111827",
                    }}
                    title={
                      c ? `${v.toFixed(2)} · n=${c.sample_count}` : "no data"
                    }
                  >
                    {c ? v.toFixed(1) : "—"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CostTable({ rows }: { rows: CostRow[] }) {
  if (rows.length === 0) {
    return <div className="text-sm text-gray-500">No costs recorded</div>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead className="text-left text-gray-600 border-b">
          <tr>
            <th className="p-1">Topic</th>
            <th className="p-1 text-right">Total USD</th>
            <th className="p-1">Breakdown</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.draft_id} className="border-b last:border-b-0">
              <td className="p-1 max-w-md truncate" title={r.topic}>
                {r.topic || "(untitled)"}
              </td>
              <td className="p-1 text-right tabular-nums">
                ${r.total_usd.toFixed(4)}
              </td>
              <td className="p-1 text-gray-600">
                {Object.entries(r.by_type)
                  .map(([k, v]) => `${k}=$${Number(v).toFixed(3)}`)
                  .join(" · ")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
