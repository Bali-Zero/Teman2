'use client';

import { usePrimeNexus } from '@/contexts/PrimeNexusContext';
import { VerdictBadge } from './VerdictBadge';

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

export function InvestmentAnalysisPanel() {
  const { analysis, isAnalyzing } = usePrimeNexus();

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
      {/* Verdict Badge */}
      <VerdictBadge verdict={verdict.label} score={verdict.score} />

      {/* Hard Blocks */}
      {verdict.hard_blocks.length > 0 && (
        <div className="space-y-1">
          {verdict.hard_blocks.map((block, i) => (
            <div
              key={i}
              className="flex items-start gap-2 text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-2"
            >
              <span className="shrink-0 mt-0.5">&#x1F6AB;</span>
              <span>{block}</span>
            </div>
          ))}
        </div>
      )}

      {/* Score Breakdown */}
      {Object.keys(verdict.breakdown).length > 0 && (
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
              {mod}
            </div>
          ))}
        </div>
      )}

      {/* CTA */}
      {verdict.label !== 'RED' && (
        <a
          href="https://balizero.com/contact"
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full text-center py-2.5 rounded-xl bg-[#d4845a] hover:bg-[#c4744a] text-white text-sm font-semibold transition-colors"
        >
          Start Your Business Here
        </a>
      )}
    </div>
  );
}
