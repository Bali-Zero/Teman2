'use client';

import type {
  OfficialDetail, FamilyConnection, MetWithConnection,
  SupervisionConnection, AlumniConnection, WorkplaceConnection,
} from '@/lib/types';
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
  const cashAmount = latestAssets?.cash ?? 0;

  // Aggregate ALL properties and vehicles across ALL years for total value
  let totalPropertyValue = 0;
  let totalVehicleValue = 0;
  const allPropertiesByYear: { year: number; count: number }[] = [];
  const allVehiclesByYear: { year: number; count: number }[] = [];
  const allPropertyCities = new Set<string>();

  for (const y of lhkpn_years) {
    const ya = assets_by_year[y];
    if (!ya) continue;
    if (ya.properties.length > 0) {
      allPropertiesByYear.push({ year: y, count: ya.properties.length });
      for (const p of ya.properties) {
        totalPropertyValue += p.nilai;
        if (p.lokasi) {
          // Extract city name (typically first word or before comma)
          const city = p.lokasi.split(',')[0].split('/')[0].trim().toUpperCase();
          if (city) allPropertyCities.add(city);
        }
      }
    }
    if (ya.vehicles.length > 0) {
      allVehiclesByYear.push({ year: y, count: ya.vehicles.length });
      for (const v of ya.vehicles) {
        totalVehicleValue += v.nilai;
      }
    }
  }

  // Latest year properties/vehicles for display
  const latestProperties = latestAssets?.properties ?? [];
  const latestVehicles = latestAssets?.vehicles ?? [];
  const propertyCount = latestProperties.length;
  const vehicleCount = latestVehicles.length;

  // Check for anomalies
  const maxDelta = delta.length > 0
    ? delta.reduce((max, d) => Math.abs(d.pct_change) > Math.abs(max.pct_change) ? d : max, delta[0])
    : null;
  const hasAnomaly = maxDelta && Math.abs(maxDelta.pct_change) > 30;

  // Count ALL connections
  const totalConnections =
    (connections.family?.length ?? 0) +
    (connections.met_with?.length ?? 0) +
    (connections.subordinates?.length ?? 0) +
    (connections.supervisors?.length ?? 0) +
    (connections.alumni?.length ?? 0) +
    (connections.children?.length ?? 0) +
    (connections.workplaces?.length ?? 0);

  // Connection type summary
  const connSummary: string[] = [];
  if ((connections.supervisors?.length ?? 0) > 0) connSummary.push(`${connections.supervisors.length} supervisor`);
  if ((connections.subordinates?.length ?? 0) > 0) connSummary.push(`${connections.subordinates.length} subordinate`);
  if ((connections.alumni?.length ?? 0) > 0) connSummary.push(`${connections.alumni.length} alumni`);
  if ((connections.family?.length ?? 0) > 0) connSummary.push(`${connections.family.length} family`);
  if ((connections.met_with?.length ?? 0) > 0) connSummary.push(`${connections.met_with.length} met_with`);
  if ((connections.workplaces?.length ?? 0) > 0) connSummary.push(`${connections.workplaces.length} workplace`);
  if ((connections.children?.length ?? 0) > 0) connSummary.push(`${connections.children.length} child`);

  // Property city summary
  const citySummary = allPropertyCities.size > 0
    ? `${propertyCount} propert${propertyCount === 1 ? 'y' : 'ies'} in ${[...allPropertyCities].join(', ')}`
    : `${propertyCount} propert${propertyCount === 1 ? 'y' : 'ies'} declared`;

  // Connections availability
  const hasFamily = (connections.family?.length ?? 0) > 0;
  const hasMetWith = (connections.met_with?.length ?? 0) > 0;
  const hasSubordinates = (connections.subordinates?.length ?? 0) > 0;
  const hasSupervisors = (connections.supervisors?.length ?? 0) > 0;
  const hasAlumni = (connections.alumni?.length ?? 0) > 0;
  const hasChildren = (connections.children?.length ?? 0) > 0;
  const hasWorkplaces = (connections.workplaces?.length ?? 0) > 0;
  const hasConnections = hasFamily || hasMetWith || hasSubordinates || hasSupervisors || hasAlumni || hasChildren || hasWorkplaces;

  // Parse TTL for display
  let ttlDisplay: string | null = null;
  if (profile.ttl) {
    ttlDisplay = profile.ttl;
  } else if (profile.asal) {
    ttlDisplay = profile.asal;
  }

  return (
    <div className="p-6 space-y-5 overflow-y-auto h-full">
      {/* DOSSIER Header */}
      <div>
        <div className="font-[family-name:var(--font-display)] text-[10px] font-bold tracking-[0.2em] uppercase text-[var(--sg-text-ghost)] mb-1">
          DOSSIER
        </div>
        <div className="w-full h-[1px] bg-[var(--sg-copper)] opacity-40 mb-3" />

        <h2 className="font-[family-name:var(--font-display)] text-[18px] font-semibold text-[var(--sg-text-primary)] leading-tight">
          {profile.name}
        </h2>
        <div className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-copper)] mt-1 uppercase tracking-wide">
          {profile.jabatan || 'N/A'}
        </div>
        {/* Kantors */}
        {profile.kantors && profile.kantors.filter(Boolean).length > 0 && (
          <div className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)] mt-0.5">
            {profile.kantors.filter(Boolean).join(' \u00b7 ')}
          </div>
        )}
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
      </div>

      {/* BIO Box */}
      {(ttlDisplay || profile.pangkat || profile.angkatan || profile.agama) && (
        <div className="p-3 rounded border border-[var(--sg-border)] bg-[var(--sg-base-deep)]">
          <div className="font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.1em] text-[var(--sg-text-ghost)] mb-2">
            BIO
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
            {ttlDisplay && (
              <BioField label="Lahir" value={ttlDisplay} />
            )}
            {profile.pangkat && (
              <BioField label="Pangkat" value={profile.pangkat} />
            )}
            {profile.angkatan && (
              <BioField label="Angkatan" value={profile.angkatan} />
            )}
            {profile.asal && !ttlDisplay?.includes(profile.asal) && (
              <BioField label="Asal" value={profile.asal} />
            )}
            {profile.agama && (
              <BioField label="Agama" value={profile.agama} />
            )}
          </div>
        </div>
      )}

      {/* INTEL SUMMARY Box */}
      {lhkpn_years.length > 0 && (
        <div className="p-3 rounded border border-[var(--sg-copper)] bg-[rgba(186,135,89,0.06)]">
          <div className="font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.1em] text-[var(--sg-copper)] mb-2 font-bold">
            INTEL SUMMARY
          </div>
          <div className="space-y-1.5">
            {/* Anomaly line */}
            {hasAnomaly && maxDelta && (
              <IntelLine
                icon={'\u{1F534}'}
                text={`ANOMALY: ${maxDelta.pct_change >= 0 ? '+' : ''}${maxDelta.pct_change.toFixed(1)}% asset growth ${maxDelta.from_year}\u2192${maxDelta.to_year}`}
                color="var(--sg-anomaly)"
              />
            )}
            {/* LHKPN filings */}
            <IntelLine
              icon={'\u{1F4CA}'}
              text={`${lhkpn_years.length} LHKPN filing${lhkpn_years.length === 1 ? '' : 's'} (${lhkpn_years[0]}-${lhkpn_years[lhkpn_years.length - 1]})`}
            />
            {/* Properties */}
            <IntelLine
              icon={'\u{1F3E0}'}
              text={citySummary}
            />
            {/* Vehicles */}
            <IntelLine
              icon={'\u{1F697}'}
              text={`${vehicleCount} vehicle${vehicleCount === 1 ? '' : 's'} declared`}
            />
            {/* Total declared */}
            <IntelLine
              icon={'\u{1F4B0}'}
              text={`${formatRupiah(totalAssets)} total declared (${latestYear})`}
              color="var(--sg-copper)"
            />
            {/* Cash */}
            {cashAmount > 0 && (
              <IntelLine
                icon={'\u{1F4B5}'}
                text={`${formatRupiah(cashAmount)} cash & equivalents (${latestYear})`}
              />
            )}
            {/* Connections */}
            {totalConnections > 0 && (
              <IntelLine
                icon={'\u{1F517}'}
                text={`${totalConnections} connection${totalConnections === 1 ? '' : 's'} (${connSummary.join(', ')})`}
              />
            )}
          </div>
        </div>
      )}

      {/* No LHKPN data notice */}
      {lhkpn_years.length === 0 && (
        <div className="p-3 rounded border border-[var(--sg-border)] bg-[var(--sg-base-deep)]">
          <div className="font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.1em] text-[var(--sg-text-ghost)] mb-2 font-bold">
            INTEL SUMMARY
          </div>
          <span className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-text-ghost)]">
            No LHKPN data available for this official
          </span>
          {totalConnections > 0 && (
            <div className="mt-2">
              <IntelLine
                icon={'\u{1F517}'}
                text={`${totalConnections} connection${totalConnections === 1 ? '' : 's'} (${connSummary.join(', ')})`}
              />
            </div>
          )}
        </div>
      )}

      {/* CONNECTIONS block — prominent */}
      {hasConnections && (
        <div>
          <div className="font-[family-name:var(--font-display)] text-[11px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-ghost)] mb-3">
            CONNECTIONS
          </div>
          <div className="w-full h-[1px] bg-[var(--sg-border)] mb-3" />

          <div className="space-y-4">
            {/* Supervisors (who supervises this official) */}
            {hasSupervisors && (
              <SupervisionGroup
                label="SUPERVISED BY"
                items={connections.supervisors}
                color="copper"
                onSelect={onSelectOfficial}
              />
            )}

            {/* Subordinates */}
            {hasSubordinates && (
              <SupervisionGroup
                label="SUPERVISES"
                items={connections.subordinates}
                color="copper"
                onSelect={onSelectOfficial}
              />
            )}

            {/* Family */}
            {hasFamily && (
              <FamilyGroup
                items={connections.family}
                onSelect={onSelectOfficial}
              />
            )}

            {/* Children */}
            {hasChildren && (
              <div>
                <div className="font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.08em] text-[var(--sg-text-ghost)] mb-1.5">
                  PARENT OF
                </div>
                <div className="flex gap-1.5 flex-wrap">
                  {connections.children.map((c) => (
                    <span
                      key={c.name}
                      className="inline-flex items-center px-2.5 py-1.5 rounded text-[10px] font-[family-name:var(--font-mono)] border border-[rgba(232,168,73,0.15)] bg-[rgba(232,168,73,0.06)] text-[var(--sg-amber)]"
                    >
                      {c.name}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Met With — context is KEY intel */}
            {hasMetWith && (
              <MetWithGroup
                items={connections.met_with}
                onSelect={onSelectOfficial}
              />
            )}

            {/* Alumni */}
            {hasAlumni && (
              <AlumniGroup
                items={connections.alumni}
                onSelect={onSelectOfficial}
              />
            )}

            {/* Workplaces — ALL types including Kanim_Office */}
            {hasWorkplaces && (
              <WorkplacesGroup
                items={connections.workplaces}
                onSelect={onSelectOfficial}
              />
            )}
          </div>
        </div>
      )}

      {/* LHKPN years badge row */}
      {lhkpn_years.length > 0 && (
        <div>
          <div className="font-[family-name:var(--font-display)] text-[11px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-ghost)] mb-2">
            LHKPN YEARS
          </div>
          <div className="w-full h-[1px] bg-[var(--sg-border)] mb-2" />
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
      {latestProperties.length > 0 && (
        <div>
          <div className="font-[family-name:var(--font-display)] text-[11px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-ghost)] mb-2">
            PROPERTIES &middot; {latestProperties.length}
          </div>
          <div className="w-full h-[1px] bg-[var(--sg-border)] mb-2" />
          <PropertyCards properties={latestProperties} />
        </div>
      )}

      {/* Vehicles */}
      {latestVehicles.length > 0 && (
        <div>
          <div className="font-[family-name:var(--font-display)] text-[11px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-ghost)] mb-2">
            VEHICLES &middot; {latestVehicles.length}
          </div>
          <div className="w-full h-[1px] bg-[var(--sg-border)] mb-2" />
          <VehicleCards vehicles={latestVehicles} />
        </div>
      )}
    </div>
  );
}

/* --- BIO Field --- */
function BioField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)]">{label}: </span>
      <span className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-text-primary)] font-medium">{value}</span>
    </div>
  );
}

