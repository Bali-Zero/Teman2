'use client';

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useNeo4j } from '@/hooks/useNeo4j';
import { OfficialsList, type OfficialListItem, type OfficialsListHandle } from '@/components/dashboard/OfficialsList';
import { OrganizationsList } from '@/components/dashboard/OrganizationsList';
import { OfficialProfile } from '@/components/dashboard/OfficialProfile';
import { AssetTimeline } from '@/components/dashboard/AssetTimeline';
import { StatsOverview } from '@/components/dashboard/StatsOverview';
import type {
  GraphStats, OfficialDetail, OrganizationData,
  RelationshipIntel, HierarchyChain, SupervisesChain, PersonData,
} from '@/lib/types';
import { formatNumber } from '@/lib/format';

type LeftTab = 'officials' | 'organizations';

export default function Home() {
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [leftTab, setLeftTab] = useState<LeftTab>('officials');
  const officialsListRef = useRef<OfficialsListHandle>(null);

  // Fetch all officials
  const { data: officialsData, loading: officialsLoading } = useNeo4j<{ officials: OfficialListItem[] }>(
    '/api/graph/officials'
  );

  // Fetch graph stats
  const { data: stats } = useNeo4j<GraphStats>('/api/graph/stats');

  // Fetch organizations
  const { data: orgsData } = useNeo4j<{ organizations: OrganizationData[] }>(
    '/api/graph/organizations'
  );

  // Fetch relationships intel
  const { data: relsData } = useNeo4j<{ relationships: RelationshipIntel[] }>(
    '/api/graph/relationships'
  );

  // Fetch hierarchy chains
  const { data: hierarchyData } = useNeo4j<{
    part_of: HierarchyChain[];
    supervises: SupervisesChain[];
  }>('/api/graph/hierarchy');

  // Fetch persons
  const { data: personsData } = useNeo4j<{ persons: PersonData[] }>(
    '/api/graph/persons'
  );

  // Fetch selected official detail
  const officialUrl = selectedName ? `/api/graph/official/${encodeURIComponent(selectedName)}` : null;
  const { data: officialDetail, loading: detailLoading } = useNeo4j<OfficialDetail>(officialUrl);

  // Determine anomaly names from officials with high delta (we only know from detail, so track across loads)
  const [anomalyNames, setAnomalyNames] = useState<Set<string>>(new Set());

  // When official detail loads, check if it has anomalies
  useEffect(() => {
    if (officialDetail && selectedName) {
      const hasAnomaly = officialDetail.delta.some((d) => Math.abs(d.pct_change) > 30);
      if (hasAnomaly) {
        setAnomalyNames((prev) => {
          if (prev.has(selectedName)) return prev;
          const next = new Set(prev);
          next.add(selectedName);
          return next;
        });
      }
    }
  }, [officialDetail, selectedName]);

  const officials = officialsData?.officials ?? [];
  const organizations = orgsData?.organizations ?? [];

  // Compute connection counts from relationships data
  const connectionCounts = useMemo(() => {
    const counts = new Map<string, number>();
    if (!relsData?.relationships) return counts;
    for (const rel of relsData.relationships) {
      counts.set(rel.from, (counts.get(rel.from) ?? 0) + 1);
      counts.set(rel.to, (counts.get(rel.to) ?? 0) + 1);
    }
    return counts;
  }, [relsData]);

  // Top 10 holders for overview
  const topHolders = useMemo(() => {
    return officials
      .filter((o) => o.has_lhkpn && o.total_assets > 0)
      .slice(0, 10)
      .map((o) => ({ name: o.name, jabatan: o.jabatan, total_assets: o.total_assets }));
  }, [officials]);

  const handleSelect = useCallback((name: string) => {
    setSelectedName((prev) => (prev === name ? null : name));
  }, []);

  // Keyboard navigation: arrow up/down in the officials list
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Only handle when not typing in an input
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

      if (leftTab !== 'officials') return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        officialsListRef.current?.navigateDown();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        officialsListRef.current?.navigateUp();
      } else if (e.key === 'Escape') {
        setSelectedName(null);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [leftTab]);

  // Header stats text
  const headerText = stats
    ? `${formatNumber(stats.officials)} Officials \u00b7 ${formatNumber(stats.lhkpn_reports)} LHKPN \u00b7 ${formatNumber(stats.nodes)} Nodes \u00b7 ${formatNumber(organizations.length)} Orgs`
    : 'Loading...';

  const showProfile = selectedName !== null;

  return (
    <div className="flex flex-col w-screen h-screen bg-[var(--sg-base)]">
      {/* Header bar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-[var(--sg-border)] bg-[var(--sg-base-deep)] shrink-0">
        <div className="flex items-center gap-3">
          <span className="font-[family-name:var(--font-display)] text-[15px] font-bold tracking-[0.08em] uppercase text-[var(--sg-copper)]">
            OSINT NEXUS
          </span>
        </div>
        <span className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-text-ghost)] tracking-[0.04em]">
          {headerText}
        </span>
      </header>

      {/* Three-column layout */}
      <div className="flex flex-1 min-h-0">
        {/* Left Panel: Directory with tab switch */}
        <div className="w-[280px] shrink-0 border-r border-[var(--sg-border)] bg-[var(--sg-base-deep)] flex flex-col">
          {/* Tab switcher */}
          <div className="flex border-b border-[var(--sg-border)]">
            <button
              onClick={() => setLeftTab('officials')}
              className={`flex-1 py-2 text-center font-[family-name:var(--font-mono)] text-[10px] uppercase tracking-[0.08em] transition-colors ${
                leftTab === 'officials'
                  ? 'text-[var(--sg-copper)] border-b-2 border-b-[var(--sg-copper)] bg-[var(--sg-copper-dim)]'
                  : 'text-[var(--sg-text-ghost)] hover:text-[var(--sg-text-secondary)]'
              }`}
            >
              Officials ({officials.length})
            </button>
            <button
              onClick={() => setLeftTab('organizations')}
              className={`flex-1 py-2 text-center font-[family-name:var(--font-mono)] text-[10px] uppercase tracking-[0.08em] transition-colors ${
                leftTab === 'organizations'
                  ? 'text-[var(--sg-periwinkle)] border-b-2 border-b-[var(--sg-periwinkle)] bg-[var(--sg-periwinkle-dim)]'
                  : 'text-[var(--sg-text-ghost)] hover:text-[var(--sg-text-secondary)]'
              }`}
            >
              Orgs ({organizations.length})
            </button>
          </div>

          {/* Tab content */}
          <div className="flex-1 min-h-0">
            {leftTab === 'officials' ? (
              officialsLoading ? (
                <div className="flex items-center justify-center flex-1 h-full">
                  <span className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-text-ghost)] animate-pulse">
                    Loading directory...
                  </span>
                </div>
              ) : (
                <OfficialsList
                  ref={officialsListRef}
                  officials={officials}
                  selected={selectedName}
                  anomalyNames={anomalyNames}
                  connectionCounts={connectionCounts}
                  onSelect={handleSelect}
                />
              )
            ) : (
              <OrganizationsList
                organizations={organizations}
                onSelectOfficial={handleSelect}
              />
            )}
          </div>
        </div>

        {/* Center Panel: Profile or Overview — thin left border when showing profile */}
        <div className={`flex-1 min-w-0 overflow-hidden ${showProfile ? 'border-l border-[var(--sg-border-copper)]' : ''}`}>
          {selectedName && officialDetail && !detailLoading ? (
            <OfficialProfile detail={officialDetail} loading={false} onSelectOfficial={handleSelect} />
          ) : selectedName && detailLoading ? (
            <OfficialProfile
              detail={{
                profile: { name: selectedName, jabatan: '', nip: null, kantor: '', pangkat: null, angkatan: null, asal: null, agama: null, ttl: null, kantors: [] },
                connections: { family: [], met_with: [], subordinates: [], supervisors: [], alumni: [], children: [], workplaces: [] },
                lhkpn_years: [],
                assets_by_year: {},
                delta: [],
              }}
              loading={true}
            />
          ) : (
            <StatsOverview
              stats={stats}
              topHolders={topHolders}
              loading={officialsLoading}
              onSelectOfficial={handleSelect}
              relationships={relsData?.relationships}
              hierarchy={hierarchyData?.part_of}
              supervisesChains={hierarchyData?.supervises}
              persons={personsData?.persons}
              officials={officials}
              connectionCounts={connectionCounts}
            />
          )}
        </div>

        {/* Right Panel: Asset Timeline */}
        <div className="w-[380px] shrink-0 border-l border-[var(--sg-border)] bg-[var(--sg-base-deep)]">
          {selectedName && officialDetail && !detailLoading && officialDetail.lhkpn_years.length > 0 ? (
            <AssetTimeline detail={officialDetail} />
          ) : selectedName && detailLoading ? (
            <div className="flex items-center justify-center h-full">
              <span className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-text-ghost)] animate-pulse">
                Loading timeline...
              </span>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full px-6">
              <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)] text-center">
                {selectedName
                  ? 'No LHKPN data for this official'
                  : 'Select an official to view asset timeline'}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Footer status bar */}
      <footer className="flex items-center justify-between px-6 py-2 border-t border-[var(--sg-border)] bg-[var(--sg-base-deep)] shrink-0">
        <span className="font-[family-name:var(--font-mono)] text-[10px] tracking-[0.08em] uppercase text-[var(--sg-text-ghost)]">
          SISMOGRAFO DEL POTERE v0.3
        </span>
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--sg-clean)]" />
          <span className="font-[family-name:var(--font-mono)] text-[10px] tracking-[0.08em] uppercase text-[var(--sg-text-ghost)]">
            bolt://localhost:17687
          </span>
        </div>
      </footer>
    </div>
  );
}
