"use client";

import { useEffect, useState } from "react";
import { intelligenceApi, IntelligenceAnalytics } from "@/lib/api/intelligence.api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import {
  Loader2,
  TrendingUp,
  TrendingDown,
  BarChart3,
  RefreshCw,
  CheckCircle,
  XCircle,
  FileText,
  Calendar,
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function IntelligenceAnalyticsPage() {
  const [analytics, setAnalytics] = useState<IntelligenceAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [periodDays, setPeriodDays] = useState(30);
  const toast = useToast();

  useEffect(() => {
    logger.componentMount('IntelligenceAnalyticsPage');
    loadAnalytics();

    return () => {
      logger.componentUnmount('IntelligenceAnalyticsPage');
    };
  }, [periodDays]);

  const loadAnalytics = async () => {
    logger.info('Loading analytics', {
      component: 'IntelligenceAnalyticsPage',
      action: 'load_analytics',
      metadata: { days: periodDays },
    });
    setLoading(true);

    try {
      const data = await intelligenceApi.getAnalytics(periodDays);
      setAnalytics(data);

      logger.info('Analytics loaded successfully', {
        component: 'IntelligenceAnalyticsPage',
        action: 'load_analytics_success',
        metadata: {
          total_processed: data.summary.total_processed,
          approval_rate: data.summary.approval_rate,
        },
      });
    } catch (error) {
      logger.error('Failed to load analytics', {
        component: 'IntelligenceAnalyticsPage',
        action: 'load_analytics_error',
      }, error as Error);

      toast.error("Failed to load analytics", "Could not fetch analytics data. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col justify-center items-center h-96 space-y-4">
        <Loader2 className="h-12 w-12 animate-spin text-[var(--accent)]" />
        <p className="text-[var(--foreground-muted)] animate-pulse text-lg">
          Loading Analytics...
        </p>
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="flex flex-col justify-center items-center h-96 space-y-4">
        <BarChart3 className="h-12 w-12 text-red-500" />
        <p className="text-[var(--foreground-muted)] text-lg">
          Analytics Unavailable
        </p>
        <Button onClick={loadAnalytics} variant="secondary">
          Retry
        </Button>
      </div>
    );
  }

  const maxDailyValue = Math.max(
    ...analytics.daily_trends.map((d) => Math.max(d.processed, d.approved, d.rejected, d.published)),
    1
  );

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex justify-between items-end border-b border-[var(--border)] pb-6">
        <div className="space-y-1">
          <h2 className="text-3xl font-bold tracking-tight text-[var(--foreground)]">
            Intelligence Analytics
          </h2>
          <p className="text-[var(--foreground-muted)] text-lg">
            Historical trends and performance metrics
          </p>
        </div>
        <div className="flex gap-2">
          <Select value={periodDays.toString()} onValueChange={(value) => setPeriodDays(parseInt(value))}>
            <SelectTrigger className="w-[140px]">
              <Calendar className="w-4 h-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">Last 7 days</SelectItem>
              <SelectItem value="30">Last 30 days</SelectItem>
              <SelectItem value="90">Last 90 days</SelectItem>
              <SelectItem value="180">Last 180 days</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={loadAnalytics} variant="secondary" size="sm" className="gap-2">
            <RefreshCw className="h-4 w-4" /> Refresh
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card className="border-t-4 border-t-blue-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Total Processed
            </CardTitle>
            <FileText className="h-5 w-5 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-[var(--foreground)]">
              {analytics.summary.total_processed}
            </div>
            <p className="mt-3 text-xs text-[var(--foreground-muted)]">
              Items reviewed in {periodDays} days
            </p>
          </CardContent>
        </Card>

        <Card className="border-t-4 border-t-green-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Approval Rate
            </CardTitle>
            <CheckCircle className="h-5 w-5 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {analytics.summary.approval_rate}%
            </div>
            <p className="mt-3 text-xs text-[var(--foreground-muted)]">
              {analytics.summary.total_approved} approved
            </p>
          </CardContent>
        </Card>

        <Card className="border-t-4 border-t-red-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Rejection Rate
            </CardTitle>
            <XCircle className="h-5 w-5 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {analytics.summary.rejection_rate}%
            </div>
            <p className="mt-3 text-xs text-[var(--foreground-muted)]">
              {analytics.summary.total_rejected} rejected
            </p>
          </CardContent>
        </Card>

        <Card className="border-t-4 border-t-purple-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Published
            </CardTitle>
            <TrendingUp className="h-5 w-5 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">
              {analytics.summary.total_published}
            </div>
            <p className="mt-3 text-xs text-[var(--foreground-muted)]">
              News articles published
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Daily Trends Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-xl font-bold text-[var(--foreground)]">
            Daily Trends
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {analytics.daily_trends.map((day, index) => {
              const processedHeight = (day.processed / maxDailyValue) * 100;
              const approvedHeight = (day.approved / maxDailyValue) * 100;
              const rejectedHeight = (day.rejected / maxDailyValue) * 100;

              return (
                <div key={day.date} className="flex items-end gap-2">
                  <div className="w-20 text-xs text-[var(--foreground-muted)] text-right">
                    {new Date(day.date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                  </div>
                  <div className="flex-1 flex items-end gap-1 h-32">
                    {day.processed > 0 && (
                      <div
                        className="flex-1 bg-blue-500 rounded-t transition-all"
                        style={{ height: `${processedHeight}%` }}
                        title={`Processed: ${day.processed}`}
                      />
                    )}
                    {day.approved > 0 && (
                      <div
                        className="flex-1 bg-green-500 rounded-t transition-all"
                        style={{ height: `${approvedHeight}%` }}
                        title={`Approved: ${day.approved}`}
                      />
                    )}
                    {day.rejected > 0 && (
                      <div
                        className="flex-1 bg-red-500 rounded-t transition-all"
                        style={{ height: `${rejectedHeight}%` }}
                        title={`Rejected: ${day.rejected}`}
                      />
                    )}
                    {day.published > 0 && (
                      <div
                        className="flex-1 bg-purple-500 rounded-t transition-all"
                        style={{ height: `${(day.published / maxDailyValue) * 100}%` }}
                        title={`Published: ${day.published}`}
                      />
                    )}
                  </div>
                  <div className="w-24 text-xs text-[var(--foreground-muted)]">
                    {day.processed} processed
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex gap-4 mt-6 pt-4 border-t border-[var(--border)]">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-blue-500 rounded" />
              <span className="text-xs text-[var(--foreground-muted)]">Processed</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-green-500 rounded" />
              <span className="text-xs text-[var(--foreground-muted)]">Approved</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-red-500 rounded" />
              <span className="text-xs text-[var(--foreground-muted)]">Rejected</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-purple-500 rounded" />
              <span className="text-xs text-[var(--foreground-muted)]">Published</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Type Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg font-bold text-[var(--foreground)]">
              Visa Oracle Breakdown
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-[var(--foreground-muted)]">Processed</span>
                <span className="text-lg font-semibold">{analytics.type_breakdown.visa.processed}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-[var(--foreground-muted)]">Approved</span>
                <span className="text-lg font-semibold text-green-600">
                  {analytics.type_breakdown.visa.approved}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-[var(--foreground-muted)]">Rejected</span>
                <span className="text-lg font-semibold text-red-600">
                  {analytics.type_breakdown.visa.rejected}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg font-bold text-[var(--foreground)]">
              News Room Breakdown
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-[var(--foreground-muted)]">Processed</span>
                <span className="text-lg font-semibold">{analytics.type_breakdown.news.processed}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-[var(--foreground-muted)]">Approved</span>
                <span className="text-lg font-semibold text-green-600">
                  {analytics.type_breakdown.news.approved}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-[var(--foreground-muted)]">Rejected</span>
                <span className="text-lg font-semibold text-red-600">
                  {analytics.type_breakdown.news.rejected}
                </span>
              </div>
              <div className="flex justify-between items-center pt-2 border-t border-[var(--border)]">
                <span className="text-sm text-[var(--foreground-muted)]">Published</span>
                <span className="text-lg font-semibold text-purple-600">
                  {analytics.type_breakdown.news.published}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
