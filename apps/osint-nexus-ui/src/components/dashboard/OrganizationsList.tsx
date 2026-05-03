'use client';

import { useState, useMemo } from 'react';
import type { OrganizationData } from '@/lib/types';

type OrgSortMode = 'count' | 'name' | 'type';

interface OrganizationsListProps {
  organizations: OrganizationData[];
  onSelectOfficial: (name: string) => void;
}

const TYPE_COLORS: Record<string, string> = {
  pt: 'var(--sg-copper)',
  KANTOR: 'var(--sg-periwinkle)',
  MEDIA: 'var(--sg-amber)',
  ORGANISASI: 'var(--sg-clean)',
  LEMBAGA_PENYIDIK: 'var(--sg-anomaly)',
};

export function OrganizationsList({ organizations, onSelectOfficial }: OrganizationsListProps) {
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<OrgSortMode>('count');
  const [expanded, setExpanded] = useState<string | null>(null);

  const filtered = useMemo(() => {
    let list = organizations;
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter((o) =>
        o.name.toLowerCase().includes(q) ||
        (o.tipe ?? '').toLowerCase().includes(q) ||
        (o.lokasi ?? '').toLowerCase().includes(q)
      );
    }
    const sorted = [...list];
    switch (sort) {
      case 'count':
        sorted.sort((a, b) => b.official_count - a.official_count);
        break;
      case 'name':
        sorted.sort((a, b) => a.name.localeCompare(b.name));
        break;
      case 'type':
        sorted.sort((a, b) => (a.tipe ?? '').localeCompare(b.tipe ?? ''));
        break;
    }
    return sorted;
  }, [organizations, search, sort]);

  return (
    <div className="flex flex-col h-full">
      {/* Search */}
      <div className="p-3 border-b border-[var(--sg-border)]">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search organizations..."
          className="w-full bg-[var(--sg-base-deep)] border border-[var(--sg-border)] rounded px-3 py-1.5 text-[12px] font-[family-name:var(--font-mono)] text-[var(--sg-text-primary)] placeholder:text-[var(--sg-text-ghost)] outline-none focus:border-[var(--sg-border-focus)] transition-colors"
        />
      </div>

      {/* Sort buttons */}
      <div className="flex gap-1 px-3 py-2 border-b border-[var(--sg-border)]">
        {(['count', 'name', 'type'] as OrgSortMode[]).map((mode) => (
          <button
            key={mode}
            onClick={() => setSort(mode)}
            className={`px-2 py-0.5 rounded text-[9px] font-[family-name:var(--font-mono)] uppercase tracking-[0.08em] transition-colors ${
              sort === mode
                ? 'bg-[var(--sg-copper-dim)] text-[var(--sg-copper)] border border-[var(--sg-border-copper)]'
                : 'text-[var(--sg-text-ghost)] hover:text-[var(--sg-text-secondary)] border border-transparent'
            }`}
          >
            {mode === 'count' ? 'OFFICIALS' : mode === 'name' ? 'A-Z' : 'TYPE'}
          </button>
        ))}
      </div>

      {/* Organizations list */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {filtered.map((org) => {
          const isExpanded = expanded === org.name;
          const typeColor = TYPE_COLORS[org.tipe ?? ''] ?? 'var(--sg-text-secondary)';

          return (
            <div key={org.name} className="border-b border-[var(--sg-border)]">
              <button
                onClick={() => setExpanded(isExpanded ? null : org.name)}
                className={`w-full text-left px-3 py-2.5 transition-all ${
                  isExpanded
                    ? 'bg-[var(--sg-copper-dim)] border-l-2 border-l-[var(--sg-copper)]'
                    : 'hover:bg-[var(--sg-surface-hover)] border-l-2 border-l-transparent'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="font-[family-name:var(--font-display)] text-[12px] font-semibold text-[var(--sg-text-primary)] truncate flex-1">
                    {org.name}
                  </span>
                  <span
                    className="font-[family-name:var(--font-mono)] text-[10px] font-medium shrink-0"
                    style={{ color: typeColor }}
                  >
                    {org.official_count}
                  </span>
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  {org.tipe && (
                    <span
                      className="px-1.5 py-0 rounded text-[8px] font-[family-name:var(--font-mono)] uppercase border"
                      style={{ color: typeColor, borderColor: `${typeColor}33`, backgroundColor: `${typeColor}0d` }}
                    >
                      {org.tipe}
                    </span>
                  )}
                  {org.lokasi && (
                    <span className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)] truncate">
                      {org.lokasi}
                    </span>
                  )}
                </div>
              </button>

              {/* Expanded: show officials */}
              {isExpanded && org.officials.length > 0 && (
                <div className="px-3 py-2 bg-[var(--sg-base-deep)] border-l-2 border-l-[var(--sg-copper)]">
                  <div className="font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.08em] text-[var(--sg-text-ghost)] mb-1.5">
                    CONNECTED OFFICIALS
                  </div>
                  <div className="flex gap-1 flex-wrap">
                    {org.officials.map((name) => (
                      <button
                        key={name}
                        onClick={() => onSelectOfficial(name)}
                        className="px-2 py-0.5 rounded text-[10px] font-[family-name:var(--font-mono)] border border-[var(--sg-border-copper)] bg-[var(--sg-copper-dim)] text-[var(--sg-copper)] hover:bg-[rgba(186,135,89,0.15)] cursor-pointer transition-colors"
                      >
                        {name}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Count footer */}
      <div className="px-3 py-2 border-t border-[var(--sg-border)]">
        <span className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)] uppercase tracking-[0.08em]">
          {filtered.length} of {organizations.length} organizations
        </span>
      </div>
    </div>
  );
}
