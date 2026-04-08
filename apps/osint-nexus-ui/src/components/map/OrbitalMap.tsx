'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Script from 'next/script';
import { useLevel } from '@/hooks/useLevel';
import { useNeo4j } from '@/hooks/useNeo4j';
import { ORBITAL_CAMERA } from '@/lib/geo';
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

export function OrbitalMap() {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const { state, dispatch } = useLevel();
  const { data } = useNeo4j<{ provinces: ProvinceData[] }>(
    state.level === 'orbital' ? '/api/graph/provinces' : null
  );
  const [spherePositions, setSpherePositions] = useState<
    Map<string, { x: number; y: number }>
  >(new Map());

  // Init map when script loads — matching PrimeMap3D pattern exactly
  useEffect(() => {
    if (!isLoaded || !mapContainerRef.current || mapRef.current) return;

    const initMap = async () => {
      try {
        const { Map3DElement } = await (window as any).google.maps.importLibrary(
          'maps3d'
        );

        const map = new Map3DElement({
          center: {
            lat: ORBITAL_CAMERA.center.lat,
            lng: ORBITAL_CAMERA.center.lng,
            altitude: 0,
          },
          tilt: ORBITAL_CAMERA.tilt,
          range: ORBITAL_CAMERA.range,
          heading: ORBITAL_CAMERA.heading,
          defaultLabelsDisabled: true,
        });

        mapContainerRef.current!.appendChild(map);
        mapRef.current = map;

        // Give the map a moment to render before marking ready
        setTimeout(() => setMapReady(true), 1000);
      } catch (err) {
        console.error('Map3D init failed:', err);
      }
    };

    initMap();
  }, [isLoaded]);

  // Project province centroids to screen coordinates
  useEffect(() => {
    if (!mapReady || !mapRef.current || !data?.provinces) return;

    const updatePositions = () => {
      const map = mapRef.current;
      // convertLocationToScreenPoint may not exist in all API versions
      if (!map || typeof map.convertLocationToScreenPoint !== 'function') return;

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
          // off-screen or API not available
        }
      }
      if (newPositions.size > 0) {
        setSpherePositions(newPositions);
      }
    };

    updatePositions();
    const interval = setInterval(updatePositions, 500);
    return () => clearInterval(interval);
  }, [mapReady, data]);

  const handleProvinceDive = useCallback(
    (province: string) => {
      dispatch({ type: 'DIVE_PROVINCE', province });
    },
    [dispatch]
  );

  // If convertLocationToScreenPoint isn't available, show spheres at fixed CSS positions
  // based on rough viewport mapping. This is the fallback for L1.
  const hasDynamicPositions = spherePositions.size > 0;

  return (
    <>
      <Script
        src={`https://maps.googleapis.com/maps/api/js?key=${process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY}&v=beta&libraries=maps3d`}
        strategy="afterInteractive"
        onLoad={() => setIsLoaded(true)}
      />

      <div
        ref={mapContainerRef}
        className="absolute inset-0"
        style={{ width: '100%', height: '100%' }}
      />

      {/* Province spheres overlay */}
      <AnimatePresence>
        {state.level === 'orbital' &&
          mapReady &&
          data?.provinces.map((prov, idx) => {
            let x: number, y: number;

            if (hasDynamicPositions) {
              const pos = spherePositions.get(prov.name);
              if (!pos) return null;
              x = pos.x;
              y = pos.y;
            } else {
              // Fallback: estimate screen position from lat/lng relative to orbital camera
              // Orbital camera center: -2.5, 118.0, viewport ~60° lon, ~30° lat
              const vw = typeof window !== 'undefined' ? window.innerWidth : 1440;
              const vh = typeof window !== 'undefined' ? window.innerHeight : 900;
              x = ((prov.centroid.lng - 95) / 50) * vw;
              y = ((prov.centroid.lat + 12) / -20) * vh;
              // Clamp to viewport
              if (x < 0 || x > vw || y < 0 || y > vh) return null;
            }

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
