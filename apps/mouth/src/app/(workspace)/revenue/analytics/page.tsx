"use client";

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

import { useState, useEffect, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  DollarSign,
  TrendingUp,
  ArrowLeft,
  Download,
  Calendar,
  CheckCircle,
  Clock,
  PieChart,
  Activity,
  Loader2,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import { useToast } from "@/components/ui/toast";
import { formatIDR, formatIDRCompact } from "@balizero/core/utils";

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
}

interface ProcessByType {
  practice_type_code: string;
  practice_type_name: string;
  total_cases: number;
  active_cases: number;
  completed_cases: number;
  total_revenue: number;
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
  <div
    className={`rounded-xl border p-4 sm:p-6 bg-${color}-500/5 border-${color}-500/20`}
  >
    <div className="flex items-start justify-between">
      <div>
        <p className="text-xs sm:text-sm text-muted-foreground">{title}</p>
        {loading ? (
          <Loader2 className="w-6 h-6 animate-spin mt-2" />
        ) : (
          <>
            <p className="text-xl sm:text-2xl font-bold mt-1">{value}</p>
            {subtitle && (
              <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
            )}
            {trend !== undefined && (
              <span
                className={`text-xs font-medium flex items-center gap-1 mt-1 ${trend >= 0 ? "text-green-500" : "text-red-500"}`}
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

const MiniChart = ({
  data,
  color = "blue",
}: {
  data: number[];
  color?: string;
}) => {
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
    .join(" ");

  const colorClasses: Record<string, string> = {
    blue: "stroke-blue-500 fill-blue-500/10",
    green: "stroke-green-500 fill-green-500/10",
    red: "stroke-red-500 fill-red-500/10",
    amber: "stroke-amber-500 fill-amber-500/10",
  };

  return (
    <svg
      viewBox="0 0 100 100"
      className="w-full h-20"
      preserveAspectRatio="none"
    >
      <polygon
        points={`0,100 ${points} 100,100`}
        className={colorClasses[color] || colorClasses.blue}
      />
      <polyline
        fill="none"
        strokeWidth="2"
        points={points}
        className={colorClasses[color]?.split(" ")[0] || "stroke-blue-500"}
      />
    </svg>
  );
};

// ================================================
// MAIN PAGE
// ================================================

export default function RevenueAnalyticsPage() {
  const router = useRouter();
  const { error: showError, warning: showWarning } = useToast();
  const [isLoading, setIsLoading] = useState(true);
  const [timeRange, setTimeRange] = useState<"month" | "quarter" | "year">(
    "quarter",
  );

  const [revenue, setRevenue] = useState<RevenueSummary | null>(null);
  const [processByType, setProcessByType] = useState<ProcessByType[]>([]);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);

      const [revenueRes, processByTypeRes] = await Promise.all([
        api.get<RevenueSummary>("/api/crm/analytics/revenue/summary"),
        api.get<ProcessByType[]>("/api/crm/analytics/processes/by-type"),
      ]);

      setRevenue(revenueRes);
      setProcessByType(processByTypeRes);
    } catch (err) {
      logger.error("Failed to load revenue analytics", {}, err as Error);
      showError("Failed to load revenue analytics", "Please try again later");
    } finally {
      setIsLoading(false);
    }
  }, [timeRange, showError]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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

  const revenueGrowth = useMemo(() => {
    if (revenueTrend.length < 2) return 0;
    const first = revenueTrend[0];
    const last = revenueTrend[revenueTrend.length - 1];
    if (!first) return last > 0 ? 100 : 0;
    return ((last - first) / first) * 100;
  }, [revenueTrend]);

  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <button
            onClick={() => router.push("/dashboard")}
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors mb-2 text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Dashboard
          </button>
          <h1 className="text-2xl sm:text-3xl font-bold">Revenue Analytics</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Financial performance and forecasts
          </p>
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
          <Button
            variant="outline"
            size="sm"
            onClick={fetchData}
            disabled={isLoading}
          >
            <Activity className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <section className="mb-8">
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          <StatCard
            title="Total Revenue"
            aria-label="Total Revenue"
            value={
              isLoading ? "-" : formatIDRCompact(revenue?.total_actual || 0)
            }
            subtitle="Actual collected"
            icon={DollarSign}
            color="green"
            loading={isLoading}
          />
          <StatCard
            title="Outstanding"
            aria-label="Outstanding"
            value={
              isLoading
                ? "-"
                : formatIDRCompact(revenue?.total_outstanding || 0)
            }
            subtitle={`${outstandingRate.toFixed(1)}% of total`}
            icon={Clock}
            color="amber"
            loading={isLoading}
          />
          <StatCard
            title="Collection Rate"
            aria-label="Collection Rate"
            value={isLoading ? "-" : `${collectionRate.toFixed(1)}%`}
            subtitle="Paid / Actual"
            icon={CheckCircle}
            color="blue"
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
                      {formatIDRCompact(
                        Math.max(...(revenueTrend.length ? revenueTrend : [0])),
                      )}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Average</p>
                    <p className="font-medium">
                      {formatIDRCompact(
                        revenueTrend.length
                          ? revenueTrend.reduce((a, b) => a + b, 0) /
                              revenueTrend.length
                          : 0,
                      )}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Growth</p>
                    <p
                      className={`font-medium ${revenueGrowth >= 0 ? "text-green-500" : "text-red-500"}`}
                    >
                      {revenueTrend.length >= 2
                        ? `${revenueGrowth >= 0 ? "+" : ""}${revenueGrowth.toFixed(1)}%`
                        : "-"}
                    </p>
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
                      const percent =
                        month.target > 0
                          ? (month.revenue / month.target) * 100
                          : 0;
                      return (
                        <tr key={idx} className="hover:bg-muted/50">
                          <td className="p-3">{month.period}</td>
                          <td className="p-3 text-right font-medium">
                            {formatIDR(month.revenue)}
                          </td>
                          <td className="p-3 text-right text-green-500">
                            {formatIDR(month.paid)}
                          </td>
                          <td className="p-3 text-right text-muted-foreground">
                            {formatIDR(month.target)}
                          </td>
                          <td className="p-3 text-right">
                            <span
                              className={`font-medium ${percent >= 100 ? "text-green-500" : percent >= 80 ? "text-amber-500" : "text-red-500"}`}
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
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Revenue by Process Type */}
          <section className="bg-card rounded-xl border p-6">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <PieChart className="w-5 h-5" />
              By Process Type
            </h2>
            {isLoading ? (
              <Loader2 className="w-6 h-6 animate-spin" />
            ) : processByType.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                No process type data available.
              </p>
            ) : (
              <div className="space-y-3">
                {processByType.slice(0, 5).map((item) => (
                  <div
                    key={item.practice_type_code}
                    className="flex items-center justify-between"
                  >
                    <span className="text-sm truncate flex-1">
                      {item.practice_type_name}
                    </span>
                    <span className="text-sm font-medium">
                      {formatIDRCompact(item.total_revenue)}
                    </span>
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
                onClick={() =>
                  showWarning(
                    "Not yet available",
                    "Revenue report export will be enabled in a future update.",
                  )
                }
              >
                <Download className="w-4 h-4" />
                Export Report
              </Button>
              <Button
                variant="outline"
                className="w-full justify-start gap-2"
                size="sm"
                onClick={() => router.push("/process?filter=outstanding")}
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
