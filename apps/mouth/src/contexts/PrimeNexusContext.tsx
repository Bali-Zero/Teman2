'use client';

import React, { createContext, useContext, useState, useCallback, useRef } from 'react';

// ─── Types ──────────────────────────────────────────────────────────

export type PrimeMode = 'invest' | 'crm' | 'intel';

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
    entity_type: 'company' | 'client';
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
  label: 'GREEN' | 'YELLOW' | 'RED';
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
}

export const PrimeNexusContext = createContext<PrimeNexusContextType | null>(null);

// ─── Provider ───────────────────────────────────────────────────────

export function PrimeNexusProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<PrimeMode>('invest');
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Bounds + intelligence
  const [bounds, setBounds] = useState<MapBounds | null>(null);
  const [intelligenceData, setIntelligenceData] = useState<IntelligenceData | null>(null);
  const [isLoadingIntelligence, setIsLoadingIntelligence] = useState(false);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const analyzePoint = useCallback(async (lat: number, lng: number, kbliCode?: string) => {
    setIsAnalyzing(true);
    try {
      const res = await fetch('/api/prime/v2/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lat,
          lng,
          kbli_code: kbliCode || undefined,
          is_pma: true,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setAnalysis(data);
      }
    } catch {
      // Silently fail — analysis is optional enhancement
    } finally {
      setIsAnalyzing(false);
    }
  }, []);

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
        const params = new URLSearchParams({
          sw_lat: String(newBounds.sw_lat),
          sw_lng: String(newBounds.sw_lng),
          ne_lat: String(newBounds.ne_lat),
          ne_lng: String(newBounds.ne_lng),
        });
        const res = await fetch(`/api/prime/v2/intelligence?${params.toString()}`);
        if (res.ok) {
          const data = await res.json();
          setIntelligenceData(data);
        } else if (res.status === 401 || res.status === 403) {
          // Auth error — set empty data with auth error flag
          setIntelligenceData({
            type: 'FeatureCollection',
            features: [],
            stats: { auth_error: 1 },
          });
        }
      } catch {
        // Silently fail — show empty state
        setIntelligenceData({ type: 'FeatureCollection', features: [], stats: {} });
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
    throw new Error('usePrimeNexus must be used inside PrimeNexusProvider');
  }
  return ctx;
}
