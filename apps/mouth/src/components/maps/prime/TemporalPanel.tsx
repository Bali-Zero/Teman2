'use client';

import { useEffect, useState } from 'react';

interface TemporalBucket {
  date: string;
  practices: number;
  companies: number;
  activity_score: number;
}

interface TemporalData {
  zone_code: string;
  period: string;
  granularity: string;
  buckets: TemporalBucket[];
  trend: 'increasing' | 'stable' | 'decreasing';
  total_activity: number;
}

const PERIODS = ['1m', '3m', '6m', '12m'] as const;

export function TemporalPanel({ zoneCode }: { zoneCode: string | null }) {
  const [data, setData] = useState<TemporalData | null>(null);
  const [loading, setLoading] = useState(false);
  const [period, setPeriod] = useState<string>('6m');

  useEffect(() => {
    if (!zoneCode) return;
    setLoading(true);
    const params = new URLSearchParams({ zone_code: zoneCode, period, granularity: 'weekly' });
    fetch(`/api/prime/v2/temporal?${params.toString()}`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [zoneCode, period]);

  const trendArrow =
    data?.trend === 'increasing' ? '\u2197' : data?.trend === 'decreasing' ? '\u2198' : '\u2192';
  const trendColor =
    data?.trend === 'increasing'
      ? 'text-emerald-400'
      : data?.trend === 'decreasing'
        ? 'text-red-400'
        : 'text-amber-400';

  const maxScore = data ? Math.max(...data.buckets.map((b) => b.activity_score), 1) : 1;

  return (
    <div className="w-80 rounded-2xl bg-black/90 backdrop-blur-xl border border-white/10 shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">&#x1F4C8;</span>
          <span className="text-sm font-semibold text-white">Zone Activity</span>
        </div>
        {data && <span className={`text-lg ${trendColor}`}>{trendArrow}</span>}
      </div>

      {/* Period selector */}
      <div className="px-4 py-2 flex gap-1">
        {PERIODS.map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className={`flex-1 py-1 rounded-lg text-xs font-medium transition-all ${
              period === p
                ? 'bg-[#d4845a] text-white'
                : 'text-slate-500 hover:text-white hover:bg-white/5'
            }`}
          >
            {p}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="px-4 pb-3 max-h-[50vh] overflow-y-auto">
        {!zoneCode && (
          <p className="text-xs text-slate-500 py-4 text-center">
            Click a zone on the map to see activity
          </p>
        )}

        {loading && (
          <div className="flex items-center justify-center py-6">
            <div className="w-5 h-5 border-2 border-slate-700 border-t-[#d4845a] rounded-full animate-spin" />
          </div>
        )}

        {!loading && data && data.buckets.length === 0 && (
          <p className="text-xs text-slate-500 py-4 text-center">
            No activity data for this period
          </p>
        )}

        {!loading && data && data.buckets.length > 0 && (
          <div className="space-y-2">
            {/* Stats */}
            <div className="grid grid-cols-3 gap-1.5">
              <div className="rounded-lg bg-white/5 border border-white/8 p-2 text-center">
                <div className="text-white font-semibold text-sm">{data.total_activity}</div>
                <div className="text-slate-500 text-[10px]">Total</div>
              </div>
              <div className="rounded-lg bg-white/5 border border-white/8 p-2 text-center">
                <div className="text-white font-semibold text-sm">{data.buckets.length}</div>
                <div className="text-slate-500 text-[10px]">Periods</div>
              </div>
              <div className="rounded-lg bg-white/5 border border-white/8 p-2 text-center">
                <div className={`font-semibold text-sm ${trendColor}`}>{data.trend}</div>
                <div className="text-slate-500 text-[10px]">Trend</div>
              </div>
            </div>

            {/* Activity bars */}
            <div className="space-y-0.5">
              {data.buckets.map((bucket) => {
                const pct = maxScore > 0 ? (bucket.activity_score / maxScore) * 100 : 0;
                return (
                  <div key={bucket.date} className="flex items-center gap-2">
                    <span className="text-[9px] text-slate-600 w-16 shrink-0 tabular-nums">
                      {bucket.date?.slice(5) || '?'}
                    </span>
                    <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-[#d4845a]/50 to-[#d4845a]"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="text-[9px] text-slate-500 w-4 text-right tabular-nums">
                      {bucket.activity_score}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
