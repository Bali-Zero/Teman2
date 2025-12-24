'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { RefreshCw, AlertCircle, Activity, Database, Brain, Globe, Server, Cpu, HardDrive } from 'lucide-react';

interface IslandHealth {
  name: string;
  label: string;
  description: string;
  health_score: number;
  status: 'healthy' | 'warning' | 'degraded' | 'critical';
  metrics: Record<string, unknown>;
  coordinates: { lat: number; lng: number };
}

interface NusantaraHealth {
  timestamp: string;
  overall_score: number;
  overall_status: string;
  status_counts: {
    healthy: number;
    warning: number;
    degraded: number;
    critical: number;
  };
  islands: Record<string, IslandHealth>;
}

interface NusantaraHealthWidgetProps {
  className?: string;
}

// Island SVG paths (simplified Indonesia archipelago)
const ISLAND_PATHS: Record<string, { path: string; viewBox: string; scale: number }> = {
  sumatra: {
    path: 'M20,10 L35,5 L45,15 L50,40 L45,70 L35,85 L20,80 L15,50 L20,10 Z',
    viewBox: '0 0 60 90',
    scale: 1.2,
  },
  java: {
    path: 'M5,20 L80,10 L95,15 L90,25 L70,30 L40,28 L10,30 L5,20 Z',
    viewBox: '0 0 100 40',
    scale: 1.0,
  },
  kalimantan: {
    path: 'M30,5 L60,10 L75,30 L80,60 L70,80 L40,85 L20,70 L10,40 L15,20 L30,5 Z',
    viewBox: '0 0 90 90',
    scale: 1.3,
  },
  sulawesi: {
    path: 'M30,5 L45,20 L55,10 L60,25 L50,40 L60,60 L45,70 L35,55 L25,70 L20,50 L30,35 L20,20 L30,5 Z',
    viewBox: '0 0 70 80',
    scale: 1.1,
  },
  papua: {
    path: 'M10,30 L30,10 L70,15 L85,25 L90,50 L80,70 L50,75 L20,65 L10,45 L10,30 Z',
    viewBox: '0 0 95 80',
    scale: 1.4,
  },
  bali: {
    path: 'M5,15 L20,5 L35,10 L40,20 L35,30 L20,35 L5,25 L5,15 Z',
    viewBox: '0 0 45 40',
    scale: 0.6,
  },
  maluku: {
    path: 'M10,10 L25,5 L35,15 L30,30 L15,35 L5,25 L10,10 Z M45,20 L55,15 L60,25 L50,35 L40,30 L45,20 Z',
    viewBox: '0 0 65 40',
    scale: 0.8,
  },
  nusa_tenggara: {
    path: 'M5,15 L20,10 L30,15 L25,25 L10,25 L5,15 Z M35,12 L50,8 L55,18 L45,25 L35,20 L35,12 Z M60,10 L75,5 L80,15 L70,22 L60,18 L60,10 Z',
    viewBox: '0 0 85 30',
    scale: 0.9,
  },
};

// Island positions on the map (relative positions)
const ISLAND_POSITIONS: Record<string, { x: number; y: number }> = {
  sumatra: { x: 12, y: 35 },
  java: { x: 32, y: 72 },
  kalimantan: { x: 45, y: 30 },
  sulawesi: { x: 62, y: 38 },
  papua: { x: 85, y: 40 },
  bali: { x: 48, y: 75 },
  maluku: { x: 75, y: 45 },
  nusa_tenggara: { x: 55, y: 78 },
};

// Icons for each island
const ISLAND_ICONS: Record<string, React.ElementType> = {
  java: Server,
  sumatra: Globe,
  kalimantan: Database,
  sulawesi: Brain,
  papua: HardDrive,
  bali: Activity,
  maluku: Cpu,
  nusa_tenggara: RefreshCw,
};

function getHealthColor(status: string, score: number): string {
  switch (status) {
    case 'healthy':
      return score >= 95 ? '#10b981' : '#22c55e';
    case 'warning':
      return '#f59e0b';
    case 'degraded':
      return '#f97316';
    case 'critical':
      return '#ef4444';
    default:
      return '#6b7280';
  }
}

