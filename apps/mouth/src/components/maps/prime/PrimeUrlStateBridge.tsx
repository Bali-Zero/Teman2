"use client";
import { useEffect, useMemo, useRef } from "react";
import {
  usePrimeNexus,
  DEFAULT_MAP_LAYERS,
  type MapLayersState,
} from "@/contexts/PrimeNexusContext";
import {
  useReadPrimeUrl,
  useWritePrimeUrl,
  type PrimeUrlState,
} from "./hooks/usePrimeUrlState";

export function PrimeUrlStateBridge() {
  const ctx = usePrimeNexus();
  const incoming = useReadPrimeUrl();
  const hydratedRef = useRef(false);

  // One-time hydrate on mount
  useEffect(() => {
    if (hydratedRef.current) return;
    hydratedRef.current = true;
    if (incoming.layers?.length) {
      const next = { ...DEFAULT_MAP_LAYERS };
      (Object.keys(next) as Array<keyof MapLayersState>).forEach((k) => {
        next[k] = incoming.layers!.includes(k);
      });
      ctx.setLayers(next);
    }
    if (incoming.compareA) {
      ctx.addToCompare({
        id: incoming.compareA,
        name: incoming.compareA,
        zoneCode: null,
        info: {},
      });
    }
    if (incoming.compareB) {
      ctx.addToCompare({
        id: incoming.compareB,
        name: incoming.compareB,
        zoneCode: null,
        info: {},
      });
    }
    // lat/lng/zoom are consumed by PrimeMap3D directly via useReadPrimeUrl (Task 9).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Outgoing sync — rebuild the URL state every render from context
  const outgoing: PrimeUrlState = useMemo(() => {
    const activeLayers = (
      Object.entries(ctx.layers) as Array<[keyof MapLayersState, boolean]>
    )
      .filter(([, v]) => v)
      .map(([k]) => k);
    return {
      layers: activeLayers.length ? activeLayers : undefined,
      compareA: ctx.compareA?.id,
      compareB: ctx.compareB?.id,
    };
  }, [ctx.layers, ctx.compareA, ctx.compareB]);

  useWritePrimeUrl(outgoing);
  return null;
}
