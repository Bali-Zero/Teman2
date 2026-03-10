'use client';
// Prime Intelligence 3D Map — Google Maps JS API (v=beta), maps3d library
import React, { useEffect, useRef, useState } from 'react';
import Script from 'next/script';
import { logger } from '@/lib/logger';

interface Coordinate {
  lat: number;
  lng: number;
  altitude?: number;
}

interface BusinessOpportunity {
  code: string;
  title_en: string;
  title_id: string;
  pma_open: boolean;
  category_en: string;
}

interface ZoningInfo {
  status: "found" | "outside_coverage" | "error";
  district?: string;
  subdistrict?: string;
  zone_code?: string;
  zone_name?: string;
  zone_type?: string;
  zone_description_en?: string;
  is_restricted?: boolean;
  businesses?: BusinessOpportunity[];
  allowed_kbli?: string[];
  risk_score?: number;
  avg_price_per_are?: number;
  source?: string;
  message?: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  "F&B": "bg-orange-500/20 text-orange-300 border-orange-500/30",
  "Hospitality": "bg-blue-500/20 text-blue-300 border-blue-500/30",
  "Wellness": "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  "Property": "bg-purple-500/20 text-purple-300 border-purple-500/30",
  "Retail": "bg-yellow-500/20 text-yellow-300 border-yellow-500/30",
  "Creative": "bg-pink-500/20 text-pink-300 border-pink-500/30",
  "Technology": "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
  "Education": "bg-indigo-500/20 text-indigo-300 border-indigo-500/30",
  "Services": "bg-slate-500/20 text-slate-300 border-slate-500/30",
  "Industry": "bg-amber-500/20 text-amber-300 border-amber-500/30",
  "Finance": "bg-teal-500/20 text-teal-300 border-teal-500/30",
  "Healthcare": "bg-rose-500/20 text-rose-300 border-rose-500/30",
  "Construction": "bg-gray-500/20 text-gray-300 border-gray-500/30",
};

function formatPrice(pricePerAre: number): string {
  if (!pricePerAre || pricePerAre === 0) return "—";
  const billions = pricePerAre / 1_000_000_000;
  if (billions >= 1) return `Rp ${billions.toFixed(1)}B / are`;
  const millions = pricePerAre / 1_000_000;
  return `Rp ${millions.toFixed(0)}M / are`;
}

