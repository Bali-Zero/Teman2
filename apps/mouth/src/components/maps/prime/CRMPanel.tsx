'use client';

import { usePrimeNexus, type IntelligenceFeature } from '@/contexts/PrimeNexusContext';

function EntityBadge({ type }: { type: 'company' | 'client' }) {
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide ${
        type === 'company'
          ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
          : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
      }`}
    >
      {type}
    </span>
  );
}

function FeatureRow({ feature }: { feature: IntelligenceFeature }) {
  const { id, name, entity_type, zone_code, zone_name } = feature.properties;

  const handleClick = () => {
    const path = entity_type === 'company' ? `/clients/${id}` : `/crm/clients/${id}`;
    window.open(path, '_blank', 'noopener,noreferrer');
  };

  return (
    <button
      onClick={handleClick}
      className="w-full text-left px-3 py-2.5 rounded-xl hover:bg-white/5 transition-colors group"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-white truncate group-hover:text-[#d4845a] transition-colors">
            {name || `Entity #${id}`}
          </p>
          {zone_name && (
            <p className="text-xs text-slate-500 truncate mt-0.5">
              {zone_code ? `${zone_code} · ` : ''}
              {zone_name}
            </p>
          )}
          {!zone_name && <p className="text-xs text-slate-600 mt-0.5 italic">No zone data</p>}
        </div>
        <EntityBadge type={entity_type} />
      </div>
    </button>
  );
}

export function CRMPanel() {
  const { intelligenceData, isLoadingIntelligence, bounds } = usePrimeNexus();

  const isAuthError = intelligenceData?.stats?.auth_error === 1;
  const features = intelligenceData?.features ?? [];
  const featureCount = features.length;

  return (
    <div className="w-72 rounded-2xl bg-black/90 backdrop-blur-xl border border-white/10 shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">&#x1F465;</span>
          <span className="text-sm font-semibold text-white">CRM Layer</span>
        </div>
        {!isLoadingIntelligence && !isAuthError && (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-[#d4845a]/20 text-[#d4845a]">
            {featureCount} {featureCount === 1 ? 'client' : 'clients'}
          </span>
        )}
        {isLoadingIntelligence && (
          <span className="w-3.5 h-3.5 border border-slate-500 border-t-[#d4845a] rounded-full animate-spin" />
        )}
      </div>

      {/* Body */}
      <div className="max-h-[50vh] overflow-y-auto">
        {/* Auth error state */}
        {isAuthError && (
          <div className="px-4 py-6 text-center">
            <span className="text-2xl block mb-2">&#x1F512;</span>
            <p className="text-sm font-medium text-white">Admin access required</p>
            <p className="text-xs text-slate-500 mt-1">
              Sign in with an admin account to view CRM data
            </p>
          </div>
        )}

        {/* Loading state */}
        {isLoadingIntelligence && !isAuthError && (
          <div className="px-4 py-6 text-center">
            <div className="flex flex-col items-center gap-3">
              <div className="w-6 h-6 border-2 border-slate-700 border-t-[#d4845a] rounded-full animate-spin" />
              <p className="text-xs text-slate-400">Loading clients in viewport...</p>
            </div>
          </div>
        )}

        {/* No bounds yet */}
        {!bounds && !isLoadingIntelligence && !isAuthError && (
          <div className="px-4 py-6 text-center">
            <p className="text-xs text-slate-500">Move the map to load CRM data</p>
          </div>
        )}

        {/* Empty state */}
        {bounds && !isLoadingIntelligence && !isAuthError && featureCount === 0 && (
          <div className="px-4 py-6 text-center">
            <span className="text-2xl block mb-2">&#x1F5FA;&#xFE0F;</span>
            <p className="text-sm font-medium text-white">No geocoded clients in this area</p>
            <p className="text-xs text-slate-500 mt-1">
              Try zooming out or panning to a different location
            </p>
          </div>
        )}

        {/* Feature list */}
        {!isLoadingIntelligence && !isAuthError && featureCount > 0 && (
          <div className="py-1">
            {features.map((feature) => (
              <FeatureRow
                key={`${feature.properties.entity_type}-${feature.properties.id}`}
                feature={feature}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      {!isAuthError && featureCount > 0 && (
        <div className="px-4 py-2 border-t border-white/10">
          <p className="text-[10px] text-slate-600 text-center">Click an item to open in CRM</p>
        </div>
      )}
    </div>
  );
}
