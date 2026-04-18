"use client";
import { z } from "zod";
import { useEffect, useRef } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { useDebouncedCallback } from "./useDebouncedCallback";

const LAYER_KEYS = [
  "zoneColors",
  "extrusion",
  "kkop",
  "lp2b",
  "tsunami",
  "floodRisk",
  "templeBuffer",
] as const;
export type LayerKey = (typeof LAYER_KEYS)[number];

const PrimeUrlSchema = z.object({
  lat: z.coerce.number().min(-9).max(-8).optional(),
  lng: z.coerce.number().min(114).max(116).optional(),
  zoom: z.coerce.number().min(6).max(22).optional(),
  layers: z.string().optional(),
  compareA: z.string().optional(),
  compareB: z.string().optional(),
});

export interface PrimeUrlState {
  lat?: number;
  lng?: number;
  zoom?: number;
  layers?: LayerKey[];
  compareA?: string;
  compareB?: string;
}

export function parsePrimeUrl(params: URLSearchParams): PrimeUrlState {
  const raw = Object.fromEntries(params.entries());
  const parsed = PrimeUrlSchema.safeParse(raw);
  if (!parsed.success) return {};
  const data = parsed.data;
  const out: PrimeUrlState = {};
  if (data.lat !== undefined) out.lat = data.lat;
  if (data.lng !== undefined) out.lng = data.lng;
  if (data.zoom !== undefined) out.zoom = data.zoom;
  if (data.layers) {
    const filtered = data.layers
      .split(",")
      .map((s) => s.trim())
      .filter((s): s is LayerKey =>
        (LAYER_KEYS as readonly string[]).includes(s),
      );
    if (filtered.length) out.layers = filtered;
  }
  if (data.compareA) out.compareA = data.compareA;
  if (data.compareB) out.compareB = data.compareB;
  return out;
}

export function serializePrimeUrl(state: PrimeUrlState): string {
  const params = new URLSearchParams();
  if (state.lat !== undefined) params.set("lat", String(state.lat));
  if (state.lng !== undefined) params.set("lng", String(state.lng));
  if (state.zoom !== undefined) params.set("zoom", String(state.zoom));
  if (state.layers?.length) params.set("layers", state.layers.join(","));
  if (state.compareA) params.set("compareA", state.compareA);
  if (state.compareB) params.set("compareB", state.compareB);
  return params.toString();
}

export function useWritePrimeUrl(state: PrimeUrlState, delayMs = 400) {
  const router = useRouter();
  const pathname = usePathname();
  const prev = useRef<string>("");

  const write = useDebouncedCallback((s: PrimeUrlState) => {
    const qs = serializePrimeUrl(s);
    if (qs === prev.current) return;
    prev.current = qs;
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, delayMs);

  useEffect(() => {
    write(state);
  }, [state, write]);
}

export function useReadPrimeUrl(): PrimeUrlState {
  const params = useSearchParams();
  return parsePrimeUrl(new URLSearchParams(params?.toString() ?? ""));
}
