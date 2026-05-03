'use client';

import React, { useState, useEffect } from 'react';
import CountUp from 'react-countup';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import type { AllAnalytics } from '@/lib/api/analytics/analytics.types';
import {
  BarChart3,
  Brain,
  Users,
  UserCog,
  Server,
  Database,
  MessageSquare,
  AlertTriangle,
  RefreshCw,
  TrendingUp,
  Clock,
  Zap,
  HardDrive,
  Activity,
  ChevronDown,
  ChevronUp,
  X,
  DollarSign,
  FileText,
  Calendar,
  Shield,
  Search,
  Cpu,
  MemoryStick,
  Download,
  Coins,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// Helper to format large numbers
const formatNumber = (n: number): string => {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toString();
};

// Helper to format duration
const formatDuration = (seconds: number): string => {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
};

// Helper to format IDR
const formatIDR = (amount: number): string => {
  return new Intl.NumberFormat('id-ID', {
    style: 'currency',
    currency: 'IDR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
};

// Helper to format USD
const formatUSD = (amount: number): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(amount);
};

// Accent color styles for stat cards
const accentColorStyles: Record<string, { border: string; icon: string }> = {
  blue: { border: 'border-l-[3px] border-l-[#60A5FA]', icon: 'text-[#60A5FA]' },
  teal: { border: 'border-l-[3px] border-l-[#2DD4BF]', icon: 'text-[#2DD4BF]' },
  amber: {
    border: 'border-l-[3px] border-l-[#FBBF24]',
    icon: 'text-[#FBBF24]',
  },
  purple: {
    border: 'border-l-[3px] border-l-[#A78BFA]',
    icon: 'text-[#A78BFA]',
  },
  pink: { border: 'border-l-[3px] border-l-[#F472B6]', icon: 'text-[#F472B6]' },
  emerald: {
    border: 'border-l-[3px] border-l-[#34D399]',
    icon: 'text-[#34D399]',
  },
  cyan: { border: 'border-l-[3px] border-l-[#22D3EE]', icon: 'text-[#22D3EE]' },
};

// Stat Card Component with animated numbers
function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  variant = 'default',
  onClick,
  animate = true,
  suffix = '',
  prefix = '',
  decimals = 0,
  accentColor,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  variant?: 'default' | 'success' | 'warning' | 'danger';
  onClick?: () => void;
  animate?: boolean;
  suffix?: string;
  prefix?: string;
  decimals?: number;
  accentColor?: 'blue' | 'teal' | 'amber' | 'purple' | 'pink' | 'emerald' | 'cyan';
}) {
  const variants = {
    default: 'text-[var(--bz-text-1)]',
    success: 'text-[var(--success)]',
    warning: 'text-[var(--warning)]',
    danger: 'text-[var(--error)]',
  };

  const accent = accentColor ? accentColorStyles[accentColor] : null;

  // Check if value is a number for CountUp
  const isNumeric =
    typeof value === 'number' ||
    (typeof value === 'string' && !isNaN(parseFloat(value.replace(/[^0-9.-]/g, ''))));
  const numericValue =
    typeof value === 'number' ? value : parseFloat(String(value).replace(/[^0-9.-]/g, '')) || 0;

  return (
    <div
      onClick={onClick}
      className={cn(
        'p-4 rounded-xl border shadow-lg backdrop-blur-md transition-all duration-300',
        onClick ? 'cursor-pointer hover:shadow-xl hover:-translate-y-1' : '',
        accent?.border
      )}
      style={{
        background: 'linear-gradient(145deg, rgba(35,35,40,0.6) 0%, rgba(25,25,30,0.3) 100%)',
        border: '1px solid rgba(255, 255, 255, 0.05)',
      }}
    >
      <div className="flex items-center gap-3 mb-2">
        <div className="p-2 rounded-lg bg-[var(--bz-card)]/50">
          <Icon className={cn('w-4 h-4', accent ? accent.icon : 'text-[var(--bz-text-2)]')} />
        </div>
        <span className="text-sm text-[var(--bz-text-2)]">{title}</span>
      </div>
      <p className={cn('text-2xl font-bold', variants[variant])}>
        {animate && isNumeric && numericValue > 0 ? (
          <CountUp
            end={numericValue}
            duration={1.5}
            separator=","
            decimals={decimals}
            prefix={prefix}
            suffix={suffix}
            enableScrollSpy
            scrollSpyOnce
          />
        ) : (
          value
        )}
      </p>
      {subtitle && <p className="text-xs text-[var(--bz-text-2)] mt-1">{subtitle}</p>}
    </div>
  );
}

// Progress Bar Component
function ProgressBar({
  value,
  max = 100,
  label,
  color = 'accent',
  showValue = true,
}: {
  value: number;
  max?: number;
  label?: string;
  color?: 'accent' | 'success' | 'warning' | 'danger';
  showValue?: boolean;
}) {
  const percent = Math.min((value / max) * 100, 100);
  const colors = {
    accent: 'bg-[var(--bz-accent)]',
    success: 'bg-[var(--success)]',
    warning: 'bg-[var(--warning)]',
    danger: 'bg-[var(--error)]',
  };

  return (
    <div className="space-y-1">
      {label && (
        <div className="flex justify-between text-xs text-[var(--bz-text-2)]">
          <span>{label}</span>
          {showValue && <span>{percent.toFixed(0)}%</span>}
        </div>
      )}
      <div className="h-2 rounded-full bg-[var(--bz-card)]">
        <div
          className={cn('h-full rounded-full transition-all', colors[color])}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

// Expandable Section Component
function ExpandableSection({
  title,
  icon: Icon,
  isExpanded,
  onToggle,
  summary,
  children,
}: {
  title: string;
  icon: React.ElementType;
  isExpanded: boolean;
  onToggle: () => void;
  summary: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        'rounded-xl border shadow-xl backdrop-blur-xl overflow-hidden transition-all duration-300 hover:shadow-2xl',
        isExpanded && 'lg:col-span-2 ring-2 ring-[var(--bz-accent)]'
      )}
      style={{
        background: 'linear-gradient(145deg, rgba(32,32,36,0.7) 0%, rgba(22,22,26,0.4) 100%)',
        border: '1px solid rgba(255, 255, 255, 0.05)',
      }}
    >
      <div
        onClick={onToggle}
        className="px-4 py-3 border-b flex items-center justify-between cursor-pointer transition-colors hover:bg-white/5"
        style={{
          borderColor: 'rgba(255, 255, 255, 0.05)',
          background: 'rgba(255, 255, 255, 0.02)',
        }}
      >
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-[var(--bz-accent)]" />
          <h3 className="font-semibold text-[var(--bz-text-1)]">{title}</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--bz-text-2)]">
            {isExpanded ? 'Click to collapse' : 'Click for details'}
          </span>
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-[var(--bz-text-2)]" />
          ) : (
            <ChevronDown className="w-4 h-4 text-[var(--bz-text-2)]" />
          )}
        </div>
      </div>
      <div className="p-4">{isExpanded ? children : summary}</div>
    </div>
  );
}

