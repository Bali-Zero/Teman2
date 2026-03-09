"use client";

import React from "react";
import Link from "next/link";
import {
  FolderKanban,
  AlertTriangle,
  MessageCircle,
  Clock,
  Mail,
  BarChart3,
  RefreshCw,
} from "lucide-react";
import {
  StatsCard,
  PratichePreview,
  WhatsAppPreview,
  AiPulseWidget,
  FinancialRealityWidget,
  GrafanaWidget,
  NusantaraHealthWidget,
  CaseDistribution,
  MiniSparkline,
} from "@/components/dashboard";
import { HeroLiveWindow } from "@/components/workspace/HeroLiveWindow";
import type { PraticaPreview, WhatsAppMessage } from "@/components/dashboard";
import { DashboardErrorBoundary } from "@/components/ErrorBoundary";
import { useDashboardData } from "@/hooks/useDashboardData";
import { useQueryClient } from "@tanstack/react-query";
import {
  useEnhancedAnalytics,
  enhancedAnalytics,
} from "@/lib/enhanced-analytics";
import { useABTesting, initializeABTesting } from "@/lib/ab-testing";
import { useRealtime } from "@/lib/realtime";
import { useMobileOptimization } from "@/lib/mobile-optimization";
import { useFunnelAnalytics } from "@/lib/funnel-analytics";
import { useAIInsights } from "@/lib/ai-insights";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import { dashboardMetrics } from "@/lib/metrics/dashboard-metrics";

