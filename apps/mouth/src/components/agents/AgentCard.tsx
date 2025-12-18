'use client';

import { Button } from '@/components/ui/button';
import { Play, ChevronRight } from 'lucide-react';

export interface AgentCardProps {
  // Newer usage: pass an `agent` object.
  agent?: {
    name: string;
    description: string;
    status: 'running' | 'idle' | 'error';
    success_rate?: number;
    total_runs?: number;
    latest_result?: Record<string, unknown>;
  };
  // Backward-compatible usage: pass fields directly.
  name?: string;
  description?: string;
  status?: 'running' | 'idle' | 'error';
  successRate?: number;
  totalRuns?: number;
  latestResult?: Record<string, unknown>;
  onRun?: () => void | Promise<void>;
}

export function AgentCard({
  agent,
  name,
  description,
  status,
  successRate,
  totalRuns,
  latestResult,
  onRun,
}: AgentCardProps) {
  const normalized = agent
    ? {
        name: agent.name,
        description: agent.description,
        status: agent.status,
        success_rate: agent.success_rate,
        total_runs: agent.total_runs,
        latest_result: agent.latest_result,
      }
    : {
        name: name || 'Agent',
        description: description || '',
        status: status || 'idle',
        success_rate: successRate,
        total_runs: totalRuns,
        latest_result: latestResult,
      };

  const {
    name: agentName,
    description: agentDescription,
    status: agentStatus,
    success_rate,
    total_runs,
    latest_result,
  } = normalized;
  const statusColor =
    agentStatus === 'running'
      ? 'bg-green-500'
      : agentStatus === 'idle'
        ? 'bg-yellow-500'
        : 'bg-red-500';

  return (
    <div className="bg-[var(--background-elevated)] border border-[var(--border)] rounded-xl p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className={`w-2.5 h-2.5 rounded-full ${statusColor}`} />
            <h3 className="text-lg font-semibold text-[var(--foreground)] truncate">{agentName}</h3>
          </div>
          <p className="text-sm text-[var(--foreground-muted)] mt-1">{agentDescription}</p>
        </div>

        <div className="flex items-center gap-2">
          {onRun && (
            <Button variant="outline" size="sm" onClick={onRun} className="gap-2">
              <Play className="w-4 h-4" />
              Run
            </Button>
          )}
          <Button variant="ghost" size="icon" aria-label="Details">
            <ChevronRight className="w-5 h-5" />
          </Button>
        </div>
      </div>

      {(success_rate !== undefined || total_runs !== undefined) && (
        <div className="mt-4 flex items-center gap-4 text-xs text-[var(--foreground-muted)]">
          {success_rate !== undefined && <span>Success: {success_rate.toFixed(1)}%</span>}
          {total_runs !== undefined && <span>Total runs: {total_runs}</span>}
        </div>
      )}

      {latest_result && (
        <div className="mt-4 rounded-lg border border-[var(--border)] bg-black/20 p-3">
          <div className="text-xs font-medium text-[var(--foreground)] mb-2">Latest result</div>
          <div className="grid grid-cols-2 gap-2 text-xs text-[var(--foreground-muted)]">
            {Object.entries(latest_result)
              .slice(0, 6)
              .map(([k, v]) => (
                <div key={k} className="truncate">
                  <span className="text-[var(--foreground-secondary)]">{k}:</span>{' '}
                  <span>{String(v)}</span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