/* --- Intel Line --- */
function IntelLine({ icon, text, color }: { icon: string; text: string; color?: string }) {
  return (
    <div className="flex items-start gap-2">
      <span className="text-[12px] shrink-0 leading-[18px]">{icon}</span>
      <span
        className="font-[family-name:var(--font-mono)] text-[10px] leading-[18px]"
        style={{ color: color ?? 'var(--sg-text-secondary)' }}
      >
        {text}
      </span>
    </div>
  );
}

/* --- Family Group --- */
function FamilyGroup({
  items,
  onSelect,
}: {
  items: FamilyConnection[];
  onSelect?: (name: string) => void;
}) {
  return (
    <div>
      <div className="font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.08em] text-[var(--sg-text-ghost)] mb-1.5">
        FAMILY
      </div>
      <div className="space-y-1.5">
        {items.map((item) => {
          const isOfficial = item.type === 'Official';
          return (
            <div key={item.name} className="flex flex-col gap-0.5">
              <button
                onClick={() => isOfficial && onSelect?.(item.name)}
                disabled={!isOfficial || !onSelect}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-[family-name:var(--font-mono)] border transition-colors self-start ${
                  isOfficial
                    ? 'border-[rgba(232,168,73,0.2)] bg-[rgba(232,168,73,0.06)] text-[var(--sg-amber)] hover:bg-[rgba(232,168,73,0.12)] cursor-pointer'
                    : 'border-[rgba(232,168,73,0.15)] bg-[rgba(232,168,73,0.04)] text-[var(--sg-amber)] cursor-default'
                }`}
              >
                {item.name}
                <span className="text-[8px] opacity-60 uppercase">{item.type}</span>
                {item.person_type && (
                  <span className="text-[8px] opacity-50">({item.person_type})</span>
                )}
              </button>
              {item.notes && (
                <div className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)] ml-2 italic">
                  {item.notes}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* --- Met With Group --- */
function MetWithGroup({
  items,
  onSelect,
}: {
  items: MetWithConnection[];
  onSelect?: (name: string) => void;
}) {
  return (
    <div>
      <div className="font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.08em] text-[var(--sg-text-ghost)] mb-1.5">
        MET WITH
      </div>
      <div className="space-y-2">
        {items.map((item) => {
          const isOfficial = item.type === 'Official';
          return (
            <div
              key={`${item.name}-${item.context ?? ''}`}
              className="p-2.5 rounded border border-[rgba(139,156,247,0.15)] bg-[rgba(139,156,247,0.04)]"
            >
              <div className="flex items-center gap-2">
                <button
                  onClick={() => isOfficial && onSelect?.(item.name)}
                  disabled={!isOfficial || !onSelect}
                  className={`font-[family-name:var(--font-mono)] text-[11px] font-medium transition-colors ${
                    isOfficial
                      ? 'text-[var(--sg-periwinkle)] hover:underline cursor-pointer'
                      : 'text-[var(--sg-periwinkle)] cursor-default'
                  }`}
                >
                  {item.name}
                </button>
                <span className="text-[8px] font-[family-name:var(--font-mono)] text-[var(--sg-text-ghost)] uppercase">
                  {item.type}
                </span>
              </div>
              {item.context && (
                <div className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-periwinkle)] mt-1 opacity-80">
                  &ldquo;{item.context}&rdquo;
                </div>
              )}
              {item.predicate && (
                <div className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)] mt-0.5">
                  {item.predicate}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* --- Supervision Group --- */
function SupervisionGroup({
  label,
  items,
  color,
  onSelect,
}: {
  label: string;
  items: SupervisionConnection[];
  color: 'copper' | 'periwinkle';
  onSelect?: (name: string) => void;
}) {
  const borderColor = color === 'copper' ? 'var(--sg-border-copper)' : 'rgba(139,156,247,0.12)';
  const bgColor = color === 'copper' ? 'var(--sg-copper-dim)' : 'rgba(139,156,247,0.04)';
  const textColor = color === 'copper' ? 'var(--sg-copper)' : 'var(--sg-periwinkle)';

  return (
    <div>
      <div className="font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.08em] text-[var(--sg-text-ghost)] mb-1.5">
        {label}
      </div>
      <div className="space-y-1.5">
        {items.map((item) => (
          <button
            key={item.name}
            onClick={() => onSelect?.(item.name)}
            className="w-full text-left flex flex-col items-start px-3 py-2 rounded text-[11px] font-[family-name:var(--font-mono)] border transition-colors cursor-pointer hover:opacity-80"
            style={{ borderColor, backgroundColor: bgColor, color: textColor }}
          >
            <span className="font-medium">{item.name}</span>
            {item.jabatan && (
              <span className="text-[9px] opacity-60 mt-0.5">{item.jabatan}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

/* --- Alumni Group --- */
function AlumniGroup({
  items,
  onSelect,
}: {
  items: AlumniConnection[];
  onSelect?: (name: string) => void;
}) {
  return (
    <div>
      <div className="font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.08em] text-[var(--sg-text-ghost)] mb-1.5">
        ALUMNI
      </div>
      <div className="flex gap-1.5 flex-wrap">
        {items.map((item) => (
          <button
            key={item.name}
            onClick={() => onSelect?.(item.name)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-[family-name:var(--font-mono)] border border-[rgba(94,196,144,0.2)] bg-[rgba(94,196,144,0.06)] text-[var(--sg-clean)] hover:bg-[rgba(94,196,144,0.12)] cursor-pointer transition-colors"
          >
            {item.name}
            {item.angkatan && (
              <span className="text-[8px] opacity-60">Angk. {item.angkatan}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

/* --- Workplaces Group --- show ALL workplaces including Kanim_Office */
function WorkplacesGroup({
  items,
  onSelect,
}: {
  items: WorkplaceConnection[];
  onSelect?: (name: string) => void;
}) {
  if (items.length === 0) return null;

  return (
    <div>
      <div className="font-[family-name:var(--font-mono)] text-[9px] uppercase tracking-[0.08em] text-[var(--sg-text-ghost)] mb-1.5">
        WORKPLACES
      </div>
      <div className="space-y-1.5">
        {items.map((item) => (
          <div
            key={item.name}
            className="p-2.5 rounded border border-[var(--sg-border)] bg-[var(--sg-base)]"
          >
            <div className="flex items-center gap-2">
              <span className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-text-secondary)] font-medium">
                {item.name}
              </span>
              <span className="text-[8px] font-[family-name:var(--font-mono)] text-[var(--sg-text-ghost)] uppercase px-1 py-0 rounded border border-[var(--sg-border)] bg-[var(--sg-base-deep)]">
                {item.type}
              </span>
            </div>
            {item.jabatan && (
              <div className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)] mt-0.5">
                Jabatan: {item.jabatan}
              </div>
            )}
            {item.context && (
              <div className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)] mt-0.5 italic">
                {item.context}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
