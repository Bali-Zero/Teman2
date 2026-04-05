'use client';

import { usePrimeNexus, type IntelligenceFeature } from '@/contexts/PrimeNexusContext';

interface ZoneDensity {
  zone_code: string;
  zone_name: string | null;
  count: number;
}

function computeZoneDensities(features: IntelligenceFeature[]): ZoneDensity[] {
  const map = new Map<string, ZoneDensity>();
  for (const f of features) {
    const code = f.properties.zone_code ?? '__unzoned__';
    const name = f.properties.zone_name ?? null;
    const existing = map.get(code);
    if (existing) {
      existing.count += 1;
    } else {
      map.set(code, { zone_code: code, zone_name: name, count: 1 });
    }
  }
  return Array.from(map.values()).sort((a, b) => b.count - a.count);
}

function StatCard({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <div className="rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-center">
      <p className={`text-lg font-bold ${accent ? 'text-[#d4845a]' : 'text-white'}`}>{value}</p>
      <p className="text-[10px] text-slate-500 mt-0.5 leading-tight">{label}</p>
    </div>
  );
}

function ZoneDensityRow({ rank, density }: { rank: number; density: ZoneDensity }) {
  const isMissing = density.zone_code === '__unzoned__';
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-xl hover:bg-white/5 transition-colors">
      <span className="w-5 h-5 rounded-full bg-white/10 flex items-center justify-center text-[10px] font-bold text-slate-400 shrink-0">
        {rank}
      </span>
      <div className="flex-1 min-w-0">
        {isMissing ? (
          <p className="text-xs text-slate-500 italic">Not geocoded</p>
        ) : (
          <>
            <p className="text-xs font-semibold text-white truncate">{density.zone_code}</p>
            {density.zone_name && (
              <p className="text-[10px] text-slate-500 truncate">{density.zone_name}</p>
            )}
          </>
        )}
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        {isMissing && (
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
            KBLI mismatch
          </span>
        )}
        <span className="text-xs font-medium text-[#d4845a]">{density.count}</span>
      </div>
    </div>
  );
}

export function ComplianceOverlay() {
  const { intelligenceData, isLoadingIntelligence, bounds } = usePrimeNexus();

  const isAuthError = intelligenceData?.stats?.auth_error === 1;
  const features = intelligenceData?.features ?? [];
  const featureCount = features.length;

  // Stats
  const totalCompanies = features.filter((f) => f.properties.entity_type === 'company').length;
  const totalClients = features.filter((f) => f.properties.entity_type === 'client').length;
  const zoneW1 = features.filter((f) => f.properties.zone_code?.startsWith('W-1')).length;
  const zoneK = features.filter(
    (f) => f.properties.zone_code?.startsWith('K-1') || f.properties.zone_code?.startsWith('K-2')
  ).length;
  const zoneOther = featureCount - zoneW1 - zoneK;

  const zoneDensities = computeZoneDensities(features).slice(0, 5);

  return (
    <div className="w-80 rounded-2xl bg-black/90 backdrop-blur-xl border border-white/10 shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">&#x1F4CA;</span>
          <span className="text-sm font-semibold text-white">Intelligence Layer</span>
        </div>
        {!isLoadingIntelligence && !isAuthError && featureCount > 0 && (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-[#d4845a]/20 text-[#d4845a]">
            {featureCount} entities
          </span>
        )}
        {isLoadingIntelligence && (
          <span className="w-3.5 h-3.5 border border-slate-500 border-t-[#d4845a] rounded-full animate-spin" />
        )}
      </div>

      {/* Auth error */}
      {isAuthError && (
        <div className="px-4 py-6 text-center">
          <span className="text-2xl block mb-2">&#x1F512;</span>
          <p className="text-sm font-medium text-white">Admin access required</p>
          <p className="text-xs text-slate-500 mt-1">
            Sign in with an admin account to access intelligence data
          </p>
        </div>
      )}

      {/* Loading */}
      {isLoadingIntelligence && !isAuthError && (
        <div className="px-4 py-6 text-center">
          <div className="flex flex-col items-center gap-3">
            <div className="w-6 h-6 border-2 border-slate-700 border-t-[#d4845a] rounded-full animate-spin" />
            <p className="text-xs text-slate-400">Analyzing viewport...</p>
          </div>
        </div>
      )}

      {/* No bounds */}
      {!bounds && !isLoadingIntelligence && !isAuthError && (
        <div className="px-4 py-6 text-center">
          <p className="text-xs text-slate-500">Move the map to analyze intelligence data</p>
        </div>
      )}

      {/* Empty state */}
      {bounds && !isLoadingIntelligence && !isAuthError && featureCount === 0 && (
        <div className="px-4 py-6 text-center">
          <span className="text-2xl block mb-2">&#x1F30F;</span>
          <p className="text-sm font-medium text-white">No data in this area</p>
          <p className="text-xs text-slate-500 mt-1">No geocoded businesses found in viewport</p>
          <a
            href="/api/prime/v2/health"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 mt-3 text-xs text-[#d4845a] hover:text-[#e09070] transition-colors"
          >
            &#x25B6; Run geocoding
          </a>
        </div>
      )}

      {/* Data view */}
      {!isLoadingIntelligence && !isAuthError && featureCount > 0 && (
        <div className="py-3 space-y-3">
          {/* Stats grid 2x2 */}
          <div className="px-3 grid grid-cols-2 gap-2">
            <StatCard label="Companies" value={totalCompanies} accent />
            <StatCard label="Clients" value={totalClients} />
            <StatCard label="Zone W-1" value={zoneW1} />
            <StatCard label="Zone K-1/K-2" value={zoneK} />
          </div>

          {zoneOther > 0 && (
            <div className="px-3">
              <StatCard label="Other zones" value={zoneOther} />
            </div>
          )}

          {/* Zone density list */}
          {zoneDensities.length > 0 && (
            <div>
              <p className="px-4 text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-1">
                Top zones by density
              </p>
              <div>
                {zoneDensities.map((d, i) => (
                  <ZoneDensityRow key={d.zone_code} rank={i + 1} density={d} />
                ))}
              </div>
            </div>
          )}

          {/* Geocoding link */}
          <div className="px-4 pt-1 border-t border-white/10">
            <a
              href="/api/prime/v2/health"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[10px] text-slate-500 hover:text-[#d4845a] transition-colors"
            >
              &#x25B6; Check geocoding status
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
