'use client';

import { useState, useMemo } from 'react';
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

  // Compute totals across ALL years
  const allYearsTotals = useMemo(() => {
    let totalProperties = 0;
    let totalVehicles = 0;
    let totalCash = 0;
    let totalOverall = 0;
    for (const y of lhkpn_years) {
      const ya = assets_by_year[y];
      if (!ya) continue;
      totalOverall += ya.total;
      totalCash += ya.cash;
      for (const p of ya.properties) totalProperties += p.nilai;
      for (const v of ya.vehicles) totalVehicles += v.nilai;
    }
    return { totalProperties, totalVehicles, totalCash, totalOverall };
  }, [lhkpn_years, assets_by_year]);

  // Compute asset density per year (for button coloring)
  const yearDensity = useMemo(() => {
    const densityMap = new Map<number, number>();
    if (lhkpn_years.length === 0) return densityMap;
    const totals = lhkpn_years.map((y) => assets_by_year[y]?.total ?? 0);
    const maxTotal = Math.max(...totals, 1);
    for (let i = 0; i < lhkpn_years.length; i++) {
      densityMap.set(lhkpn_years[i], totals[i] / maxTotal);
    }
    return densityMap;
  }, [lhkpn_years, assets_by_year]);

  // Asset growth: first year -> latest year
  const firstYear = lhkpn_years.length > 0 ? lhkpn_years[0] : null;
  const lastYear = lhkpn_years.length > 0 ? lhkpn_years[lhkpn_years.length - 1] : null;
  const firstTotal = firstYear !== null ? (assets_by_year[firstYear]?.total ?? 0) : 0;
  const lastTotal = lastYear !== null ? (assets_by_year[lastYear]?.total ?? 0) : 0;
  const growthPct = firstTotal > 0 ? ((lastTotal - firstTotal) / firstTotal) * 100 : 0;

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
    <div className="p-4 space-y-5 overflow-y-auto h-full">
      {/* Cumulative Totals */}
      <div>
        <div className="font-[family-name:var(--font-display)] text-[11px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-ghost)] mb-2">
          ALL-TIME TOTALS
        </div>
        <div className="grid grid-cols-2 gap-2">
          <YearStat label="PROPERTIES" value={formatRupiah(allYearsTotals.totalProperties)} />
          <YearStat label="VEHICLES" value={formatRupiah(allYearsTotals.totalVehicles)} />
          <YearStat label="CASH" value={formatRupiah(allYearsTotals.totalCash)} />
          <YearStat label="CUMULATIVE" value={formatRupiah(allYearsTotals.totalOverall)} />
        </div>
      </div>

      {/* Asset Growth mini-table */}
      {lhkpn_years.length >= 2 && firstYear !== null && lastYear !== null && (
        <div className="p-2.5 rounded border border-[var(--sg-border)] bg-[var(--sg-base-deep)]">
          <div className="font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.08em] text-[var(--sg-text-ghost)] mb-2">
            ASSET GROWTH
          </div>
          <div className="space-y-1">
            <div className="flex justify-between items-center">
              <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-secondary)]">
                {firstYear}
              </span>
              <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-secondary)]">
                {formatRupiah(firstTotal)}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-secondary)]">
                {lastYear}
              </span>
              <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-copper)] font-medium">
                {formatRupiah(lastTotal)}
              </span>
            </div>
            <div className="h-[1px] bg-[var(--sg-border)] my-1" />
            <div className="flex justify-between items-center">
              <span className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)]">
                Change
              </span>
              <span
                className={`font-[family-name:var(--font-mono)] text-[11px] font-bold ${
                  growthPct > 30 ? 'text-[var(--sg-anomaly)]' :
                  growthPct > 0 ? 'text-[var(--sg-clean)]' :
                  growthPct < -10 ? 'text-[var(--sg-anomaly)]' :
                  'text-[var(--sg-text-secondary)]'
                }`}
              >
                {growthPct >= 0 ? '+' : ''}{growthPct.toFixed(1)}%
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ECG Chart */}
      <AssetECG detail={detail} />

      {/* Delta Analysis */}
      {delta.length > 0 && <DeltaBar deltas={delta} />}

      {/* Year Selector with density coloring */}
      <div>
        <div className="font-[family-name:var(--font-display)] text-[11px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-ghost)] mb-2">
          YEAR BREAKDOWN
        </div>
        <div className="flex gap-1.5 flex-wrap mb-3">
          {lhkpn_years.map((y) => {
            const density = yearDensity.get(y) ?? 0;
            // Brighter copper for higher density (0.15 to 0.5 opacity)
            const densityOpacity = 0.08 + density * 0.3;
            const isActive = selectedYear === y;

            return (
              <button
                key={y}
                onClick={() => setSelectedYear(y)}
                className={`px-2.5 py-1 rounded text-[10px] font-[family-name:var(--font-mono)] transition-colors border ${
                  isActive
                    ? 'text-[var(--sg-copper)] border-[var(--sg-border-copper)] font-bold'
                    : 'text-[var(--sg-text-ghost)] hover:text-[var(--sg-text-secondary)] border-[var(--sg-border)]'
                }`}
                style={{
                  backgroundColor: isActive
                    ? 'var(--sg-copper-dim)'
                    : `rgba(186,135,89,${densityOpacity.toFixed(2)})`,
                }}
              >
                {y}
              </button>
            );
          })}
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
      <div className="font-[family-name:var(--font-mono)] text-[12px] font-medium text-[var(--sg-copper)] mt-0.5">
        {value}
      </div>
    </div>
  );
}
