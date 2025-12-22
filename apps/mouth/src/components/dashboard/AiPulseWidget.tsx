'use client';

import React from 'react';
import { Activity, Zap, AlertCircle } from 'lucide-react';

interface AiPulseWidgetProps {
  systemAppStatus: 'healthy' | 'degraded';
  oracleStatus: 'active' | 'inactive';
}

export function AiPulseWidget({ systemAppStatus, oracleStatus }: AiPulseWidgetProps) {
  const isHealthy = systemAppStatus === 'healthy';
  const isOracleActive = oracleStatus === 'active';

  return (
    <div className="rounded-lg border border-white/10 bg-white/5 p-6 backdrop-blur-sm">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white/90 uppercase tracking-wider">AI Pulse</h3>
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${
              isHealthy ? 'bg-green-500 animate-pulse' : 'bg-yellow-500'
            }`}
          />
          <span className="text-xs text-white/60">{isHealthy ? 'Healthy' : 'Degraded'}</span>
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan-500" />
            <span className="text-sm text-white/80">System Status</span>
          </div>
          <span
            className={`text-sm font-medium ${isHealthy ? 'text-green-400' : 'text-yellow-400'}`}
          >
            {systemAppStatus.toUpperCase()}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-500" />
            <span className="text-sm text-white/80">Oracle Engine</span>
          </div>
          <span
            className={`text-sm font-medium ${isOracleActive ? 'text-green-400' : 'text-gray-400'}`}
          >
            {isOracleActive ? 'ACTIVE' : 'INACTIVE'}
          </span>
        </div>

        {!isHealthy && (
          <div className="flex items-start gap-2 p-3 rounded bg-yellow-500/10 border border-yellow-500/20">
            <AlertCircle className="w-4 h-4 text-yellow-500 mt-0.5 flex-shrink-0" />
            <p className="text-xs text-yellow-500/80">
              Some system components are experiencing issues. Monitoring in progress.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
