'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { useLevel } from '@/hooks/useLevel';
import { useNeo4j } from '@/hooks/useNeo4j';
import { formatRupiah, formatDelta } from '@/lib/format';
import type { ProvinceDetail } from '@/lib/types';
import { ObsidianPanel } from '@/components/ui/ObsidianPanel';
import { RedactedText } from '@/components/ui/RedactedText';
import { DataPylon } from '@/components/ui/DataPylon';

/** Project Bali lat/lng to screen pixel coordinates */
function baliToScreen(lat: number, lng: number, width: number, height: number) {
  // Bali spans roughly lat -8.85 to -8.05, lng 114.4 to 115.7
  const x = ((lng - 114.4) / (115.7 - 114.4)) * width;
  const y = ((lat - (-8.05)) / (-8.85 - (-8.05))) * height;
  return { x, y };
}

export function ProvincialMap() {
  const { state, dispatch } = useLevel();
  const province = state.province;
  const { data } = useNeo4j<ProvinceDetail>(
    province ? `/api/graph/province/${encodeURIComponent(province)}` : null
  );
  const [dimensions, setDimensions] = useState({ width: 1440, height: 900 });

  useEffect(() => {
    const update = () =>
      setDimensions({ width: window.innerWidth, height: window.innerHeight });
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  if (!data || !province) return null;

  return (
    <motion.div
      className="absolute inset-0 z-20 pointer-events-none"
      initial={{ opacity: 0, scale: 1.05 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, ease: 'easeOut' }}
    >
      {data.institutions.map((inst, i) => {
        const pos = baliToScreen(inst.lat, inst.lng, dimensions.width, dimensions.height);
        return (
          <div key={inst.name} className="pointer-events-auto">
            <DataPylon
              type={inst.type}
              name={inst.name}
              officialCount={inst.official_count}
              hasAnomaly={inst.anomaly_count > 0}
              x={pos.x}
              y={pos.y}
              delay={i * 100}
              onClick={() => dispatch({ type: 'DIVE_INSTITUTION', institution: inst.name })}
            />
          </div>
        );
      })}

      <motion.div
        initial={{ x: -380, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
        className="absolute left-4 top-16 bottom-12 pointer-events-auto"
        style={{ width: 360 }}
      >
        <ObsidianPanel className="h-full overflow-y-auto p-5">
          <div className="mb-5">
            <div className="font-[family-name:var(--font-display)] text-[15px] font-bold tracking-[0.08em] uppercase text-[var(--sg-text-primary)]">
              {province}
            </div>
            <div className="font-[family-name:var(--font-mono)] text-[10px] tracking-[0.08em] uppercase text-[var(--sg-text-ghost)] mt-1">
              PROVINCIAL INTELLIGENCE
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 mb-6">
            <StatItem label="INSTITUTIONS" value={data.institutions.length} />
            <StatItem label="TRACKED OFFICIALS" value={data.stats.officials} />
            <StatItem label="LHKPN FILED" value={data.stats.lhkpn} />
            <div className="col-span-2">
              <div className="font-[family-name:var(--font-mono)] text-[10px] uppercase text-[var(--sg-text-ghost)]">TOTAL DECLARED ASSETS</div>
              <div className="font-[family-name:var(--font-mono)] text-[18px] text-[var(--sg-copper)] mt-0.5">{formatRupiah(data.stats.total_assets)}</div>
            </div>
          </div>

          <div className="mb-6">
            <div className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-3">
              TOP ASSET HOLDERS
            </div>
            {data.top_holders.map((h, i) => (
              <div key={h.name} className="flex items-center justify-between py-1.5 border-b border-[var(--sg-border)]">
                <div className="flex items-center gap-2">
                  <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)] w-4">{i + 1}.</span>
                  <RedactedText text={h.name} className="font-[family-name:var(--font-mono)] text-[11px]" />
                </div>
                <span className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-copper)]">
                  {formatRupiah(h.total_assets)}
                </span>
              </div>
            ))}
          </div>

          {data.anomalies.length > 0 && (
            <div>
              <div className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-anomaly)] mb-3">
                ANOMALY ALERTS · {data.anomalies.length}
              </div>
              {data.anomalies.map((a) => (
                <div key={`${a.official}-${a.year}`} className="flex items-center gap-2 py-1.5">
                  <span className="text-[var(--sg-anomaly)] text-[10px]">&#x26A0;</span>
                  <span className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-amber)]">
                    {formatDelta(a.delta_pct)} assets YoY
                  </span>
                  <span className="text-[var(--sg-text-ghost)]">&mdash;</span>
                  <RedactedText text={a.official} className="font-[family-name:var(--font-mono)] text-[10px]" />
                </div>
              ))}
            </div>
          )}
        </ObsidianPanel>
      </motion.div>
    </motion.div>
  );
}

function StatItem({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="font-[family-name:var(--font-mono)] text-[10px] uppercase text-[var(--sg-text-ghost)]">{label}</div>
      <div className="font-[family-name:var(--font-mono)] text-[16px] text-[var(--sg-text-primary)] mt-0.5">{value}</div>
    </div>
  );
}
