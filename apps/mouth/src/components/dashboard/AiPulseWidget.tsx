'use client';

import React, { useEffect, useState } from 'react';
import { Activity, Zap, AlertCircle, Brain, Database, Terminal } from 'lucide-react';
import { api } from '@/lib/api';

interface NeuralPulseData {
  status: string;
  memory_facts: number;
  knowledge_docs: number;
  latency_ms: number;
  model_version: string;
  last_activity: string;
}

interface AiPulseWidgetProps {
  systemAppStatus: 'healthy' | 'degraded';
  oracleStatus: 'active' | 'inactive';
}

export function AiPulseWidget({ systemAppStatus, oracleStatus }: AiPulseWidgetProps) {
  const [pulseData, setPulseData] = useState<NeuralPulseData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchPulse = async () => {
      try {
        // Fetch from the new backend endpoint
        const data = await api.get<NeuralPulseData>('/api/dashboard/neural-pulse');
        setPulseData(data);
      } catch (error) {
        console.error('Failed to fetch neural pulse:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchPulse();
    // Poll every 30 seconds to keep the pulse alive
    const interval = setInterval(fetchPulse, 30000);
    return () => clearInterval(interval);
  }, []);

  const isHealthy = systemAppStatus === 'healthy';
  
  // Format numbers for display (e.g. 53,757 -> 53.7k)
  const formatK = (num: number) => {
    return num > 999 ? (num / 1000).toFixed(1) + 'k' : num;
  };

  return (
    <div className="rounded-lg border border-white/10 bg-white/5 p-6 backdrop-blur-sm relative overflow-hidden group">
      {/* Cyberpunk accent line */}
      <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-transparent via-cyan-500 to-transparent opacity-50 group-hover:opacity-100 transition-opacity" />

      {/* HEADER ROW */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-400" />
          <h3 className="text-sm font-semibold text-white/90 uppercase tracking-wider">
            Zantara v6.0
          </h3>
        </div>
        <div className="flex items-center gap-2 px-2 py-1 rounded-full bg-black/30 border border-white/5">
          <div
            className={`w-2 h-2 rounded-full ${
              isHealthy ? 'bg-green-500 animate-pulse' : 'bg-red-500'
            }`}
          />
          <span className="text-xs font-mono text-green-400">
            {pulseData ? `${pulseData.latency_ms}ms` : '---'}
          </span>
        </div>
      </div>

      {/* METRICS GRID */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        {/* Memory Core */}
        <div className="p-3 rounded-lg bg-black/20 border border-white/5 hover:border-purple-500/30 transition-colors">
          <div className="flex items-center gap-2 mb-1">
            <Brain className="w-3.5 h-3.5 text-purple-400" />
            <span className="text-xs text-white/60 font-medium">Memory Facts</span>
          </div>
          <div className="text-2xl font-bold text-white tracking-tight">
            {pulseData ? pulseData.memory_facts : '-'}
          </div>
        </div>

        {/* Knowledge Base */}
        <div className="p-3 rounded-lg bg-black/20 border border-white/5 hover:border-cyan-500/30 transition-colors">
          <div className="flex items-center gap-2 mb-1">
            <Database className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-xs text-white/60 font-medium">Knowledge Docs</span>
          </div>
          <div className="text-2xl font-bold text-white tracking-tight">
            {pulseData ? formatK(pulseData.knowledge_docs) : '-'}
          </div>
        </div>
      </div>

      {/* CONSOLE STREAM */}
      <div className="mt-auto">
        <div className="flex items-center gap-2 mb-2">
          <Terminal className="w-3 h-3 text-white/40" />
          <span className="text-[10px] text-white/40 uppercase tracking-wide">System Activity</span>
        </div>
        <div className="font-mono text-xs text-green-400/80 bg-black/40 p-2 rounded border border-white/5 truncate">
          {pulseData ? `> ${pulseData.last_activity}` : '> Initializing neural link...'}
        </div>
      </div>
    </div>
  );
}
