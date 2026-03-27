'use client';

import { cn } from '@/lib/utils';

interface KBLIFiltersProps {
  pmaFilter: string | null;
  transitionFilter: string | null;
  onPMAChange: (value: string | null) => void;
  onTransitionChange: (value: string | null) => void;
  counts?: {
    pma: { all: number; open: number; restricted: number; closed: number };
    transition: { new: number; merged: number; renamed: number };
  };
}

function Chip({
  active,
  onClick,
  children,
  count,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  count?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-full border px-3 py-1 text-xs font-medium transition-all backdrop-blur-md',
        active
          ? 'border-[var(--kbli-accent)] bg-[var(--kbli-accent)]/10 text-[var(--kbli-accent)] shadow-[0_0_12px_rgba(220,38,38,0.2)]'
          : 'border-white/10 bg-white/5 text-[var(--foreground-muted)] hover:bg-white/10 hover:border-white/20 hover:text-[var(--foreground)]'
      )}
      aria-pressed={active}
    >
      {children}
      {count !== undefined && (
        <span className="ml-1 opacity-60" aria-label={`${count} results`}>
          {count}
        </span>
      )}
    </button>
  );
}

export function KBLIFilters({
  pmaFilter,
  transitionFilter,
  onPMAChange,
  onTransitionChange,
  counts,
}: KBLIFiltersProps) {
  const hasActiveFilters = pmaFilter !== null || transitionFilter !== null;

  const resetAll = () => {
    onPMAChange(null);
    onTransitionChange(null);
  };

  return (
    <div className="space-y-3" role="group" aria-label="Filter KBLI codes">
      {/* PMA Status */}
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Investment filter">
        <span className="w-20 shrink-0 text-xs font-medium text-[var(--foreground-muted)]">
          Investment:
        </span>
        <Chip active={!pmaFilter} onClick={() => onPMAChange(null)}>
          All
        </Chip>
        <Chip
          active={pmaFilter === 'open'}
          onClick={() => onPMAChange(pmaFilter === 'open' ? null : 'open')}
          count={counts?.pma.open}
        >
          ✅ Open
        </Chip>
        <Chip
          active={pmaFilter === 'restricted'}
          onClick={() => onPMAChange(pmaFilter === 'restricted' ? null : 'restricted')}
          count={counts?.pma.restricted}
        >
          ⚠️ Restricted
        </Chip>
        <Chip
          active={pmaFilter === 'closed'}
          onClick={() => onPMAChange(pmaFilter === 'closed' ? null : 'closed')}
          count={counts?.pma.closed}
        >
          🚫 Closed
        </Chip>
      </div>

      {/* 2020→2025 Transition */}
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="2025 status filter">
        <span className="w-20 shrink-0 text-xs font-medium text-[var(--foreground-muted)]">
          2025 Status:
        </span>
        <Chip active={!transitionFilter} onClick={() => onTransitionChange(null)}>
          All
        </Chip>
        <Chip
          active={transitionFilter === 'BPS_ONLY'}
          onClick={() => onTransitionChange(transitionFilter === 'BPS_ONLY' ? null : 'BPS_ONLY')}
          count={counts?.transition.new}
        >
          🆕 New
        </Chip>
        <Chip
          active={transitionFilter === 'MATCH_CON_AGGREGAZIONE'}
          onClick={() =>
            onTransitionChange(
              transitionFilter === 'MATCH_CON_AGGREGAZIONE' ? null : 'MATCH_CON_AGGREGAZIONE'
            )
          }
          count={counts?.transition.merged}
        >
          🔀 Merged
        </Chip>
        <Chip
          active={transitionFilter === 'CODICE_RINUMERATO'}
          onClick={() =>
            onTransitionChange(
              transitionFilter === 'CODICE_RINUMERATO' ? null : 'CODICE_RINUMERATO'
            )
          }
          count={counts?.transition.renamed}
        >
          🔄 Renumbered
        </Chip>

        {/* Reset all filters */}
        {hasActiveFilters && (
          <button
            type="button"
            onClick={resetAll}
            className="ml-2 rounded-full border border-white/20 bg-white/5 px-3 py-1 text-xs font-medium text-[var(--foreground-muted)] transition-all hover:bg-white/10 hover:border-white/30 hover:text-white"
            aria-label="Reset all filters"
          >
            ✕ Reset all
          </button>
        )}
      </div>
    </div>
  );
}
