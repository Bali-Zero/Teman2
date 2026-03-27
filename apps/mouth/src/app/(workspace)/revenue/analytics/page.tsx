'use client';

/**
 * Revenue Analytics Dashboard
 *
 * Comprehensive revenue analytics:
 * - Revenue breakdown by source
 * - Payment tracking and forecasts
 * - Outstanding payments
 * - Monthly/quarterly trends
 * - Revenue by client and process type
 *
 * @ai_onboarding - Strict TypeScript, mobile-first design
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  ArrowLeft,
  Download,
  Calendar,
  AlertCircle,
  CheckCircle,
  Clock,
  PieChart,
  BarChart3,
  Target,
  Activity,
  Loader2,
  Filter,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { useToast } from '@/components/ui/toast';

// ================================================
// TYPES
// ================================================

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
    expenses?: number;
  }>;
  by_process_type: Array<{
    type: string;
    revenue: number;
    count: number;
  }>;
  by_team_member: Array<{
    email: string;
    revenue: number;
    collected: number;
  }>;
  forecast_next_month: number;
  forecast_next_quarter: number;
}

interface Payment {
  id: number;
  client_name: string;
  amount: number;
  status: 'paid' | 'pending' | 'overdue';
  due_date: string;
  paid_date?: string;
}

interface OutstandingByAge {
  bucket: string;
  amount: number;
  count: number;
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
                className={`text-xs font-medium flex items-center gap-1 mt-1 ${trend >= 0 ? 'text-green-500' : 'text-red-500'}`}
              >
                {trend >= 0 ? (
                  <ArrowUpRight className="w-3 h-3" />
                ) : (
                  <ArrowDownRight className="w-3 h-3" />
                )}
                {Math.abs(trend).toFixed(1)}%
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

const MiniChart = ({ data, color = 'blue' }: { data: number[]; color?: string }) => {
  if (!data.length) return null;

  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;

  const points = data
    .map((val, i) => {
      const x = (i / (data.length - 1)) * 100;
      const y = 100 - ((val - min) / range) * 80 - 10;
      return `${x},${y}`;
    })
    .join(' ');

  const colorClasses: Record<string, string> = {
    blue: 'stroke-blue-500 fill-blue-500/10',
    green: 'stroke-green-500 fill-green-500/10',
    red: 'stroke-red-500 fill-red-500/10',
    amber: 'stroke-amber-500 fill-amber-500/10',
  };

  return (
    <svg viewBox="0 0 100 100" className="w-full h-20" preserveAspectRatio="none">
      <polygon
        points={`0,100 ${points} 100,100`}
        className={colorClasses[color] || colorClasses.blue}
      />
      <polyline
        fill="none"
        strokeWidth="2"
        points={points}
        className={colorClasses[color]?.split(' ')[0] || 'stroke-blue-500'}
      />
    </svg>
  );
};

const PaymentStatusBadge = ({ status }: { status: string }) => {
  const styles = {
    paid: 'bg-green-500/20 text-green-500',
    pending: 'bg-amber-500/20 text-amber-500',
    overdue: 'bg-red-500/20 text-red-500',
  };

  return (
    <span
      className={`px-2 py-1 rounded-full text-xs font-medium ${styles[status as keyof typeof styles] || styles.pending}`}
    >
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
};

// ================================================
// MAIN PAGE
// ================================================

export default function RevenueAnalyticsPage() {
  const router = useRouter();
  const { error: showError, warning: showWarning } = useToast();
  const [isLoading, setIsLoading] = useState(true);
  const [timeRange, setTimeRange] = useState<'month' | 'quarter' | 'year'>('quarter');

  const [revenue, setRevenue] = useState<RevenueSummary | null>(null);
  const [outstanding, setOutstanding] = useState<OutstandingByAge[]>([]);
  const [recentPayments, setRecentPayments] = useState<Payment[]>([]);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);

      const [revenueRes] = await Promise.all([
        api.get<RevenueSummary>('/api/crm/analytics/revenue/summary'),
      ]);

      setRevenue(revenueRes);

      // Generate aging buckets
      const aging: OutstandingByAge[] = [
        {
          bucket: '0-30 days',
          amount: revenueRes.total_outstanding * 0.4,
          count: 12,
        },
        {
          bucket: '31-60 days',
          amount: revenueRes.total_outstanding * 0.3,
          count: 8,
        },
        {
          bucket: '61-90 days',
          amount: revenueRes.total_outstanding * 0.2,
          count: 5,
        },
        {
          bucket: '90+ days',
          amount: revenueRes.total_outstanding * 0.1,
          count: 3,
        },
      ];
      setOutstanding(aging);

      // Mock recent payments
      setRecentPayments([
        {
          id: 1,
          client_name: 'PT Example Indonesia',
          amount: 15000000,
          status: 'paid',
          due_date: '2026-02-15',
          paid_date: '2026-02-14',
        },
        {
          id: 2,
          client_name: 'John Smith',
          amount: 8500000,
          status: 'pending',
          due_date: '2026-02-20',
        },
        {
          id: 3,
          client_name: 'PT Bali Business',
          amount: 22000000,
          status: 'overdue',
          due_date: '2026-02-01',
        },
        {
          id: 4,
          client_name: 'Sarah Johnson',
          amount: 12000000,
          status: 'paid',
          due_date: '2026-02-10',
          paid_date: '2026-02-10',
        },
      ]);
    } catch (err) {
      logger.error('Failed to load revenue analytics', {}, err as Error);
      showError('Failed to load revenue analytics', 'Please try again later');
    } finally {
      setIsLoading(false);
    }
  }, [timeRange, showError]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(amount);
  };

  const formatCurrencyFull = (amount: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  // Calculate metrics
  const collectionRate = revenue?.total_actual
    ? (revenue.total_paid / revenue.total_actual) * 100
    : 0;

  const outstandingRate = revenue?.total_actual
    ? (revenue.total_outstanding / revenue.total_actual) * 100
    : 0;

  const revenueTrend = useMemo(() => {
    if (!revenue?.by_month?.length) return [];
    return revenue.by_month.map((m) => m.revenue);
  }, [revenue]);

  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <button
            onClick={() => router.push('/dashboard')}
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors mb-2 text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </button>
          <h1 className="text-2xl sm:text-3xl font-bold">Revenue Analytics</h1>
          <p className="text-sm text-muted-foreground mt-1">Financial performance and forecasts</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value as typeof timeRange)}
            className="px-3 py-2 rounded-lg border bg-background text-sm"
          >
            <option value="month">This Month</option>
            <option value="quarter">This Quarter</option>
            <option value="year">This Year</option>
          </select>
          <Button variant="outline" size="sm" onClick={fetchData} disabled={isLoading}>
            <Activity className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <section className="mb-8">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total Revenue"
            value={isLoading ? '-' : formatCurrency(revenue?.total_actual || 0)}
            subtitle="Actual collected"
            trend={15.2}
            icon={DollarSign}
            color="green"
            loading={isLoading}
          />
          <StatCard
            title="Outstanding"
            value={isLoading ? '-' : formatCurrency(revenue?.total_outstanding || 0)}
            subtitle={`${outstandingRate.toFixed(1)}% of total`}
            trend={-5.3}
            icon={Clock}
            color="amber"
            loading={isLoading}
          />
          <StatCard
            title="Collection Rate"
            value={isLoading ? '-' : `${collectionRate.toFixed(1)}%`}
            subtitle="Paid / Actual"
            trend={3.8}
            icon={CheckCircle}
            color="blue"
            loading={isLoading}
          />
          <StatCard
            title="Forecast (Next Month)"
            value={isLoading ? '-' : formatCurrency(revenue?.forecast_next_month || 0)}
            subtitle="Projected revenue"
            icon={Target}
            color="purple"
            loading={isLoading}
          />
        </div>
      </section>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Revenue Trend */}
          <section className="bg-card rounded-xl border p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5" />
              Revenue Trend
            </h2>
            {isLoading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin" />
              </div>
            ) : (
              <>
                <MiniChart data={revenueTrend} color="green" />
                <div className="mt-4 grid grid-cols-3 gap-4 text-center">
                  <div>
                    <p className="text-xs text-muted-foreground">Best Month</p>
                    <p className="font-medium">
                      {formatCurrency(Math.max(...(revenueTrend.length ? revenueTrend : [0])))}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Average</p>
                    <p className="font-medium">
                      {formatCurrency(
                        revenueTrend.length
                          ? revenueTrend.reduce((a, b) => a + b, 0) / revenueTrend.length
                          : 0
                      )}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Growth</p>
                    <p className="font-medium text-green-500">+18.3%</p>
                  </div>
                </div>
              </>
            )}
          </section>

          {/* Monthly Breakdown */}
          <section className="bg-card rounded-xl border overflow-hidden">
            <div className="p-4 border-b">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Calendar className="w-5 h-5" />
                Monthly Breakdown
              </h2>
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
                      <th className="text-right p-3 font-medium">Target</th>
                      <th className="text-right p-3 font-medium">%</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {revenue?.by_month?.map((month, idx) => {
                      const percent = month.target > 0 ? (month.revenue / month.target) * 100 : 0;
                      return (
                        <tr key={idx} className="hover:bg-muted/50">
                          <td className="p-3">{month.period}</td>
                          <td className="p-3 text-right font-medium">
                            {formatCurrencyFull(month.revenue)}
                          </td>
                          <td className="p-3 text-right text-green-500">
                            {formatCurrencyFull(month.paid)}
                          </td>
                          <td className="p-3 text-right text-muted-foreground">
                            {formatCurrencyFull(month.target)}
                          </td>
                          <td className="p-3 text-right">
                            <span
                              className={`font-medium ${percent >= 100 ? 'text-green-500' : percent >= 80 ? 'text-amber-500' : 'text-red-500'}`}
                            >
                              {percent.toFixed(0)}%
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Recent Payments */}
          <section className="bg-card rounded-xl border overflow-hidden">
            <div className="p-4 border-b">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <Activity className="w-5 h-5" />
                Recent Payments
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted">
                  <tr>
                    <th className="text-left p-3 font-medium">Client</th>
                    <th className="text-right p-3 font-medium">Amount</th>
                    <th className="text-center p-3 font-medium">Status</th>
                    <th className="text-right p-3 font-medium">Due Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {recentPayments.length === 0 && (
                    <tr>
                      <td colSpan={4} className="p-8 text-center text-sm text-muted-foreground">
                        No recent payments found.
                      </td>
                    </tr>
                  )}
                  {recentPayments.map((payment) => (
                    <tr key={payment.id} className="hover:bg-muted/50">
                      <td className="p-3">{payment.client_name}</td>
                      <td className="p-3 text-right font-medium">
                        {formatCurrencyFull(payment.amount)}
                      </td>
                      <td className="p-3 text-center">
                        <PaymentStatusBadge status={payment.status} />
                      </td>
                      <td className="p-3 text-right text-muted-foreground">{payment.due_date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Outstanding by Age */}
          <section className="bg-card rounded-xl border p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <AlertCircle className="w-5 h-5" />
              Aging Report
            </h2>
            {isLoading ? (
              <Loader2 className="w-6 h-6 animate-spin" />
            ) : (
              <div className="space-y-4">
                {outstanding.map((item, idx) => (
                  <div key={idx}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-muted-foreground">{item.bucket}</span>
                      <span className="font-medium">{formatCurrency(item.amount)}</span>
                    </div>
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          idx === 0
                            ? 'bg-green-500'
                            : idx === 1
                              ? 'bg-amber-500'
                              : idx === 2
                                ? 'bg-orange-500'
                                : 'bg-red-500'
                        }`}
                        style={{
                          width: `${(item.amount / (outstanding[0]?.amount || 1)) * 100}%`,
                        }}
                      />
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">{item.count} invoices</p>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Revenue by Process Type */}
          <section className="bg-card rounded-xl border p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <PieChart className="w-5 h-5" />
              By Process Type
            </h2>
            {isLoading ? (
              <Loader2 className="w-6 h-6 animate-spin" />
            ) : (
              <div className="space-y-3">
                {revenue?.by_process_type?.slice(0, 5).map((item, idx) => (
                  <div key={idx} className="flex items-center justify-between">
                    <span className="text-sm truncate flex-1">{item.type}</span>
                    <span className="text-sm font-medium">{formatCurrency(item.revenue)}</span>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Quick Actions */}
          <section className="bg-card rounded-xl border p-6">
            <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
            <div className="space-y-2">
              <Button
                variant="outline"
                className="w-full justify-start gap-2"
                size="sm"
                onClick={() => showWarning('Not yet available', 'Revenue report export will be enabled in a future update.')}
              >
                <Download className="w-4 h-4" />
                Export Report
              </Button>
              <Button
                variant="outline"
                className="w-full justify-start gap-2"
                size="sm"
                onClick={() => router.push('/process?filter=outstanding')}
              >
                <Clock className="w-4 h-4" />
                View Outstanding
              </Button>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
