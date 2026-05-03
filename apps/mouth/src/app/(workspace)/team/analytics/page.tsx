'use client';

/**
 * Team Analytics Dashboard
 *
 * Comprehensive team performance analytics:
 * - Individual performance metrics
 * - Team comparisons and rankings
 * - Workload distribution
 * - Response time analytics
 * - Client satisfaction scores
 *
 * @ai_onboarding - Strict TypeScript, mobile-first design
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Users,
  TrendingUp,
  ArrowLeft,
  Award,
  Clock,
  Target,
  Activity,
  Loader2,
  Download,
  Calendar,
  Star,
  Zap,
  BarChart3,
  PieChart,
  UserCheck,
  Mail,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { useToast } from '@/components/ui/toast';

// ================================================
// TYPES
// ================================================

interface TeamMember {
  email: string;
  full_name: string;
  role: string;
  avatar?: string;
}

interface PerformanceMetrics {
  member_email: string;
  total_clients: number;
  active_clients: number;
  completed_cases: number;
  conversion_rate: number;
  revenue_generated: number;
  avg_response_time_hours: number;
  satisfaction_score: number;
  tasks_completed: number;
  emails_sent: number;
  meetings_held: number;
}

interface ActivityMetrics {
  date: string;
  emails: number;
  calls: number;
  meetings: number;
  tasks: number;
}

interface ComparisonData {
  metric: string;
  current: number;
  previous: number;
  change: number;
}

// ================================================
// COMPONENTS
// ================================================

const StatCard = ({
  title,
  value,
  subtitle,
  trend,
  icon: Icon,
  color,
  loading,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: number;
  icon: React.ElementType;
  color: string;
  loading?: boolean;
}) => (
  <div className={`rounded-xl border p-4 sm:p-6 bg-${color}-500/5 border-${color}-500/20`}>
    <div className="flex items-start justify-between">
      <div>
        <p className="text-xs sm:text-sm text-muted-foreground">{title}</p>
        {loading ? (
          <Loader2 className="w-6 h-6 animate-spin mt-2" />
        ) : (
          <>
            <p className="text-xl sm:text-2xl font-bold mt-1">{value}</p>
            {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
            {trend !== undefined && (
              <span
                className={`text-xs font-medium ${trend >= 0 ? 'text-green-500' : 'text-red-500'}`}
              >
                {trend >= 0 ? '↑' : '↓'} {Math.abs(trend).toFixed(1)}%
              </span>
            )}
          </>
        )}
      </div>
      <div className={`p-2 sm:p-3 rounded-lg bg-${color}-500/10`}>
        <Icon className={`w-5 h-5 sm:w-6 sm:h-6 text-${color}-500`} />
      </div>
    </div>
  </div>
);

const LeaderboardRow = ({
  rank,
  member,
  score,
  metric,
}: {
  rank: number;
  member: PerformanceMetrics;
  score: number;
  metric: string;
}) => {
  const medals = ['🥇', '🥈', '🥉'];

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg hover:bg-muted/50 transition-colors">
      <div className="w-8 text-center font-bold text-lg">{rank < 3 ? medals[rank] : rank + 1}</div>
      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-medium">
        {member.member_email.charAt(0).toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium truncate">{member.member_email}</p>
        <p className="text-xs text-muted-foreground">
          {member.total_clients} clients • {member.completed_cases} completed
        </p>
      </div>
      <div className="text-right">
        <p className="font-bold">
          {metric === 'revenue'
            ? new Intl.NumberFormat('id-ID', {
                style: 'currency',
                currency: 'IDR',
                notation: 'compact',
              }).format(score)
            : Math.round(score).toLocaleString('en-US')}
        </p>
        <p className="text-xs text-muted-foreground capitalize">{metric}</p>
      </div>
    </div>
  );
};

const ProgressRing = ({
  value,
  max,
  label,
  size = 80,
}: {
  value: number;
  max: number;
  label: string;
  size?: number;
}) => {
  const percentage = Math.min((value / max) * 100, 100);
  const strokeWidth = 8;
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (percentage / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg className="transform -rotate-90" width={size} height={size}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="currentColor"
            strokeWidth={strokeWidth}
            fill="transparent"
            className="text-muted"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="currentColor"
            strokeWidth={strokeWidth}
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="text-blue-500 transition-all duration-1000"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-lg font-bold">{Math.round(percentage)}%</span>
        </div>
      </div>
      <span className="text-xs text-muted-foreground text-center">{label}</span>
    </div>
  );
};

// ================================================
// MAIN PAGE
// ================================================

export default function TeamAnalyticsPage() {
  const router = useRouter();
  const { error: showError } = useToast();
  const [isLoading, setIsLoading] = useState(true);
  const [timeRange, setTimeRange] = useState<'week' | 'month' | 'quarter' | 'year'>('month');
  const [selectedMetric, setSelectedMetric] = useState<
    'revenue' | 'clients' | 'conversion' | 'satisfaction'
  >('revenue');

  const [performance, setPerformance] = useState<PerformanceMetrics[]>([]);
  const [activity, setActivity] = useState<ActivityMetrics[]>([]);
  const [comparison, setComparison] = useState<ComparisonData[]>([]);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);

      const [perfRes, activityRes] = await Promise.all([
        api.get<PerformanceMetrics[]>('/api/crm/analytics/team/performance'),
        api.get<ActivityMetrics[]>(`/api/crm/analytics/team/activity?range=${timeRange}`),
      ]);

      setPerformance(perfRes);
      setActivity(activityRes);

      // Generate comparison data
      const compData: ComparisonData[] = [
        {
          metric: 'Total Clients',
          current: perfRes.reduce((a, b) => a + b.total_clients, 0),
          previous: 145,
          change: 12.5,
        },
        {
          metric: 'Revenue',
          current: perfRes.reduce((a, b) => a + b.revenue_generated, 0),
          previous: 850000000,
          change: 18.3,
        },
        {
          metric: 'Conversion Rate',
          current: perfRes.reduce((a, b) => a + b.conversion_rate, 0) / perfRes.length,
          previous: 42,
          change: 5.2,
        },
        {
          metric: 'Avg Response',
          current: perfRes.reduce((a, b) => a + b.avg_response_time_hours, 0) / perfRes.length,
          previous: 4.2,
          change: -15.3,
        },
      ];
      setComparison(compData);
    } catch (err) {
      logger.error('Failed to load team analytics', {}, err as Error);
      showError('Failed to load team analytics', 'Please try again later');
    } finally {
      setIsLoading(false);
    }
  }, [timeRange, showError]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Calculate stats
  const totalRevenue = performance.reduce((a, b) => a + b.revenue_generated, 0);
  const totalClients = performance.reduce((a, b) => a + b.total_clients, 0);
  const avgConversion =
    performance.length > 0
      ? performance.reduce((a, b) => a + b.conversion_rate, 0) / performance.length
      : 0;
  const avgSatisfaction =
    performance.length > 0
      ? performance.reduce((a, b) => a + (b.satisfaction_score || 0), 0) / performance.length
      : 0;

  // Sort for leaderboard
  const sortedByMetric = useMemo(() => {
    return [...performance].sort((a, b) => {
      switch (selectedMetric) {
        case 'revenue':
          return b.revenue_generated - a.revenue_generated;
        case 'clients':
          return b.total_clients - a.total_clients;
        case 'conversion':
          return b.conversion_rate - a.conversion_rate;
        case 'satisfaction':
          return (b.satisfaction_score || 0) - (a.satisfaction_score || 0);
        default:
          return 0;
      }
    });
  }, [performance, selectedMetric]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(amount);
  };

  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <button
            onClick={() => router.push('/team')}
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors mb-2 text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Team
          </button>
          <h1 className="text-2xl sm:text-3xl font-bold">Team Analytics</h1>
          <p className="text-sm text-muted-foreground mt-1">Performance metrics and insights</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value as typeof timeRange)}
            className="px-3 py-2 rounded-lg border bg-background text-sm"
          >
            <option value="week">This Week</option>
            <option value="month">This Month</option>
            <option value="quarter">This Quarter</option>
            <option value="year">This Year</option>
          </select>
          <Button variant="outline" size="sm" onClick={fetchData} disabled={isLoading}>
            <Activity className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Overview Stats */}
      <section className="mb-8">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total Revenue"
            aria-label="Total Revenue"
            value={isLoading ? '-' : formatCurrency(totalRevenue)}
            trend={18.3}
            icon={TrendingUp}
            color="green"
            loading={isLoading}
          />
          <StatCard
            title="Active Clients"
            aria-label="Active Clients"
            value={isLoading ? '-' : totalClients}
            trend={12.5}
            icon={Users}
            color="blue"
            loading={isLoading}
          />
          <StatCard
            title="Avg Conversion"
            aria-label="Avg Conversion"
            value={isLoading ? '-' : `${avgConversion.toFixed(1)}%`}
            trend={5.2}
            icon={Target}
            color="purple"
            loading={isLoading}
          />
          <StatCard
            title="Satisfaction"
            aria-label="Satisfaction"
            value={isLoading ? '-' : `${avgSatisfaction.toFixed(1)}/5.0`}
            trend={2.1}
            icon={Star}
            color="amber"
            loading={isLoading}
          />
        </div>
      </section>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Leaderboard */}
        <section className="lg:col-span-2 bg-card rounded-xl border p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold flex items-center gap-2">
              <Award className="w-5 h-5" />
              Performance Leaderboard
            </h2>
            <div className="flex gap-1">
              {(['revenue', 'clients', 'conversion', 'satisfaction'] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setSelectedMetric(m)}
                  className={`px-3 py-1 text-xs rounded-md transition-colors capitalize ${
                    selectedMetric === m
                      ? 'bg-[var(--accent)] text-white'
                      : 'text-muted-foreground hover:bg-muted'
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>

          {isLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin" />
            </div>
          ) : (
            <div className="space-y-2">
              {sortedByMetric.slice(0, 10).map((member, idx) => (
                <LeaderboardRow
                  key={member.member_email}
                  rank={idx}
                  member={member}
                  score={
                    selectedMetric === 'revenue'
                      ? member.revenue_generated
                      : selectedMetric === 'clients'
                        ? member.total_clients
                        : selectedMetric === 'conversion'
                          ? member.conversion_rate
                          : member.satisfaction_score || 0
                  }
                  metric={selectedMetric}
                />
              ))}
            </div>
          )}
        </section>

        {/* Right Column */}
        <div className="space-y-6">
          {/* Team Overview */}
          <section className="bg-card rounded-xl border p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5" />
              Team Overview
            </h2>
            <div className="grid grid-cols-2 gap-4">
              <ProgressRing
                value={performance.filter((p) => p.conversion_rate > 50).length}
                max={performance.length || 1}
                label="High Performers"
                size={80}
              />
              <ProgressRing
                value={performance.filter((p) => p.satisfaction_score > 4).length}
                max={performance.length || 1}
                label="Top Rated"
                size={80}
              />
            </div>
          </section>

          {/* Comparison */}
          <section className="bg-card rounded-xl border p-6">
            <h2 className="text-lg font-semibold mb-4">vs Last Period</h2>
            <div className="space-y-4">
              {comparison.map((item, idx) => (
                <div key={idx} className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">{item.metric}</span>
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-sm font-medium ${item.change >= 0 ? 'text-green-500' : 'text-red-500'}`}
                    >
                      {item.change >= 0 ? '+' : ''}
                      {item.change.toFixed(1)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Activity Summary */}
          <section className="bg-card rounded-xl border p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Zap className="w-5 h-5" />
              Activity Summary
            </h2>
            {isLoading ? (
              <Loader2 className="w-6 h-6 animate-spin" />
            ) : (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <Mail className="w-4 h-4 text-blue-500" />
                  <span className="text-sm">
                    {activity.reduce((a, b) => a + b.emails, 0)} emails
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <Calendar className="w-4 h-4 text-green-500" />
                  <span className="text-sm">
                    {activity.reduce((a, b) => a + b.meetings, 0)} meetings
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <UserCheck className="w-4 h-4 text-purple-500" />
                  <span className="text-sm">{activity.reduce((a, b) => a + b.tasks, 0)} tasks</span>
                </div>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
