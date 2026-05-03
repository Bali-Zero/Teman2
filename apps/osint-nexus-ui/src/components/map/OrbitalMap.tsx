'use client';

import { useCallback, useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLevel } from '@/hooks/useLevel';
import { useNeo4j } from '@/hooks/useNeo4j';
import { formatRupiah } from '@/lib/format';
import type { ProvinceData } from '@/lib/types';

function sphereColor(count: number): string {
  if (count >= 20) return '#d4845a';
  if (count >= 6) return '#b08f73';
  return '#8b9cf7';
}

function sphereOpacity(count: number): number {
  if (count >= 20) return 0.7;
  if (count >= 6) return 0.6;
  return 0.5;
}

function sphereSize(count: number): number {
  return Math.max(32, Math.log2(count + 1) * 28);
}

/** Project lat/lng to screen pixel coordinates for Indonesia overview */
function geoToScreen(lat: number, lng: number, width: number, height: number) {
  // Indonesia spans roughly lat -11 to 6, lng 95 to 141
  const x = ((lng - 95) / (141 - 95)) * width;
  const y = ((lat - 6) / (-11 - 6)) * height;
  return { x, y };
}

export function OrbitalMap() {
  const { state, dispatch } = useLevel();
  const { data } = useNeo4j<{ provinces: ProvinceData[] }>(
    state.level === 'orbital' ? '/api/graph/provinces' : null
  );
  const [dimensions, setDimensions] = useState({ width: 1440, height: 900 });

  useEffect(() => {
    const update = () =>
      setDimensions({ width: window.innerWidth, height: window.innerHeight });
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  const handleProvinceDive = useCallback(
    (province: string) => {
      dispatch({ type: 'DIVE_PROVINCE', province });
    },
    [dispatch]
  );

  return (
    <>
      {/* Dark surveillance background with subtle grid */}
      <div className="absolute inset-0" style={{ background: 'var(--sg-base)' }}>
        {/* Grid lines */}
        <svg className="absolute inset-0 w-full h-full" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="orbital-grid" width="100" height="100" patternUnits="userSpaceOnUse">
              <path
                d="M 100 0 L 0 0 0 100"
                fill="none"
                stroke="rgba(255,255,255,0.03)"
                strokeWidth="1"
              />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#orbital-grid)" />
        </svg>

        {/* Ambient radial glow */}
        <div
          className="absolute inset-0"
          style={{
            background:
              'radial-gradient(ellipse 60% 50% at 50% 50%, rgba(139,156,247,0.05), transparent 70%)',
          }}
        />
      </div>

      {/* Province spheres overlay */}
      <AnimatePresence>
        {state.level === 'orbital' &&
          data?.provinces.map((prov, idx) => {
            const { x, y } = geoToScreen(
              prov.centroid.lat,
              prov.centroid.lng,
              dimensions.width,
              dimensions.height
            );

            // Clamp to viewport
            if (x < 0 || x > dimensions.width || y < 0 || y > dimensions.height) return null;

            const size = sphereSize(prov.official_count);
            const color = sphereColor(prov.official_count);
            const opacity = sphereOpacity(prov.official_count);

            return (
              <motion.div
                key={prov.name}
                initial={{ opacity: 0, scale: 0.5 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.5 }}
                transition={{ duration: 0.4, delay: idx * 0.1 }}
                className="absolute cursor-pointer group"
                style={{
                  left: x - size / 2,
                  top: y - size / 2,
                  width: size,
                  height: size,
                  zIndex: 20,
                }}
                onClick={() => handleProvinceDive(prov.name)}
              >
                {/* Glowing sphere */}
                <div
                  className="w-full h-full rounded-full"
                  style={{
                    background: `radial-gradient(circle at 35% 35%, ${color}, transparent 70%)`,
                    opacity,
                    animation: 'sphere-pulse 2s ease-in-out infinite',
                    boxShadow: `0 0 ${size * 0.8}px ${color}, 0 0 ${size * 0.3}px ${color}`,
                  }}
                />

                {/* Label */}
                <div className="absolute left-1/2 -translate-x-1/2 mt-2 whitespace-nowrap text-center">
                  <div className="font-[family-name:var(--font-mono)] text-[10px] tracking-[0.08em] uppercase text-[var(--sg-text-ghost)] group-hover:text-[var(--sg-text-primary)] transition-colors">
                    {prov.name}
                  </div>
                  <div className="font-[family-name:var(--font-mono)] text-[9px] tracking-[0.02em] text-[var(--sg-text-ghost)] group-hover:text-[var(--sg-text-secondary)] transition-colors">
                    {prov.official_count} OFFICIALS · {prov.lhkpn_count} LHKPN
                  </div>
                </div>

                {/* Hover tooltip */}
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                  <div className="obsidian-glass rounded px-3 py-2 whitespace-nowrap">
                    <div className="font-[family-name:var(--font-display)] text-[11px] font-semibold text-[var(--sg-text-primary)]">
                      {prov.name}
                    </div>
                    <div className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-copper)]">
                      {formatRupiah(prov.total_assets)} declared
                    </div>
                  </div>
                </div>
              </motion.div>
            );
          })}
      </AnimatePresence>
    </>
  );
}
