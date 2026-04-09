'use client';

import { useMemo } from 'react';
import type {
  GraphStats, RelationshipIntel, HierarchyChain, SupervisesChain, PersonData,
} from '@/lib/types';
import { formatRupiah, formatNumber } from '@/lib/format';
import type { OfficialListItem } from './OfficialsList';

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
  relationships?: RelationshipIntel[];
  hierarchy?: HierarchyChain[];
  supervisesChains?: SupervisesChain[];
  persons?: PersonData[];
  officials?: OfficialListItem[];
  connectionCounts?: Map<string, number>;
}

const REL_COLORS: Record<string, string> = {
  FAMILY_OF: 'var(--sg-amber)',
  MET_WITH: 'var(--sg-periwinkle)',
  SUPERVISES: 'var(--sg-copper)',
  ALUMNI: 'var(--sg-clean)',
  PARENT_OF: 'var(--sg-amber)',
};

interface KeyFinding {
  icon: string;
  text: string;
  name: string | null;
  color: string;
}

export function StatsOverview({
  stats, topHolders, loading, onSelectOfficial,
  relationships, hierarchy, supervisesChains, persons,
  officials, connectionCounts,
}: StatsOverviewProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-text-ghost)] animate-pulse">
          Loading intelligence...
        </span>
      </div>
    );
  }

  // Compute KEY FINDINGS from available data
  const keyFindings = useMemo(() => {
    const findings: KeyFinding[] = [];

    // Richest official
    if (topHolders.length > 0) {
      const richest = topHolders[0];
      findings.push({
        icon: '\u{1F4B0}',
        text: `Richest official: ${formatRupiah(richest.total_assets)}`,
        name: richest.name,
        color: 'var(--sg-copper)',
      });
    }

    // Biggest anomaly from relationships delta data
    if (relationships && relationships.length > 0) {
      // We look for high-delta anomalies - these come from the data we can infer
      const supervisesCount = relationships.filter((r) => r.type === 'SUPERVISES').length;
      const familyCount = relationships.filter((r) => r.type === 'FAMILY_OF').length;
      const metWithCount = relationships.filter((r) => r.type === 'MET_WITH').length;

      if (metWithCount > 0) {
        findings.push({
          icon: '\u{1F91D}',
          text: `${metWithCount} documented meetings between officials`,
          name: null,
          color: 'var(--sg-periwinkle)',
        });
      }

      if (familyCount > 0) {
        findings.push({
          icon: '\u{1F46A}',
          text: `${familyCount} family relationship${familyCount === 1 ? '' : 's'} mapped`,
          name: null,
          color: 'var(--sg-amber)',
        });
      }

      if (supervisesCount > 0) {
        findings.push({
          icon: '\u{1F3DB}',
          text: `${supervisesCount} command chain${supervisesCount === 1 ? '' : 's'} identified`,
          name: null,
          color: 'var(--sg-copper)',
        });
      }
    }

    // Densest network
    if (connectionCounts && connectionCounts.size > 0) {
      let maxName = '';
      let maxCount = 0;
      for (const [name, count] of connectionCounts) {
        if (count > maxCount) {
          maxName = name;
          maxCount = count;
        }
      }
      if (maxCount > 0) {
        findings.push({
          icon: '\u{1F578}',
          text: `Densest network: ${maxCount} connections`,
          name: maxName,
          color: 'var(--sg-periwinkle)',
        });
      }
    }

    // Most properties
    if (officials && officials.length > 0) {
      const withLhkpn = officials.filter((o) => o.has_lhkpn);
      if (withLhkpn.length > 0) {
        findings.push({
          icon: '\u{1F4C8}',
          text: `${withLhkpn.length} of ${officials.length} officials have LHKPN data`,
          name: null,
          color: 'var(--sg-clean)',
        });
      }
    }

    // Persons of interest
    if (persons && persons.length > 0) {
      findings.push({
        icon: '\u{1F50D}',
        text: `${persons.length} person${persons.length === 1 ? '' : 's'} of interest identified`,
        name: null,
        color: 'var(--sg-amber)',
      });
    }

    return findings;
  }, [topHolders, relationships, connectionCounts, officials, persons]);

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      {/* Header */}
      <div>
        <h2 className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-1">
          INTELLIGENCE OVERVIEW
        </h2>
        <p className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)]">
          Select an official from the directory to view their full dossier
        </p>
      </div>

      {/* KEY FINDINGS — intelligence briefing */}
      {keyFindings.length > 0 && (
        <div className="p-4 rounded border border-[var(--sg-copper)] bg-[rgba(186,135,89,0.06)]">
          <div className="font-[family-name:var(--font-display)] text-[11px] font-bold tracking-[0.15em] uppercase text-[var(--sg-copper)] mb-3">
            KEY FINDINGS
          </div>
          <div className="space-y-2">
            {keyFindings.map((finding, idx) => (
              <div key={idx} className="flex items-start gap-2">
                <span className="text-[13px] shrink-0 leading-[20px]">{finding.icon}</span>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span
                    className="font-[family-name:var(--font-mono)] text-[11px] leading-[20px]"
                    style={{ color: finding.color }}
                  >
                    {finding.text}
                  </span>
                  {finding.name && onSelectOfficial && (
                    <button
                      onClick={() => onSelectOfficial(finding.name!)}
                      className="font-[family-name:var(--font-mono)] text-[10px] underline cursor-pointer hover:opacity-80 transition-opacity"
                      style={{ color: finding.color }}
                    >
                      {finding.name}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Primary stats */}
      {stats && (
        <div className="grid grid-cols-2 gap-3">
          <StatCard label="Graph Nodes" value={formatNumber(stats.nodes)} icon="N" />
          <StatCard label="Relationships" value={formatNumber(stats.relationships)} icon="R" />
          <StatCard label="Officials" value={formatNumber(stats.officials)} icon="O" />
          <StatCard label="LHKPN Reports" value={formatNumber(stats.lhkpn_reports)} icon="L" />
        </div>
      )}

      {/* Top 10 Holders — moved up for prominence */}
      {topHolders.length > 0 && (
        <div>
          <h3 className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-3">
            TOP ASSET HOLDERS
          </h3>
          <div className="space-y-1.5">
            {topHolders.map((h, i) => (
              <button
                key={h.name}
                onClick={() => onSelectOfficial?.(h.name)}
                className="w-full flex items-center gap-3 p-2.5 rounded border border-[var(--sg-border)] bg-[var(--sg-base-deep)] hover:bg-[var(--sg-surface-hover)] transition-colors text-left"
              >
                <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)] w-5 shrink-0">
                  #{i + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="font-[family-name:var(--font-display)] text-[12px] font-semibold text-[var(--sg-text-primary)] truncate">
                    {h.name}
                  </div>
                  <div className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)] truncate">
                    {h.jabatan}
                  </div>
                </div>
                <span className="font-[family-name:var(--font-mono)] text-[12px] font-medium text-[var(--sg-copper)] shrink-0">
                  {formatRupiah(h.total_assets)}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* SUPERVISES Chains */}
      {supervisesChains && supervisesChains.length > 0 && (
        <div>
          <h3 className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-3">
            COMMAND CHAINS
          </h3>
          <div className="space-y-2">
            {supervisesChains.map((chain, idx) => (
              <div key={idx} className="p-3 rounded border border-[var(--sg-border-copper)] bg-[var(--sg-copper-dim)]">
                <div className="flex items-center gap-1.5 flex-wrap">
                  {chain.chain.map((node, ni) => (
                    <span key={ni} className="inline-flex items-center gap-1">
                      <button
                        onClick={() => onSelectOfficial?.(node.name)}
                        className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-copper)] hover:underline cursor-pointer"
                      >
                        {node.name}
                      </button>
                      {node.jabatan && (
                        <span className="font-[family-name:var(--font-mono)] text-[8px] text-[var(--sg-text-ghost)]">
                          ({node.jabatan})
                        </span>
                      )}
                      {ni < chain.chain.length - 1 && (
                        <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)] mx-0.5">
                          &rarr;
                        </span>
                      )}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
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

      {/* Organizational Hierarchy (PART_OF) */}
      {hierarchy && hierarchy.length > 0 && (
        <div>
          <h3 className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-3">
            ORGANIZATIONAL HIERARCHY
          </h3>
          <div className="space-y-2">
            {hierarchy.map((h, idx) => (
              <div key={idx} className="p-3 rounded border border-[var(--sg-border)] bg-[var(--sg-base-deep)]">
                <div className="flex items-center gap-1.5 flex-wrap">
                  {h.chain.map((node, ni) => (
                    <span key={ni} className="inline-flex items-center gap-1">
                      <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-primary)]">
                        {node.name}
                      </span>
                      <span className="font-[family-name:var(--font-mono)] text-[8px] text-[var(--sg-text-ghost)] uppercase">
                        {node.type}
                      </span>
                      {ni < h.chain.length - 1 && (
                        <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)] mx-0.5">
                          &rarr;
                        </span>
                      )}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Intelligence Relationships (FAMILY_OF, MET_WITH with context) */}
      {relationships && relationships.length > 0 && (
        <div>
          <h3 className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-3">
            RELATIONSHIP INTEL
          </h3>
          <div className="space-y-2">
            {relationships.map((rel, idx) => {
              const color = REL_COLORS[rel.type] ?? 'var(--sg-text-secondary)';
              return (
                <div
                  key={idx}
                  className="p-2.5 rounded border bg-[var(--sg-base-deep)]"
                  style={{ borderColor: `${color}22` }}
                >
                  <div className="flex items-center gap-2 flex-wrap">
                    <button
                      onClick={() => onSelectOfficial?.(rel.from)}
                      className="font-[family-name:var(--font-mono)] text-[11px] font-medium hover:underline cursor-pointer"
                      style={{ color }}
                    >
                      {rel.from}
                    </button>
                    <span
                      className="px-1.5 py-0 rounded text-[8px] font-[family-name:var(--font-mono)] uppercase border"
                      style={{ color, borderColor: `${color}33`, backgroundColor: `${color}0d` }}
                    >
                      {rel.type.replace('_', ' ')}
                    </span>
                    <button
                      onClick={() => onSelectOfficial?.(rel.to)}
                      className="font-[family-name:var(--font-mono)] text-[11px] font-medium hover:underline cursor-pointer"
                      style={{ color }}
                    >
                      {rel.to}
                    </button>
                  </div>
                  {rel.context && (
                    <div className="font-[family-name:var(--font-mono)] text-[10px] mt-1" style={{ color, opacity: 0.8 }}>
                      &ldquo;{rel.context}&rdquo;
                    </div>
                  )}
                  {rel.predicate && (
                    <div className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)] mt-0.5">
                      {rel.predicate}
                    </div>
                  )}
                  {rel.notes && (
                    <div className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)] mt-0.5 italic">
                      {rel.notes}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Persons */}
      {persons && persons.length > 0 && (
        <div>
          <h3 className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-3">
            PERSONS OF INTEREST
          </h3>
          <div className="space-y-2">
            {persons.map((p) => (
              <div key={p.name} className="p-2.5 rounded border border-[rgba(232,168,73,0.12)] bg-[rgba(232,168,73,0.03)]">
                <div className="flex items-center gap-2">
                  <span className="font-[family-name:var(--font-mono)] text-[11px] font-medium text-[var(--sg-amber)]">
                    {p.name}
                  </span>
                  {p.person_type && (
                    <span className="px-1.5 py-0 rounded text-[8px] font-[family-name:var(--font-mono)] uppercase border border-[rgba(232,168,73,0.15)] text-[var(--sg-amber)] bg-[rgba(232,168,73,0.06)]">
                      {p.person_type}
                    </span>
                  )}
                </div>
                {p.notes && (
                  <div className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)] mt-1 italic">
                    {p.notes}
                  </div>
                )}
                {p.relationship_to_us && (
                  <div className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-amber)] mt-0.5 opacity-70">
                    {p.relationship_to_us}
                  </div>
                )}
                {p.connected_to.length > 0 && (
                  <div className="flex gap-1 flex-wrap mt-1.5">
                    {p.connected_to.map((name) => (
                      <button
                        key={name}
                        onClick={() => onSelectOfficial?.(name)}
                        className="px-1.5 py-0.5 rounded text-[9px] font-[family-name:var(--font-mono)] border border-[var(--sg-border-copper)] bg-[var(--sg-copper-dim)] text-[var(--sg-copper)] hover:bg-[rgba(186,135,89,0.15)] cursor-pointer transition-colors"
                      >
                        {name}
                      </button>
                    ))}
                  </div>
                )}
              </div>
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
