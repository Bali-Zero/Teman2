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

interface ZoningInfo {
  status: "found" | "outside_coverage" | "error";
  district?: string;
  subdistrict?: string;
  zone_code?: string;
  zone_name?: string;
  zone_type?: string;
  allowed_kbli?: string[];
  risk_score?: number;
  source?: string;
  message?: string;
}

export default function PrimeMap3D() {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const [map3DElement, setMap3DElement] = useState<any>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [selectedPoint, setSelectedPoint] = useState<Coordinate | null>(null);
  const [zoningResult, setZoningResult] = useState<ZoningInfo | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Load the map once the script is ready
  useEffect(() => {
    if (!isLoaded || !mapContainerRef.current) return;

    const initMap = async () => {
      try {
        // Import specific 3D map libraries
        const { Map3DElement, Marker3DInteractiveElement, PinElement } = 
          await (window as any).google.maps.importLibrary("maps3d");

        // Create the 3D Map Element
        const map = new Map3DElement({
          center: { lat: -8.648, lng: 115.132, altitude: 200 }, // Default: Canggu area
          tilt: 65,
          range: 1500,
          heading: 45,
          mode: 'HYBRID', // Shows labels and satellite
        });

        // Append to container
        if (!mapContainerRef.current) return;
        mapContainerRef.current.appendChild(map);
        setMap3DElement(map);

        // Add a click listener to the map itself to drop a pin and analyze zoning
        map.addEventListener('gmp-click', async (event: any) => {
           if (event.position) {
             const newPos = { lat: event.position.lat, lng: event.position.lng, altitude: 0 };
             setSelectedPoint(newPos);
             analyzeLocation(newPos);
             
             // Add a temporary marker
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

  const analyzeLocation = async (pos: Coordinate) => {
    setIsAnalyzing(true);
    setZoningResult(null);
    try {
      const res = await fetch(
        `/api/prime/zoning?lat=${pos.lat}&lng=${pos.lng}`,
      );
      const data: ZoningInfo = await res.json();
      setZoningResult(data);
    } catch (e) {
      logger.error("Zoning fetch failed", { metadata: { lat: pos.lat, lng: pos.lng } }, e instanceof Error ? e : new Error(String(e)));
      setZoningResult({ status: "error", message: "Could not reach zoning database." });
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="relative w-full h-[800px] bg-slate-900 rounded-xl overflow-hidden shadow-2xl border border-slate-700">
      
      {/* 
        We use Next.js Script to load the maps API asynchronously.
        v=beta is REQUIRED for 3D Maps.
      */}
      <Script 
        src={`https://maps.googleapis.com/maps/api/js?key=${process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY}&v=beta&libraries=maps3d`} 
        strategy="afterInteractive"
        onLoad={() => setIsLoaded(true)}
      />

      {/* The 3D Map Container */}
      <div ref={mapContainerRef} className="absolute inset-0 w-full h-full" />

      {/* Nuzantara Intelligence Overlay */}
      <div className="absolute top-6 left-6 z-10 w-80 bg-black/80 backdrop-blur-md text-white p-6 rounded-lg border border-white/10 shadow-xl">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center font-bold font-serif">P</div>
          <h2 className="text-xl font-semibold tracking-tight">Prime Intelligence</h2>
        </div>
        
        <p className="text-sm text-slate-300 mb-6 leading-relaxed">
          Click anywhere on the map to analyze zoning laws and business potential in real-time.
        </p>

        {selectedPoint && (
          <div className="bg-slate-800/50 rounded-md p-3 mb-4 border border-slate-700">
            <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Selected Coordinates</div>
            <div className="font-mono text-sm">{selectedPoint.lat.toFixed(5)}, {selectedPoint.lng.toFixed(5)}</div>
          </div>
        )}

        {isAnalyzing && (
          <div className="flex items-center gap-3 text-blue-400 animate-pulse py-2">
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span className="text-sm font-medium">Querying legal zoning database...</span>
          </div>
        )}

        {zoningResult && !isAnalyzing && (
          <div className="space-y-3 animate-in fade-in slide-in-from-bottom-2 duration-300">
            {zoningResult.status === "found" ? (
              <>
                <div className="border-l-2 border-blue-500 pl-3">
                  <div className="text-xs text-slate-400 uppercase tracking-wider">District</div>
                  <div className="font-medium text-white">
                    {zoningResult.subdistrict
                      ? `${zoningResult.subdistrict}, ${zoningResult.district}`
                      : zoningResult.district}
                  </div>
                </div>
                <div className="border-l-2 border-emerald-500 pl-3">
                  <div className="text-xs text-slate-400 uppercase tracking-wider">Zone Code</div>
                  <div className="font-mono text-emerald-400 font-semibold">
                    {zoningResult.zone_code}
                  </div>
                  <div className="text-xs text-slate-400 mt-0.5">{zoningResult.zone_name}</div>
                </div>
                <div className="border-l-2 border-purple-500 pl-3">
                  <div className="text-xs text-slate-400 uppercase tracking-wider">Risk</div>
                  <div className={`text-sm font-medium ${(zoningResult.risk_score ?? 0) > 0.7 ? "text-red-400" : "text-emerald-400"}`}>
                    {(zoningResult.risk_score ?? 0) > 0.7 ? "High" : "Normal"}
                    <span className="text-slate-500 font-normal ml-1">
                      ({((zoningResult.risk_score ?? 0) * 100).toFixed(0)}%)
                    </span>
                  </div>
                </div>
                <div className="text-xs text-slate-600 pt-1">
                  Source: {zoningResult.source}
                </div>
                <button className="w-full mt-2 bg-white text-black font-semibold py-2.5 rounded hover:bg-slate-200 transition-colors text-sm">
                  Generate PMA Quote
                </button>
              </>
            ) : (
              <div className="text-sm text-amber-400 border-l-2 border-amber-500 pl-3">
                {zoningResult.message ?? "Outside GISTARU coverage area."}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
