"use client";

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
} from "react";
import { api } from "@/lib/api";

// ─── Types ──────────────────────────────────────────────────────────

export type PrimeMode = "invest" | "crm" | "intel" | "temporal" | "portfolio";

export interface Coordinate {
  lat: number;
  lng: number;
}

export interface MapBounds {
  sw_lat: number;
  sw_lng: number;
  ne_lat: number;
  ne_lng: number;
}

export interface IntelligenceFeature {
  type: string;
  geometry: { type: string; coordinates: [number, number] };
  properties: {
    id: number;
    name: string;
    entity_type: "company" | "client";
    zone_code: string | null;
    zone_name: string | null;
    kbli_code: string | null;
    [key: string]: unknown;
  };
}

export interface IntelligenceData {
  type: string;
  features: IntelligenceFeature[];
  stats: Record<string, number>;
}

export interface AnalysisVerdict {
  can_invest: boolean;
  risk_level: string;
  score: number;
  label: "GREEN" | "YELLOW" | "RED";
  breakdown: Record<string, Record<string, unknown>>;
  modifiers: string[];
  hard_blocks: string[];
}

export interface AnalysisResult {
  status: string;
  coordinates: { lat: number; lng: number };
  zone: Record<string, unknown> | null;
  kbli: Record<string, unknown> | null;
  roi: Record<string, unknown> | null;
  verdict: AnalysisVerdict | null;
  opportunities: Record<string, unknown>[];
  intel_articles: Record<string, unknown>[];
  cache_hit: boolean;
}

// ─── PF3a — Layer + compare state ───────────────────────────────────

export interface MapLayersState {
  zoneColors: boolean;
  extrusion: boolean;
  kkop: boolean;
  lp2b: boolean;
  tsunami: boolean;
  floodRisk: boolean;
  templeBuffer: boolean;
}

export const DEFAULT_MAP_LAYERS: MapLayersState = {
  zoneColors: true,
  extrusion: false,
  kkop: false,
  lp2b: false,
  tsunami: false,
  floodRisk: false,
  templeBuffer: false,
};

export interface ZoneSelection {
  id: string;
  name: string;
  zoneCode: string | null;
  info: Record<string, unknown>;
}

// ─── Context Shape ──────────────────────────────────────────────────

interface PrimeNexusContextType {
  // Mode
  mode: PrimeMode;
  setMode: (mode: PrimeMode) => void;

  // Analysis (Layer 2)
  analysis: AnalysisResult | null;
  isAnalyzing: boolean;
  analyzePoint: (lat: number, lng: number, kbliCode?: string) => Promise<void>;
  clearAnalysis: () => void;

  // Bounds (Layer 3 — CRM/INTEL)
  bounds: MapBounds | null;
  setBounds: (bounds: MapBounds) => void;

  // Intelligence data (CRM/INTEL mode)
  intelligenceData: IntelligenceData | null;
  isLoadingIntelligence: boolean;
  fetchIntelligence: (bounds: MapBounds) => Promise<void>;

  // PF3a — layer toggles + isolate + hover highlight
  layers: MapLayersState;
  setLayers: (layers: MapLayersState) => void;
  toggleLayer: (key: keyof MapLayersState) => void;
  isolateLayer: (key: keyof MapLayersState) => void;
  hoveredLayer: keyof MapLayersState | null;
  setHoveredLayer: (key: keyof MapLayersState | null) => void;

  // PF3a — compare drawer (slot A/B)
  compareA: ZoneSelection | null;
  compareB: ZoneSelection | null;
  addToCompare: (zone: ZoneSelection) => void;
  clearCompareSlot: (slot: "A" | "B") => void;
  clearCompareAll: () => void;
}

export const PrimeNexusContext = createContext<PrimeNexusContextType | null>(
  null,
);

// ─── Provider ───────────────────────────────────────────────────────

