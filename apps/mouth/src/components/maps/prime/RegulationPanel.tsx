'use client';

import { useEffect, useState } from 'react';
import { usePrimeNexus } from '@/contexts/PrimeNexusContext';

interface Regulation {
  title: string;
  summary: string;
  category: string;
  sentiment: string;
  published_at: string;
  source_url: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  immigration: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  business: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  property: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  legal: 'bg-red-500/20 text-red-300 border-red-500/30',
  tax: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
};

const SENTIMENT_DOTS: Record<string, string> = {
  positive: 'bg-emerald-400',
  negative: 'bg-red-400',
  neutral: 'bg-slate-400',
};

export function RegulationPanel() {
  const { analysis } = usePrimeNexus();
  const zoneCode = analysis?.zone?.zone_code ? String(analysis.zone.zone_code) : null;

  const [data, setData] = useState<Regulation[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!zoneCode) return;
    setLoading(true);
    fetch(`/api/prime/v2/regulations?zone_code=${encodeURIComponent(zoneCode)}&limit=10`)
      .then((r) => r.json())
      .then((d) => setData(d.regulations ?? []))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [zoneCode]);

  return (
    <div className="w-80 rounded-2xl bg-black/90 backdrop-blur-xl border border-white/10 shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">&#x1F4DC;</span>
          <span className="text-sm font-semibold text-white">Regulations</span>
        </div>
        {!loading && data.length > 0 && (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-accent-warm/20 text-accent-warm">
            {data.length}
          </span>
        )}
        {loading && (
          <span className="w-3.5 h-3.5 border border-slate-500 border-t-[#d4845a] rounded-full animate-spin" />
        )}
      </div>

      {/* Body */}
      <div className="max-h-[50vh] overflow-y-auto">
        {!zoneCode && (
          <div className="px-4 py-6 text-center">
            <p className="text-xs text-slate-500">Click a zone on the map to see regulations</p>
          </div>
        )}

        {loading && (
          <div className="px-4 py-6 text-center">
            <div className="w-5 h-5 border-2 border-slate-700 border-t-[#d4845a] rounded-full animate-spin mx-auto" />
          </div>
        )}

        {!loading && zoneCode && data.length === 0 && (
          <div className="px-4 py-6 text-center">
            <p className="text-xs text-slate-500">No regulations found for this zone</p>
          </div>
        )}

        {!loading && data.length > 0 && (
          <div className="py-1 space-y-0.5">
            {data.map((reg, i) => {
              const catClass =
                CATEGORY_COLORS[reg.category] ||
                'bg-slate-500/20 text-slate-300 border-slate-500/30';
              const dotClass = SENTIMENT_DOTS[reg.sentiment] || 'bg-slate-400';

              return (
                <a
                  key={i}
                  href={reg.source_url || '#'}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block px-3 py-2.5 hover:bg-white/5 transition-colors"
                >
                  <div className="flex items-start gap-2">
                    <span className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${dotClass}`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-white leading-relaxed line-clamp-2">{reg.title}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span
                          className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold uppercase tracking-wide border ${catClass}`}
                        >
                          {reg.category}
                        </span>
                        {reg.published_at && (
                          <span className="text-[9px] text-slate-600">
                            {reg.published_at.slice(0, 10)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </a>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
