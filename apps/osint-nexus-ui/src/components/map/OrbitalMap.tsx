'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Script from 'next/script';
import { useLevel } from '@/hooks/useLevel';
import { useNeo4j } from '@/hooks/useNeo4j';
import { ORBITAL_CAMERA } from '@/lib/geo';
import { formatRupiah } from '@/lib/format';
import type { ProvinceData } from '@/lib/types';
import { PulseRing } from '@/components/ui/PulseRing';

function sphereColor(count: number): string {
  if (count >= 20) return 'var(--sg-copper)';
  if (count >= 6) return '#b08f73';
  return 'var(--sg-periwinkle)';
}

function sphereOpacity(count: number): number {
  if (count >= 20) return 0.6;
  if (count >= 6) return 0.5;
  return 0.4;
}

function sphereRadius(count: number): number {
  return Math.log2(count + 1) * 24;
}

export function OrbitalMap() {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const [mapReady, setMapReady] = useState(false);
  const { state, dispatch } = useLevel();
  const { data } = useNeo4j<{ provinces: ProvinceData[] }>(
    state.level === 'orbital' ? '/api/graph/provinces' : null
  );
  const [spherePositions, setSpherePositions] = useState<Map<string, { x: number; y: number }>>(new Map());

  const initMap = useCallback(async () => {
    if (!mapContainerRef.current || mapRef.current) return;

    const { Map3DElement } = await (window as any).google.maps.importLibrary('maps3d');
    const map = new Map3DElement();
    map.defaultLabelsDisabled = true;

    map.center = { lat: ORBITAL_CAMERA.center.lat, lng: ORBITAL_CAMERA.center.lng, altitude: 0 };
    map.tilt = ORBITAL_CAMERA.tilt;
    map.range = ORBITAL_CAMERA.range;
    map.heading = ORBITAL_CAMERA.heading;

    map.style.width = '100%';
    map.style.height = '100%';

    mapContainerRef.current.appendChild(map);
    mapRef.current = map;
    setMapReady(true);
  }, []);

  useEffect(() => {
    if (!mapReady || !mapRef.current || !data?.provinces) return;

    const updatePositions = () => {
      const map = mapRef.current;
      if (!map?.convertLocationToScreenPoint) return;

      const newPositions = new Map<string, { x: number; y: number }>();
      for (const prov of data.provinces) {
        try {
          const point = map.convertLocationToScreenPoint({
            lat: prov.centroid.lat,
            lng: prov.centroid.lng,
            altitude: 50000,
          });
          if (point) {
            newPositions.set(prov.name, { x: point.x, y: point.y });
          }
        } catch {
          // Point may be off-screen
        }
      }
      setSpherePositions(newPositions);
    };

    updatePositions();
    const interval = setInterval(updatePositions, 100);
    return () => clearInterval(interval);
  }, [mapReady, data]);

  const handleProvinceDive = useCallback((province: string) => {
    dispatch({ type: 'DIVE_PROVINCE', province });
  }, [dispatch]);

  return (
    <>
      <Script
        src={`https://maps.googleapis.com/maps/api/js?key=${process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY}&v=alpha&libraries=maps3d`}
        onLoad={initMap}
      />

      <div ref={mapContainerRef} className="absolute inset-0" />
      <PulseRing containerRef={mapContainerRef} />

      <AnimatePresence>
      {state.level === 'orbital' && data?.provinces.map((prov) => {
        const pos = spherePositions.get(prov.name);
        if (!pos) return null;
        const radius = sphereRadius(prov.official_count);
        const color = sphereColor(prov.official_count);
        const opacity = sphereOpacity(prov.official_count);

        return (
          <motion.div
            key={prov.name}
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.5 }}
            transition={{ duration: 0.4 }}
            className="absolute cursor-pointer group"
            style={{
              left: pos.x - radius,
              top: pos.y - radius,
              width: radius * 2,
              height: radius * 2,
              zIndex: 20,
            }}
            onClick={() => handleProvinceDive(prov.name)}
          >
            <div
              className="w-full h-full rounded-full"
              style={{
                background: `radial-gradient(circle at 35% 35%, ${color}, transparent)`,
                opacity,
                animation: 'sphere-pulse 2s ease-in-out infinite',
                boxShadow: `0 0 ${radius}px ${color}`,
              }}
            />

            <div className="absolute left-1/2 -translate-x-1/2 mt-1 whitespace-nowrap text-center transition-colors">
              <div className="font-[family-name:var(--font-mono)] text-[10px] tracking-[0.08em] uppercase text-[var(--sg-text-ghost)] group-hover:text-[var(--sg-text-primary)]">
                {prov.name}
              </div>
              <div className="font-[family-name:var(--font-mono)] text-[9px] tracking-[0.02em] text-[var(--sg-text-ghost)] group-hover:text-[var(--sg-text-secondary)]">
                {prov.official_count} OFFICIALS · {prov.lhkpn_count} LHKPN
              </div>
            </div>

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
