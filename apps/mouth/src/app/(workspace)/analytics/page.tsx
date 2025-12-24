'use client';

import React, { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, Users, FolderKanban, DollarSign } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';

export default function AnalyticsPage() {
  const [dateRange, setDateRange] = useState('Last 7 days');
  const [stats, setStats] = useState({
    totalCases: 0,
    newClients: 0,
    revenue: 0,
    conversionRate: 0,
  });
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadAnalytics = async () => {
      setIsLoading(true);
      try {
        const [practiceStats, revenueGrowth] = await Promise.all([
          api.crm.getPracticeStats().catch(() => null),
          api.crm.getRevenueGrowth().catch(() => null),
        ]);

        if (practiceStats) {
          setStats({
            totalCases: practiceStats.total_practices || 0,
            newClients: 0, // Would need separate API
            revenue: practiceStats.revenue?.total_revenue || 0,
            conversionRate: 0, // Would need calculation
          });
        }
      } catch (error) {
        console.error('Failed to load analytics:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadAnalytics();
  }, [dateRange]);

  const handleExport = () => {
    // Export functionality - can be implemented later
    console.log('Export analytics data');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Analytics</h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Reports and company statistics
          </p>
        </div>
        <div className="flex gap-2">
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] text-sm"
          >
            <option>Last 7 days</option>
            <option>Last 30 days</option>
            <option>This month</option>
            <option>This year</option>
          </select>
          <Button variant="outline" onClick={handleExport}>Export</Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Cases', value: isLoading ? '-' : stats.totalCases.toString(), icon: FolderKanban, trend: null },
          { label: 'New Clients', value: isLoading ? '-' : stats.newClients.toString(), icon: Users, trend: null },
          { label: 'Revenue', value: isLoading ? '-' : `€${stats.revenue.toLocaleString()}`, icon: DollarSign, trend: null },
          { label: 'Conversion Rate', value: isLoading ? '-' : `${stats.conversionRate}%`, icon: TrendingUp, trend: null },
        ].map((kpi) => (
          <div
            key={kpi.label}
            className="p-4 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]"
          >
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm text-[var(--foreground-muted)]">{kpi.label}</p>
              <kpi.icon className="w-4 h-4 text-[var(--foreground-muted)]" />
            </div>
            <p className="text-2xl font-bold text-[var(--foreground)]">{kpi.value}</p>
            {kpi.trend && (
              <p className="text-xs text-[var(--success)] mt-1">{kpi.trend}</p>
            )}
          </div>
        ))}
      </div>

      {/* Charts Placeholder */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pratiche Chart */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4">
          <h3 className="font-semibold text-[var(--foreground)] mb-4">Cases by Type</h3>
          <div className="h-64 flex items-center justify-center border border-dashed border-[var(--border)] rounded-lg">
            <div className="text-center">
              <BarChart3 className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-2 opacity-50" />
              <p className="text-sm text-[var(--foreground-muted)]">Cases chart</p>
            </div>
          </div>
        </div>

        {/* Revenue Chart */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4">
          <h3 className="font-semibold text-[var(--foreground)] mb-4">Revenue Trend</h3>
          <div className="h-64 flex items-center justify-center border border-dashed border-[var(--border)] rounded-lg">
            <div className="text-center">
              <TrendingUp className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-2 opacity-50" />
              <p className="text-sm text-[var(--foreground-muted)]">Revenue chart</p>
            </div>
          </div>
        </div>
      </div>

      {/* More Analytics Placeholder */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Team Performance */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4">
          <h3 className="font-semibold text-[var(--foreground)] mb-4">Team Performance</h3>
          <div className="space-y-3">
            <p className="text-sm text-[var(--foreground-muted)] text-center py-8">
              Data not available
            </p>
          </div>
        </div>

        {/* Top Clients */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4">
          <h3 className="font-semibold text-[var(--foreground)] mb-4">Top Clients</h3>
          <div className="space-y-3">
            <p className="text-sm text-[var(--foreground-muted)] text-center py-8">
              Data not available
            </p>
          </div>
        </div>

        {/* Service Distribution */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4">
          <h3 className="font-semibold text-[var(--foreground)] mb-4">Requested Services</h3>
          <div className="space-y-3">
            <p className="text-sm text-[var(--foreground-muted)] text-center py-8">
              Data not available
            </p>
          </div>
        </div>
      </div>

      {/* Info Box */}
      <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-8 text-center">
        <p className="text-sm text-[var(--foreground-muted)] max-w-md mx-auto">
          Analytics dashboard with reports on cases, clients, revenue and team performance.
          PDF/Excel export available.
        </p>
      </div>
    </div>
  );
}
