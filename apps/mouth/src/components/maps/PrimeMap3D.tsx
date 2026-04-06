'use client';
// Prime Intelligence 3D Map — Google Maps JS API (v=beta), maps3d library
// Cache bust: 2026-03-17-1555
import React, { useEffect, useRef, useState, useCallback, useContext } from 'react';
import Script from 'next/script';
import Image from 'next/image';
import { PrimeZantaraChat } from './PrimeZantaraChat';
import { logger } from '@/lib/logger';
import { PrimeNexusContext } from '@/contexts/PrimeNexusContext';

// ─── Types ───────────────────────────────────────────────────────────────────

interface Coordinate {
  lat: number;
  lng: number;
  altitude?: number;
}

interface BusinessOpportunity {
  code?: string;
  title_en: string;
  title_id?: string;
  pma_open?: boolean;
  category_en: string;
}

interface BuildingCodes {
  zone_name_id: string;
  kdb_pct: number;
  klb_ratio: number;
  kdh_pct: number;
  ktb_pct: number;
  height_limit: string;
  max_height_meters: number | null;
  setback: string;
  notes: string;
}

interface ZoningInfo {
  status: 'found' | 'outside_coverage' | 'error';
  district?: string;
  subdistrict?: string;
  zone_code?: string;
  zone_name?: string;
  zone_label_en?: string;
  zone_color_hex?: string;
  zone_type?: string;
  zone_description_en?: string;
  is_restricted?: boolean;
  businesses?: BusinessOpportunity[];
  overlays?: Record<string, string>;
  building_codes?: BuildingCodes;
  allowed_kbli?: string[];
  risk_score?: number;
  avg_price_per_are?: number;
  intel_articles?: IntelArticle[];
  source?: string;
  message?: string;
}

interface IntelArticle {
  title: string;
  source_url: string;
  category?: string;
  source_name?: string;
  published_at?: string;
  relevance_score?: number;
}

