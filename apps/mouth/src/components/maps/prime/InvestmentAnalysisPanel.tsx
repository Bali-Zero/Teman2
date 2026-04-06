'use client';

import { useEffect, useState } from 'react';
import { usePrimeNexus } from '@/contexts/PrimeNexusContext';
import { VerdictBadge } from './VerdictBadge';
import { DealFlowWizard } from './DealFlowWizard';

const FACTOR_LABELS: Record<string, string> = {
  roi: 'ROI Quality',
  zone_kbli_fit: 'Zone-KBLI Fit',
  building_capacity: 'Building Capacity',
  break_even: 'Break-Even',
  flood_risk: 'Flood Risk',
  market: 'Market Validation',
  regulatory: 'Regulatory Risk',
  amenity: 'Amenity Access',
};

interface PredictData {
  zone_code: string;
  trend: 'improving' | 'stable' | 'declining';
  trend_score: number;
  predicted_label: string;
  factors: { signal: string; direction: string; detail: string }[];
}

function TrendBadge({ zoneCode }: { zoneCode: string }) {
  const [data, setData] = useState<PredictData | null>(null);

  useEffect(() => {
    if (!zoneCode) return;
    fetch(`/api/prime/v2/predict?zone_code=${encodeURIComponent(zoneCode)}`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null));
  }, [zoneCode]);

  if (!data || (!data.factors.length && data.trend === 'stable')) return null;

  const arrow =
    data.trend === 'improving' ? '\u2197' : data.trend === 'declining' ? '\u2198' : '\u2192';
  const color =
    data.trend === 'improving'
      ? 'text-emerald-400'
      : data.trend === 'declining'
        ? 'text-red-400'
        : 'text-amber-400';

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className={`text-base ${color}`}>{arrow}</span>
      <span className="text-slate-400">
        Zone <span className={`font-semibold ${color}`}>{data.trend}</span>
      </span>
    </div>
  );
}

interface DensityData {
  zone_code: string;
  total_companies: number;
  by_kbli: Record<string, number>;
  by_kbli_labels: Record<string, string>;
  saturation_index: number;
  saturation_label: 'LOW' | 'MEDIUM' | 'HIGH';
}

function DensitySection({ zoneCode }: { zoneCode: string }) {
  const [data, setData] = useState<DensityData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!zoneCode) return;
    setLoading(true);
    fetch(`/api/prime/v2/density?zone_code=${encodeURIComponent(zoneCode)}`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [zoneCode]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-2">
        <div className="w-3 h-3 border border-slate-600 border-t-[#d4845a] rounded-full animate-spin" />
        <span className="text-[10px] text-slate-500">Loading market density...</span>
      </div>
    );
  }

  if (!data || data.total_companies === 0) return null;

  const maxCount = Math.max(...Object.values(data.by_kbli));
  const sortedSectors = Object.entries(data.by_kbli)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  const satColor =
    data.saturation_label === 'HIGH'
      ? 'text-red-400 bg-red-500/10'
      : data.saturation_label === 'MEDIUM'
        ? 'text-amber-400 bg-amber-500/10'
        : 'text-emerald-400 bg-emerald-500/10';

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-widest text-slate-600 font-semibold">
          Market Density
        </div>
        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${satColor}`}>
          {data.saturation_label}
        </span>
      </div>
      <div className="text-xs text-slate-400">
        {data.total_companies} {data.total_companies === 1 ? 'company' : 'companies'} in zone
      </div>
      <div className="space-y-1">
        {sortedSectors.map(([sector, count]) => {
          const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
          const label = data.by_kbli_labels?.[sector] || `Sector ${sector}`;
          return (
            <div key={sector} className="flex items-center gap-2">
              <span className="text-[10px] text-slate-500 w-24 shrink-0 truncate">{label}</span>
              <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                <div className="h-full rounded-full bg-[#d4845a]/70" style={{ width: `${pct}%` }} />
              </div>
              <span className="text-[10px] text-slate-500 tabular-nums w-6 text-right">
                {count}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function InvestmentAnalysisPanel() {
  const { analysis, isAnalyzing } = usePrimeNexus();
  const [showDealFlow, setShowDealFlow] = useState(false);

  if (isAnalyzing) {
    return (
      <div className="px-4 py-6 text-center">
        <div className="inline-flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-[#d4845a] border-t-transparent rounded-full animate-spin" />
          <span className="text-xs text-slate-400">Analyzing investment potential...</span>
        </div>
      </div>
    );
  }

  if (!analysis || !analysis.verdict) return null;

  const { verdict } = analysis;

  return (
    <div className="px-4 py-3 space-y-3 border-b border-white/5">
      {/* Verdict Badge + Trend */}
      <VerdictBadge verdict={verdict.label} score={verdict.score} />
      {analysis.zone?.zone_code ? <TrendBadge zoneCode={String(analysis.zone.zone_code)} /> : null}

      {/* Hard Blocks */}
      {verdict.hard_blocks.length > 0 && (
        <div className="space-y-1">
          {verdict.hard_blocks.map((block, i) => (
            <div
              key={i}
              className="flex items-start gap-2 text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-2"
            >
              <span className="shrink-0 mt-0.5">&#x1F6AB;</span>
              <span>{String(block)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Score Breakdown */}
      {verdict.breakdown && Object.keys(verdict.breakdown).length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[10px] uppercase tracking-widest text-slate-600 font-semibold">
            Score Breakdown
          </div>
          {Object.entries(verdict.breakdown).map(([key, factor]) => {
            const f = factor as { score: number | null; max: number };
            if (f.score === null) return null;
            const pct = f.max > 0 ? (f.score / f.max) * 100 : 0;
            return (
              <div key={key} className="flex items-center gap-2">
                <span className="text-xs text-slate-500 w-28 shrink-0 truncate">
                  {FACTOR_LABELS[key] || key}
                </span>
                <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      pct >= 70 ? 'bg-emerald-500' : pct >= 40 ? 'bg-amber-500' : 'bg-red-500'
                    }`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="text-[10px] text-slate-500 tabular-nums w-8 text-right">
                  {f.score}/{f.max}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Modifiers */}
      {verdict.modifiers.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] uppercase tracking-widest text-slate-600 font-semibold">
            Notes
          </div>
          {verdict.modifiers.map((mod, i) => (
            <div key={i} className="text-xs text-slate-500 leading-relaxed">
              {String(mod)}
            </div>
          ))}
        </div>
      )}

      {/* Market Density */}
      {analysis.zone?.zone_code ? (
        <DensitySection zoneCode={String(analysis.zone.zone_code)} />
      ) : null}

      {/* CTA */}
      {verdict.label !== 'RED' && (
        <button
          onClick={() => setShowDealFlow(true)}
          className="w-full text-center py-2.5 rounded-xl bg-[#d4845a] hover:bg-[#c4744a] text-white text-sm font-semibold transition-colors"
        >
          Start Investment
        </button>
      )}

      {showDealFlow && <DealFlowWizard onClose={() => setShowDealFlow(false)} />}
    </div>
  );
}