function getGlowColor(status: string): string {
  switch (status) {
    case 'healthy':
      return 'rgba(34, 197, 94, 0.4)';
    case 'warning':
      return 'rgba(245, 158, 11, 0.4)';
    case 'degraded':
      return 'rgba(249, 115, 22, 0.4)';
    case 'critical':
      return 'rgba(239, 68, 68, 0.6)';
    default:
      return 'rgba(107, 114, 128, 0.3)';
  }
}

export function NusantaraHealthWidget({ className = '' }: NusantaraHealthWidgetProps) {
  const [health, setHealth] = useState<NusantaraHealth | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedIsland, setSelectedIsland] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch('/api/nusantara/health', {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      setHealth(data);
      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      console.error('Failed to fetch Nusantara health:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();

    // Poll every 60 seconds
    intervalRef.current = setInterval(fetchHealth, 60000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchHealth]);

  const handleIslandClick = (islandKey: string) => {
    setSelectedIsland(selectedIsland === islandKey ? null : islandKey);
  };

  if (isLoading) {
    return (
      <div className={`rounded-lg border border-white/10 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6 ${className}`}>
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-6 h-6 text-cyan-500 animate-spin" />
          <span className="ml-2 text-white/60">Loading Nusantara Health Map...</span>
        </div>
      </div>
    );
  }

  if (error && !health) {
    return (
      <div className={`rounded-lg border border-red-500/20 bg-red-500/10 p-6 ${className}`}>
        <div className="flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-500" />
          <div>
            <h3 className="font-semibold text-red-500">Health Map Unavailable</h3>
            <p className="text-sm text-red-500/80">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  const selectedIslandData = selectedIsland && health?.islands[selectedIsland];

  return (
    <div className={`rounded-lg border border-white/10 bg-gradient-to-br from-slate-900 via-blue-950/30 to-slate-900 overflow-hidden ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-white/10 bg-black/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative">
              <Globe className="w-5 h-5 text-cyan-500" />
              <div className="absolute -top-1 -right-1 w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-white uppercase tracking-wider">
                Nusantara System Map
              </h3>
              <p className="text-xs text-white/50">
                {lastUpdate ? `Updated ${lastUpdate.toLocaleTimeString()}` : 'Live monitoring'}
              </p>
            </div>
          </div>
          {health && (
            <div className="flex items-center gap-2">
              <span
                className="px-2 py-1 rounded text-xs font-bold"
                style={{
                  backgroundColor: getGlowColor(health.overall_status),
                  color: getHealthColor(health.overall_status, health.overall_score),
                }}
              >
                {health.overall_score}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Map Container */}
      <div className="relative h-80 bg-gradient-to-b from-blue-950/50 via-blue-900/30 to-slate-900/50 overflow-hidden">
        {/* Ocean effect */}
        <div className="absolute inset-0 opacity-30">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-cyan-900/20 via-transparent to-transparent" />
        </div>

        {/* Grid overlay for satellite effect */}
        <div
          className="absolute inset-0 opacity-10"
          style={{
            backgroundImage: `
              linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
              linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)
            `,
            backgroundSize: '20px 20px',
          }}
        />

        {/* Islands */}
        {health?.islands &&
          Object.entries(health.islands).map(([key, island]) => {
            const position = ISLAND_POSITIONS[key];
            const pathData = ISLAND_PATHS[key];
            const IconComponent = ISLAND_ICONS[key] || Activity;
            const isSelected = selectedIsland === key;

            if (!position || !pathData) return null;

            const color = getHealthColor(island.status, island.health_score);
            const glowColor = getGlowColor(island.status);

            return (
              <div
                key={key}
                className="absolute cursor-pointer transition-all duration-300 group"
                style={{
                  left: `${position.x}%`,
                  top: `${position.y}%`,
                  transform: `translate(-50%, -50%) scale(${isSelected ? 1.2 : 1})`,
                  zIndex: isSelected ? 20 : 10,
                }}
                onClick={() => handleIslandClick(key)}
              >
                {/* Glow effect */}
                <div
                  className={`absolute inset-0 rounded-full blur-xl transition-opacity duration-300 ${
                    island.status === 'critical' ? 'animate-pulse' : ''
                  }`}
                  style={{
                    backgroundColor: glowColor,
                    transform: 'scale(2)',
                    opacity: isSelected ? 0.8 : 0.5,
                  }}
                />

                {/* Island shape */}
                <svg
                  width={60 * pathData.scale}
                  height={60 * pathData.scale}
                  viewBox={pathData.viewBox}
                  className="relative drop-shadow-lg"
                >
                  <path
                    d={pathData.path}
                    fill={color}
                    stroke="rgba(255,255,255,0.3)"
                    strokeWidth="1"
                    className="transition-all duration-300"
                    style={{
                      filter: `drop-shadow(0 0 ${isSelected ? 10 : 5}px ${color})`,
                    }}
                  />
                </svg>

                {/* Icon overlay */}
                <div
                  className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 opacity-80"
                >
                  <IconComponent className="w-4 h-4 text-white/90" />
                </div>

                {/* Tooltip on hover */}
                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-30">
                  <div className="bg-black/90 rounded px-2 py-1 text-xs whitespace-nowrap">
                    <div className="font-semibold text-white">{island.label}</div>
                    <div className="text-white/60">{island.health_score}% health</div>
                  </div>
                </div>
              </div>
            );
          })}

        {/* Connection lines (simplified) */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-20">
          <line x1="32%" y1="72%" x2="45%" y2="30%" stroke="cyan" strokeWidth="0.5" strokeDasharray="4 4" />
          <line x1="45%" y1="30%" x2="62%" y2="38%" stroke="cyan" strokeWidth="0.5" strokeDasharray="4 4" />
          <line x1="62%" y1="38%" x2="85%" y2="40%" stroke="cyan" strokeWidth="0.5" strokeDasharray="4 4" />
          <line x1="32%" y1="72%" x2="48%" y2="75%" stroke="cyan" strokeWidth="0.5" strokeDasharray="4 4" />
        </svg>
      </div>

      {/* Status Counts Bar */}
      {health && (
        <div className="flex items-center justify-center gap-4 p-2 bg-black/30 border-t border-white/5">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-green-500" />
            <span className="text-xs text-white/60">{health.status_counts.healthy} healthy</span>
          </div>
          {health.status_counts.warning > 0 && (
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-yellow-500" />
              <span className="text-xs text-white/60">{health.status_counts.warning} warning</span>
            </div>
          )}
          {health.status_counts.degraded > 0 && (
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-orange-500" />
              <span className="text-xs text-white/60">{health.status_counts.degraded} degraded</span>
            </div>
          )}
          {health.status_counts.critical > 0 && (
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              <span className="text-xs text-white/60">{health.status_counts.critical} critical</span>
            </div>
          )}
        </div>
      )}

      {/* Selected Island Details Panel */}
      {selectedIslandData && (
        <div className="p-4 border-t border-white/10 bg-black/40 animate-in slide-in-from-bottom-2 duration-300">
          <div className="flex items-start justify-between mb-3">
            <div>
              <h4 className="text-sm font-semibold text-white">{selectedIslandData.label}</h4>
              <p className="text-xs text-white/50">{selectedIslandData.description}</p>
            </div>
            <div
              className="px-2 py-1 rounded text-xs font-bold"
              style={{
                backgroundColor: getGlowColor(selectedIslandData.status),
                color: getHealthColor(selectedIslandData.status, selectedIslandData.health_score),
              }}
            >
              {selectedIslandData.health_score}%
            </div>
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            {Object.entries(selectedIslandData.metrics).slice(0, 4).map(([key, value]) => (
              <div key={key} className="bg-white/5 rounded px-2 py-1">
                <div className="text-white/40 capitalize">{key.replace(/_/g, ' ')}</div>
                <div className="text-white/80 truncate">
                  {typeof value === 'object'
                    ? (value as Record<string, unknown>)?.available !== undefined
                      ? (value as Record<string, unknown>).available ? 'Available' : 'Unavailable'
                      : JSON.stringify(value).slice(0, 20)
                    : String(value)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
