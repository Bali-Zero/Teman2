'use client';

import type { OfficialDetail } from '@/lib/types';
import { formatRupiah } from '@/lib/format';
import { PropertyCards, VehicleCards } from '@/components/timeline/PropertyCard';

interface OfficialProfileProps {
  detail: OfficialDetail;
  loading: boolean;
  onSelectOfficial?: (name: string) => void;
}

export function OfficialProfile({ detail, loading, onSelectOfficial }: OfficialProfileProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <span className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-text-ghost)] animate-pulse">
          Loading profile...
        </span>
      </div>
    );
  }

  const { profile, connections, lhkpn_years, assets_by_year, delta } = detail;

  // Aggregate totals from latest year
  const latestYear = lhkpn_years.length > 0 ? lhkpn_years[lhkpn_years.length - 1] : null;
  const latestAssets = latestYear !== null ? assets_by_year[latestYear] : null;

  const totalAssets = latestAssets?.total ?? 0;
  const propertyCount = latestAssets?.properties.length ?? 0;
  const vehicleCount = latestAssets?.vehicles.length ?? 0;
  const cashAmount = latestAssets?.cash ?? 0;

  // Check for anomalies
  const maxDelta = delta.length > 0
    ? delta.reduce((max, d) => Math.abs(d.pct_change) > Math.abs(max.pct_change) ? d : max, delta[0])
    : null;
  const hasAnomaly = maxDelta && Math.abs(maxDelta.pct_change) > 30;

  // Collect all properties and vehicles across all years (deduplicated by latest year)
  const allProperties = latestAssets?.properties ?? [];
  const allVehicles = latestAssets?.vehicles ?? [];

  // Personal info tags (only non-empty)
  const personalTags: { label: string; value: string }[] = [];
  if (profile.pangkat) personalTags.push({ label: 'Pangkat', value: profile.pangkat });
  if (profile.angkatan) personalTags.push({ label: 'Angkatan', value: profile.angkatan });
  if (profile.asal) personalTags.push({ label: 'Asal', value: profile.asal });
  if (profile.agama) personalTags.push({ label: 'Agama', value: profile.agama });
  if (profile.ttl) personalTags.push({ label: 'TTL', value: profile.ttl });

  // Connections
  const hasConnections = connections &&
    ((connections.family?.length ?? 0) > 0 ||
     (connections.met_with?.length ?? 0) > 0 ||
     (connections.supervises?.length ?? 0) > 0);

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      {/* Header block */}
      <div>
        <h2 className="font-[family-name:var(--font-display)] text-[16px] font-semibold text-[var(--sg-text-primary)]">
          {profile.name}
        </h2>
        <div className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-text-ghost)] mt-1">
          {profile.jabatan || 'N/A'}
        </div>
        {/* Kantors */}
        {profile.kantors && profile.kantors.filter(Boolean).length > 0 && (
          <div className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)] mt-0.5">
            {profile.kantors.filter(Boolean).join(' \u00b7 ')}
          </div>
        )}
        {/* Fallback single kantor */}
        {(!profile.kantors || profile.kantors.filter(Boolean).length === 0) && profile.kantor && (
          <div className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)] mt-0.5">
            {profile.kantor}
          </div>
        )}
        {profile.nip && (
          <div className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)] mt-0.5">
            NIP: {profile.nip}
          </div>
        )}

        {/* Personal info tags */}
        {personalTags.length > 0 && (
          <div className="flex gap-1.5 flex-wrap mt-2">
            {personalTags.map((tag) => (
              <span
                key={tag.label}
                className="px-2 py-0.5 rounded text-[9px] font-[family-name:var(--font-mono)] bg-[var(--sg-base-deep)] text-[var(--sg-text-secondary)] border border-[var(--sg-border)]"
              >
                {tag.label}: {tag.value}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Connections block */}
      {hasConnections && (
        <div className="p-4 rounded border border-[var(--sg-border)] bg-[var(--sg-base-deep)]">
          <div className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-3">
            CONNECTIONS
          </div>
          <div className="space-y-3">
            {connections.family && connections.family.length > 0 && (
              <ConnectionGroup
                label="FAMILY"
                items={connections.family.map((f) => ({ name: f.name, badge: f.type }))}
                onSelect={onSelectOfficial}
              />
            )}
            {connections.met_with && connections.met_with.length > 0 && (
              <ConnectionGroup
                label="MET WITH"
                items={connections.met_with.map((m) => ({ name: m.name, badge: m.type }))}
                onSelect={onSelectOfficial}
              />
            )}
            {connections.supervises && connections.supervises.length > 0 && (
              <ConnectionGroup
                label="SUPERVISES"
                items={connections.supervises.map((s) => ({ name: s.name, badge: 'Official' }))}
                onSelect={onSelectOfficial}
              />
            )}
          </div>
        </div>
      )}

      {/* Summary cards */}
      {lhkpn_years.length > 0 && (
        <div className="grid grid-cols-4 gap-3">
          <SummaryCard icon="Rp" label="TOTAL ASSETS" value={formatRupiah(totalAssets)} />
          <SummaryCard icon="P" label="PROPERTIES" value={String(propertyCount)} />
          <SummaryCard icon="V" label="VEHICLES" value={String(vehicleCount)} />
          <SummaryCard icon="$" label="CASH" value={formatRupiah(cashAmount)} />
        </div>
      )}

      {/* No LHKPN data */}
      {lhkpn_years.length === 0 && (
        <div className="p-4 rounded border border-[var(--sg-border)] bg-[var(--sg-base-deep)]">
          <span className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-text-ghost)]">
            No LHKPN data available for this official
          </span>
        </div>
      )}

      {/* Anomaly banner */}
      {hasAnomaly && maxDelta && (
        <div className="p-3 rounded border border-[var(--sg-anomaly)] bg-[rgba(232,113,108,0.08)]">
          <div className="flex items-center gap-2">
            <span className="text-[var(--sg-anomaly)] text-[14px]">&#9888;</span>
            <div>
              <div className="font-[family-name:var(--font-display)] text-[12px] font-semibold text-[var(--sg-anomaly)]">
                ANOMALY DETECTED
              </div>
              <div className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-secondary)] mt-0.5">
                {maxDelta.from_year}&rarr;{maxDelta.to_year}: {maxDelta.pct_change >= 0 ? '+' : ''}{maxDelta.pct_change.toFixed(0)}% asset change
              </div>
            </div>
          </div>
        </div>
      )}

      {/* LHKPN years badge row */}
      {lhkpn_years.length > 0 && (
        <div>
          <div className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-2">
            LHKPN YEARS
          </div>
          <div className="flex gap-1.5 flex-wrap">
            {lhkpn_years.map((y) => (
              <span
                key={y}
                className="px-2 py-0.5 rounded text-[10px] font-[family-name:var(--font-mono)] bg-[var(--sg-copper-dim)] text-[var(--sg-copper)] border border-[var(--sg-border-copper)]"
              >
                {y}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Properties */}
      {allProperties.length > 0 && <PropertyCards properties={allProperties} />}

      {/* Vehicles */}
      {allVehicles.length > 0 && <VehicleCards vehicles={allVehicles} />}
    </div>
  );
}

function ConnectionGroup({
  label,
  items,
  onSelect,
}: {
  label: string;
  items: { name: string; badge: string }[];
  onSelect?: (name: string) => void;
}) {
  return (
    <div>
      <div className="font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.08em] text-[var(--sg-text-ghost)] mb-1.5">
        {label}
      </div>
      <div className="flex gap-1.5 flex-wrap">
        {items.map((item) => {
          const isOfficial = item.badge === 'Official';
          return (
            <button
              key={item.name}
              onClick={() => isOfficial && onSelect?.(item.name)}
              disabled={!isOfficial || !onSelect}
              className={`inline-flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-[family-name:var(--font-mono)] border transition-colors ${
                isOfficial
                  ? 'border-[var(--sg-border-copper)] bg-[var(--sg-copper-dim)] text-[var(--sg-copper)] hover:bg-[rgba(186,135,89,0.15)] cursor-pointer'
                  : 'border-[var(--sg-border)] bg-[var(--sg-base)] text-[var(--sg-text-secondary)] cursor-default'
              }`}
            >
              {item.name}
              <span className="text-[8px] opacity-60 uppercase">{item.badge}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SummaryCard({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div className="obsidian-glass rounded-lg p-3">
      <div className="relative z-10">
        <div className="flex items-center gap-1.5 mb-1.5">
          <span className="w-4 h-4 rounded flex items-center justify-center bg-[var(--sg-copper-dim)] font-[family-name:var(--font-mono)] text-[8px] text-[var(--sg-copper)]">
            {icon}
          </span>
          <span className="font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.08em] text-[var(--sg-text-ghost)]">
            {label}
          </span>
        </div>
        <div className="font-[family-name:var(--font-mono)] text-[14px] font-medium text-[var(--sg-copper)]">
          {value}
        </div>
      </div>
    </div>
  );
}
