'use client';

import React, { useState, useEffect } from 'react';
import { BarChart3, ExternalLink, Activity, Database, RefreshCw, FileText, Zap, CheckCircle2, XCircle } from 'lucide-react';

interface GrafanaWidgetProps {
  className?: string;
}

interface HealthData {
  status: string;
  version?: string;
  database?: {
    status: string;
    type: string;
    collections: number;
    total_documents: number;
  };
  embeddings?: {
    status: string;
    provider: string;
    model: string;
  };
}

const GRAFANA_DASHBOARD_URL = 'https://zero1987.grafana.net/d/fastapi-observability/zantara-backend-observability?orgId=1&from=now-1h&to=now&refresh=30s';
const BACKEND_HEALTH_URL = 'https://nuzantara-rag.fly.dev/health';

export function GrafanaWidget({ className = '' }: GrafanaWidgetProps) {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(BACKEND_HEALTH_URL, {
        cache: 'no-store',
        mode: 'cors',
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      setHealth(data);
      setLastUpdated(new Date());
    } catch (err) {
      console.error('Failed to fetch health:', err);
      setError('Connection failed');
      setHealth(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const isHealthy = health?.status === 'healthy';
  const isDbConnected = health?.database?.status === 'connected';

  return (
    <div className={`rounded-xl border-2 border-orange-500/40 bg-gradient-to-br from-orange-500/10 to-orange-600/5 overflow-hidden ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4">
        <div className="flex items-center gap-3">
          <div className={`p-3 rounded-xl ${isHealthy ? 'bg-green-500/20' : 'bg-orange-500/20'}`}>
            {isHealthy ? (
              <CheckCircle2 className="w-6 h-6 text-green-400" />
            ) : (
              <BarChart3 className="w-6 h-6 text-orange-400" />
            )}
          </div>
          <div>
            <h3 className="font-semibold text-lg text-[var(--foreground)]">System Health</h3>
            <p className="text-sm text-[var(--foreground-muted)]">
              {health?.version || 'Backend Status'}
            </p>
          </div>
        </div>
        <button
          onClick={fetchHealth}
          disabled={isLoading}
          className="p-2 rounded-lg hover:bg-orange-500/20 transition-colors"
          title="Refresh"
        >
          <RefreshCw className={`w-5 h-5 text-orange-400 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Stats Grid */}
      <div className="px-5 pb-4">
        {error ? (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 mb-4 flex items-center gap-3">
            <XCircle className="w-5 h-5 text-red-400" />
            <div>
              <p className="text-sm font-medium text-red-400">Connection Error</p>
              <p className="text-xs text-[var(--foreground-muted)]">Backend unreachable</p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 mb-4">
            {/* Backend Status */}
            <div className={`rounded-lg p-3 ${isHealthy ? 'bg-green-500/10' : 'bg-[var(--background-secondary)]'}`}>
              <div className="flex items-center gap-2 mb-1">
                <Activity className={`w-4 h-4 ${isHealthy ? 'text-green-400' : 'text-red-400'}`} />
                <p className="text-xs text-[var(--foreground-muted)]">Backend</p>
              </div>
              <p className={`text-sm font-semibold ${isHealthy ? 'text-green-400' : 'text-red-400'}`}>
                {isLoading ? '...' : isHealthy ? 'Healthy' : 'Unhealthy'}
              </p>
            </div>

            {/* Qdrant Status */}
            <div className={`rounded-lg p-3 ${isDbConnected ? 'bg-blue-500/10' : 'bg-[var(--background-secondary)]'}`}>
              <div className="flex items-center gap-2 mb-1">
                <Database className={`w-4 h-4 ${isDbConnected ? 'text-blue-400' : 'text-red-400'}`} />
                <p className="text-xs text-[var(--foreground-muted)]">Qdrant</p>
              </div>
              <p className={`text-sm font-semibold ${isDbConnected ? 'text-blue-400' : 'text-red-400'}`}>
                {isLoading ? '...' : isDbConnected ? 'Connected' : 'Disconnected'}
              </p>
            </div>

            {/* Collections */}
            <div className="bg-[var(--background-secondary)] rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <FileText className="w-4 h-4 text-purple-400" />
                <p className="text-xs text-[var(--foreground-muted)]">Collections</p>
              </div>
              <p className="text-sm font-semibold text-purple-400">
                {isLoading ? '...' : health?.database?.collections || 0}
              </p>
            </div>

            {/* Documents */}
            <div className="bg-[var(--background-secondary)] rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <FileText className="w-4 h-4 text-cyan-400" />
                <p className="text-xs text-[var(--foreground-muted)]">Documents</p>
              </div>
              <p className="text-sm font-semibold text-cyan-400">
                {isLoading ? '...' : health?.database?.total_documents?.toLocaleString() || 0}
              </p>
            </div>
          </div>
        )}

        {/* Open Grafana Button */}
        <a
          href={GRAFANA_DASHBOARD_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-2 w-full py-3 px-4 rounded-lg bg-orange-500 hover:bg-orange-600 text-white font-medium transition-colors"
        >
          <Zap className="w-5 h-5" />
          Advanced Metrics (Grafana)
          <ExternalLink className="w-4 h-4" />
        </a>
      </div>

      {/* Footer */}
      <div className="px-5 py-2 bg-orange-500/5 border-t border-orange-500/20">
        <p className="text-xs text-[var(--foreground-muted)] text-center">
          {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : 'Loading...'} • Auto-refresh 30s
        </p>
      </div>
    </div>
  );
}

export default GrafanaWidget;