// Data Table Component
function DataTable({
  headers,
  rows,
}: {
  headers: string[];
  rows: (string | number | React.ReactNode)[][];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--bz-border)]">
            {headers.map((h, i) => (
              <th key={i} className="text-left py-2 px-3 text-[var(--bz-text-2)] font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className="border-b border-[var(--bz-border)]/50 hover:bg-[var(--bz-card)]/30"
            >
              {row.map((cell, j) => (
                <td key={j} className="py-2 px-3">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Query Insights Types (from /api/analytics/query-insights)
interface QueryInsightsData {
  period_days: number;
  failed_queries: Array<{
    query_text: string;
    fail_count: number;
    collections_attempted: string[];
    last_seen: string;
  }>;
  collection_hit_rates: Array<{
    collection_name: string;
    total_queries: number;
    successful_queries: number;
    hit_rate_percent: number;
  }>;
  query_volume_hourly: Array<{
    bucket: string;
    query_count: number;
    failed_count: number;
    avg_latency_ms: number;
  }>;
  query_volume_daily: Array<{
    bucket: string;
    query_count: number;
    failed_count: number;
    avg_latency_ms: number;
  }>;
  satisfaction: {
    thumbs_up: number;
    thumbs_down: number;
    total_feedback: number;
    total_queries: number;
    satisfaction_percent: number | null;
  };
  generated_at: string;
}

// LLM Usage Stats Types
interface LLMUsageStats {
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  usage_by_model: Array<{
    model: string;
    prompt_tokens: number;
    completion_tokens: number;
    cost_usd: number;
  }>;
  usage_by_endpoint: Array<{
    endpoint: string;
    prompt_tokens: number;
    completion_tokens: number;
  }>;
  daily_trend: Array<{
    date: string;
    tokens: number;
    cost: number;
  }>;
  generated_at: string;
}

export default function AnalyticsDashboard() {
  const [data, setData] = useState<AllAnalytics | null>(null);
  const [llmUsage, setLlmUsage] = useState<LLMUsageStats | null>(null);
  const [queryInsights, setQueryInsights] = useState<QueryInsightsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [expandedSection, setExpandedSection] = useState<string | null>(null);

  const loadData = async (showToast = false) => {
    try {
      setIsLoading(true);
      setError(null);

      // Fetch analytics, LLM usage, and query insights in parallel
      const [analytics, llmStats, qInsights] = await Promise.all([
        api.analytics.getAll(),
        api.analytics.getLlmUsage<LLMUsageStats>(),
        api.analytics.getQueryInsights<QueryInsightsData>(7),
      ]);

      setData(analytics);
      setLlmUsage(llmStats);
      setQueryInsights(qInsights);
      setLastRefresh(new Date());

      if (showToast) {
        toast.success('Analytics refreshed', {
          description: `Last update: ${new Date().toLocaleTimeString('en-US')}`,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analytics');
      toast.error('Failed to refresh analytics');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefresh = () => loadData(true);

  // Export data as JSON
  const handleExport = () => {
    if (!data) {
      toast.error('No data to export');
      return;
    }

    const exportData = {
      ...data,
      llm_usage: llmUsage,
      query_insights: queryInsights,
      exported_at: new Date().toISOString(),
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `analytics-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    toast.success('Analytics exported successfully', {
      description: `File: analytics-${new Date().toISOString().split('T')[0]}.json`,
    });
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 60000);
    return () => clearInterval(interval);
  }, []);

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  if (isLoading && !data) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <RefreshCw className="w-8 h-8 animate-spin text-[var(--bz-accent)]" />
          <p className="text-[var(--bz-text-2)]">Loading analytics...</p>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4 p-6 rounded-xl border border-[var(--error)]/20 bg-[var(--error)]/5">
          <AlertTriangle className="w-8 h-8 text-[var(--error)]" />
          <p className="text-[var(--bz-text-1)]">{error}</p>
          <button
            onClick={handleRefresh}
            className="px-4 py-2 rounded-lg bg-[var(--bz-accent)] text-white"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--bz-text-1)]">System Analytics</h1>
          <p className="text-sm text-[var(--bz-text-2)]">
            Founder Dashboard - Click on any section to see full details
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-xs text-[var(--bz-text-2)]">
              Updated: {lastRefresh.toLocaleTimeString('en-US')}
            </span>
          )}
          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-[var(--bz-border)] hover:bg-[var(--bz-card)] text-sm"
            title="Export analytics data"
            aria-label="Export analytics data"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
          <button
            onClick={handleRefresh}
            disabled={isLoading}
            className={cn(
              'p-2 rounded-lg border border-[var(--bz-border)] hover:bg-[var(--bz-card)]',
              isLoading && 'opacity-50'
            )}
            title="Refresh data"
            aria-label="Refresh data"
          >
            <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          title="Conversations Today"
          aria-label="Conversations Today"
          value={data.overview.conversations_today}
          subtitle={`${data.overview.conversations_week} this week`}
          icon={MessageSquare}
          onClick={() => toggleSection('rag')}
          accentColor="blue"
        />
        <StatCard
          title="Active Users"
          aria-label="Active Users"
          value={data.overview.users_active}
          icon={Users}
          onClick={() => toggleSection('team')}
          accentColor="teal"
        />
        <StatCard
          title="System Uptime"
          aria-label="System Uptime"
          value={formatDuration(data.overview.uptime_seconds)}
          icon={Clock}
          onClick={() => toggleSection('system')}
          accentColor="purple"
        />
        <StatCard
          title="Services Health"
          aria-label="Services Health"
          value={`${data.overview.services_healthy}/${data.overview.services_total}`}
          variant={
            data.overview.services_healthy === data.overview.services_total ? 'success' : 'warning'
          }
          icon={Activity}
          onClick={() => toggleSection('system')}
          accentColor="emerald"
        />
      </div>

      {/* LLM Cost Summary */}
      {llmUsage && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            title="Total Tokens"
            aria-label="Total Tokens"
            value={formatNumber(llmUsage.total_tokens)}
            subtitle={`${formatNumber(llmUsage.total_prompt_tokens)} prompt / ${formatNumber(llmUsage.total_completion_tokens)} completion`}
            icon={Coins}
            onClick={() => toggleSection('llm')}
            accentColor="amber"
          />
          <StatCard
            title="LLM Cost"
            aria-label="LLM Cost"
            value={formatUSD(llmUsage.total_cost_usd)}
            subtitle="Since last restart"
            icon={DollarSign}
            variant={llmUsage.total_cost_usd > 10 ? 'warning' : 'default'}
            onClick={() => toggleSection('llm')}
            accentColor="emerald"
          />
          <StatCard
            title="Models Used"
            aria-label="Models Used"
            value={llmUsage.usage_by_model.length}
            icon={Brain}
            onClick={() => toggleSection('llm')}
            accentColor="pink"
          />
          <StatCard
            title="Endpoints Active"
            aria-label="Endpoints Active"
            value={llmUsage.usage_by_endpoint.length}
            icon={Server}
            onClick={() => toggleSection('llm')}
            accentColor="cyan"
          />
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* LLM Usage Section */}
        {llmUsage && (
          <ExpandableSection
            title="LLM Token Usage & Costs"
            aria-label="LLM Token Usage & Costs"
            icon={Coins}
            isExpanded={expandedSection === 'llm'}
            onToggle={() => toggleSection('llm')}
            summary={
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-lg bg-[var(--bz-card)]/50">
                  <p className="text-xs text-[var(--bz-text-2)]">Total Cost</p>
                  <p className="text-lg font-bold text-[var(--success)]">
                    {formatUSD(llmUsage.total_cost_usd)}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-[var(--bz-card)]/50">
                  <p className="text-xs text-[var(--bz-text-2)]">Total Tokens</p>
                  <p className="text-lg font-bold">{formatNumber(llmUsage.total_tokens)}</p>
                </div>
              </div>
            }
          >
            <div className="space-y-6">
              {/* Token Overview */}
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 rounded-lg bg-[var(--bz-accent)]/10 text-center">
                  <p className="text-xs text-[var(--bz-accent)]">Prompt Tokens</p>
                  <p className="text-2xl font-bold text-[var(--bz-accent)]">
                    {formatNumber(llmUsage.total_prompt_tokens)}
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-[var(--success)]/10 text-center">
                  <p className="text-xs text-[var(--success)]">Completion Tokens</p>
                  <p className="text-2xl font-bold text-[var(--success)]">
                    {formatNumber(llmUsage.total_completion_tokens)}
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-[var(--warning)]/10 text-center">
                  <p className="text-xs text-[var(--warning)]">Total Cost</p>
                  <p className="text-2xl font-bold text-[var(--warning)]">
                    {formatUSD(llmUsage.total_cost_usd)}
                  </p>
                </div>
              </div>

              {/* Usage by Model */}
              {llmUsage.usage_by_model.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-3">Usage by Model</h4>
                  <DataTable
                    headers={['Model', 'Prompt', 'Completion', 'Cost']}
                    rows={llmUsage.usage_by_model.map((m) => [
                      <span key="m" className="font-medium">
                        {m.model}
                      </span>,
                      formatNumber(m.prompt_tokens),
                      formatNumber(m.completion_tokens),
                      <span key="c" className="text-[var(--success)]">
                        {formatUSD(m.cost_usd)}
                      </span>,
                    ])}
                  />
                </div>
              )}

              {/* Usage by Endpoint */}
              {llmUsage.usage_by_endpoint.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-3">Usage by Endpoint</h4>
                  <DataTable
                    headers={['Endpoint', 'Prompt', 'Completion', 'Total']}
                    rows={llmUsage.usage_by_endpoint.map((e) => [
                      <span key="e" className="font-medium truncate max-w-[200px] block">
                        {e.endpoint}
                      </span>,
                      formatNumber(e.prompt_tokens),
                      formatNumber(e.completion_tokens),
                      formatNumber(e.prompt_tokens + e.completion_tokens),
                    ])}
                  />
                </div>
              )}
            </div>
          </ExpandableSection>
        )}

        {/* RAG Pipeline */}
        <ExpandableSection
          title="RAG Pipeline"
          aria-label="RAG Pipeline"
          icon={Brain}
          isExpanded={expandedSection === 'rag'}
          onToggle={() => toggleSection('rag')}
          summary={
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-[var(--bz-card)]/50">
                <p className="text-xs text-[var(--bz-text-2)]">Avg Latency</p>
                <p className="text-lg font-bold">{data.rag.avg_latency_ms.toFixed(0)}ms</p>
              </div>
              <div className="p-3 rounded-lg bg-[var(--bz-card)]/50">
                <p className="text-xs text-[var(--bz-text-2)]">Queries Today</p>
                <p className="text-lg font-bold">{data.rag.queries_today}</p>
              </div>
            </div>
          }
        >
          <div className="space-y-6">
            {/* Latency Breakdown */}
            <div>
              <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                <Zap className="w-4 h-4 text-[var(--bz-accent)]" />
                Latency Breakdown
              </h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-3 rounded-lg bg-[var(--bz-card)]/50 text-center">
                  <p className="text-xs text-[var(--bz-text-2)]">Embedding</p>
                  <p className="text-xl font-bold">{data.rag.embedding_latency_ms.toFixed(0)}ms</p>
                </div>
                <div className="p-3 rounded-lg bg-[var(--bz-card)]/50 text-center">
                  <p className="text-xs text-[var(--bz-text-2)]">Search</p>
                  <p className="text-xl font-bold">{data.rag.search_latency_ms.toFixed(0)}ms</p>
                </div>
                <div className="p-3 rounded-lg bg-[var(--bz-card)]/50 text-center">
                  <p className="text-xs text-[var(--bz-text-2)]">Rerank</p>
                  <p className="text-xl font-bold">{data.rag.rerank_latency_ms.toFixed(0)}ms</p>
                </div>
                <div className="p-3 rounded-lg bg-[var(--bz-card)]/50 text-center">
                  <p className="text-xs text-[var(--bz-text-2)]">LLM</p>
                  <p className="text-xl font-bold">{data.rag.llm_latency_ms.toFixed(0)}ms</p>
                </div>
              </div>
            </div>

            {/* Performance Metrics */}
            <div className="grid grid-cols-2 gap-6">
              <div>
                <h4 className="text-sm font-medium mb-3">Cache Performance</h4>
                <ProgressBar
                  value={data.rag.cache_hit_rate * 100}
                  label="Cache Hit Rate"
                  color={data.rag.cache_hit_rate > 0.5 ? 'success' : 'warning'}
                />
                <div className="mt-3">
                  <ProgressBar
                    value={data.rag.early_exit_rate * 100}
                    label="Early Exit Rate"
                    color={data.rag.early_exit_rate > 0.3 ? 'success' : 'accent'}
                  />
                </div>
              </div>
              <div>
                <h4 className="text-sm font-medium mb-3">Usage Stats</h4>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--bz-text-2)]">Queries Today</span>
                    <span className="font-medium">{data.rag.queries_today}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--bz-text-2)]">Tokens Used</span>
                    <span className="font-medium">{formatNumber(data.rag.token_usage_today)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--bz-text-2)]">Avg Latency</span>
                    <span className="font-medium">{data.rag.avg_latency_ms.toFixed(0)}ms</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Top Queries */}
            {data.rag.top_queries.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                  <Search className="w-4 h-4 text-[var(--bz-accent)]" />
                  Top Queries
                </h4>
                <DataTable
                  headers={['Query', 'Count']}
                  rows={data.rag.top_queries.map((q) => [
                    <span key="q" className="truncate max-w-[300px] block">
                      {q.query}
                    </span>,
                    <span key="c" className="font-medium">
                      {q.count}x
                    </span>,
                  ])}
                />
              </div>
            )}
          </div>
        </ExpandableSection>

        {/* Query Insights */}
        {queryInsights && (
          <ExpandableSection
            title="Query Insights"
            aria-label="Query Insights"
            icon={Search}
            isExpanded={expandedSection === 'query-insights'}
            onToggle={() => toggleSection('query-insights')}
            summary={
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-lg bg-[var(--bz-card)]/50 text-center">
                  <p className="text-xs text-[var(--bz-text-2)]">Total Queries</p>
                  <p className="text-lg font-bold">{queryInsights.satisfaction.total_queries}</p>
                </div>
                <div className="p-3 rounded-lg bg-[var(--error)]/10 text-center">
                  <p className="text-xs text-[var(--error)]">Failed Queries</p>
                  <p className="text-lg font-bold text-[var(--error)]">
                    {queryInsights.failed_queries.length}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-[var(--success)]/10 text-center">
                  <p className="text-xs text-[var(--success)]">Satisfaction</p>
                  <p className="text-lg font-bold text-[var(--success)]">
                    {queryInsights.satisfaction.satisfaction_percent != null
                      ? `${queryInsights.satisfaction.satisfaction_percent}%`
                      : 'N/A'}
                  </p>
                </div>
              </div>
            }
          >
            <div className="space-y-6">
              {/* Satisfaction Overview */}
              <div>
                <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-[var(--bz-accent)]" />
                  User Satisfaction
                </h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-4 rounded-lg bg-[var(--success)]/10 text-center">
                    <p className="text-xs text-[var(--success)]">Thumbs Up</p>
                    <p className="text-2xl font-bold text-[var(--success)]">
                      {queryInsights.satisfaction.thumbs_up}
                    </p>
                  </div>
                  <div className="p-4 rounded-lg bg-[var(--error)]/10 text-center">
                    <p className="text-xs text-[var(--error)]">Thumbs Down</p>
                    <p className="text-2xl font-bold text-[var(--error)]">
                      {queryInsights.satisfaction.thumbs_down}
                    </p>
                  </div>
                  <div className="p-4 rounded-lg bg-[var(--bz-card)]/50 text-center">
                    <p className="text-xs text-[var(--bz-text-2)]">Total Feedback</p>
                    <p className="text-2xl font-bold">
                      {queryInsights.satisfaction.total_feedback}
                    </p>
                  </div>
                  <div className="p-4 rounded-lg bg-[var(--bz-accent)]/10 text-center">
                    <p className="text-xs text-[var(--bz-accent)]">Satisfaction</p>
                    <p className="text-2xl font-bold text-[var(--bz-accent)]">
                      {queryInsights.satisfaction.satisfaction_percent != null
                        ? `${queryInsights.satisfaction.satisfaction_percent}%`
                        : 'N/A'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Collection Hit Rates */}
              {queryInsights.collection_hit_rates.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                    <Database className="w-4 h-4 text-[var(--bz-accent)]" />
                    Collection Hit Rates
                  </h4>
                  <div className="space-y-3">
                    {queryInsights.collection_hit_rates.map((c) => (
                      <div key={c.collection_name}>
                        <ProgressBar
                          value={c.hit_rate_percent}
                          label={`${c.collection_name} (${c.total_queries} queries)`}
                          color={
                            c.hit_rate_percent > 70
                              ? 'success'
                              : c.hit_rate_percent > 40
                                ? 'warning'
                                : 'danger'
                          }
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Failed Queries */}
              {queryInsights.failed_queries.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-[var(--error)]" />
                    Top Failed Queries (0 chunks retrieved)
                  </h4>
                  <DataTable
                    headers={['Query', 'Fails', 'Collections', 'Last Seen']}
                    rows={queryInsights.failed_queries.map((q) => [
                      <span key="q" className="truncate max-w-[250px] block text-sm">
                        {q.query_text}
                      </span>,
                      <span key="c" className="font-medium text-[var(--error)]">
                        {q.fail_count}x
                      </span>,
                      <span key="col" className="text-xs text-[var(--bz-text-2)]">
                        {q.collections_attempted?.join(', ') || '-'}
                      </span>,
                      <span key="t" className="text-xs text-[var(--bz-text-2)]">
                        {q.last_seen ? new Date(q.last_seen).toLocaleDateString('en-US') : '-'}
                      </span>,
                    ])}
                  />
                </div>
              )}

              {/* Query Volume (Daily) */}
              {queryInsights.query_volume_daily.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-[var(--bz-accent)]" />
                    Query Volume (Daily)
                  </h4>
                  <div className="flex items-end gap-2 h-32">
                    {queryInsights.query_volume_daily
                      .slice()
                      .reverse()
                      .map((v, i) => {
                        const maxCount = Math.max(
                          ...queryInsights.query_volume_daily.map((d) => d.query_count),
                          1
                        );
                        const heightPercent = (v.query_count / maxCount) * 100;
                        const failPercent =
                          v.query_count > 0 ? (v.failed_count / v.query_count) * 100 : 0;
                        return (
                          <div key={i} className="flex-1 flex flex-col items-center gap-1">
                            <span className="text-[10px] text-[var(--bz-text-2)]">
                              {v.query_count}
                            </span>
                            <div
                              className="w-full rounded-t relative overflow-hidden"
                              style={{
                                height: `${Math.max(heightPercent, 4)}%`,
                              }}
                            >
                              <div className="absolute inset-0 bg-[var(--bz-accent)]" />
                              {failPercent > 0 && (
                                <div
                                  className="absolute bottom-0 left-0 right-0 bg-[var(--error)]"
                                  style={{ height: `${failPercent}%` }}
                                />
                              )}
                            </div>
                            <span className="text-[10px] text-[var(--bz-text-2)]">
                              {v.bucket
                                ? new Date(v.bucket).toLocaleDateString('en', {
                                    month: 'short',
                                    day: 'numeric',
                                  })
                                : '-'}
                            </span>
                          </div>
                        );
                      })}
                  </div>
                  <div className="flex items-center gap-4 mt-2 text-[10px] text-[var(--bz-text-2)]">
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-sm bg-[var(--bz-accent)]" /> Total
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-sm bg-[var(--error)]" /> Failed
                    </span>
                  </div>
                </div>
              )}
            </div>
          </ExpandableSection>
        )}

        {/* System Health */}
        <ExpandableSection
          title="System Health"
          aria-label="System Health"
          icon={Server}
          isExpanded={expandedSection === 'system'}
          onToggle={() => toggleSection('system')}
          summary={
            <div className="grid grid-cols-2 gap-3">
              <ProgressBar
                value={data.system.cpu_percent}
                label="CPU Usage"
                color={data.system.cpu_percent > 80 ? 'danger' : 'accent'}
              />
              <ProgressBar
                value={data.system.memory_percent}
                label="Memory Usage"
                color={data.system.memory_percent > 80 ? 'danger' : 'accent'}
              />
            </div>
          }
        >
          <div className="space-y-6">
            {/* Resource Usage */}
            <div>
              <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                <Cpu className="w-4 h-4 text-[var(--bz-accent)]" />
                Resource Usage
              </h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 rounded-lg bg-[var(--bz-card)]/50">
                  <ProgressBar
                    value={data.system.cpu_percent}
                    label="CPU"
                    color={
                      data.system.cpu_percent > 80
                        ? 'danger'
                        : data.system.cpu_percent > 60
                          ? 'warning'
                          : 'success'
                    }
                  />
                </div>
                <div className="p-4 rounded-lg bg-[var(--bz-card)]/50">
                  <ProgressBar
                    value={data.system.memory_percent}
                    label="Memory"
                    color={
                      data.system.memory_percent > 80
                        ? 'danger'
                        : data.system.memory_percent > 60
                          ? 'warning'
                          : 'success'
                    }
                  />
                </div>
                <div className="p-4 rounded-lg bg-[var(--bz-card)]/50 text-center">
                  <p className="text-xs text-[var(--bz-text-2)]">Memory Used</p>
                  <p className="text-xl font-bold">
                    {(data.system.memory_mb / 1024).toFixed(1)} GB
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-[var(--bz-card)]/50 text-center">
                  <p className="text-xs text-[var(--bz-text-2)]">Requests/min</p>
                  <p className="text-xl font-bold">{data.system.requests_per_minute.toFixed(1)}</p>
                </div>
              </div>
            </div>

            {/* Response Times */}
            <div>
              <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                <Clock className="w-4 h-4 text-[var(--bz-accent)]" />
                Response Times (Percentiles)
              </h4>
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 rounded-lg bg-[var(--success)]/10 text-center">
                  <p className="text-xs text-[var(--success)]">P50</p>
                  <p className="text-xl font-bold text-[var(--success)]">
                    {data.system.response_time_p50.toFixed(0)}ms
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-[var(--warning)]/10 text-center">
                  <p className="text-xs text-[var(--warning)]">P95</p>
                  <p className="text-xl font-bold text-[var(--warning)]">
                    {data.system.response_time_p95.toFixed(0)}ms
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-[var(--error)]/10 text-center">
                  <p className="text-xs text-[var(--error)]">P99</p>
                  <p className="text-xl font-bold text-[var(--error)]">
                    {data.system.response_time_p99.toFixed(0)}ms
                  </p>
                </div>
              </div>
            </div>

            {/* Database Connections */}
            <div>
              <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                <Database className="w-4 h-4 text-[var(--bz-accent)]" />
                Database Connections
              </h4>
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 rounded-lg bg-[var(--bz-card)]/50 text-center">
                  <p className="text-xs text-[var(--bz-text-2)]">Active</p>
                  <p className="text-xl font-bold text-[var(--bz-accent)]">
                    {data.system.db_connections_active}
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-[var(--bz-card)]/50 text-center">
                  <p className="text-xs text-[var(--bz-text-2)]">Idle</p>
                  <p className="text-xl font-bold">{data.system.db_connections_idle}</p>
                </div>
                <div className="p-4 rounded-lg bg-[var(--bz-card)]/50 text-center">
                  <p className="text-xs text-[var(--bz-text-2)]">Error Rate</p>
                  <p
                    className={cn(
                      'text-xl font-bold',
                      data.system.error_rate_percent > 5
                        ? 'text-[var(--error)]'
                        : 'text-[var(--success)]'
                    )}
                  >
                    {data.system.error_rate_percent.toFixed(2)}%
                  </p>
                </div>
              </div>
            </div>

            {/* Services Status */}
            {data.system.services.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-3">Services Status</h4>
                <DataTable
                  headers={['Service', 'Status', 'Last Check', 'Error']}
                  rows={data.system.services.map((s) => [
                    s.name,
                    <span
                      key="s"
                      className={cn(
                        'px-2 py-1 rounded-full text-xs',
                        s.healthy
                          ? 'bg-[var(--success)]/10 text-[var(--success)]'
                          : 'bg-[var(--error)]/10 text-[var(--error)]'
                      )}
                    >
                      {s.healthy ? '● Healthy' : '● Down'}
                    </span>,
                    s.last_check ? new Date(s.last_check).toLocaleTimeString('en-US') : '-',
                    s.error || '-',
                  ])}
                />
              </div>
            )}
          </div>
        </ExpandableSection>

        {/* Qdrant */}
        <ExpandableSection
          title="Vector Database (Qdrant)"
          aria-label="Vector Database (Qdrant)"
          icon={Database}
          isExpanded={expandedSection === 'qdrant'}
          onToggle={() => toggleSection('qdrant')}
          summary={
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-[var(--bz-card)]/50">
                <p className="text-xs text-[var(--bz-text-2)]">Total Documents</p>
                <p className="text-lg font-bold">{formatNumber(data.qdrant.total_documents)}</p>
              </div>
              <div className="p-3 rounded-lg bg-[var(--bz-card)]/50">
                <p className="text-xs text-[var(--bz-text-2)]">Collections</p>
                <p className="text-lg font-bold">{data.qdrant.collections.length}</p>
              </div>
            </div>
          }
        >
          <div className="space-y-6">
            {/* Overview Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 rounded-lg bg-[var(--bz-accent)]/10 text-center">
                <p className="text-xs text-[var(--bz-accent)]">Total Documents</p>
                <p className="text-2xl font-bold text-[var(--bz-accent)]">
                  {formatNumber(data.qdrant.total_documents)}
                </p>
              </div>
              <div className="p-4 rounded-lg bg-[var(--bz-card)]/50 text-center">
                <p className="text-xs text-[var(--bz-text-2)]">Avg Search Latency</p>
                <p className="text-2xl font-bold">
                  {data.qdrant.search_latency_avg_ms.toFixed(0)}ms
                </p>
              </div>
              <div className="p-4 rounded-lg bg-[var(--bz-card)]/50 text-center">
                <p className="text-xs text-[var(--bz-text-2)]">Searches Today</p>
                <p className="text-2xl font-bold">{data.qdrant.search_operations_today}</p>
              </div>
              <div className="p-4 rounded-lg bg-[var(--bz-card)]/50 text-center">
                <p className="text-xs text-[var(--bz-text-2)]">Upserts Today</p>
                <p className="text-2xl font-bold">{data.qdrant.upsert_operations_today}</p>
              </div>
            </div>

            {/* Collections */}
            <div>
              <h4 className="text-sm font-medium mb-3">Collections</h4>
              <DataTable
                headers={['Collection', 'Documents', 'Status']}
                rows={data.qdrant.collections.map((c) => [
                  c.name,
                  <span key="d" className="font-medium">
                    {formatNumber(c.documents)}
                  </span>,
                  <span
                    key="s"
                    className={cn(
                      'px-2 py-1 rounded-full text-xs',
                      c.status === 'green'
                        ? 'bg-[var(--success)]/10 text-[var(--success)]'
                        : 'bg-[var(--warning)]/10 text-[var(--warning)]'
                    )}
                  >
                    {c.status}
                  </span>,
                ])}
              />
            </div>

            {/* Error Count */}
            {data.qdrant.error_count > 0 && (
              <div className="p-4 rounded-lg bg-[var(--error)]/10 border border-[var(--error)]/20">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-[var(--error)]" />
                  <span className="font-medium text-[var(--error)]">
                    {data.qdrant.error_count} errors detected today
                  </span>
                </div>
              </div>
            )}
          </div>
        </ExpandableSection>

        {/* CRM */}
        <ExpandableSection
          title="CRM Analytics"
          aria-label="CRM Analytics"
          icon={UserCog}
          isExpanded={expandedSection === 'crm'}
          onToggle={() => toggleSection('crm')}
          summary={
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 rounded-lg bg-[var(--bz-card)]/50 text-center">
                <p className="text-xs text-[var(--bz-text-2)]">Clients</p>
                <p className="text-lg font-bold">{data.crm.clients_total}</p>
              </div>
              <div className="p-3 rounded-lg bg-[var(--bz-card)]/50 text-center">
                <p className="text-xs text-[var(--bz-text-2)]">Active</p>
                <p className="text-lg font-bold text-[var(--success)]">{data.crm.clients_active}</p>
              </div>
              <div className="p-3 rounded-lg bg-[var(--bz-card)]/50 text-center">
                <p className="text-xs text-[var(--bz-text-2)]">Practices</p>
                <p className="text-lg font-bold">{data.crm.practices_total}</p>
              </div>
            </div>
          }
        >
          <div className="space-y-6">
            {/* Client Stats */}
            <div>
              <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                <Users className="w-4 h-4 text-[var(--bz-accent)]" />
                Client Overview
              </h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 rounded-lg bg-[var(--bz-accent)]/10 text-center">
                  <p className="text-xs text-[var(--bz-accent)]">Total Clients</p>
                  <p className="text-2xl font-bold text-[var(--bz-accent)]">
                    {data.crm.clients_total}
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-[var(--success)]/10 text-center">
                  <p className="text-xs text-[var(--success)]">Active</p>
                  <p className="text-2xl font-bold text-[var(--success)]">
                    {data.crm.clients_active}
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-[var(--bz-card)]/50 text-center">
                  <p className="text-xs text-[var(--bz-text-2)]">Docs Pending</p>
                  <p className="text-2xl font-bold">{data.crm.documents_pending}</p>
                </div>
                <div className="p-4 rounded-lg bg-[var(--bz-card)]/50 text-center">
                  <p className="text-xs text-[var(--bz-text-2)]">Practices</p>
                  <p className="text-2xl font-bold">{data.crm.practices_total}</p>
                </div>
              </div>
            </div>

            {/* Clients by Status */}
            {Object.keys(data.crm.clients_by_status).length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-3">Clients by Status</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {Object.entries(data.crm.clients_by_status).map(([status, count]) => (
                    <div key={status} className="p-3 rounded-lg bg-[var(--bz-card)]/50 text-center">
                      <p className="text-xs text-[var(--bz-text-2)] capitalize">
                        {status.replace(/_/g, ' ')}
                      </p>
                      <p className="text-lg font-bold">{count}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Revenue */}
            <div>
              <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-[var(--bz-accent)]" />
                Revenue
              </h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="p-4 rounded-lg bg-[var(--success)]/10">
                  <p className="text-xs text-[var(--success)]">Revenue Paid</p>
                  <p className="text-xl font-bold text-[var(--success)]">
                    {formatIDR(data.crm.revenue_paid)}
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-[var(--warning)]/10">
                  <p className="text-xs text-[var(--warning)]">Outstanding</p>
                  <p className="text-xl font-bold text-[var(--warning)]">
                    {formatIDR(data.crm.revenue_quoted - data.crm.revenue_paid)}
                  </p>
                </div>
              </div>
              <div className="mt-3 p-3 rounded-lg bg-[var(--bz-card)]/50">
                <div className="flex justify-between text-sm">
                  <span className="text-[var(--bz-text-2)]">Total Quoted</span>
                  <span className="font-medium">{formatIDR(data.crm.revenue_quoted)}</span>
                </div>
              </div>
            </div>

            {/* Renewals */}
            <div>
              <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                <Calendar className="w-4 h-4 text-[var(--bz-accent)]" />
                Upcoming Renewals
              </h4>
              <div className="grid grid-cols-3 gap-4">
                <div
                  className={cn(
                    'p-4 rounded-lg text-center',
                    data.crm.renewals_30_days > 0
                      ? 'bg-[var(--error)]/10'
                      : 'bg-[var(--bz-card)]/50'
                  )}
                >
                  <p
                    className={cn(
                      'text-xs',
                      data.crm.renewals_30_days > 0
                        ? 'text-[var(--error)]'
                        : 'text-[var(--bz-text-2)]'
                    )}
                  >
                    Next 30 Days
                  </p>
                  <p
                    className={cn(
                      'text-2xl font-bold',
                      data.crm.renewals_30_days > 0 && 'text-[var(--error)]'
                    )}
                  >
                    {data.crm.renewals_30_days}
                  </p>
                </div>
                <div
                  className={cn(
                    'p-4 rounded-lg text-center',
                    data.crm.renewals_60_days > 0
                      ? 'bg-[var(--warning)]/10'
                      : 'bg-[var(--bz-card)]/50'
                  )}
                >
                  <p
                    className={cn(
                      'text-xs',
                      data.crm.renewals_60_days > 0
                        ? 'text-[var(--warning)]'
                        : 'text-[var(--bz-text-2)]'
                    )}
                  >
                    Next 60 Days
                  </p>
                  <p
                    className={cn(
                      'text-2xl font-bold',
                      data.crm.renewals_60_days > 0 && 'text-[var(--warning)]'
                    )}
                  >
                    {data.crm.renewals_60_days}
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-[var(--bz-card)]/50 text-center">
                  <p className="text-xs text-[var(--bz-text-2)]">Next 90 Days</p>
                  <p className="text-2xl font-bold">{data.crm.renewals_90_days}</p>
                </div>
              </div>
            </div>

            {/* Practices by Status */}
            {Object.keys(data.crm.practices_by_status).length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-[var(--bz-accent)]" />
                  Practices by Status
                </h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {Object.entries(data.crm.practices_by_status).map(([status, count]) => (
                    <div key={status} className="p-3 rounded-lg bg-[var(--bz-card)]/50 text-center">
                      <p className="text-xs text-[var(--bz-text-2)] capitalize">
                        {status.replace(/_/g, ' ')}
                      </p>
                      <p className="text-lg font-bold">{count}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </ExpandableSection>

        {/* Team */}
        <ExpandableSection
          title="Team Productivity"
          aria-label="Team Productivity"
          icon={Users}
          isExpanded={expandedSection === 'team'}
          onToggle={() => toggleSection('team')}
          summary={
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-[var(--bz-card)]/50">
                <p className="text-xs text-[var(--bz-text-2)]">Hours Today</p>
                <p className="text-lg font-bold">{data.team.hours_today.toFixed(1)}h</p>
              </div>
              <div className="p-3 rounded-lg bg-[var(--bz-card)]/50">
                <p className="text-xs text-[var(--bz-text-2)]">Hours This Week</p>
                <p className="text-lg font-bold">{data.team.hours_week.toFixed(1)}h</p>
              </div>
            </div>
          }
        >
          <div className="space-y-6">
            {/* Hours Overview */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 rounded-lg bg-[var(--bz-accent)]/10 text-center">
                <p className="text-xs text-[var(--bz-accent)]">Hours Today</p>
                <p className="text-2xl font-bold text-[var(--bz-accent)]">
                  {data.team.hours_today.toFixed(1)}h
                </p>
              </div>
              <div className="p-4 rounded-lg bg-[var(--bz-card)]/50 text-center">
                <p className="text-xs text-[var(--bz-text-2)]">Hours This Week</p>
                <p className="text-2xl font-bold">{data.team.hours_week.toFixed(1)}h</p>
              </div>
              <div className="p-4 rounded-lg bg-[var(--success)]/10 text-center">
                <p className="text-xs text-[var(--success)]">Active Sessions</p>
                <p className="text-2xl font-bold text-[var(--success)]">
                  {data.team.active_sessions}
                </p>
              </div>
              <div className="p-4 rounded-lg bg-[var(--warning)]/10 text-center">
                <p className="text-xs text-[var(--warning)]">Open Actions</p>
                <p className="text-2xl font-bold text-[var(--warning)]">
                  {data.team.action_items_open}
                </p>
              </div>
            </div>

            {/* Conversations by Agent */}
            {Object.keys(data.team.conversations_by_agent).length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-3">Conversations by Agent</h4>
                <DataTable
                  headers={['Agent', 'Conversations']}
                  rows={Object.entries(data.team.conversations_by_agent).map(([agent, count]) => [
                    agent,
                    <span key="c" className="font-medium">
                      {count}
                    </span>,
                  ])}
                />
              </div>
            )}

            {/* Productivity Scores */}
            {Object.keys(data.team.productivity_scores).length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-3">Productivity Scores</h4>
                <div className="space-y-3">
                  {Object.entries(data.team.productivity_scores).map(([agent, score]) => (
                    <div key={agent}>
                      <ProgressBar
                        value={score * 100}
                        label={agent}
                        color={score > 0.7 ? 'success' : score > 0.5 ? 'warning' : 'danger'}
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </ExpandableSection>

        {/* Feedback */}
        <ExpandableSection
          title="Quality & Feedback"
          aria-label="Quality & Feedback"
          icon={TrendingUp}
          isExpanded={expandedSection === 'feedback'}
          onToggle={() => toggleSection('feedback')}
          summary={
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 rounded-lg bg-[var(--bz-card)]/50 text-center">
                <p className="text-xs text-[var(--bz-text-2)]">Avg Rating</p>
                <p className="text-lg font-bold text-[var(--success)]">
                  {data.feedback.avg_rating.toFixed(1)}/5
                </p>
              </div>
              <div className="p-3 rounded-lg bg-[var(--bz-card)]/50 text-center">
                <p className="text-xs text-[var(--bz-text-2)]">Total</p>
                <p className="text-lg font-bold">{data.feedback.total_ratings}</p>
              </div>
              <div className="p-3 rounded-lg bg-[var(--error)]/10 text-center">
                <p className="text-xs text-[var(--error)]">Negative</p>
                <p className="text-lg font-bold text-[var(--error)]">
                  {data.feedback.negative_feedback_count}
                </p>
              </div>
            </div>
          }
        >
          <div className="space-y-6">
            {/* Rating Overview */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 rounded-lg bg-[var(--success)]/10 text-center">
                <p className="text-xs text-[var(--success)]">Average Rating</p>
                <p className="text-3xl font-bold text-[var(--success)]">
                  {data.feedback.avg_rating.toFixed(2)}
                </p>
                <p className="text-xs text-[var(--success)]">out of 5</p>
              </div>
              <div className="p-4 rounded-lg bg-[var(--bz-card)]/50 text-center">
                <p className="text-xs text-[var(--bz-text-2)]">Total Ratings</p>
                <p className="text-2xl font-bold">{data.feedback.total_ratings}</p>
              </div>
              <div className="p-4 rounded-lg bg-[var(--error)]/10 text-center">
                <p className="text-xs text-[var(--error)]">Negative Feedback</p>
                <p className="text-2xl font-bold text-[var(--error)]">
                  {data.feedback.negative_feedback_count}
                </p>
              </div>
              <div className="p-4 rounded-lg bg-[var(--bz-card)]/50 text-center">
                <p className="text-xs text-[var(--bz-text-2)]">Satisfaction Rate</p>
                <p className="text-2xl font-bold">
                  {data.feedback.total_ratings > 0
                    ? (
                        (1 - data.feedback.negative_feedback_count / data.feedback.total_ratings) *
                        100
                      ).toFixed(0)
                    : 0}
                  %
                </p>
              </div>
            </div>

            {/* Rating Distribution */}
            <div>
              <h4 className="text-sm font-medium mb-3">Rating Distribution</h4>
              <div className="space-y-2">
                {[5, 4, 3, 2, 1].map((rating) => {
                  const count = data.feedback.rating_distribution[rating.toString()] || 0;
                  const percent =
                    data.feedback.total_ratings > 0
                      ? (count / data.feedback.total_ratings) * 100
                      : 0;
                  return (
                    <div key={rating} className="flex items-center gap-3">
                      <span className="w-8 text-sm font-medium">{rating} ⭐</span>
                      <div className="flex-1 h-4 rounded-full bg-[var(--bz-card)]">
                        <div
                          className={cn(
                            'h-full rounded-full transition-all',
                            rating >= 4
                              ? 'bg-[var(--success)]'
                              : rating === 3
                                ? 'bg-[var(--warning)]'
                                : 'bg-[var(--error)]'
                          )}
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                      <span className="w-12 text-sm text-right text-[var(--bz-text-2)]">
                        {count}
                      </span>
                      <span className="w-12 text-sm text-right text-[var(--bz-text-2)]">
                        {percent.toFixed(0)}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Recent Negative Feedback */}
            {data.feedback.recent_negative_feedback.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-3 text-[var(--error)]">
                  Recent Negative Feedback
                </h4>
                <div className="space-y-2">
                  {data.feedback.recent_negative_feedback.map((f, i) => (
                    <div
                      key={i}
                      className="p-3 rounded-lg bg-[var(--error)]/5 border border-[var(--error)]/20"
                    >
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-[var(--error)]">Rating: {f.rating}/5</span>
                        <span className="text-[var(--bz-text-2)]">
                          {new Date(f.date).toLocaleDateString('en-US')}
                        </span>
                      </div>
                      <p className="text-sm">{f.feedback || 'No comment provided'}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Quality Trend */}
            {data.feedback.quality_trend.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-3">Quality Trend (Last 7 Days)</h4>
                <div className="flex items-end gap-2 h-24">
                  {data.feedback.quality_trend.map((t, i) => (
                    <div key={i} className="flex-1 flex flex-col items-center gap-1">
                      <div
                        className={cn(
                          'w-full rounded-t',
                          t.rating >= 4
                            ? 'bg-[var(--success)]'
                            : t.rating >= 3
                              ? 'bg-[var(--warning)]'
                              : 'bg-[var(--error)]'
                        )}
                        style={{ height: `${(t.rating / 5) * 100}%` }}
                      />
                      <span className="text-[10px] text-[var(--bz-text-2)]">
                        {new Date(t.date).toLocaleDateString('en', {
                          weekday: 'short',
                        })}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </ExpandableSection>

        {/* Alerts */}
        <ExpandableSection
          title="Alerts & Errors"
          aria-label="Alerts & Errors"
          icon={AlertTriangle}
          isExpanded={expandedSection === 'alerts'}
          onToggle={() => toggleSection('alerts')}
          summary={
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-[var(--error)]/10">
                <p className="text-xs text-[var(--error)]">Auth Failures</p>
                <p className="text-lg font-bold text-[var(--error)]">
                  {data.alerts.auth_failures_today}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-[var(--warning)]/10">
                <p className="text-xs text-[var(--warning)]">Active Alerts</p>
                <p className="text-lg font-bold text-[var(--warning)]">
                  {data.alerts.active_alerts.length}
                </p>
              </div>
            </div>
          }
        >
          <div className="space-y-6">
            {/* Overview Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 rounded-lg bg-[var(--error)]/10 text-center">
                <p className="text-xs text-[var(--error)]">Auth Failures Today</p>
                <p className="text-2xl font-bold text-[var(--error)]">
                  {data.alerts.auth_failures_today}
                </p>
              </div>
              <div className="p-4 rounded-lg bg-[var(--warning)]/10 text-center">
                <p className="text-xs text-[var(--warning)]">Active Alerts</p>
                <p className="text-2xl font-bold text-[var(--warning)]">
                  {data.alerts.active_alerts.length}
                </p>
              </div>
              <div className="p-4 rounded-lg bg-[var(--bz-card)]/50 text-center">
                <p className="text-xs text-[var(--bz-text-2)]">Errors Today</p>
                <p className="text-2xl font-bold">{data.alerts.error_count_today}</p>
              </div>
              <div className="p-4 rounded-lg bg-[var(--bz-card)]/50 text-center">
                <p className="text-xs text-[var(--bz-text-2)]">Slow Queries</p>
                <p className="text-2xl font-bold">{data.alerts.slow_queries.length}</p>
              </div>
            </div>

            {/* Active Alerts */}
            {data.alerts.active_alerts.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-3 flex items-center gap-2">
                  <Shield className="w-4 h-4 text-[var(--error)]" />
                  Active Alerts
                </h4>
                <div className="space-y-2">
                  {data.alerts.active_alerts.map((a, i) => (
                    <div
                      key={i}
                      className={cn(
                        'p-3 rounded-lg border',
                        a.severity === 'critical'
                          ? 'bg-[var(--error)]/10 border-[var(--error)]/30'
                          : a.severity === 'warning'
                            ? 'bg-[var(--warning)]/10 border-[var(--warning)]/30'
                            : 'bg-[var(--bz-card)] border-[var(--bz-border)]'
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{a.service}</span>
                        <span
                          className={cn(
                            'px-2 py-0.5 rounded-full text-xs',
                            a.severity === 'critical'
                              ? 'bg-[var(--error)]/20 text-[var(--error)]'
                              : a.severity === 'warning'
                                ? 'bg-[var(--warning)]/20 text-[var(--warning)]'
                                : 'bg-[var(--bz-card)] text-[var(--bz-text-2)]'
                          )}
                        >
                          {a.severity}
                        </span>
                      </div>
                      <p className="text-sm mt-1 text-[var(--bz-text-2)]">{a.message}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recent Errors */}
            {data.alerts.recent_errors.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-3">Recent Errors</h4>
                <DataTable
                  headers={['Action', 'User', 'Reason', 'Time']}
                  rows={data.alerts.recent_errors.map((e) => [
                    e.action,
                    e.email,
                    <span key="r" className="text-[var(--error)] truncate max-w-[200px] block">
                      {e.reason}
                    </span>,
                    new Date(e.time).toLocaleTimeString('en-US'),
                  ])}
                />
              </div>
            )}

            {/* Slow Queries */}
            {data.alerts.slow_queries.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-3">Slow Queries</h4>
                <DataTable
                  headers={['Query', 'Duration']}
                  rows={data.alerts.slow_queries.map((q) => [
                    <span key="q" className="truncate max-w-[400px] block">
                      {q.query}
                    </span>,
                    <span key="d" className="text-[var(--warning)] font-medium">
                      {q.duration_ms}ms
                    </span>,
                  ])}
                />
              </div>
            )}
          </div>
        </ExpandableSection>
      </div>

      {/* Footer */}
      <div className="text-center text-xs text-[var(--bz-text-2)] py-4">
        Generated at{' '}
        {new Date(data.generated_at).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          year: 'numeric',
        })}{' '}
        {new Date(data.generated_at).toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
        })}{' '}
        • Auto-refreshes every 60s •
        Founder Dashboard
      </div>
    </div>
  );
}
