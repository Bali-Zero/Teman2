'use client';

import { useState, useMemo, forwardRef, useImperativeHandle, useCallback } from 'react';
import { formatRupiah } from '@/lib/format';

export interface OfficialListItem {
  name: string;
  jabatan: string;
  nip: string | null;
  pangkat: string | null;
  angkatan: string | null;
  asal: string | null;
  agama: string | null;
  ttl: string | null;
  kantors: string[];
  total_assets: number;
  asset_count: number;
  has_lhkpn: boolean;
  connection_count?: number;
}

type SortMode = 'name' | 'assets' | 'anomaly';

interface OfficialsListProps {
  officials: OfficialListItem[];
  selected: string | null;
  anomalyNames: Set<string>;
  connectionCounts: Map<string, number>;
  onSelect: (name: string) => void;
}

export interface OfficialsListHandle {
  navigateUp: () => void;
  navigateDown: () => void;
  getFilteredNames: () => string[];
}

export const OfficialsList = forwardRef<OfficialsListHandle, OfficialsListProps>(
  function OfficialsList({ officials, selected, anomalyNames, connectionCounts, onSelect }, ref) {
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<SortMode>('assets');

  const filtered = useMemo(() => {
    let list = officials;
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((o) => o.name.toLowerCase().includes(q) || (o.nip && o.nip.includes(q)));
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

  const navigateUp = useCallback(() => {
    if (filtered.length === 0) return;
    const idx = selected ? filtered.findIndex((o) => o.name === selected) : -1;
    const newIdx = idx <= 0 ? filtered.length - 1 : idx - 1;
    onSelect(filtered[newIdx].name);
  }, [filtered, selected, onSelect]);

  const navigateDown = useCallback(() => {
    if (filtered.length === 0) return;
    const idx = selected ? filtered.findIndex((o) => o.name === selected) : -1;
    const newIdx = idx >= filtered.length - 1 ? 0 : idx + 1;
    onSelect(filtered[newIdx].name);
  }, [filtered, selected, onSelect]);

  useImperativeHandle(ref, () => ({
    navigateUp,
    navigateDown,
    getFilteredNames: () => filtered.map((o) => o.name),
  }), [navigateUp, navigateDown, filtered]);

  return (
    <div className="flex flex-col h-full">
      {/* Search */}
      <div className="p-3 border-b border-[var(--sg-border)]">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search name or NIP..."
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
          const connCount = connectionCounts.get(o.name) ?? 0;

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
              {/* Row 1: Name + anomaly + connection badge */}
              <div className="flex items-center gap-1.5">
                {hasAnomaly && (
                  <span className="text-[10px] text-[var(--sg-anomaly)] shrink-0">&#9888;</span>
                )}
                <span
                  className={`font-[family-name:var(--font-display)] text-[13px] font-semibold truncate flex-1 ${
                    isSelected ? 'text-[var(--sg-copper)]' : 'text-[var(--sg-text-primary)]'
                  }`}
                >
                  {o.name}
                </span>
                {connCount > 0 && (
                  <span className="inline-flex items-center gap-0.5 px-1.5 py-0 rounded-full text-[8px] font-[family-name:var(--font-mono)] bg-[var(--sg-copper-dim)] text-[var(--sg-copper)] border border-[var(--sg-border-copper)] shrink-0">
                    <span className="opacity-70">&#128279;</span>{connCount}
                  </span>
                )}
              </div>

              {/* Row 2: Jabatan + Pangkat */}
              <div className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)] mt-0.5 truncate">
                {o.jabatan || 'N/A'}{o.pangkat ? ` \u00b7 ${o.pangkat}` : ''}
              </div>

              {/* Row 3: Kantor */}
              {o.kantors && o.kantors.filter(Boolean).length > 0 && (
                <div className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)] mt-0.5 truncate opacity-60">
                  {o.kantors.filter(Boolean).join(' \u00b7 ')}
                </div>
              )}

              {/* Row 4: Angkatan + Asal tags */}
              {(o.angkatan || o.asal) && (
                <div className="flex gap-1 flex-wrap mt-1">
                  {o.angkatan && (
                    <span className="px-1.5 py-0 rounded text-[8px] font-[family-name:var(--font-mono)] bg-[rgba(94,196,144,0.08)] text-[var(--sg-clean)] border border-[rgba(94,196,144,0.15)]">
                      Angk. {o.angkatan}
                    </span>
                  )}
                  {o.asal && (
                    <span className="px-1.5 py-0 rounded text-[8px] font-[family-name:var(--font-mono)] bg-[rgba(139,156,247,0.08)] text-[var(--sg-periwinkle)] border border-[rgba(139,156,247,0.12)]">
                      {o.asal}
                    </span>
                  )}
                </div>
              )}

              {/* Row 5: Asset value + NIP */}
              <div className="flex items-center justify-between mt-0.5">
                <div className="font-[family-name:var(--font-mono)] text-[11px]">
                  {o.has_lhkpn ? (
                    <span className="text-[var(--sg-copper)]">{formatRupiah(o.total_assets)}</span>
                  ) : (
                    <span className="text-[var(--sg-text-ghost)]">&mdash;</span>
                  )}
                </div>
                {o.nip && (
                  <span className="font-[family-name:var(--font-mono)] text-[7px] text-[var(--sg-text-ghost)] opacity-50">
                    {o.nip}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Count footer */}
      <div className="px-3 py-2 border-t border-[var(--sg-border)]">
        <span className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)] uppercase tracking-[0.08em]">
          {filtered.length} of {officials.length} officials &middot; &#8593;&#8595; navigate
        </span>
      </div>
    </div>
  );
});