export function PrimeNexusProvider({
  children,
  initialMode = "invest",
}: {
  children: React.ReactNode;
  initialMode?: PrimeMode;
}) {
  const [mode, setMode] = useState<PrimeMode>(initialMode);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Bounds + intelligence
  const [bounds, setBounds] = useState<MapBounds | null>(null);
  const [intelligenceData, setIntelligenceData] =
    useState<IntelligenceData | null>(null);
  const [isLoadingIntelligence, setIsLoadingIntelligence] = useState(false);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // PF3a — layer + compare state
  const [layers, setLayersState] = useState<MapLayersState>(DEFAULT_MAP_LAYERS);
  const [hoveredLayer, setHoveredLayer] = useState<keyof MapLayersState | null>(
    null,
  );
  const [compareA, setCompareA] = useState<ZoneSelection | null>(null);
  const [compareB, setCompareB] = useState<ZoneSelection | null>(null);

  const setLayers = useCallback((next: MapLayersState) => {
    setLayersState(next);
  }, []);

  const toggleLayer = useCallback((key: keyof MapLayersState) => {
    setLayersState((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  const isolateLayer = useCallback((key: keyof MapLayersState) => {
    setLayersState(() => {
      const next = { ...DEFAULT_MAP_LAYERS };
      (Object.keys(next) as Array<keyof MapLayersState>).forEach((k) => {
        next[k] = k === key;
      });
      return next;
    });
  }, []);

  const addToCompare = useCallback(
    (zone: ZoneSelection) => {
      // Fill A first, then B; if both full, rotate: A ← B, B ← new
      if (!compareA) {
        setCompareA(zone);
      } else if (!compareB) {
        setCompareB(zone);
      } else {
        setCompareA(compareB);
        setCompareB(zone);
      }
    },
    [compareA, compareB],
  );

  const clearCompareSlot = useCallback((slot: "A" | "B") => {
    if (slot === "A") setCompareA(null);
    else setCompareB(null);
  }, []);

  const clearCompareAll = useCallback(() => {
    setCompareA(null);
    setCompareB(null);
  }, []);

  const analyzePoint = useCallback(
    async (lat: number, lng: number, kbliCode?: string) => {
      setIsAnalyzing(true);
      try {
        const data = await api.prime.analyze<AnalysisResult>({
          lat,
          lng,
          kbli_code: kbliCode || undefined,
          is_pma: true,
        });
        setAnalysis(data);
      } catch {
        // Silently fail — analysis is optional enhancement
      } finally {
        setIsAnalyzing(false);
      }
    },
    [],
  );

  const clearAnalysis = useCallback(() => {
    setAnalysis(null);
  }, []);

  const fetchIntelligence = useCallback(async (newBounds: MapBounds) => {
    // Debounce 500ms
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }
    debounceTimer.current = setTimeout(async () => {
      setIsLoadingIntelligence(true);
      try {
        const data =
          await api.prime.getIntelligence<IntelligenceData>(newBounds);
        setIntelligenceData(data);
      } catch (err: unknown) {
        // Check for auth errors from ApiClient (it throws on 401)
        const message = err instanceof Error ? err.message : "";
        if (message.includes("expired") || message.includes("Authentication")) {
          setIntelligenceData({
            type: "FeatureCollection",
            features: [],
            stats: { auth_error: 1 },
          });
        } else {
          // Silently fail — show empty state
          setIntelligenceData({
            type: "FeatureCollection",
            features: [],
            stats: {},
          });
        }
      } finally {
        setIsLoadingIntelligence(false);
      }
    }, 500);
  }, []);

  return (
    <PrimeNexusContext.Provider
      value={{
        mode,
        setMode,
        analysis,
        isAnalyzing,
        analyzePoint,
        clearAnalysis,
        bounds,
        setBounds,
        intelligenceData,
        isLoadingIntelligence,
        fetchIntelligence,
        // PF3a
        layers,
        setLayers,
        toggleLayer,
        isolateLayer,
        hoveredLayer,
        setHoveredLayer,
        compareA,
        compareB,
        addToCompare,
        clearCompareSlot,
        clearCompareAll,
      }}
    >
      {children}
    </PrimeNexusContext.Provider>
  );
}

// ─── Hook ───────────────────────────────────────────────────────────

export function usePrimeNexus() {
  const ctx = useContext(PrimeNexusContext);
  if (!ctx) {
    throw new Error("usePrimeNexus must be used inside PrimeNexusProvider");
  }
  return ctx;
}
