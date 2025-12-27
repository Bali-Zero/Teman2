'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { ArrowLeft, RefreshCw, Activity, CheckCircle2, AlertCircle, Pause } from 'lucide-react';
import { AgentCard } from '@/components/agents/AgentCard';
import { SchedulerStatus } from '@/components/agents/SchedulerStatus';
import { INTERVALS, TIMEOUTS, PAGINATION } from '@/constants';

interface AgentStatus {
  name: string;
  description: string;
  status: 'running' | 'idle' | 'error';
  last_run?: string;
  next_run?: string;
  success_rate?: number;
  total_runs?: number;
  latest_result?: Record<string, unknown>;
}

interface SchedulerStatusData {
  is_running: boolean;
  tasks?: Array<{
    name: string;
    next_run: string;
    interval: string;
    enabled: boolean;
  }>;
}

export default function AgentsPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatusData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [error, setError] = useState<string | null>(null);

  const loadAgentsStatus = useCallback(async () => {
    try {
      const response =
        await api.client.autonomousTier1.getAutonomousAgentsStatusApiAutonomousAgentsStatusGet();

      console.log('Backend response:', response);

      // Transform backend response to our format
      // Backend now returns proper AgentStatus format!
      const agentsData: AgentStatus[] =
        response.agents?.map((agent: any) => ({
          name: agent.name,
          description: agent.description,
          status: agent.status || 'idle',
          last_run: agent.last_run,
          next_run: agent.next_run,
          success_rate: agent.success_rate,
          total_runs: agent.total_runs || 0,
          latest_result: agent.latest_result,
        })) || [];

      setAgents(agentsData);
      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      console.error('Failed to load agents status:', err);
      setError('Failed to load agents status. Please try again.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadSchedulerStatus = useCallback(async () => {
    try {
      const response =
        await api.client.autonomousTier1.getSchedulerStatusApiAutonomousAgentsSchedulerStatusGet();
      setSchedulerStatus(response);
    } catch (err) {
      console.error('Failed to load scheduler status:', err);
      // Scheduler errors are non-critical, just log them
    }
  }, []);

  useEffect(() => {
    if (!api.isAuthenticated()) {
      router.push('/login');
      return;
    }
    loadAgentsStatus();
    loadSchedulerStatus();

    // Auto-refresh
    const interval = setInterval(() => {
      loadAgentsStatus();
      loadSchedulerStatus();
    }, INTERVALS.AGENTS_REFRESH);

    return () => clearInterval(interval);
  }, [router, loadAgentsStatus, loadSchedulerStatus]);

  const handleRefresh = async () => {
    setIsLoading(true);
    await Promise.all([loadAgentsStatus(), loadSchedulerStatus()]);
  };

  const handleRunAgent = useCallback(
    async (agentName: string) => {
      try {
        setError(null);
        // Map agent names to API endpoints
        const agentEndpoints: Record<string, () => Promise<unknown>> = {
          'Conversation Quality Trainer': () =>
            api.client.autonomousTier1.runConversationTrainerApiAutonomousAgentsConversationTrainerRunPost(
              PAGINATION.TRAINER_DAYS_BACK
            ),
          'Client LTV Predictor': () =>
            api.client.autonomousTier1.runClientValuePredictorApiAutonomousAgentsClientValuePredictorRunPost(),
          'Knowledge Graph Builder': () =>
            api.client.autonomousTier1.runKnowledgeGraphBuilderApiAutonomousAgentsKnowledgeGraphBuilderRunPost(
              PAGINATION.KG_BUILDER_DAYS_BACK,
              false
            ),
        };

        const endpoint = agentEndpoints[agentName];
        if (endpoint) {
          await endpoint();
          // Refresh status after run
          setTimeout(() => loadAgentsStatus(), TIMEOUTS.AGENT_RELOAD_DELAY);
        }
      } catch (err) {
        console.error(`Failed to run ${agentName}:`, err);
        setError(`Failed to run ${agentName}. Please try again.`);
      }
    },
    [loadAgentsStatus]
  );

  return (
    <div className="min-h-screen bg-[var(--background)] p-6">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => router.push('/chat')}
              className="hover:bg-[var(--background-elevated)]"
              aria-label="Back to chat"
            >
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div>
              <h1 className="text-3xl font-bold text-[var(--foreground)] flex items-center gap-3">
                <Activity className="w-8 h-8 text-[var(--accent)]" />
                Autonomous Agents Control Center
              </h1>
              <p className="text-sm text-[var(--foreground-muted)] mt-1">
                Monitor and control autonomous background agents
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-[var(--foreground-muted)]">
              Last updated: {lastUpdate.toLocaleTimeString()}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={isLoading}
              className="gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 mb-4 flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-red-500" />
              <span className="text-sm text-red-500">{error}</span>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-500 hover:text-red-400 transition-colors"
              aria-label="Dismiss error"
            >
              ✕
            </button>
          </motion.div>
        )}

        {/* System Status Banner */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-[var(--background-elevated)] border border-[var(--border)] rounded-xl p-4 flex items-center justify-between"
        >
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-green-500 animate-pulse" />
            <span className="font-medium text-[var(--foreground)]">System Status: HEALTHY</span>
          </div>
          <div className="flex items-center gap-6 text-sm text-[var(--foreground-muted)]">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-500" />
              <span>{agents.filter((a) => a.status === 'running').length} Running</span>
            </div>
            <div className="flex items-center gap-2">
              <Pause className="w-4 h-4 text-yellow-500" />
              <span>{agents.filter((a) => a.status === 'idle').length} Idle</span>
            </div>
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-500" />
              <span>{agents.filter((a) => a.status === 'error').length} Error</span>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Agents Grid */}
      <div className="max-w-7xl mx-auto space-y-4">
        {isLoading && agents.length === 0 ? (
          <div className="flex items-center justify-center py-20">
            <RefreshCw className="w-8 h-8 animate-spin text-[var(--accent)]" />
          </div>
        ) : (
          agents.map((agent) => (
            <AgentCard key={agent.name} agent={agent} onRun={() => handleRunAgent(agent.name)} />
          ))
        )}
      </div>

      {/* Scheduler Status */}
      {schedulerStatus && (
        <div className="max-w-7xl mx-auto mt-8">
          <SchedulerStatus status={schedulerStatus} />
        </div>
      )}
    </div>
  );
}
