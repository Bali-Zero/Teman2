'use client';

import { useState, useMemo } from 'react';
import { formatRupiah } from '@/lib/format';

export interface OfficialListItem {
  name: string;
  jabatan: string;
  nip: string | null;
  kantors: string[];
  total_assets: number;
  asset_count: number;
  has_lhkpn: boolean;
}

type SortMode = 'name' | 'assets' | 'anomaly';

interface OfficialsListProps {
  officials: OfficialListItem[];
  selected: string | null;
  anomalyNames: Set<string>;
  onSelect: (name: string) => void;
}

export function OfficialsList({ officials, selected, anomalyNames, onSelect }: OfficialsListProps) {
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<SortMode>('assets');

  const filtered = useMemo(() => {
    let list = officials;
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((o) => o.name.toLowerCase().includes(q));
    }
    const sorted = [...list];
    switch (sort) {
      case 'name':
        sorted.sort((a, b) => a.name.localeCompare(b.name));
        break;
      case 'assets':
        sorted.sort((a, b) => b.total_assets - a.total_assets);
        break;
      case 'anomaly':
        sorted.sort((a, b) => {
          const aA = anomalyNames.has(a.name) ? 1 : 0;
          const bA = anomalyNames.has(b.name) ? 1 : 0;
          if (bA !== aA) return bA - aA;
          return b.total_assets - a.total_assets;
        });
        break;
    }
    return sorted;
  }, [officials, search, sort, anomalyNames]);

  return (
    <div className="flex flex-col h-full">
      {/* Search */}
      <div className="p-3 border-b border-[var(--sg-border)]">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search officials..."
          className="w-full bg-[var(--sg-base-deep)] border border-[var(--sg-border)] rounded px-3 py-1.5 text-[12px] font-[family-name:var(--font-mono)] text-[var(--sg-text-primary)] placeholder:text-[var(--sg-text-ghost)] outline-none focus:border-[var(--sg-border-focus)] transition-colors"
        />
      </div>

      {/* Sort buttons */}
      <div className="flex gap-1 px-3 py-2 border-b border-[var(--sg-border)]">
        {(['name', 'assets', 'anomaly'] as SortMode[]).map((mode) => (
          <button
            key={mode}
            onClick={() => setSort(mode)}
            className={`px-2 py-0.5 rounded text-[9px] font-[family-name:var(--font-mono)] uppercase tracking-[0.08em] transition-colors ${
              sort === mode
                ? 'bg-[var(--sg-copper-dim)] text-[var(--sg-copper)] border border-[var(--sg-border-copper)]'
                : 'text-[var(--sg-text-ghost)] hover:text-[var(--sg-text-secondary)] border border-transparent'
            }`}
          >
            {mode === 'name' ? 'A-Z' : mode === 'assets' ? 'ASSETS' : 'ANOMALY'}
          </button>
        ))}
      </div>

      {/* Officials list */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {filtered.map((o) => {
          const isSelected = selected === o.name;
          const hasAnomaly = anomalyNames.has(o.name);

          return (
            <button
              key={o.name}
              onClick={() => onSelect(o.name)}
              className={`w-full text-left px-3 py-2.5 border-l-2 transition-all ${
                isSelected
                  ? 'border-l-[var(--sg-copper)] bg-[var(--sg-copper-dim)]'
                  : 'border-l-transparent hover:bg-[var(--sg-surface-hover)]'
              }`}
            >
              <div className="flex items-center gap-1.5">
                {hasAnomaly && (
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--sg-anomaly)] shrink-0" />
                )}
                <span
                  className={`font-[family-name:var(--font-display)] text-[13px] font-semibold truncate ${
                    isSelected ? 'text-[var(--sg-copper)]' : 'text-[var(--sg-text-primary)]'
                  }`}
                >
                  {o.name}
                </span>
              </div>
              <div className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)] mt-0.5 truncate">
                {o.jabatan || 'N/A'}
              </div>
              {o.kantors && o.kantors.filter(Boolean).length > 0 && (
                <div className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)] mt-0.5 truncate opacity-60">
                  {o.kantors.filter(Boolean).join(' \u00b7 ')}
                </div>
              )}
              <div className="font-[family-name:var(--font-mono)] text-[11px] mt-0.5">
                {o.has_lhkpn ? (
                  <span className="text-[var(--sg-copper)]">{formatRupiah(o.total_assets)}</span>
                ) : (
                  <span className="text-[var(--sg-text-ghost)]">&mdash;</span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Count footer */}
      <div className="px-3 py-2 border-t border-[var(--sg-border)]">
        <span className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)] uppercase tracking-[0.08em]">
          {filtered.length} of {officials.length} officials
        </span>
      </div>
    </div>
  );
}
