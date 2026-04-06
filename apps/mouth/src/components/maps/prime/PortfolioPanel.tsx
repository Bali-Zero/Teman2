'use client';

import { useEffect, useState } from 'react';

interface PortfolioEntity {
  type: 'company' | 'practice';
  id: number;
  name: string;
  zone_code?: string;
  kbli_code?: string;
  status?: string;
  lat?: number;
  lng?: number;
  health_score: number;
  issues: string[];
  expiry_date?: string;
  days_until_expiry?: number | null;
}

interface PortfolioData {
  client_id: number;
  entities: PortfolioEntity[];
  risk_concentration: {
    by_zone: Record<string, number>;
    by_kbli: Record<string, number>;
    warnings: string[];
  };
  suggestions: string[];
  overall_health: number;
}

function HealthDot({ score }: { score: number }) {
  const color = score >= 0.7 ? 'bg-emerald-400' : score >= 0.4 ? 'bg-amber-400' : 'bg-red-400';
  return <span className={`w-2 h-2 rounded-full shrink-0 ${color}`} />;
}

export function PortfolioPanel({ clientId }: { clientId: number | null }) {
  const [data, setData] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!clientId) return;
    setLoading(true);
    fetch(`/api/prime/v2/portfolio?client_id=${clientId}`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [clientId]);

  const healthColor =
    (data?.overall_health ?? 0) >= 0.7
      ? 'text-emerald-400'
      : (data?.overall_health ?? 0) >= 0.4
        ? 'text-amber-400'
        : 'text-red-400';

  return (
    <div className="w-80 rounded-2xl bg-black/90 backdrop-blur-xl border border-white/10 shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">&#x1F4BC;</span>
          <span className="text-sm font-semibold text-white">Portfolio</span>
        </div>
        {data && (
          <span className={`text-sm font-bold ${healthColor}`}>
            {Math.round(data.overall_health * 100)}%
          </span>
        )}
        {loading && (
          <span className="w-3.5 h-3.5 border border-slate-500 border-t-[#d4845a] rounded-full animate-spin" />
        )}
      </div>

      <div className="max-h-[55vh] overflow-y-auto">
        {!clientId && (
          <div className="px-4 py-6 text-center">
            <p className="text-xs text-slate-500">Sign in to view your investment portfolio</p>
          </div>
        )}

        {loading && (
          <div className="px-4 py-6 text-center">
            <div className="w-5 h-5 border-2 border-slate-700 border-t-[#d4845a] rounded-full animate-spin mx-auto" />
          </div>
        )}

        {!loading && data && data.entities.length === 0 && (
          <div className="px-4 py-6 text-center">
            <p className="text-xs text-slate-500">No geocoded entities found</p>
          </div>
        )}

        {!loading && data && data.entities.length > 0 && (
          <div className="py-1 space-y-0.5">
            {/* Warnings */}
            {data.risk_concentration.warnings.length > 0 && (
              <div className="mx-3 mb-2">
                {data.risk_concentration.warnings.map((w, i) => (
                  <div
                    key={i}
                    className="text-[10px] text-amber-400 bg-amber-500/10 rounded-lg px-2 py-1 mb-1"
                  >
                    &#x26A0;&#xFE0F; {w}
                  </div>
                ))}
              </div>
            )}

            {/* Entities */}
            {data.entities.map((entity) => (
              <div
                key={`${entity.type}-${entity.id}`}
                className="px-3 py-2 hover:bg-white/5 transition-colors"
              >
                <div className="flex items-start gap-2">
                  <HealthDot score={entity.health_score} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-white truncate">{entity.name}</span>
                      <span className="text-[9px] text-slate-600 uppercase">{entity.type}</span>
                    </div>
                    {entity.zone_code && (
                      <span className="text-[10px] text-slate-500">{entity.zone_code}</span>
                    )}
                    {entity.days_until_expiry != null && entity.days_until_expiry < 90 && (
                      <span
                        className={`text-[10px] ml-1 ${entity.days_until_expiry < 30 ? 'text-red-400' : 'text-amber-400'}`}
                      >
                        {entity.days_until_expiry}d left
                      </span>
                    )}
                    {entity.issues.length > 0 && (
                      <div className="text-[9px] text-red-400 mt-0.5">
                        {entity.issues.join(', ')}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}

            {/* Suggestions */}
            {data.suggestions.length > 0 && (
              <div className="mx-3 mt-2 pt-2 border-t border-white/5">
                <div className="text-[10px] uppercase tracking-widest text-slate-600 font-semibold mb-1">
                  Suggestions
                </div>
                {data.suggestions.map((s, i) => (
                  <div key={i} className="text-[10px] text-[#d4845a] mb-0.5">
                    &#x2192; {s}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
