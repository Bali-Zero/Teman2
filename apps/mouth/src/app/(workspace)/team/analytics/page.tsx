"use client";

/**
 * Team Analytics Dashboard
 *
 * Individual + comparative team performance, sourced from the live CRM
 * analytics endpoint. Every metric shown maps to a field the backend
 * actually returns (GET /api/crm/analytics/team/performance):
 *   member_email, total_clients, active_clients, completed_cases,
 *   conversion_rate, revenue_generated.
 *
 * There is deliberately NO satisfaction / response-time / activity-feed
 * widget here: no backend endpoint produces that data today. Adding a
 * placeholder would surface fabricated numbers to a business-decision
 * surface (WAVE 1.5 data-integrity). When such an endpoint ships, wire
 * it here — do not synthesize.
 *
 * @ai_onboarding - Strict TypeScript, mobile-first design
 */

import { useState, useEffect, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Users,
  TrendingUp,
  ArrowLeft,
  Award,
  Target,
  Activity,
  Loader2,
  BarChart3,
  CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import { useToast } from "@/components/ui/toast";
import { formatIDRCompact } from "@balizero/core/utils";

// ================================================
// TYPES
// ================================================

// Mirrors backend crm_analytics.py get_team_performance() response exactly.
interface PerformanceMetrics {
  member_email: string;
  total_clients: number;
  active_clients: number;
  completed_cases: number;
  conversion_rate: number;
  revenue_generated: number;
}

type LeaderboardMetric = "revenue" | "clients" | "conversion" | "completed";

// ================================================
// COMPONENTS
// ================================================

const StatCard = ({
  title,
  value,
  subtitle,
  icon: Icon,
  color,
  loading,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
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
  metric: LeaderboardMetric;
}) => {
  const medals = ["🥇", "🥈", "🥉"];

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg hover:bg-muted/50 transition-colors">
      <div className="w-8 text-center font-bold text-lg">
        {rank < 3 ? medals[rank] : rank + 1}
      </div>
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
          {metric === "revenue"
            ? formatIDRCompact(score)
            : metric === "conversion"
              ? `${score.toFixed(1)}%`
              : Math.round(score).toLocaleString("en-US")}
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
  const [selectedMetric, setSelectedMetric] =
    useState<LeaderboardMetric>("revenue");

  const [performance, setPerformance] = useState<PerformanceMetrics[]>([]);

  const fetchData = useCallback(async () => {
    try {
      setIsLoading(true);
      const perfRes = await api.get<PerformanceMetrics[]>(
        "/api/crm/analytics/team/performance",
      );
      setPerformance(perfRes);
    } catch (err) {
      logger.error("Failed to load team analytics", {}, err as Error);
      showError("Failed to load team analytics", "Please try again later");
    } finally {
      setIsLoading(false);
    }
  }, [showError]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Aggregate stats — all from real fields
  const totalRevenue = performance.reduce((a, b) => a + b.revenue_generated, 0);
  const totalClients = performance.reduce((a, b) => a + b.total_clients, 0);
  const totalCompleted = performance.reduce(
    (a, b) => a + b.completed_cases,
    0,
  );
  const avgConversion =
    performance.length > 0
      ? performance.reduce((a, b) => a + b.conversion_rate, 0) /
        performance.length
      : 0;

  // Sort for leaderboard
  const sortedByMetric = useMemo(() => {
    return [...performance].sort((a, b) => {
      switch (selectedMetric) {
        case "revenue":
          return b.revenue_generated - a.revenue_generated;
        case "clients":
          return b.total_clients - a.total_clients;
        case "conversion":
          return b.conversion_rate - a.conversion_rate;
        case "completed":
          return b.completed_cases - a.completed_cases;
        default:
          return 0;
      }
    });
  }, [performance, selectedMetric]);

  const scoreFor = (member: PerformanceMetrics): number => {
    switch (selectedMetric) {
      case "revenue":
        return member.revenue_generated;
      case "clients":
        return member.total_clients;
      case "conversion":
        return member.conversion_rate;
      case "completed":
        return member.completed_cases;
    }
  };

  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <button
            onClick={() => router.push("/team")}
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors mb-2 text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Team
          </button>
          <h1 className="text-2xl sm:text-3xl font-bold">Team Analytics</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Performance metrics and insights
          </p>
        </div>
        <div className="flex items-center gap-2">
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

      {/* Overview Stats */}
      <section className="mb-8">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total Revenue"
            value={isLoading ? "-" : formatIDRCompact(totalRevenue)}
            icon={TrendingUp}
            color="green"
            loading={isLoading}
          />
          <StatCard
            title="Total Clients"
            value={isLoading ? "-" : totalClients}
            icon={Users}
            color="blue"
            loading={isLoading}
          />
          <StatCard
            title="Avg Conversion"
            value={isLoading ? "-" : `${avgConversion.toFixed(1)}%`}
            icon={Target}
            color="purple"
            loading={isLoading}
          />
          <StatCard
            title="Completed Cases"
            value={isLoading ? "-" : totalCompleted}
            icon={CheckCircle2}
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
              {(
                ["revenue", "clients", "conversion", "completed"] as const
              ).map((m) => (
                <button
                  key={m}
                  onClick={() => setSelectedMetric(m)}
                  className={`px-3 py-1 text-xs rounded-md transition-colors capitalize ${
                    selectedMetric === m
                      ? "bg-[var(--accent)] text-white"
                      : "text-muted-foreground hover:bg-muted"
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
          ) : performance.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground text-sm">
              No team performance data available yet.
            </div>
          ) : (
            <div className="space-y-2">
              {sortedByMetric.slice(0, 10).map((member, idx) => (
                <LeaderboardRow
                  key={member.member_email}
                  rank={idx}
                  member={member}
                  score={scoreFor(member)}
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
                value={performance.filter((p) => p.active_clients > 0).length}
                max={performance.length || 1}
                label="Active Owners"
                size={80}
              />
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
