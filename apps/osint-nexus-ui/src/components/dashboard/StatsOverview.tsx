'use client';

import type { GraphStats } from '@/lib/types';
import { formatRupiah, formatNumber } from '@/lib/format';

interface TopHolder {
  name: string;
  jabatan: string;
  total_assets: number;
}

interface StatsOverviewProps {
  stats: GraphStats | null;
  topHolders: TopHolder[];
  loading: boolean;
  onSelectOfficial?: (name: string) => void;
}

export function StatsOverview({ stats, topHolders, loading, onSelectOfficial }: StatsOverviewProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-text-ghost)] animate-pulse">
          Loading intelligence...
        </span>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-8 overflow-y-auto h-full">
      {/* Header */}
      <div>
        <h2 className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-1">
          INTELLIGENCE OVERVIEW
        </h2>
        <p className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)]">
          Select an official from the directory to view their full profile
        </p>
      </div>

      {/* Primary stats */}
      {stats && (
        <div className="grid grid-cols-2 gap-3">
          <StatCard label="Graph Nodes" value={formatNumber(stats.nodes)} icon="N" />
          <StatCard label="Relationships" value={formatNumber(stats.relationships)} icon="R" />
          <StatCard label="Officials" value={formatNumber(stats.officials)} icon="O" />
          <StatCard label="LHKPN Reports" value={formatNumber(stats.lhkpn_reports)} icon="L" />
        </div>
      )}

      {/* Nodes by type */}
      {stats?.nodes_by_type && (
        <div>
          <h3 className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-3">
            NODES BY TYPE
          </h3>
          <div className="grid grid-cols-3 gap-2">
            {Object.entries(stats.nodes_by_type)
              .filter(([, count]) => count > 0)
              .sort(([, a], [, b]) => b - a)
              .map(([label, count]) => (
                <div key={label} className="flex items-center justify-between p-2 rounded border border-[var(--sg-border)] bg-[var(--sg-base-deep)]">
                  <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-secondary)]">
                    {label}
                  </span>
                  <span className="font-[family-name:var(--font-mono)] text-[11px] font-medium text-[var(--sg-copper)]">
                    {formatNumber(count)}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Relationships by type */}
      {stats?.rels_by_type && (
        <div>
          <h3 className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-3">
            RELATIONSHIPS BY TYPE
          </h3>
          <div className="grid grid-cols-3 gap-2">
            {Object.entries(stats.rels_by_type)
              .filter(([, count]) => count > 0)
              .sort(([, a], [, b]) => b - a)
              .map(([label, count]) => (
                <div key={label} className="flex items-center justify-between p-2 rounded border border-[var(--sg-border)] bg-[var(--sg-base-deep)]">
                  <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-secondary)]">
                    {label}
                  </span>
                  <span className="font-[family-name:var(--font-mono)] text-[11px] font-medium text-[var(--sg-copper)]">
                    {formatNumber(count)}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Top 10 Holders */}
      {topHolders.length > 0 && (
        <div>
          <h3 className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-3">
            TOP ASSET HOLDERS
          </h3>
          <div className="space-y-2">
            {topHolders.map((h, i) => (
              <button
                key={h.name}
                onClick={() => onSelectOfficial?.(h.name)}
                className="w-full flex items-center gap-3 p-3 rounded border border-[var(--sg-border)] bg-[var(--sg-base-deep)] hover:bg-[var(--sg-surface-hover)] transition-colors text-left"
              >
                <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)] w-5 shrink-0">
                  #{i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="font-[family-name:var(--font-display)] text-[13px] font-semibold text-[var(--sg-text-primary)] truncate">
                    {h.name}
                  </div>
                  <div className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)] truncate">
                    {h.jabatan}
                  </div>
                </div>
                <span className="font-[family-name:var(--font-mono)] text-[13px] font-medium text-[var(--sg-copper)] shrink-0">
                  {formatRupiah(h.total_assets)}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, icon }: { label: string; value: string; icon: string }) {
  return (
    <div className="obsidian-glass rounded-lg p-4">
      <div className="relative z-10">
        <div className="flex items-center gap-2 mb-2">
          <span className="w-5 h-5 rounded flex items-center justify-center bg-[var(--sg-copper-dim)] font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-copper)]">
            {icon}
          </span>
          <span className="font-[family-name:var(--font-mono)] text-[10px] uppercase tracking-[0.08em] text-[var(--sg-text-ghost)]">
            {label}
          </span>
        </div>
        <div className="font-[family-name:var(--font-mono)] text-[20px] font-medium text-[var(--sg-copper)]">
          {value}
        </div>
      </div>
    </div>
  );
}
