'use client';

/**
 * Client Analytics Dashboard v2
 *
 * Enhanced analytics for client management:
 * - Client overview metrics with trends
 * - Team performance analytics with rankings
 * - Revenue statistics with forecasts
 * - Process/case analytics with completion rates
 * - Temporal trends with comparison
 * - Mobile-optimized responsive design
 * - Data export functionality
 *
 * @ai_onboarding - Strict TypeScript, async patterns, error handling, mobile-first
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Users,
  TrendingUp,
  DollarSign,
  Briefcase,
  ArrowLeft,
  BarChart3,
  PieChart,
  Calendar,
  UserCog,
  Globe,
  Activity,
  Loader2,
  Download,
  Filter,
  ChevronDown,
  Target,
  Clock,
  Award,
  ArrowUpRight,
  ArrowDownRight,
  Smartphone,
  Tablet,
  Monitor,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { useToast } from '@/components/ui/toast';

// ================================================
// TYPES
// ================================================

interface ClientOverview {
  total_clients: number;
  new_this_month: number;
  new_this_week: number;
  by_status: Record<string, number>;
  by_nationality: Record<string, number>;
  growth_rate: number;
  churn_rate: number;
}

interface TeamPerformance {
  member_email: string;
  full_name?: string;
  total_clients: number;
  active_clients: number;
  completed_cases: number;
  conversion_rate: number;
  revenue_generated: number;
  avg_response_time_hours: number;
  satisfaction_score: number;
}

interface RevenueSummary {
  total_quoted: number;
  total_actual: number;
  total_paid: number;
  total_outstanding: number;
  avg_per_client: number;
  by_month: Array<{
    period: string;
    revenue: number;
    paid: number;
    target: number;
  }>;
  forecast_next_month: number;
}

interface ProcessTypeMetric {
  practice_type_code: string;
  practice_type_name: string;
  total_cases: number;
  active_cases: number;
  completed_cases: number;
  avg_completion_days: number;
  total_revenue: number;
  success_rate: number;
}

interface TrendPoint {
  period: string;
  new_clients: number;
  revenue: number;
  active_cases: number;
  completed_cases: number;
}

interface FunnelStage {
  stage: string;
  count: number;
  percentage: number;
  drop_off: number;
}

type DateRange = '7d' | '30d' | '90d' | '6m' | '1y' | 'all';
type ViewMode = 'desktop' | 'tablet' | 'mobile';

// ================================================
// UTILITY COMPONENTS
// ================================================

const TrendIndicator = ({ value, suffix = '%' }: { value: number; suffix?: string }) => {
  const isPositive = value >= 0;
  return (
    <span
      className={`flex items-center gap-1 text-xs font-medium ${isPositive ? 'text-green-500' : 'text-red-500'}`}
    >
      {isPositive ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
      {Math.abs(value).toFixed(1)}
      {suffix}
    </span>
  );
};

// ================================================
// STAT CARD COMPONENT
// ================================================

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: number;
  icon: React.ElementType;
  color: 'blue' | 'green' | 'amber' | 'purple' | 'red' | 'cyan';
  loading?: boolean;
  onClick?: () => void;
}

const StatCard = ({
  title,
  value,
  subtitle,
  trend,
  icon: Icon,
  color,
  loading,
  onClick,
}: StatCardProps) => {
  const colorClasses = {
    blue: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
    green: 'bg-green-500/10 text-green-500 border-green-500/20',
    amber: 'bg-amber-500/10 text-amber-500 border-amber-500/20',
    purple: 'bg-purple-500/10 text-purple-500 border-purple-500/20',
    red: 'bg-red-500/10 text-red-500 border-red-500/20',
    cyan: 'bg-cyan-500/10 text-cyan-500 border-cyan-500/20',
  };

  return (
    <div
      onClick={onClick}
      className={`rounded-xl border p-4 sm:p-6 ${colorClasses[color]} ${onClick ? 'cursor-pointer hover:opacity-80 transition-opacity' : ''}`}
    >
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <p className="text-xs sm:text-sm font-medium opacity-80 truncate">{title}</p>
          {loading ? (
            <Loader2 className="w-6 h-6 sm:w-8 sm:h-8 animate-spin mt-2" />
          ) : (
            <>
              <p className="text-xl sm:text-2xl lg:text-3xl font-bold mt-1 sm:mt-2 truncate">
                {value}
              </p>
              {subtitle && <p className="text-xs mt-1 opacity-70 truncate">{subtitle}</p>}
              {trend !== undefined && (
                <div className="mt-1">
                  <TrendIndicator value={trend} />
                </div>
              )}
            </>
          )}
        </div>
        <div className="p-2 sm:p-3 rounded-lg bg-white/5 shrink-0 ml-2">
          <Icon className="w-4 h-4 sm:w-5 sm:h-5 lg:w-6 lg:h-6" />
        </div>
      </div>
    </div>
  );
};

// ================================================
// MINI CHART COMPONENT
// ================================================

const MiniSparkline = ({ data, color = 'var(--accent)' }: { data: number[]; color?: string }) => {
  if (!data.length) return null;

  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;

  const points = data
    .map((val, i) => {
      const x = (i / (data.length - 1)) * 100;
      const y = 100 - ((val - min) / range) * 100;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg viewBox="0 0 100 100" className="w-full h-12 sm:h-16" preserveAspectRatio="none">
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="2"
        points={points}
        className="drop-shadow-sm"
      />
      <polygon fill={color} fillOpacity="0.1" points={`0,100 ${points} 100,100`} />
    </svg>
  );
};

// ================================================
// FUNNEL CHART COMPONENT
// ================================================

const FunnelChart = ({ data }: { data: FunnelStage[] }) => {
  const maxCount = Math.max(...data.map((d) => d.count));

  return (
    <div className="space-y-2">
      {data.map((stage, idx) => (
        <div key={idx} className="flex items-center gap-2 sm:gap-3">
          <div className="w-16 sm:w-24 text-xs text-muted-foreground truncate">{stage.stage}</div>
          <div className="flex-1 relative">
            <div
              className="h-6 sm:h-8 rounded-md bg-gradient-to-r from-blue-500 to-cyan-500 flex items-center justify-end pr-2 transition-all duration-500"
              style={{ width: `${(stage.count / maxCount) * 100}%` }}
            >
              <span className="text-xs text-white font-medium">{stage.count}</span>
            </div>
          </div>
          <div className="w-12 sm:w-16 text-right">
            <span className="text-xs font-medium">{stage.percentage}%</span>
          </div>
        </div>
      ))}
    </div>
  );
};

// ================================================
// PROGRESS BAR COMPONENT
// ================================================

const ProgressBar = ({
  value,
  max,
  label,
  color = 'blue',
}: {
  value: number;
  max: number;
  label: string;
  color?: string;
}) => {
  const percentage = max > 0 ? (value / max) * 100 : 0;
  const colorMap: Record<string, string> = {
    blue: 'bg-blue-500',
    green: 'bg-green-500',
    amber: 'bg-amber-500',
    purple: 'bg-purple-500',
    red: 'bg-red-500',
  };

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">{value.toLocaleString('en-US')}</span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full ${colorMap[color] || colorMap.blue} transition-all duration-500 rounded-full`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
};

// ================================================
// DATE RANGE SELECTOR
// ================================================

const DateRangeSelector = ({
  value,
  onChange,
}: {
  value: DateRange;
  onChange: (v: DateRange) => void;
}) => {
  const ranges: { value: DateRange; label: string }[] = [
    { value: '7d', label: '7 Days' },
    { value: '30d', label: '30 Days' },
    { value: '90d', label: '90 Days' },
    { value: '6m', label: '6 Months' },
    { value: '1y', label: '1 Year' },
    { value: 'all', label: 'All Time' },
  ];

  return (
    <div className="flex flex-wrap gap-1 bg-muted p-1 rounded-lg">
      {ranges.map((r) => (
        <button
          key={r.value}
          onClick={() => onChange(r.value)}
          className={`px-2 sm:px-3 py-1 text-xs rounded-md transition-all ${
            value === r.value
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
          }`}
        >
          {r.label}
        </button>
      ))}
    </div>
  );
};

// ================================================
// EXPORT BUTTON
// ================================================

const ExportButton = ({ data, filename }: { data: unknown; filename: string }) => {
  const handleExport = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename}-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Button variant="outline" size="sm" onClick={handleExport} className="gap-2">
      <Download className="w-4 h-4" />
      <span className="hidden sm:inline">Export</span>
    </Button>
  );
};

// ================================================
// MAIN PAGE
// ================================================

export default function ClientAnalyticsPage() {
  const router = useRouter();
  const { error: showError } = useToast();
  const [isLoading, setIsLoading] = useState(true);
  const [dateRange, setDateRange] = useState<DateRange>('6m');
  const [viewMode, setViewMode] = useState<ViewMode>('desktop');
  const [activeTab, setActiveTab] = useState<'overview' | 'team' | 'revenue' | 'processes'>(
    'overview'
  );

  // Data states
  const [overview, setOverview] = useState<ClientOverview | null>(null);
  const [teamPerformance, setTeamPerformance] = useState<TeamPerformance[]>([]);
  const [revenue, setRevenue] = useState<RevenueSummary | null>(null);
  const [processTypes, setProcessTypes] = useState<ProcessTypeMetric[]>([]);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [funnel, setFunnel] = useState<FunnelStage[]>([]);

  // Detect viewport size
  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      if (width < 640) setViewMode('mobile');
      else if (width < 1024) setViewMode('tablet');
      else setViewMode('desktop');
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Fetch all data
  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);

      const [overviewRes, teamRes, revenueRes, processRes, trendRes] = await Promise.all([
        api.get<ClientOverview>('/api/crm/analytics/clients/overview'),
        api.get<TeamPerformance[]>('/api/crm/analytics/team/performance'),
        api.get<RevenueSummary>('/api/crm/analytics/revenue/summary'),
        api.get<ProcessTypeMetric[]>('/api/crm/analytics/processes/by-type'),
        api.get<TrendPoint[]>(
          `/api/crm/analytics/clients/trend?months=${dateRange === '6m' ? 6 : dateRange === '1y' ? 12 : 6}`
        ),
      ]);

      setOverview(overviewRes);
      setTeamPerformance(teamRes);
      setRevenue(revenueRes);
      setProcessTypes(processRes);
      setTrend(trendRes);

      // Generate funnel data from overview
      if (overviewRes?.by_status) {
        const total = overviewRes.total_clients || 1;
        const funnelData: FunnelStage[] = [
          {
            stage: 'Leads',
            count: overviewRes.by_status.lead || 0,
            percentage: Math.round(((overviewRes.by_status.lead || 0) / total) * 100),
            drop_off: 0,
          },
          {
            stage: 'Active',
            count: overviewRes.by_status.active || 0,
            percentage: Math.round(((overviewRes.by_status.active || 0) / total) * 100),
            drop_off: Math.round(
              (((overviewRes.by_status.lead || 0) - (overviewRes.by_status.active || 0)) /
                (overviewRes.by_status.lead || 1)) *
                100
            ),
          },
          {
            stage: 'Completed',
            count: overviewRes.by_status.completed || 0,
            percentage: Math.round(((overviewRes.by_status.completed || 0) / total) * 100),
            drop_off: Math.round(
              (((overviewRes.by_status.active || 0) - (overviewRes.by_status.completed || 0)) /
                (overviewRes.by_status.active || 1)) *
                100
            ),
          },
        ];
        setFunnel(funnelData);
      }
    } catch (err) {
      logger.error('Failed to load analytics data', {}, err as Error);
      showError('Failed to load analytics', 'Please try again later');
    } finally {
      setIsLoading(false);
    }
  }, [dateRange, showError]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Memoized calculations
  const nationalityData = useMemo(() => {
    if (!overview?.by_nationality) return [];
    return Object.entries(overview.by_nationality)
      .map(([nationality, count]) => ({ nationality, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, viewMode === 'mobile' ? 5 : 8);
  }, [overview?.by_nationality, viewMode]);

  const revenueSparkline = useMemo(() => {
    return trend.map((t) => t.revenue);
  }, [trend]);

  const formatCurrency = (amount: number) => {
    if (viewMode === 'mobile') {
      return new Intl.NumberFormat('id-ID', {
        style: 'currency',
        currency: 'IDR',
        notation: 'compact',
        maximumFractionDigits: 1,
      }).format(amount);
    }
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatCompact = (num: number) => {
    return new Intl.NumberFormat('id-ID', { notation: 'compact' }).format(num);
  };

  // Mobile-optimized tabs
  const TabButton = ({
    id,
    label,
    icon: Icon,
  }: {
    id: typeof activeTab;
    label: string;
    icon: React.ElementType;
  }) => (
    <button
      onClick={() => setActiveTab(id)}
      className={`flex items-center gap-2 px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium transition-all ${
        activeTab === id
          ? 'bg-[var(--accent)] text-white'
          : 'text-muted-foreground hover:text-foreground hover:bg-muted'
      }`}
    >
      <Icon className="w-4 h-4" />
      <span className="hidden sm:inline">{label}</span>
    </button>
  );

  return (
    <div className="p-3 sm:p-4 lg:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col gap-4 mb-6 sm:mb-8">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <button
              onClick={() => router.push('/clients')}
              className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors mb-2 text-sm"
              aria-label="Back to clients"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Clients
            </button>
            <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold">Client Analytics</h1>
            <p className="text-xs sm:text-sm text-muted-foreground mt-1">
              Insights into your client base and team performance
            </p>
          </div>
          <div className="flex items-center gap-2">
            <ExportButton
              data={{ overview, teamPerformance, revenue, processTypes, trend }}
              filename="client-analytics"
            />
            <Button variant="outline" size="sm" onClick={fetchData} disabled={isLoading}>
              <Activity className="w-4 h-4 sm:mr-2" />
              <span className="hidden sm:inline">{isLoading ? 'Loading...' : 'Refresh'}</span>
            </Button>
          </div>
        </div>

        {/* Controls Row */}
        <div className="flex flex-col sm:flex-row gap-3 justify-between items-start sm:items-center">
          <DateRangeSelector value={dateRange} onChange={setDateRange} />
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="hidden sm:inline">View:</span>
            <Monitor className={`w-4 h4 ${viewMode === 'desktop' ? 'text-foreground' : ''}`} />
            <Tablet className={`w-4 h-4 ${viewMode === 'tablet' ? 'text-foreground' : ''}`} />
            <Smartphone className={`w-4 h-4 ${viewMode === 'mobile' ? 'text-foreground' : ''}`} />
          </div>
        </div>
      </div>

      {/* Mobile Tabs */}
      {viewMode === 'mobile' && (
        <div className="flex gap-1 overflow-x-auto pb-2 mb-4 scrollbar-hide">
          <TabButton id="overview" label="Overview" icon={BarChart3} />
          <TabButton id="team" label="Team" icon={UserCog} />
          <TabButton id="revenue" label="Revenue" icon={DollarSign} />
          <TabButton id="processes" label="Processes" icon={Briefcase} />
        </div>
      )}

      {/* Overview Section */}
      {(!viewMode || activeTab === 'overview') && (
        <section className="mb-6 sm:mb-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base sm:text-lg font-semibold flex items-center gap-2">
              <Users className="w-4 h-4 sm:w-5 sm:h-5" />
              Client Overview
            </h2>
            {overview?.growth_rate !== undefined && <TrendIndicator value={overview.growth_rate} />}
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <StatCard
              title="Total Clients"
              aria-label="Total Clients"
              value={isLoading ? '-' : formatCompact(overview?.total_clients || 0)}
              subtitle={`+${overview?.new_this_month || 0} this month`}
              trend={overview?.growth_rate}
              icon={Users}
              color="blue"
              loading={isLoading}
            />
            <StatCard
              title="New This Week"
              aria-label="New This Week"
              value={isLoading ? '-' : overview?.new_this_week || 0}
              subtitle="Active acquisition"
              icon={TrendingUp}
              color="green"
              loading={isLoading}
            />
            <StatCard
              title="Active Clients"
              aria-label="Active Clients"
              value={isLoading ? '-' : overview?.by_status?.active || 0}
              subtitle="Currently managed"
              icon={Activity}
              color="amber"
              loading={isLoading}
            />
            <StatCard
              title="Conversion Rate"
              aria-label="Conversion Rate"
              value={
                isLoading
                  ? '-'
                  : `${
                      overview?.by_status?.active && overview?.total_clients
                        ? Math.round((overview.by_status.active / overview.total_clients) * 100)
                        : 0
                    }%`
              }
              subtitle="Active / Total"
              aria-label="Conversion Rate"
              icon={Target}
              color="purple"
              loading={isLoading}
            />
          </div>

          {/* Funnel & Sparkline Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
            {/* Conversion Funnel */}
            <div className="bg-card rounded-xl border p-4 sm:p-6">
              <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
                <Target className="w-4 h-4" />
                Conversion Funnel
              </h3>
              {isLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-8 h-8 animate-spin" />
                </div>
              ) : funnel.length > 0 ? (
                <FunnelChart data={funnel} />
              ) : (
                <p className="text-muted-foreground text-center py-8 text-sm">No data available</p>
              )}
            </div>

            {/* Revenue Trend Sparkline */}
            <div className="bg-card rounded-xl border p-4 sm:p-6">
              <h3 className="text-sm font-semibold mb-4 flex items-center gap-2">
                <TrendingUp className="w-4 h-4" />
                Revenue Trend
              </h3>
              {isLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-8 h-8 animate-spin" />
                </div>
              ) : revenueSparkline.length > 0 ? (
                <MiniSparkline data={revenueSparkline} />
              ) : (
                <p className="text-muted-foreground text-center py-8 text-sm">No data available</p>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Revenue Section */}
      {(viewMode !== 'mobile' || activeTab === 'revenue') && (
        <section className="mb-6 sm:mb-8 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-100">
          <h2 className="text-base sm:text-lg font-semibold mb-4 flex items-center gap-2">
            <DollarSign className="w-4 h-4 sm:w-5 sm:h-5" />
            Revenue Analysis
          </h2>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-4">
            <StatCard
              title="Total Revenue"
              aria-label="Total Revenue"
              value={isLoading ? '-' : formatCurrency(revenue?.total_actual || 0)}
              subtitle="Actual collected"
              icon={DollarSign}
              color="green"
              loading={isLoading}
            />
            <StatCard
              title="Paid"
              aria-label="Paid"
              value={isLoading ? '-' : formatCurrency(revenue?.total_paid || 0)}
              subtitle={`${revenue?.total_actual ? Math.round((revenue.total_paid / revenue.total_actual) * 100) : 0}% collection rate`}
              icon={Activity}
              color="blue"
              loading={isLoading}
            />
            <StatCard
              title="Outstanding"
              aria-label="Outstanding"
              value={isLoading ? '-' : formatCurrency(revenue?.total_outstanding || 0)}
              subtitle="Pending payment"
              icon={Clock}
              color="amber"
              loading={isLoading}
            />
            <StatCard
              title="Avg per Client"
              aria-label="Avg per Client"
              value={isLoading ? '-' : formatCurrency(revenue?.avg_per_client || 0)}
              subtitle="Revenue average"
              icon={BarChart3}
              color="cyan"
              loading={isLoading}
            />
          </div>

          {/* Monthly Trend Table */}
          <div className="bg-card rounded-xl border overflow-hidden">
            <div className="p-4 border-b">
              <h3 className="text-sm font-semibold">Monthly Breakdown</h3>
            </div>
            {isLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="w-8 h-8 animate-spin" />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-muted">
                    <tr>
                      <th className="text-left p-3 font-medium">Period</th>
                      <th className="text-right p-3 font-medium">Revenue</th>
                      <th className="text-right p-3 font-medium">Paid</th>
                      <th className="text-right p-3 font-medium hidden sm:table-cell">
                        Collection %
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {revenue?.by_month?.map((month, idx) => (
                      <tr key={idx} className="hover:bg-muted/50">
                        <td className="p-3">{month.period}</td>
                        <td className="p-3 text-right font-medium">
                          {formatCurrency(month.revenue)}
                        </td>
                        <td className="p-3 text-right text-green-500">
                          {formatCurrency(month.paid)}
                        </td>
                        <td className="p-3 text-right hidden sm:table-cell">
                          {month.revenue > 0 ? Math.round((month.paid / month.revenue) * 100) : 0}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
      )}

      {/* Team Performance Section */}
      {(viewMode !== 'mobile' || activeTab === 'team') && (
        <section className="mb-6 sm:mb-8 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-200">
          <h2 className="text-base sm:text-lg font-semibold mb-4 flex items-center gap-2">
            <UserCog className="w-4 h-4 sm:w-5 sm:h-5" />
            Team Performance
          </h2>

          <div className="bg-card rounded-xl border overflow-hidden">
            {isLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="w-8 h-8 animate-spin" />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs sm:text-sm">
                  <thead className="bg-muted">
                    <tr>
                      <th className="text-left p-3 font-medium">Team Member</th>
                      <th className="text-center p-3 font-medium">Clients</th>
                      <th className="text-center p-3 font-medium hidden sm:table-cell">Active</th>
                      <th className="text-center p-3 font-medium hidden md:table-cell">
                        Completed
                      </th>
                      <th className="text-center p-3 font-medium">Conversion</th>
                      <th className="text-right p-3 font-medium">Revenue</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {teamPerformance.map((member, idx) => (
                      <tr key={idx} className="hover:bg-muted/50">
                        <td className="p-3">
                          <div className="flex items-center gap-2">
                            {idx < 3 && (
                              <Award
                                className={`w-4 h-4 ${
                                  idx === 0
                                    ? 'text-yellow-500'
                                    : idx === 1
                                      ? 'text-gray-400'
                                      : 'text-amber-600'
                                }`}
                              />
                            )}
                            <span className="truncate max-w-[120px] sm:max-w-[200px]">
                              {member.member_email}
                            </span>
                          </div>
                        </td>
                        <td className="p-3 text-center">{member.total_clients}</td>
                        <td className="p-3 text-center text-green-500 hidden sm:table-cell">
                          {member.active_clients}
                        </td>
                        <td className="p-3 text-center hidden md:table-cell">
                          {member.completed_cases}
                        </td>
                        <td className="p-3 text-center">
                          <span
                            className={`px-2 py-1 rounded-full text-xs ${
                              member.conversion_rate >= 50
                                ? 'bg-green-500/20 text-green-500'
                                : member.conversion_rate >= 30
                                  ? 'bg-amber-500/20 text-amber-500'
                                  : 'bg-red-500/20 text-red-500'
                            }`}
                          >
                            {member.conversion_rate}%
                          </span>
                        </td>
                        <td className="p-3 text-right font-medium">
                          {formatCurrency(member.revenue_generated)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
      )}

      {/* Processes & Nationalities Grid */}
      {(viewMode !== 'mobile' || activeTab === 'processes') && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500 delay-300">
          {/* Process Types */}
          <section className="bg-card rounded-xl border p-4 sm:p-6">
            <h2 className="text-base sm:text-lg font-semibold mb-4 flex items-center gap-2">
              <Briefcase className="w-4 h-4 sm:w-5 sm:h-5" />
              Cases by Type
            </h2>
            {isLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="w-8 h-8 animate-spin" />
              </div>
            ) : (
              <div className="space-y-3">
                {processTypes.slice(0, viewMode === 'mobile' ? 4 : 6).map((process, idx) => (
                  <div key={idx} className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="font-medium truncate">{process.practice_type_name}</span>
                      <span className="text-muted-foreground">
                        {formatCurrency(process.total_revenue)}
                      </span>
                    </div>
                    <ProgressBar
                      value={process.active_cases}
                      max={process.total_cases}
                      label={`${process.active_cases} active / ${process.completed_cases} completed`}
                      color={idx % 2 === 0 ? 'blue' : 'purple'}
                    />
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Nationalities */}
          <section className="bg-card rounded-xl border p-4 sm:p-6">
            <h2 className="text-base sm:text-lg font-semibold mb-4 flex items-center gap-2">
              <Globe className="w-4 h-4 sm:w-5 sm:h-5" />
              Top Nationalities
            </h2>
            {isLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="w-8 h-8 animate-spin" />
              </div>
            ) : nationalityData.length > 0 ? (
              <div className="space-y-3">
                {nationalityData.map((item, idx) => (
                  <ProgressBar
                    key={idx}
                    value={item.count}
                    max={nationalityData[0]?.count || 1}
                    label={item.nationality}
                    color={['blue', 'green', 'amber', 'purple', 'cyan'][idx % 5]}
                  />
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-center py-8 text-sm">No data available</p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
