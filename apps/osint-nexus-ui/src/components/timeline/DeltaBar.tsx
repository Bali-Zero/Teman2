'use client';

import { formatDelta } from '@/lib/format';

interface DeltaBarProps {
  deltas: { from_year: number; to_year: number; pct_change: number }[];
}

export function DeltaBar({ deltas }: DeltaBarProps) {
  const maxAbs = Math.max(...deltas.map((d) => Math.abs(d.pct_change)), 1);

  return (
    <div>
      <div className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-3">
        DELTA ANALYSIS
      </div>
      <div className="space-y-2">
        {deltas.map((d) => {
          const pct = Math.abs(d.pct_change) / maxAbs * 100;
          const isAnomaly = Math.abs(d.pct_change) > 30;
          const color = isAnomaly ? 'var(--sg-anomaly)' : d.pct_change >= 0 ? 'var(--sg-copper)' : 'var(--sg-periwinkle)';

          return (
            <div key={`${d.from_year}-${d.to_year}`} className="flex items-center gap-3">
              <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)] w-16 shrink-0">
                {d.from_year}→{d.to_year}
              </span>
              <div className="flex-1 h-3 rounded-sm bg-[var(--sg-border)] overflow-hidden">
                <div
                  className="h-full rounded-sm transition-all duration-500"
                  style={{ width: `${pct}%`, background: color }}
                />
              </div>
              <span className="font-[family-name:var(--font-mono)] text-[11px] w-12 text-right" style={{ color }}>
                {formatDelta(d.pct_change)}
              </span>
              {isAnomaly && <span className="text-[var(--sg-anomaly)] text-[10px]">⚠</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
