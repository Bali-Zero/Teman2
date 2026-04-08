'use client';

import { useState } from 'react';
import type { OfficialDetail } from '@/lib/types';
import { formatRupiah } from '@/lib/format';
import { AssetECG } from '@/components/timeline/AssetECG';
import { DeltaBar } from '@/components/timeline/DeltaBar';

interface AssetTimelineProps {
  detail: OfficialDetail;
}

export function AssetTimeline({ detail }: AssetTimelineProps) {
  const { lhkpn_years, assets_by_year, delta } = detail;
  const [selectedYear, setSelectedYear] = useState<number | null>(
    lhkpn_years.length > 0 ? lhkpn_years[lhkpn_years.length - 1] : null
  );

  if (lhkpn_years.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-text-ghost)]">
          No LHKPN timeline data
        </span>
      </div>
    );
  }

  const yearAssets = selectedYear !== null ? assets_by_year[selectedYear] : null;

  return (
    <div className="p-4 space-y-6 overflow-y-auto h-full">
      {/* ECG Chart */}
      <AssetECG detail={detail} />

      {/* Delta Analysis */}
      {delta.length > 0 && <DeltaBar deltas={delta} />}

      {/* Year Selector */}
      <div>
        <div className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-2">
          YEAR BREAKDOWN
        </div>
        <div className="flex gap-1.5 flex-wrap mb-3">
          {lhkpn_years.map((y) => (
            <button
              key={y}
              onClick={() => setSelectedYear(y)}
              className={`px-2.5 py-1 rounded text-[10px] font-[family-name:var(--font-mono)] transition-colors ${
                selectedYear === y
                  ? 'bg-[var(--sg-copper-dim)] text-[var(--sg-copper)] border border-[var(--sg-border-copper)]'
                  : 'text-[var(--sg-text-ghost)] hover:text-[var(--sg-text-secondary)] border border-[var(--sg-border)]'
              }`}
            >
              {y}
            </button>
          ))}
        </div>

        {/* Year breakdown detail */}
        {yearAssets && selectedYear !== null && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <YearStat label="TOTAL" value={formatRupiah(yearAssets.total)} />
              <YearStat label="CASH" value={formatRupiah(yearAssets.cash)} />
              <YearStat label="PROPERTIES" value={String(yearAssets.properties.length)} />
              <YearStat label="VEHICLES" value={String(yearAssets.vehicles.length)} />
            </div>

            {/* Property values for selected year */}
            {yearAssets.properties.length > 0 && (
              <div>
                <div className="font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.08em] text-[var(--sg-text-ghost)] mb-1.5">
                  PROPERTIES ({selectedYear})
                </div>
                <div className="space-y-1">
                  {yearAssets.properties.map((p, i) => (
                    <div key={i} className="flex justify-between items-center py-1 border-b border-[var(--sg-border)]">
                      <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-secondary)] truncate flex-1 mr-2">
                        {p.lokasi || 'Unknown'}
                      </span>
                      <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-copper)] shrink-0">
                        {formatRupiah(p.nilai)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Vehicle values for selected year */}
            {yearAssets.vehicles.length > 0 && (
              <div>
                <div className="font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.08em] text-[var(--sg-text-ghost)] mb-1.5">
                  VEHICLES ({selectedYear})
                </div>
                <div className="space-y-1">
                  {yearAssets.vehicles.map((v, i) => (
                    <div key={i} className="flex justify-between items-center py-1 border-b border-[var(--sg-border)]">
                      <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-secondary)] truncate flex-1 mr-2">
                        {v.merk_model || v.jenis}
                      </span>
                      <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-copper)] shrink-0">
                        {formatRupiah(v.nilai)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function YearStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-2 rounded border border-[var(--sg-border)] bg-[var(--sg-base-deep)]">
      <div className="font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.08em] text-[var(--sg-text-ghost)]">
        {label}
      </div>
      <div className="font-[family-name:var(--font-mono)] text-[13px] font-medium text-[var(--sg-copper)] mt-0.5">
        {value}
      </div>
    </div>
  );
}