export default function PrimeMap3D() {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [map3DElement, setMap3DElement] = useState<any>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [selectedPoint, setSelectedPoint] = useState<Coordinate | null>(null);
  const [zoningResult, setZoningResult] = useState<ZoningInfo | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [searchValue, setSearchValue] = useState('');

  // Load the map once the script is ready
  useEffect(() => {
    if (!isLoaded || !mapContainerRef.current) return;

    const initMap = async () => {
      try {
        const { Map3DElement, Marker3DInteractiveElement, PinElement } =
          await (window as any).google.maps.importLibrary("maps3d");

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
            const newPos = { lat: event.position.lat, lng: event.position.lng, altitude: 0 };
            setSelectedPoint(newPos);
            analyzeLocation(newPos);

            const pin = new PinElement({
              background: '#1a73e8',
              glyphColor: 'white',
              scale: 1.5
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
        logger.error("Failed to initialize 3D map", { component: "PrimeMap3D", action: "initMap" }, e instanceof Error ? e : new Error(String(e)));
      }
    };

    initMap();
  }, [isLoaded]);

  // Initialize Places Autocomplete
  useEffect(() => {
    if (!isLoaded || !searchInputRef.current) return;

    const initAutocomplete = async () => {
      try {
        const { Autocomplete } = await (window as any).google.maps.importLibrary("places");
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
        logger.error("Failed to initialize Places Autocomplete", { component: "PrimeMap3D" }, e instanceof Error ? e : new Error(String(e)));
      }
    };

    initAutocomplete();
  }, [isLoaded]);

  const analyzeLocation = async (pos: Coordinate) => {
    setIsAnalyzing(true);
    setZoningResult(null);
    try {
      const res = await fetch(`/api/prime/zoning?lat=${pos.lat}&lng=${pos.lng}`);
      const data: ZoningInfo = await res.json();
      setZoningResult(data);
    } catch (e) {
      logger.error("Zoning fetch failed", { metadata: { lat: pos.lat, lng: pos.lng } }, e instanceof Error ? e : new Error(String(e)));
      setZoningResult({ status: "error", message: "Could not reach zoning database." });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const riskScore = zoningResult?.risk_score ?? 0;
  const isHighRisk = riskScore > 0.7;

  return (
    <div className="relative w-full h-[800px] bg-slate-900 rounded-xl overflow-hidden shadow-2xl border border-slate-700">

      <Script
        src={`https://maps.googleapis.com/maps/api/js?key=${process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY}&v=beta&libraries=maps3d,places`}
        strategy="afterInteractive"
        onLoad={() => setIsLoaded(true)}
      />

      {/* 3D Map */}
      <div ref={mapContainerRef} className="absolute inset-0 w-full h-full" />

      {/* Search Bar */}
      <div className="absolute top-6 left-1/2 -translate-x-1/2 z-20 w-96">
        <div className="relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            ref={searchInputRef}
            type="text"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            placeholder="Search location in Bali..."
            className="w-full pl-10 pr-4 py-3 bg-black/80 backdrop-blur-md text-white placeholder-slate-400 rounded-lg border border-white/20 shadow-xl focus:outline-none focus:border-blue-500 text-sm"
          />
        </div>
      </div>

      {/* Intelligence Panel */}
      <div className="absolute top-6 left-6 z-10 w-80 bg-black/85 backdrop-blur-md text-white rounded-xl border border-white/10 shadow-2xl overflow-hidden">

        {/* Header */}
        <div className="px-5 pt-5 pb-4 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center font-bold font-serif text-sm">P</div>
            <h2 className="text-lg font-semibold tracking-tight">Prime Intelligence</h2>
          </div>
          {!selectedPoint && (
            <p className="text-xs text-slate-400 mt-2 leading-relaxed">
              Click anywhere on the map to discover what businesses you can open at that location.
            </p>
          )}
        </div>

        {/* Content */}
        <div className="px-5 py-4 max-h-[680px] overflow-y-auto">

          {/* Loading */}
          {isAnalyzing && (
            <div className="flex items-center gap-3 text-blue-400 animate-pulse py-2">
              <svg className="animate-spin h-4 w-4 flex-shrink-0" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span className="text-sm">Analyzing zoning laws...</span>
            </div>
          )}

          {/* Results */}
          {zoningResult && !isAnalyzing && (
            <>
              {zoningResult.status === "found" ? (
                <div className="space-y-4">

                  {/* Location */}
                  <div>
                    <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Location</div>
                    <div className="text-sm font-medium text-white">
                      {zoningResult.subdistrict
                        ? `${zoningResult.subdistrict}, ${zoningResult.district}`
                        : zoningResult.district}
                    </div>
                    {zoningResult.avg_price_per_are && zoningResult.avg_price_per_are > 0 && (
                      <div className="text-xs text-slate-400 mt-0.5">
                        Est. land price: {formatPrice(zoningResult.avg_price_per_are)}
                      </div>
                    )}
                  </div>

                  {/* Zone */}
                  <div className="bg-slate-800/60 rounded-lg p-3 border border-slate-700/50">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Zoning</div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-emerald-400 font-bold text-base">{zoningResult.zone_code}</span>
                          <span className={`text-xs px-1.5 py-0.5 rounded ${isHighRisk ? 'bg-red-500/20 text-red-300' : 'bg-emerald-500/20 text-emerald-300'}`}>
                            {isHighRisk ? '⚠ High risk' : '✓ Normal'}
                          </span>
                        </div>
                        <div className="text-xs text-slate-400 mt-0.5">{zoningResult.zone_name}</div>
                      </div>
                    </div>
                    {zoningResult.zone_description_en && (
                      <div className="text-xs text-slate-500 mt-2 leading-relaxed border-t border-slate-700/50 pt-2">
                        {zoningResult.zone_description_en}
                      </div>
                    )}
                  </div>

                  {/* Businesses you can open */}
                  {zoningResult.is_restricted ? (
                    <div className="bg-red-900/20 border border-red-500/20 rounded-lg p-3">
                      <div className="text-xs text-red-400 font-medium mb-1">⛔ Protected Zone</div>
                      <div className="text-xs text-slate-400 leading-relaxed">
                        This area is protected by Indonesian law. Commercial activities are not permitted here.
                      </div>
                    </div>
                  ) : zoningResult.businesses && zoningResult.businesses.length > 0 ? (
                    <div>
                      <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">
                        Businesses you can open here
                      </div>
                      <div className="space-y-1.5">
                        {zoningResult.businesses.map((biz) => (
                          <div
                            key={biz.code}
                            className="flex items-center justify-between gap-2 bg-slate-800/40 rounded-lg px-3 py-2 border border-white/5"
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <span className={`text-xs px-1.5 py-0.5 rounded border flex-shrink-0 ${CATEGORY_COLORS[biz.category_en] ?? CATEGORY_COLORS["Services"]}`}>
                                {biz.category_en}
                              </span>
                              <span className="text-sm text-white truncate">{biz.title_en}</span>
                            </div>
                            {biz.pma_open && (
                              <span className="text-xs text-emerald-400 flex-shrink-0 font-medium" title="Open to foreign investors (PMA)">
                                ✓ Foreigner
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                      <div className="text-xs text-slate-600 mt-2">
                        ✓ Foreigner = open to PT PMA (foreign-owned company)
                      </div>
                    </div>
                  ) : null}

                  {/* Source */}
                  <div className="text-xs text-slate-700 pt-1">
                    Source: {zoningResult.source}
                  </div>

                  {/* CTA */}
                  <button className="w-full bg-white text-black font-semibold py-2.5 rounded-lg hover:bg-slate-100 transition-colors text-sm">
                    Get a Free Business Setup Quote →
                  </button>

                </div>
              ) : zoningResult.status === "outside_coverage" ? (
                <div className="text-sm text-amber-400 border-l-2 border-amber-500 pl-3 py-1">
                  <div className="font-medium mb-0.5">Outside coverage area</div>
                  <div className="text-xs text-slate-400">GISTARU data covers Kabupaten Badung only (Kuta, Seminyak, Canggu, Jimbaran, Uluwatu).</div>
                </div>
              ) : (
                <div className="text-sm text-red-400 border-l-2 border-red-500 pl-3 py-1">
                  {zoningResult.message ?? "Lookup failed. Please try again."}
                </div>
              )}
            </>
          )}

          {/* Empty state */}
          {!isAnalyzing && !zoningResult && (
            <div className="text-center py-6 text-slate-500">
              <div className="text-3xl mb-2">📍</div>
              <div className="text-xs">Tap any spot in Bali to see<br />what you can build there</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
