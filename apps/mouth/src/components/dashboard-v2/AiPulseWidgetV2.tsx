'use client';

import React, { useEffect, useState } from 'react';
import { Zap, Brain, Database, Terminal } from 'lucide-react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface NeuralPulseData {
  status: string;
  memory_facts: number;
  knowledge_docs: number;
  latency_ms: number;
  model_version: string;
  last_activity: string;
}

interface AiPulseWidgetV2Props {
  systemStatus: 'healthy' | 'degraded';
  /** Optional mock data for preview/demo mode - skips API calls */
  mockData?: NeuralPulseData;
}

/**
 * AiPulseWidgetV2 - Improved AI Pulse widget with:
 * - Full CSS variables (no hardcoded colors like white/10, cyan-500)
 * - Respects prefers-reduced-motion
 * - Better accessibility
 * - Consistent with Design System v2.0
 */
export function AiPulseWidgetV2({ systemStatus, mockData }: AiPulseWidgetV2Props) {
  const [pulseData, setPulseData] = useState<NeuralPulseData | null>(mockData ?? null);
  const [isLoading, setIsLoading] = useState(!mockData);

  useEffect(() => {
    // Skip API calls if mock data is provided (demo/preview mode)
    if (mockData) {
      setPulseData(mockData);
      setIsLoading(false);
      return;
    }

    const fetchPulse = async () => {
      try {
        const data = await api.get<NeuralPulseData>('/api/dashboard/neural-pulse');
        setPulseData(data);
      } catch (error) {
        console.error('Failed to fetch neural pulse:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchPulse();
    const interval = setInterval(fetchPulse, 30000);
    return () => clearInterval(interval);
  }, [mockData]);

  const isHealthy = systemStatus === 'healthy';

  const formatK = (num: number) => {
    return num > 999 ? (num / 1000).toFixed(1) + 'k' : num;
  };

  return (
    <div
      className={cn(
        'rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-6',
        'relative overflow-hidden group transition-all duration-[var(--transition-normal)]',
        'hover:border-[var(--border-hover)]'
      )}
    >
      {/* Accent line - uses CSS variable */}
      <div
        className={cn(
          'absolute top-0 left-0 w-full h-[2px]',
          'bg-gradient-to-r from-transparent via-[var(--accent)] to-transparent',
          'opacity-50 group-hover:opacity-100 transition-opacity'
        )}
        aria-hidden="true"
      />

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-[var(--warning)]" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-[var(--foreground)] uppercase tracking-wider">
            Zantara v6.0
          </h3>
        </div>
        <div
          className={cn(
            'flex items-center gap-2 px-2 py-1 rounded-full',
            'bg-[var(--background-elevated)] border border-[var(--border)]'
          )}
        >
          <div
            className={cn(
              'w-2 h-2 rounded-full',
              isHealthy
                ? 'bg-[var(--success)] motion-safe:animate-pulse'
                : 'bg-[var(--error)]'
            )}
            role="status"
            aria-label={isHealthy ? 'System healthy' : 'System degraded'}
          />
          <span className="text-xs font-mono text-[var(--success)]">
            {pulseData ? `${pulseData.latency_ms}ms` : '---'}
          </span>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        {/* Memory Core */}
        <div
          className={cn(
            'p-3 rounded-lg bg-[var(--background-elevated)] border border-[var(--border)]',
            'hover:border-[var(--accent)]/50 transition-colors'
          )}
        >
          <div className="flex items-center gap-2 mb-1">
            <Brain className="w-3.5 h-3.5 text-[var(--accent)]" aria-hidden="true" />
            <span className="text-xs text-[var(--foreground-muted)] font-medium">Memory Facts</span>
          </div>
          <div className="text-2xl font-bold text-[var(--foreground)] tracking-tight">
            {isLoading ? (
              <span className="skeleton inline-block w-12 h-7 rounded" />
            ) : (
              pulseData?.memory_facts ?? '-'
            )}
          </div>
        </div>

        {/* Knowledge Base */}
        <div
          className={cn(
            'p-3 rounded-lg bg-[var(--background-elevated)] border border-[var(--border)]',
            'hover:border-[var(--info)]/50 transition-colors'
          )}
        >
          <div className="flex items-center gap-2 mb-1">
            <Database className="w-3.5 h-3.5 text-[var(--info)]" aria-hidden="true" />
            <span className="text-xs text-[var(--foreground-muted)] font-medium">Knowledge Docs</span>
          </div>
          <div className="text-2xl font-bold text-[var(--foreground)] tracking-tight">
            {isLoading ? (
              <span className="skeleton inline-block w-12 h-7 rounded" />
            ) : (
              pulseData ? formatK(pulseData.knowledge_docs) : '-'
            )}
          </div>
        </div>
      </div>

      {/* Console Stream */}
      <div className="mt-auto">
        <div className="flex items-center gap-2 mb-2">
          <Terminal className="w-3 h-3 text-[var(--foreground-muted)]" aria-hidden="true" />
          <span className="text-[10px] text-[var(--foreground-muted)] uppercase tracking-wide">
            System Activity
          </span>
        </div>
        <div
          className={cn(
            'font-mono text-xs text-[var(--success)] p-2 rounded',
            'bg-[var(--background-elevated)] border border-[var(--border)]',
            'truncate'
          )}
          aria-live="polite"
        >
          {isLoading ? (
            <span className="skeleton inline-block w-full h-4 rounded" />
          ) : (
            `> ${pulseData?.last_activity ?? 'Initializing neural link...'}`
          )}
        </div>
      </div>
    </div>
  );
}

export default AiPulseWidgetV2;
