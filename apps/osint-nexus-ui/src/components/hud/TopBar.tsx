'use client';

import { useLevel } from '@/hooks/useLevel';
import { useNeo4j } from '@/hooks/useNeo4j';
import { formatNumber } from '@/lib/format';
import type { GraphStats } from '@/lib/types';

const LEVEL_LABELS: Record<string, string> = {
  orbital: 'ORBITAL VIEW',
  provincial: 'PROVINCIAL INTELLIGENCE',
  authority: 'AUTHORITY ANALYSIS',
};

export function TopBar() {
  const { state, goBack } = useLevel();
  const { data: stats } = useNeo4j<GraphStats>('/api/graph/stats');

  return (
    <div className="fixed top-0 left-0 right-0 z-40 flex items-center justify-between px-6 py-3 pointer-events-none">
      <div className="flex items-center gap-4 pointer-events-auto">
        <span className="font-[family-name:var(--font-display)] text-[15px] font-bold tracking-[0.08em] uppercase text-[var(--sg-copper)]">
          OSINT NEXUS
        </span>
        <span className="text-[var(--sg-border-copper)] select-none">/</span>
        <span className="font-[family-name:var(--font-mono)] text-[10px] tracking-[0.08em] uppercase text-[var(--sg-text-ghost)]">
          {LEVEL_LABELS[state.level]}
        </span>

        {state.province && (
          <>
            <span className="text-[var(--sg-border-copper)] select-none">/</span>
            <button
              onClick={() => { if (state.level === 'authority') goBack(); }}
              className="font-[family-name:var(--font-mono)] text-[10px] tracking-[0.08em] uppercase text-[var(--sg-text-secondary)] hover:text-[var(--sg-copper)] transition-colors"
            >
              {state.province}
            </button>
          </>
        )}
        {state.institution && (
          <>
            <span className="text-[var(--sg-border-copper)] select-none">/</span>
            <span className="font-[family-name:var(--font-mono)] text-[10px] tracking-[0.08em] uppercase text-[var(--sg-text-secondary)]">
              {state.institution}
            </span>
          </>
        )}
      </div>

      <div className="flex items-center gap-4 pointer-events-auto">
        {stats && (
          <span className="font-[family-name:var(--font-mono)] text-[10px] tracking-[0.08em] uppercase text-[var(--sg-text-ghost)]">
            {formatNumber(stats.nodes)} NODES · {formatNumber(stats.relationships)} RELS · {formatNumber(stats.lhkpn_reports)} LHKPN
          </span>
        )}
        <span className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--sg-clean)] animate-pulse" />
          <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)]">
            CONNECTED
          </span>
        </span>
      </div>
    </div>
  );
}