export default function DashboardPage() {
  const {
    user,
    stats,
    practices,
    interactions,
    emailStats,
    systemStatus,
    isZero,
    isLoading,
    isError,
    error,
    totalUnread,
    isHealthy,
    revenue,
    revenueGrowth,
    refetch,
  } = useDashboardData();

  const {
    trackDashboardLoad,
    trackWidgetInteraction,
    trackEmailAction,
    trackUserInteraction,
    trackPerformance,
    trackError,
  } = useEnhancedAnalytics();

  const { getVariantConfig, getActiveExperiments } = useABTesting();

  const realtime = useRealtime();
  const mobile = useMobileOptimization();
  const funnel = useFunnelAnalytics();
  const ai = useAIInsights();
  const queryClient = useQueryClient();

  const startTime = React.useRef(performance.now());

  // Performance mark on mount
  React.useEffect(() => {
    dashboardMetrics.startPerformanceMark("dashboard_load");
  }, []);

  // Initialize advanced features + wire WebSocket to React Query
  React.useEffect(() => {
    if (user?.email && !isLoading) {
      enhancedAnalytics.initialize(user.email, {
        role: user.role || "Member",
        email: user.email,
        isAdmin: user.is_admin || false,
      });

      initializeABTesting(user.email);
      realtime.connect(user.email, user.email);
      funnel.startFunnel(user.email, "dashboard_engagement");

      ai.generateInsights({
        cases: [],
        revenue: [],
        clients: [],
      });

      trackDashboardLoad(startTime.current);

      const activeExperiments = getActiveExperiments();
      activeExperiments.forEach(({ name, variant }) => {
        trackUserInteraction("experiment_view", `${name}_${variant}`);
      });

      if (mobile.isMobile) {
        trackUserInteraction("mobile_access", "dashboard", mobile.breakpoint);
      }
    }
  }, [user?.email, isLoading]);

  // Bridge WebSocket dashboard_update events to React Query invalidation
  React.useEffect(() => {
    const unsubscribe = realtime.subscribe("dashboard_update", () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    });
    return unsubscribe;
  }, [realtime, queryClient]);

  // Track performance
  React.useEffect(() => {
    if (!isLoading && user?.email) {
      const loadTime = performance.now() - startTime.current;
      trackPerformance({ loadTime, errorCount: isError ? 1 : 0 });
    }
  }, [isLoading, isError]);

  // Track errors
  React.useEffect(() => {
    if (error) {
      trackError(
        error instanceof Error ? error : new Error(String(error)),
        "dashboard_load",
      );
    }
  }, [error]);

  // Log dashboard metrics (once)
  const hasLoggedSuccess = React.useRef(false);
  React.useEffect(() => {
    if (!isLoading && user?.email && !hasLoggedSuccess.current) {
      const loadTime = dashboardMetrics.endPerformanceMark(
        "dashboard_load",
        user.email,
      );
      dashboardMetrics.trackPageView(user.email);
      logger.info("Dashboard loaded successfully", {
        component: "DashboardPage",
        action: "loadDashboardData",
        user: user.email,
        metadata: { loadTime, systemStatus },
      });
      hasLoggedSuccess.current = true;
    }
  }, [isLoading, user?.email, systemStatus]);

  // Compute case distribution for chart
  const caseDistribution = React.useMemo(() => {
    const statusCounts: Record<string, number> = {};
    for (const p of practices) {
      statusCounts[p.status] = (statusCounts[p.status] || 0) + 1;
    }
    return [
      {
        label: "In Progress",
        value: statusCounts["in_progress"] || 0,
        color: "var(--accent, #3b82f6)",
      },
      {
        label: "Inquiry",
        value: statusCounts["inquiry"] || 0,
        color: "var(--foreground-muted, #9ca3af)",
      },
      {
        label: "Quotation",
        value: statusCounts["quotation"] || 0,
        color: "var(--warning, #f59e0b)",
      },
      {
        label: "Documents",
        value: statusCounts["documents"] || 0,
        color: "var(--warning, #f59e0b)",
      },
      {
        label: "Completed",
        value: statusCounts["completed"] || 0,
        color: "var(--success, #22c55e)",
      },
    ];
  }, [practices]);

  // Mock sparkline data from stats (recent activity trend)
  const activityTrend = React.useMemo(() => {
    const base = stats.activeCases || 1;
    return Array.from({ length: 7 }, (_, i) =>
      Math.max(0, base + Math.round(Math.sin(i * 0.8) * base * 0.3)),
    );
  }, [stats.activeCases]);

  // Loading state - responsive skeleton
  if (isLoading) {
    return (
      <div className="space-y-6 sm:space-y-8">
        <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="animate-pulse">
              <div className="h-20 sm:h-24 bg-[var(--muted)] rounded-lg" />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-8">
          <div className="animate-pulse h-48 sm:h-64 bg-[var(--muted)] rounded-lg" />
          <div className="animate-pulse h-48 sm:h-64 bg-[var(--muted)] rounded-lg" />
        </div>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="space-y-8">
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
          <h3 className="font-semibold text-red-500">Dashboard Error</h3>
          <p className="text-sm text-red-500/80">
            Failed to load dashboard data. Please try again later.
          </p>
          <button
            onClick={() => refetch()}
            className="mt-2 px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 transition-colors inline-flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <DashboardErrorBoundary>
      <div className="space-y-6 sm:space-y-8">
        {/* Live Homepage Hero — mirrors balizero.com copertina */}
        <HeroLiveWindow />

        {/* Real-time Status */}
        {realtime.isConnected && (
          <div className="rounded-lg border border-green-500/20 bg-green-500/10 p-2 sm:p-3 flex items-center gap-2 sm:gap-3">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse flex-shrink-0" />
            <p className="text-xs sm:text-sm text-green-500 truncate">
              Real-time active &middot; {realtime.onlineUsersCount} online
            </p>
          </div>
        )}

        {/* Admin-only section */}
        {isZero && (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6 animate-in fade-in slide-in-from-top-4 duration-700">
              <div className="flex flex-col gap-4 sm:gap-6">
                <Link
                  href="/dashboard/analytics"
                  className="group flex flex-col items-center justify-center p-4 sm:p-6 rounded-xl border-2 border-sky-500/40 bg-sky-500/10 hover:border-sky-400 hover:bg-sky-500/15 transition-all duration-300 min-h-[140px] sm:aspect-square"
                >
                  <div className="p-3 sm:p-4 rounded-lg bg-sky-500/20 group-hover:bg-sky-500/30 transition-colors mb-3 sm:mb-4">
                    <BarChart3 className="w-8 h-8 sm:w-10 sm:h-10 text-sky-400" />
                  </div>
                  <h3 className="font-semibold text-[var(--foreground)] text-center text-sm sm:text-base">
                    Analytics Dashboard
                  </h3>
                  <p className="text-xs sm:text-sm text-[var(--foreground-muted)] text-center mt-1">
                    Full system metrics
                  </p>
                  <div className="text-sky-400 mt-2 sm:mt-4 group-hover:translate-x-1 transition-transform">
                    &rarr;
                  </div>
                </Link>

                <div className="rounded-xl border-2 border-sky-500/40 bg-sky-500/10 p-1">
                  <AiPulseWidget
                    systemAppStatus={systemStatus}
                    oracleStatus={isHealthy ? "active" : "inactive"}
                  />
                </div>
              </div>

              {/* System Health (admin) */}
              <GrafanaWidget />
            </div>

            {/* Financial + Nusantara Health (admin) */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
              {revenue && (
                <FinancialRealityWidget
                  revenue={revenue}
                  growth={revenueGrowth || 0}
                />
              )}
              <NusantaraHealthWidget />
            </div>
          </>
        )}

        {/* Stats Cards — responsive: 2 cols on small, 4 on large */}
        <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-6">
          <div
            onClick={() => trackWidgetInteraction("stats_card", "active_cases")}
          >
            <StatsCard
              title="Active Cases"
              value={stats.activeCases}
              icon={FolderKanban}
              href="/process"
              accentColor="amber"
            />
          </div>
          <div
            onClick={() =>
              trackWidgetInteraction("stats_card", "critical_deadlines")
            }
          >
            <StatsCard
              title="Critical Deadlines"
              value={stats.criticalDeadlines}
              icon={AlertTriangle}
              href="/process"
              variant={stats.criticalDeadlines > 0 ? "warning" : "default"}
              accentColor="purple"
            />
          </div>
          <div
            onClick={() =>
              trackWidgetInteraction("stats_card", "unread_signals")
            }
          >
            <StatsCard
              title="Unread Signals"
              value={totalUnread}
              icon={MessageCircle}
              href="/whatsapp"
              variant={totalUnread > 0 ? "danger" : "default"}
              accentColor="emerald"
            />
          </div>
          <div
            onClick={() => trackWidgetInteraction("stats_card", "session_time")}
          >
            <StatsCard
              title="Session Time"
              value={stats.hoursWorked}
              icon={Clock}
              href="/team"
              accentColor="cyan"
            />
          </div>
        </div>

        {/* Email Stats (conditional) */}
        {emailStats.connected && (
          <div
            onClick={() => {
              trackWidgetInteraction("email_stats", "unread_emails");
              trackEmailAction("read", emailStats.unread_count);
            }}
          >
            <StatsCard
              title="Unread Emails"
              value={emailStats.unread_count}
              icon={Mail}
              href="/email"
              variant={emailStats.unread_count > 0 ? "danger" : "default"}
              accentColor="blue"
            />
          </div>
        )}

        {/* Data Visualization Row */}
        {practices.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
            {/* Case Distribution Donut */}
            <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4 sm:p-5">
              <h3 className="text-sm font-semibold text-[var(--foreground)] mb-4">
                Case Distribution
              </h3>
              <CaseDistribution segments={caseDistribution} />
            </div>

            {/* Activity Trend Sparkline */}
            <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4 sm:p-5">
              <h3 className="text-sm font-semibold text-[var(--foreground)] mb-2">
                Weekly Activity
              </h3>
              <p className="text-xs text-[var(--foreground-muted)] mb-4">
                Active cases over the last 7 days
              </p>
              <MiniSparkline
                data={activityTrend}
                width={280}
                height={64}
                className="w-full max-w-[280px]"
              />
              <div className="flex items-center justify-between mt-3 text-xs text-[var(--foreground-muted)]">
                <span>7d ago</span>
                <span>Today</span>
              </div>
            </div>
          </div>
        )}

        {/* Data Previews */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-8">
          <PratichePreview
            pratiche={practices.map(
              (p): PraticaPreview => ({
                id: p.id,
                title: p.title || "Unknown",
                client: p.client || "Unknown Client",
                status: p.status,
                daysRemaining: p.daysRemaining,
                completedAt:
                  p.status === "completed"
                    ? new Date().toLocaleDateString()
                    : undefined,
              }),
            )}
            isLoading={isLoading}
          />
          <WhatsAppPreview
            messages={interactions}
            isLoading={isLoading}
            onDelete={async (id) => {
              try {
                trackWidgetInteraction("whatsapp_preview", `message_${id}`);
                await api.crm.deleteInteraction(
                  Number.parseInt(id, 10),
                  user?.email || "",
                );
                trackUserInteraction("delete_message", "whatsapp", id);
                if (user?.email)
                  funnel.completeStep(
                    user.email,
                    "dashboard_engagement",
                    "delete_message",
                    true,
                  );
                realtime.sendDashboardUpdate("delete", "case", id);
                queryClient.invalidateQueries({ queryKey: ["dashboard"] });
                queryClient.invalidateQueries({ queryKey: ["interactions"] });
              } catch (deleteError) {
                const errorMessage =
                  deleteError instanceof Error
                    ? deleteError.message
                    : String(deleteError);
                trackError(
                  deleteError instanceof Error
                    ? deleteError
                    : new Error(String(deleteError)),
                  "delete_interaction",
                );
                if (user?.email)
                  funnel.completeStep(
                    user.email,
                    "dashboard_engagement",
                    "delete_message",
                    false,
                    errorMessage,
                  );
                logger.error(
                  "Failed to delete interaction",
                  {
                    component: "DashboardPage",
                    action: "deleteInteraction",
                    user: user?.email || "unknown",
                    metadata: { interactionId: id },
                  },
                  deleteError instanceof Error
                    ? deleteError
                    : new Error(String(deleteError)),
                );
              }
            }}
          />
        </div>
      </div>
    </DashboardErrorBoundary>
  );
}