interface MapLayers {
  zoneColors: boolean;
  extrusion: boolean;
  kkop: boolean;
  lp2b: boolean;
  tsunami: boolean;
  floodRisk: boolean;
  templeBuffer: boolean;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const ZONE_COLORS: Record<string, string> = {
  'K-1': '#E8472A',
  'K-2': '#E8472A',
  'K-3': '#E8472A',
  'C-1': '#F0826E',
  'C-2': '#F0826E',
  W: '#FFA5FF',
  'W-1': '#FFA5FF',
  'W-2': '#FF85F5',
  'R-2': '#FF7D00',
  'R-3': '#FF9D30',
  'R-4': '#FFB860',
  'P-1': '#C8C83C',
  'P-2': '#D4D44A',
  'P-3': '#C8C83C',
  'P-4': '#BEB82E',
  KT: '#A855F7',
  KPI: '#690000',
  'SPU-1': '#D4845A',
  'SPU-2': '#D4845A',
  'SPU-3': '#D4845A',
  'SPU-4': '#D4845A',
  HL: '#224027',
  'KS-4': '#224027',
  THR: '#224027',
  TWA: '#224027',
  EM: '#2D966E',
  PS: '#05D7D7',
  SS: '#05D7D7',
  SP: '#05D7D7',
  LS: '#F59E0B',
  CB: '#B45309',
  'RTH-2': '#3BA062',
  'RTH-3': '#3BA062',
  'RTH-4': '#3BA062',
  'RTH-5': '#3BA062',
  'RTH-7': '#6B7280',
  'RTH-8': '#3BA062',
  RTNH: '#9CA3AF',
  BA: '#97DBF2',
  BJ: '#9CA3AF',
  TR: '#6B7280',
  HK: '#9B00FF',
  'PL-3': '#6B7280',
  'PL-4': '#6B7280',
  PTL: '#6B7280',
  'IK-1': '#507DD2',
};

const CATEGORY_COLORS: Record<string, string> = {
  'F&B': 'bg-orange-500/20 text-orange-300 border-orange-500/30',
  Hospitality: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  Wellness: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  Property: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
  Retail: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
  Creative: 'bg-pink-500/20 text-pink-300 border-pink-500/30',
  Technology: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  Education: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
  Services: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
  Industry: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  Finance: 'bg-teal-500/20 text-teal-300 border-teal-500/30',
  Healthcare: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
};

function formatPrice(pricePerAre: number): string {
  if (!pricePerAre || pricePerAre === 0) return '—';
  const billions = pricePerAre / 1_000_000_000;
  if (billions >= 1) return `Rp ${billions.toFixed(1)}B / are`;
  const millions = pricePerAre / 1_000_000;
  return `Rp ${millions.toFixed(0)}M / are`;
}

// ─── Accordion Section ───────────────────────────────────────────────────────

function AccordionSection({
  id,
  icon,
  title,
  defaultOpen = false,
  children,
  hasContent = true,
}: {
  id: string;
  icon: React.ReactNode;
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
  hasContent?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  if (!hasContent) return null;

  return (
    <div className="border-b border-white/5 last:border-0">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-colors group"
      >
        <div className="flex items-center gap-2.5">
          <span
            className={`transition-colors ${open ? 'text-[#d4845a]' : 'text-slate-500 group-hover:text-slate-400'}`}
          >
            {icon}
          </span>
          <span
            className={`text-sm font-semibold tracking-tight transition-colors ${open ? 'text-white' : 'text-slate-400 group-hover:text-slate-300'}`}
          >
            {title}
          </span>
        </div>
        <svg
          className={`w-3.5 h-3.5 transition-all duration-200 ${open ? 'rotate-180 text-[#d4845a]' : 'text-slate-600'}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

// ─── Layer Toggle ─────────────────────────────────────────────────────────────

function LayerToggle({
  label,
  icon,
  enabled,
  onChange,
  disabled = false,
}: {
  label: string;
  icon: string;
  enabled: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <div className={`flex items-center justify-between py-2 ${disabled ? 'opacity-40' : ''}`}>
      <div className="flex items-center gap-2">
        <span className="text-sm">{icon}</span>
        <span className="text-xs text-slate-300">{label}</span>
        {disabled && <span className="text-[10px] text-slate-600 ml-1">soon</span>}
      </div>
      <button
        disabled={disabled}
        onClick={() => !disabled && onChange(!enabled)}
        className={`relative w-9 h-5 rounded-full transition-colors duration-200 ${enabled ? 'bg-[#d4845a]' : 'bg-white/10'}`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${enabled ? 'translate-x-4' : 'translate-x-0'}`}
        />
      </button>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function PrimeMap3D() {
  // Optional: connect to PrimeNexusContext when mounted inside PrimeNexusLayout.
  // Falls back gracefully to null when no provider is present.
  const primeNexus = useContext(PrimeNexusContext);

  const mapContainerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [map3DElement, setMap3DElement] = useState<any>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [selectedPoint, setSelectedPoint] = useState<Coordinate | null>(null);
  const [zoningResult, setZoningResult] = useState<ZoningInfo | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [searchValue, setSearchValue] = useState('');
  const [kbliSearchQuery, setKbliSearchQuery] = useState('');
  const [highlightedZones, setHighlightedZones] = useState<string[]>([]);
  const [isSearchingKbli, setIsSearchingKbli] = useState(false);
  const [streetAddress, setStreetAddress] = useState<string | null>(null);
  const [sidebarWidth, setSidebarWidth] = useState(320);
  const [showFilters, setShowFilters] = useState(false);
  const [sidebarTab, setSidebarTab] = useState<'data' | 'chat'>('data');
  const [layers, setLayers] = useState<MapLayers>({
    zoneColors: true,
    extrusion: false,
    kkop: false,
    lp2b: false,
    tsunami: false,
    floodRisk: false,
    templeBuffer: false,
  });

  // Refs for zone polygon management
  const zonesGeoJsonRef = useRef<any>(null);
  const zonePolygonsRef = useRef<any[]>([]);
  const isResizing = useRef(false);
  const filtersRef = useRef<HTMLDivElement>(null);

  // ── Resize handle ──────────────────────────────────────────────────────────
  const startResize = useCallback((e: React.MouseEvent) => {
    isResizing.current = true;
    e.preventDefault();

    const onMove = (ev: MouseEvent) => {
      if (!isResizing.current) return;
      const newW = Math.min(480, Math.max(260, ev.clientX));
      setSidebarWidth(newW);
    };
    const onUp = () => {
      isResizing.current = false;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, []);

  // ── Close filter panel on outside click ───────────────────────────────────
  useEffect(() => {
    if (!showFilters) return;
    const handler = (e: MouseEvent) => {
      if (filtersRef.current && !filtersRef.current.contains(e.target as Node)) {
        setShowFilters(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showFilters]);

  // ── Reverse geocode ────────────────────────────────────────────────────────
  const reverseGeocode = useCallback(async (lat: number, lng: number) => {
    const key = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
    if (!key) return;
    try {
      const res = await fetch(
        `https://maps.googleapis.com/maps/api/geocode/json?latlng=${lat},${lng}&key=${key}`
      );
      const data = await res.json();
      if (data.results?.[0]) {
        const components = data.results[0].address_components as Array<{
          long_name: string;
          types: string[];
        }>;
        const route = components.find((c) => c.types.includes('route'))?.long_name;
        const streetNum = components.find((c) => c.types.includes('street_number'))?.long_name;
        if (route) {
          setStreetAddress(streetNum ? `${route} ${streetNum}` : route);
        } else {
          setStreetAddress(data.results[0].formatted_address?.split(',')[0] ?? null);
        }
      }
    } catch (e) {
      logger.error(
        'Reverse geocode failed',
        { metadata: { lat, lng } },
        e instanceof Error ? e : new Error(String(e))
      );
    }
  }, []);

  // ── Analyze location ───────────────────────────────────────────────────────
  const analyzeLocation = useCallback(
    async (pos: Coordinate) => {
      setIsAnalyzing(true);
      setZoningResult(null);
      setSidebarTab('data');
      setStreetAddress(null);
      try {
        const [zoningRes] = await Promise.all([
          fetch(`/api/prime/zoning?lat=${pos.lat}&lng=${pos.lng}`).then((r) => r.json()),
          reverseGeocode(pos.lat, pos.lng),
        ]);
        setZoningResult(zoningRes as ZoningInfo);
        // Bridge to PrimeNexusContext (INVEST mode analysis) — no-op when no provider
        primeNexus?.analyzePoint(pos.lat, pos.lng);
      } catch (e) {
        logger.error(
          'Zoning fetch failed',
          { metadata: { lat: pos.lat, lng: pos.lng } },
          e instanceof Error ? e : new Error(String(e))
        );
        setZoningResult({
          status: 'error',
          message: 'Could not reach zoning database.',
        });
      } finally {
        setIsAnalyzing(false);
      }
    },
    [reverseGeocode, primeNexus]
  );

  // ── Zone colors layer ──────────────────────────────────────────────────────
  const toggleZoneColors = useCallback(
    async (enabled: boolean, extrude: boolean = false, highlightCodes: string[] = []) => {
      const map = map3DElement;
      if (!map) return;

      // Always clear existing polygons first to redraw correctly
      zonePolygonsRef.current.forEach((p) => {
        try {
          p.remove();
        } catch (_) {
          /* already removed */
        }
      });
      zonePolygonsRef.current = [];

      if (!enabled) return;

      try {
        if (!zonesGeoJsonRef.current) {
          const res = await fetch('/api/prime/zones-geojson');
          zonesGeoJsonRef.current = await res.json();
        }

        const { Polygon3DElement } = await (window as any).google.maps.importLibrary('maps3d');
        const features = zonesGeoJsonRef.current?.features ?? [];

        for (const feature of features) {
          const geom = feature.geometry;
          const props = feature.properties;
          const zoneCode = props?.zone_code;
          let color: string = props?.color ?? '#6B7280';

          if (!geom) continue;

          // KBLI Highlight logic
          const isHighlighted = highlightCodes.length > 0 && highlightCodes.includes(zoneCode);
          if (highlightCodes.length > 0 && !isHighlighted) {
            // Fade out non-matching zones
            color = '#334155';
          }

          try {
            // Build outer coords from GeoJSON coordinates
            const coords =
              geom.type === 'Polygon'
                ? geom.coordinates[0]
                : geom.type === 'MultiPolygon'
                  ? geom.coordinates[0][0]
                  : null;

            if (!coords || coords.length < 3) continue;

            const outerCoords = coords.map(([lng, lat]: [number, number]) => ({
              lat,
              lng,
              altitude: 0,
            }));

            // Extrusion height calculation
            let altitude = 0;
            if (extrude) {
              altitude =
                props?.max_height_meters ?? (props?.max_floors ? props.max_floors * 3.5 : 5);
            }

            const poly = new Polygon3DElement({
              altitudeMode: extrude ? 'RELATIVE_TO_GROUND' : 'CLAMP_TO_GROUND',
              fillColor: isHighlighted ? `${color}BB` : `${color}55`, // Higher opacity for highlights
              strokeColor: isHighlighted ? '#FFFFFF' : `${color}99`,
              strokeWidth: isHighlighted ? 3 : 1,
              extruded: extrude,
              drawsOccludedSegments: true,
            });

            if (extrude) {
              poly.outerCoordinates = outerCoords.map((c: Record<string, unknown>) => ({
                ...c,
                altitude,
              }));
            } else {
              poly.outerCoordinates = outerCoords;
            }

            map.append(poly);
            zonePolygonsRef.current.push(poly);
          } catch (_) {
            /* skip malformed polygons */
          }
        }

        logger.info(
          `[Prime] Zone layer: ${zonePolygonsRef.current.length} polygons drawn (extrude=${extrude})`
        );
      } catch (e) {
        logger.error('Zone colors layer failed', {}, e instanceof Error ? e : new Error(String(e)));
      }
    },
    [map3DElement]
  );

  // ── Layer toggle handler ───────────────────────────────────────────────────
  const handleLayerChange = useCallback(
    (layer: keyof MapLayers, value: boolean) => {
      const nextLayers = { ...layers, [layer]: value };
      setLayers(nextLayers);

      if (layer === 'zoneColors' || layer === 'extrusion') {
        toggleZoneColors(nextLayers.zoneColors, nextLayers.extrusion, highlightedZones);
      }
    },
    [layers, toggleZoneColors, highlightedZones]
  );

  const handleKbliSearch = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!kbliSearchQuery.trim()) {
        setHighlightedZones([]);
        toggleZoneColors(layers.zoneColors, layers.extrusion, []);
        return;
      }

      setIsSearchingKbli(true);
      try {
        const res = await fetch(`/api/prime/search-kbli?q=${encodeURIComponent(kbliSearchQuery)}`);
        const data = await res.json();
        if (data.status === 'success' && data.matching_zone_codes) {
          setHighlightedZones(data.matching_zone_codes);
          // Force redraw with highlights
          toggleZoneColors(true, layers.extrusion, data.matching_zone_codes);
          // Enable zone colors if they weren't enabled
          if (!layers.zoneColors) {
            setLayers((prev) => ({ ...prev, zoneColors: true }));
          }
        }
      } catch (err) {
        logger.error('KBLI search failed', {}, err instanceof Error ? err : new Error(String(err)));
      } finally {
        setIsSearchingKbli(false);
      }
    },
    [kbliSearchQuery, layers, toggleZoneColors]
  );

  // ── Init 3D map ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (map3DElement && layers.zoneColors) {
      toggleZoneColors(true, layers.extrusion, highlightedZones);
    }
  }, [map3DElement, toggleZoneColors, layers.extrusion, layers.zoneColors, highlightedZones]);

  useEffect(() => {
    if (!isLoaded || !mapContainerRef.current) return;

    const initMap = async () => {
      try {
        const { Map3DElement, Marker3DInteractiveElement, PinElement } = await (
          window as any
        ).google.maps.importLibrary('maps3d');

        const map = new Map3DElement({
          center: { lat: -8.648, lng: 115.132, altitude: 200 },
          tilt: 65,
          range: 1500,
          heading: 45,
          mode: 'HYBRID',
        });

        if (!mapContainerRef.current) return;
        mapContainerRef.current.appendChild(map);
        setMap3DElement(map);

        map.addEventListener('gmp-click', async (event: any) => {
          if (event.position) {
            const newPos = {
              lat: event.position.lat,
              lng: event.position.lng,
              altitude: 0,
            };
            setSelectedPoint(newPos);
            analyzeLocation(newPos);

            const pin = new PinElement({
              background: '#d4845a',
              glyphColor: 'white',
              scale: 1.4,
            });
            const marker = new Marker3DInteractiveElement({
              position: { lat: newPos.lat, lng: newPos.lng, altitude: 10 },
              altitudeMode: 'RELATIVE_TO_GROUND',
              extruded: true,
            });
            marker.appendChild(pin.element);
            map.append(marker);
          }
        });
      } catch (e) {
        logger.error(
          'Failed to initialize 3D map',
          { component: 'PrimeMap3D' },
          e instanceof Error ? e : new Error(String(e))
        );
      }
    };

    initMap();
  }, [isLoaded, analyzeLocation]);

  // ── Places Autocomplete ────────────────────────────────────────────────────
  useEffect(() => {
    if (!isLoaded || !searchInputRef.current) return;

    const initAutocomplete = async () => {
      try {
        const { Autocomplete } = await (window as any).google.maps.importLibrary('places');
        const autocomplete = new Autocomplete(searchInputRef.current, {
          componentRestrictions: { country: 'id' },
          fields: ['geometry', 'name', 'formatted_address'],
          types: ['geocode', 'establishment'],
        });

        autocomplete.addListener('place_changed', () => {
          const place = autocomplete.getPlace();
          if (!place.geometry?.location) return;

          const lat = place.geometry.location.lat();
          const lng = place.geometry.location.lng();
          const newPos = { lat, lng, altitude: 0 };

          setSelectedPoint(newPos);
          setSearchValue(place.name || place.formatted_address || '');
          analyzeLocation(newPos);

          setMap3DElement((currentMap: any) => {
            if (currentMap) {
              currentMap.center = { lat, lng, altitude: 300 };
              currentMap.tilt = 65;
              currentMap.range = 1200;
            }
            return currentMap;
          });
        });
      } catch (e) {
        logger.error(
          'Failed to initialize Places Autocomplete',
          { component: 'PrimeMap3D' },
          e instanceof Error ? e : new Error(String(e))
        );
      }
    };

    initAutocomplete();
  }, [isLoaded, analyzeLocation]);

  // ── Derived values ─────────────────────────────────────────────────────────
  const riskScore = zoningResult?.risk_score ?? 0;
  const isHighRisk = riskScore > 0.7;
  const zoneColor =
    zoningResult?.zone_color_hex ??
    (zoningResult?.zone_code ? (ZONE_COLORS[zoningResult.zone_code] ?? '#6B7280') : '#6B7280');

  const hasOverlays = zoningResult?.overlays && Object.keys(zoningResult.overlays).length > 0;
  const hasBusinesses = !!(zoningResult?.businesses && zoningResult.businesses.length > 0);
  const hasBuildingCodes = !!(zoningResult?.building_codes && !zoningResult.is_restricted);
  const hasPrice = !!(zoningResult?.avg_price_per_are && zoningResult.avg_price_per_are > 0);
  const hasIntel = !!(zoningResult?.intel_articles && zoningResult.intel_articles.length > 0);

  // ── Icons (inline SVG, no extra dep) ──────────────────────────────────────
  const IconPin = (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
      />
    </svg>
  );
  const IconLayers = (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 2l9 4.5-9 4.5L3 6.5 12 2zM3 12l9 4.5 9-4.5M3 17.5l9 4.5 9-4.5"
      />
    </svg>
  );
  const IconBuilding = (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-2 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
      />
    </svg>
  );
  const IconRuler = (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M3 10h18M3 6h18M3 14h18M3 18h18"
      />
    </svg>
  );
  const IconAlert = (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
      />
    </svg>
  );
  const IconTrend = (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
      />
    </svg>
  );
  const IconNews = (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"
      />
    </svg>
  );

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="flex w-full h-screen bg-black overflow-hidden">
      <Script
        src={`https://maps.googleapis.com/maps/api/js?key=${process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY}&v=beta&libraries=maps3d`}
        strategy="afterInteractive"
        onLoad={() => setIsLoaded(true)}
      />

      {/* ── Sidebar ── */}
      <div
        className="relative flex-shrink-0 flex flex-col bg-black border-r border-white/10 h-full overflow-hidden"
        style={{ width: sidebarWidth }}
      >
        {/* Resize handle */}
        <div
          onMouseDown={startResize}
          className="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize bg-transparent hover:bg-[#d4845a]/40 transition-colors z-10"
        />

        {/* Header */}
        <div className="flex items-center justify-center px-4 py-4 border-b border-white/10 flex-shrink-0 overflow-hidden">
          <Image
            src="/assets/logo/balizeromap.svg"
            alt="Bali Zero Map"
            width={240}
            height={80}
            className="flex-shrink-0"
            unoptimized
          />
        </div>

        {/* Tab bar — visible after map click */}
        {zoningResult && (
          <div className="flex border-b border-white/10 flex-shrink-0">
            <button
              onClick={() => setSidebarTab('data')}
              className={`flex-1 py-2 text-xs font-semibold tracking-wide transition-colors ${
                sidebarTab === 'data'
                  ? 'text-white border-b-2 border-[#d4845a]'
                  : 'text-slate-500 hover:text-slate-400'
              }`}
            >
              📊 Data
            </button>
            <button
              onClick={() => setSidebarTab('chat')}
              className={`flex-1 py-2 text-xs font-semibold tracking-wide transition-colors ${
                sidebarTab === 'chat'
                  ? 'text-white border-b-2 border-[#d4845a]'
                  : 'text-slate-500 hover:text-slate-400'
              }`}
            >
              💬 Ask Zantara
            </button>
          </div>
        )}

        {/* Scrollable content */}
        {sidebarTab === 'data' && (
          <div className="flex-1 overflow-y-auto overflow-x-hidden">
            {/* Loading state */}
            {isAnalyzing && (
              <div className="flex items-center gap-3 px-4 py-4 text-[#d4845a]">
                <svg className="animate-spin h-4 w-4 flex-shrink-0" viewBox="0 0 24 24">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                    fill="none"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                <span className="text-sm">Analyzing zoning laws…</span>
              </div>
            )}

            {/* Idle state */}
            {!isAnalyzing && !zoningResult && (
              <div className="flex flex-col items-center justify-center py-12 px-6 text-center">
                <div className="w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mb-4 backdrop-blur-sm">
                  <svg
                    className="w-5 h-5 text-slate-500"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                    />
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                    />
                  </svg>
                </div>
                <p className="text-xs text-slate-500 leading-relaxed">
                  Tap any spot on the map
                  <br />
                  to see what you can build there
                </p>
              </div>
            )}

            {/* Results */}
            {zoningResult && !isAnalyzing && (
              <>
                {zoningResult.status === 'found' ? (
                  <div>
                    {/* ── Location ── */}
                    <AccordionSection
                      id="location"
                      icon={IconPin}
                      title="Location"
                      aria-label="Location"
                      defaultOpen
                      hasContent
                    >
                      <div className="rounded-xl bg-white/5 border border-white/8 p-3 backdrop-blur-sm space-y-1">
                        {streetAddress && (
                          <div className="text-sm font-semibold text-white">{streetAddress}</div>
                        )}
                        <div
                          className={`text-xs text-slate-400 ${streetAddress ? '' : 'text-sm text-white font-medium'}`}
                        >
                          {zoningResult.subdistrict
                            ? `${zoningResult.subdistrict}, ${zoningResult.district}`
                            : zoningResult.district}
                        </div>
                        {selectedPoint && (
                          <div className="text-[10px] text-slate-600 font-mono mt-1">
                            {selectedPoint.lat.toFixed(6)}, {selectedPoint.lng.toFixed(6)}
                          </div>
                        )}
                      </div>
                    </AccordionSection>

                    {/* ── Zone ── */}
                    <AccordionSection
                      id="zone"
                      icon={IconLayers}
                      title="Zone"
                      aria-label="Zone"
                      defaultOpen
                      hasContent
                    >
                      <div
                        className="rounded-xl p-3 border backdrop-blur-sm"
                        style={{
                          backgroundColor: `${zoneColor}14`,
                          borderColor: `${zoneColor}35`,
                        }}
                      >
                        <div className="flex items-start gap-2 mb-1.5">
                          <div className="flex items-center gap-1.5 flex-shrink-0 mt-0.5">
                            <span
                              className="w-2.5 h-2.5 rounded-full"
                              style={{ backgroundColor: zoneColor }}
                            />
                            <span
                              className="font-mono font-bold text-sm"
                              style={{ color: zoneColor }}
                            >
                              {zoningResult.zone_code}
                            </span>
                          </div>
                          <span className="text-white font-semibold text-sm leading-snug">
                            {zoningResult.zone_label_en}
                          </span>
                        </div>
                        <div className="text-[11px] text-slate-500 ml-4 mb-1">
                          {zoningResult.zone_name}
                        </div>
                        {zoningResult.zone_description_en && (
                          <div className="text-xs text-slate-400 ml-4 leading-relaxed">
                            {zoningResult.zone_description_en}
                          </div>
                        )}
                        <div className="ml-4 mt-2">
                          <span
                            className={`text-xs px-1.5 py-0.5 rounded font-medium ${isHighRisk ? 'bg-red-500/20 text-red-300' : 'bg-emerald-500/20 text-emerald-300'}`}
                          >
                            {isHighRisk ? '⚠ High regulatory risk' : '✓ Normal regulatory risk'}
                          </span>
                        </div>
                      </div>
                    </AccordionSection>

                    {/* ── What you can open ── */}
                    <AccordionSection
                      id="businesses"
                      icon={IconBuilding}
                      title="What you can open"
                      aria-label="What you can open"
                      defaultOpen
                      hasContent={hasBusinesses || !!zoningResult.is_restricted}
                    >
                      {zoningResult.is_restricted ? (
                        <div className="rounded-xl bg-red-900/20 border border-red-500/20 p-3 backdrop-blur-sm">
                          <div className="text-xs text-red-400 font-semibold mb-1">
                            ⛔ Protected Zone — No Commercial Activity
                          </div>
                          <div className="text-xs text-slate-400 leading-relaxed">
                            This area is legally protected. No construction or commercial activity
                            is permitted.
                          </div>
                        </div>
                      ) : (
                        <div className="space-y-1.5">
                          {zoningResult.businesses?.map((biz, idx) => (
                            <div
                              key={biz.code ?? `${biz.title_en}-${idx}`}
                              className="flex items-center gap-2 rounded-lg bg-white/5 border border-white/8 px-3 py-2 backdrop-blur-sm hover:bg-white/8 transition-colors"
                            >
                              <span
                                className={`text-xs px-1.5 py-0.5 rounded border flex-shrink-0 ${CATEGORY_COLORS[biz.category_en] ?? CATEGORY_COLORS['Services']}`}
                              >
                                {biz.category_en}
                              </span>
                              <span className="text-xs text-white truncate">{biz.title_en}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </AccordionSection>

                    {/* ── Development Limits ── */}
                    <AccordionSection
                      id="building"
                      icon={IconRuler}
                      title="Development Limits"
                      aria-label="Development Limits"
                      hasContent={hasBuildingCodes}
                    >
                      {zoningResult.building_codes && (
                        <div className="space-y-2">
                          <div className="grid grid-cols-3 gap-1.5">
                            {[
                              {
                                val: `${zoningResult.building_codes.kdb_pct}%`,
                                label: 'Coverage',
                              },
                              {
                                val: zoningResult.building_codes.height_limit.replace(
                                  ' Meter',
                                  'm'
                                ),
                                label: 'Max Height',
                              },
                              {
                                val: `${zoningResult.building_codes.kdh_pct}%`,
                                label: 'Green Area',
                              },
                            ].map(({ val, label }) => (
                              <div
                                key={label}
                                className="rounded-lg bg-white/5 border border-white/8 p-2 text-center backdrop-blur-sm"
                              >
                                <div className="text-white font-semibold text-sm">{val}</div>
                                <div className="text-slate-500 text-[10px] mt-0.5">{label}</div>
                              </div>
                            ))}
                          </div>
                          {/* Height comparison bar */}
                          {zoningResult.building_codes.max_height_meters != null && (
                            <div className="space-y-1">
                              <div className="flex items-end gap-1.5 h-12">
                                {[4, 8, 12, 15].map((h) => (
                                  <div
                                    key={h}
                                    className="flex-1 flex flex-col items-center justify-end h-full"
                                  >
                                    <div
                                      className={`w-full rounded-t transition-all ${
                                        h <= (zoningResult.building_codes?.max_height_meters ?? 0)
                                          ? 'bg-[#d4845a]/60'
                                          : 'bg-white/5'
                                      }`}
                                      style={{ height: `${(h / 15) * 100}%` }}
                                    />
                                    <span className="text-[8px] text-slate-600 mt-0.5">{h}m</span>
                                  </div>
                                ))}
                              </div>
                              <div className="text-[10px] text-center text-slate-500">
                                Zone max:{' '}
                                <span className="text-[#d4845a] font-semibold">
                                  {zoningResult.building_codes.max_height_meters}m
                                </span>{' '}
                                | KLB:{' '}
                                <span className="text-white/80 font-medium">
                                  {zoningResult.building_codes.klb_ratio}
                                </span>
                              </div>
                            </div>
                          )}
                          {zoningResult.building_codes.notes && (
                            <div className="text-[10px] text-slate-600 leading-relaxed">
                              {zoningResult.building_codes.notes}
                            </div>
                          )}
                        </div>
                      )}
                    </AccordionSection>

                    {/* ── Overlays & Risks ── */}
                    <AccordionSection
                      id="overlays"
                      icon={IconAlert}
                      title="Overlays & Risks"
                      aria-label="Overlays & Risks"
                      hasContent={!!hasOverlays}
                    >
                      <div className="space-y-1.5">
                        {zoningResult.overlays?.kkop && (
                          <div className="text-xs rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300 px-3 py-2 backdrop-blur-sm">
                            ✈ KKOP Aviation Zone — height restrictions apply
                          </div>
                        )}
                        {zoningResult.overlays?.lp2b && (
                          <div className="text-xs rounded-xl bg-green-500/10 border border-green-500/20 text-green-300 px-3 py-2 backdrop-blur-sm">
                            🌾 Protected Farmland (LP2B) — conversion restricted
                          </div>
                        )}
                        {zoningResult.overlays?.tsunami && (
                          <div className="text-xs rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-300 px-3 py-2 backdrop-blur-sm">
                            🌊 Tsunami Risk Zone — {zoningResult.overlays.tsunami}
                          </div>
                        )}
                        {zoningResult.overlays?.heritage && (
                          <div className="text-xs rounded-xl bg-yellow-500/10 border border-yellow-500/20 text-yellow-300 px-3 py-2 backdrop-blur-sm">
                            🏛 Heritage Area — {zoningResult.overlays.heritage}
                          </div>
                        )}
                      </div>
                    </AccordionSection>

                    {/* ── Land Price ── */}
                    <AccordionSection
                      id="price"
                      icon={IconTrend}
                      title="Land Price"
                      aria-label="Land Price"
                      hasContent={hasPrice}
                    >
                      <div className="rounded-xl bg-white/5 border border-white/8 px-4 py-3 backdrop-blur-sm">
                        <div className="text-xl font-bold text-white">
                          {formatPrice(zoningResult.avg_price_per_are!)}
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5">
                          Estimated market rate — {zoningResult.subdistrict}
                        </div>
                      </div>
                    </AccordionSection>

                    {/* ── Latest Intel ── */}
                    <AccordionSection
                      id="intel"
                      icon={IconNews}
                      title="Latest Intel"
                      aria-label="Latest Intel"
                      hasContent={hasIntel}
                    >
                      <div className="space-y-1.5">
                        {zoningResult.intel_articles?.map((article, idx) => (
                          <a
                            key={idx}
                            href={article.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-start gap-2 rounded-xl bg-white/5 border border-white/8 px-3 py-2 backdrop-blur-sm hover:bg-white/10 hover:border-white/15 transition-colors group"
                          >
                            <span className="text-slate-500 text-[10px] mt-0.5 flex-shrink-0">
                              ↗
                            </span>
                            <div className="min-w-0">
                              <div className="text-xs text-slate-300 group-hover:text-white transition-colors line-clamp-2 leading-snug">
                                {article.title}
                              </div>
                              {article.source_name && (
                                <div className="text-[10px] text-slate-600 mt-0.5">
                                  {article.source_name}
                                </div>
                              )}
                            </div>
                          </a>
                        ))}
                      </div>
                    </AccordionSection>

                    {/* Source */}
                    <div className="px-4 py-2 text-[10px] text-slate-700">
                      Source: {zoningResult.source}
                    </div>
                  </div>
                ) : zoningResult.status === 'outside_coverage' ? (
                  <div className="mx-4 my-4 rounded-xl bg-amber-500/10 border border-amber-500/20 px-4 py-3 backdrop-blur-sm">
                    <div className="text-xs text-amber-400 font-semibold mb-1">
                      Outside coverage area
                    </div>
                    <div className="text-xs text-slate-400 leading-relaxed">
                      This specific spot doesn't have detailed RDTR zoning data yet. We currently
                      cover most of Badung, Gianyar, Tabanan, Denpasar, Bangli, Buleleng,
                      Karangasem, and Jembrana.
                    </div>
                  </div>
                ) : (
                  <div className="mx-4 my-4 rounded-xl bg-red-900/20 border border-red-500/20 px-4 py-3 backdrop-blur-sm">
                    <div className="text-xs text-red-400">
                      {zoningResult.message ?? 'Lookup failed. Please try again.'}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* CHAT TAB */}
        {sidebarTab === 'chat' && (
          <PrimeZantaraChat
            zoningResult={zoningResult}
            selectedPoint={selectedPoint}
            streetAddress={streetAddress}
          />
        )}

        {/* CTA — sticky bottom */}
        {zoningResult?.status === 'found' && (
          <div className="flex-shrink-0 px-4 py-4 border-t border-white/10 bg-black">
            <button className="w-full bg-[#d4845a] hover:bg-[#c27348] text-white font-semibold py-2.5 rounded-xl transition-colors text-sm shadow-lg shadow-[#d4845a]/20">
              Get a Free Business Setup Quote →
            </button>
          </div>
        )}
      </div>

      {/* ── Map area ── */}
      <div className="relative flex-1 h-full">
        {/* Skeleton placeholder while Maps 3D WASM loads */}
        {!isLoaded && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-[#0c0c0e]">
            <div className="w-16 h-16 border-2 border-slate-800 border-t-[#d4845a] rounded-full animate-spin mb-4" />
            <p className="text-sm text-slate-500 font-medium">Loading 3D Map</p>
            <p className="text-xs text-slate-700 mt-1">Initializing terrain data...</p>
          </div>
        )}
        {/* 3D Map canvas */}
        <div ref={mapContainerRef} className="absolute inset-0 w-full h-full" />

        {/* Search Bar */}
        <div className="absolute top-5 left-1/2 -translate-x-1/2 z-20 w-80">
          <div className="relative">
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <input
              ref={searchInputRef}
              type="text"
              aria-label="Search location by address or coordinates"
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key !== 'Enter') return;
                const val = searchValue.trim();
                // Match: -8.644590, 115.148143 or -8.644590 115.148143
                const match = val.match(/^(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)$/);
                if (!match) return;
                const lat = parseFloat(match[1]);
                const lng = parseFloat(match[2]);
                if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return;
                const newPos = { lat, lng, altitude: 0 };
                setSelectedPoint(newPos);
                analyzeLocation(newPos);
                setMap3DElement((currentMap: any) => {
                  if (currentMap) {
                    currentMap.center = { lat, lng, altitude: 300 };
                    currentMap.tilt = 65;
                    currentMap.range = 1200;
                  }
                  return currentMap;
                });
              }}
              placeholder="Search location or -8.644, 115.148…"
              className="w-full pl-9 pr-4 py-2.5 bg-black/85 backdrop-blur-xl text-white placeholder-slate-500 rounded-xl border border-white/15 shadow-2xl focus:outline-none focus:border-[#d4845a]/60 text-sm"
            />
          </div>
        </div>

        {/* Bottom-center: logo watermark */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-20 pointer-events-none">
          <Image
            src="/assets/logo/balizeromap.svg"
            alt="Bali Zero Map"
            width={320}
            height={107}
            className="opacity-100 drop-shadow-[0_2px_12px_rgba(0,0,0,0.7)]"
            unoptimized
          />
        </div>

        {/* Bottom-right: coordinates + filter button */}
        <div className="absolute bottom-6 right-6 z-20 flex flex-col items-end gap-2">
          {/* Coordinates */}
          {selectedPoint && (
            <div className="text-[10px] text-slate-500 font-mono bg-black/60 backdrop-blur-sm rounded-lg px-2.5 py-1 border border-white/10">
              {selectedPoint.lat.toFixed(5)}, {selectedPoint.lng.toFixed(5)}
            </div>
          )}

          {/* Filter panel */}
          {showFilters && (
            <div
              ref={filtersRef}
              className="bg-black/90 backdrop-blur-xl border border-white/15 rounded-2xl p-4 w-56 shadow-2xl"
            >
              <div className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">
                Business Matching
              </div>
              <form onSubmit={handleKbliSearch} className="mb-4">
                <div className="relative">
                  <input
                    type="text"
                    value={kbliSearchQuery}
                    onChange={(e) => setKbliSearchQuery(e.target.value)}
                    placeholder="Search Business (e.g. Gym)"
                    aria-label="Search business type"
                    className="w-full pl-3 pr-8 py-1.5 bg-white/5 border border-white/10 rounded-lg text-xs text-white placeholder-slate-600 focus:outline-none focus:border-[#d4845a]/50"
                  />
                  <button
                    type="submit"
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white"
                  >
                    {isSearchingKbli ? (
                      <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                          fill="none"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        />
                      </svg>
                    ) : (
                      <svg
                        className="w-3 h-3"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                        />
                      </svg>
                    )}
                  </button>
                </div>
                {highlightedZones.length > 0 && (
                  <div className="mt-1.5 flex justify-between items-center px-1">
                    <span className="text-[10px] text-emerald-400 font-medium">
                      {highlightedZones.length} matching zones
                    </span>
                    <button
                      onClick={() => {
                        setKbliSearchQuery('');
                        setHighlightedZones([]);
                        toggleZoneColors(layers.zoneColors, layers.extrusion, []);
                      }}
                      className="text-[10px] text-slate-500 hover:text-red-400 underline"
                    >
                      Clear
                    </button>
                  </div>
                )}
              </form>

              <div className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">
                Map Layers
              </div>
              <LayerToggle
                icon="🎨"
                label="Zone colors"
                enabled={layers.zoneColors}
                onChange={(v) => handleLayerChange('zoneColors', v)}
              />
              <LayerToggle
                icon="🏢"
                label="3D Extrusion"
                enabled={layers.extrusion}
                onChange={(v) => handleLayerChange('extrusion', v)}
              />
              <LayerToggle
                icon="✈️"
                label="Aviation zones"
                enabled={layers.kkop}
                onChange={(v) => handleLayerChange('kkop', v)}
                disabled
              />
              <LayerToggle
                icon="🕌"
                label="Temple Buffer"
                enabled={layers.templeBuffer}
                onChange={(v) => handleLayerChange('templeBuffer', v)}
                disabled
              />
              <LayerToggle
                icon="🌊"
                label="Flood Risk"
                enabled={layers.floodRisk}
                onChange={(v) => handleLayerChange('floodRisk', v)}
                disabled
              />
            </div>
          )}

          {/* Filter button */}
          <button
            onClick={() => setShowFilters((s) => !s)}
            className={`w-10 h-10 rounded-xl backdrop-blur-xl border shadow-lg flex items-center justify-center transition-colors ${showFilters ? 'bg-[#d4845a] border-[#d4845a]/60 text-white' : 'bg-black/80 border-white/20 text-slate-400 hover:text-white hover:border-white/30'}`}
            title="Map layers"
            aria-label="Toggle map layers"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
