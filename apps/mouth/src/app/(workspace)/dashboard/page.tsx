'use client';

import React from 'react';
import Link from 'next/link';
import { FolderKanban, AlertTriangle, MessageCircle, Clock, Mail, BarChart3 } from 'lucide-react';
import {
  StatsCard,
  PratichePreview,
  WhatsAppPreview,
  PraticaPreview,
  WhatsAppMessage,
  AiPulseWidget,
  FinancialRealityWidget,
  AutoCRMWidget,
} from '@/components/dashboard';
import { DashboardErrorBoundary } from '@/components/ErrorBoundary';
import { useDashboardData } from '@/hooks/useDashboardData';
import { useEnhancedAnalytics, enhancedAnalytics } from '@/lib/enhanced-analytics';
import { useABTesting, initializeABTesting } from '@/lib/ab-testing';
import { useRealtime } from '@/lib/realtime';
import { useMobileOptimization } from '@/lib/mobile-optimization';
import { useFunnelAnalytics } from '@/lib/funnel-analytics';
import { useAIInsights } from '@/lib/ai-insights';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { dashboardMetrics } from '@/lib/metrics/dashboard-metrics';

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
  } = useDashboardData();

  // Analytics and A/B testing hooks
  const {
    trackDashboardLoad,
    trackWidgetInteraction,
    trackEmailAction,
    trackUserInteraction,
    trackPerformance,
    trackError,
  } = useEnhancedAnalytics();

  const { getVariantConfig, getActiveExperiments } = useABTesting();

  // Advanced features hooks
  const realtime = useRealtime();
  const mobile = useMobileOptimization();
  const funnel = useFunnelAnalytics();
  const ai = useAIInsights();

  // Performance tracking
  const startTime = React.useRef(performance.now());

  // Initialize all advanced features
  React.useEffect(() => {
    if (user.email && !isLoading) {
      // Initialize enhanced analytics
      enhancedAnalytics.initialize(user.email, {
        role: user.role,
        email: user.email,
        isAdmin: user.is_admin,
      });

      // Initialize A/B testing
      initializeABTesting(user.email);

      // Initialize real-time collaboration
      realtime.connect(user.email, user.email);

      // Initialize funnel analytics
      funnel.startFunnel(user.email, 'dashboard_engagement');

      // Generate AI insights
      ai.generateInsights({
        cases: [stats.activeCases, stats.criticalDeadlines],
        revenue: [0], // Would come from actual revenue data
        clients: [], // Would come from actual client data
        currentWorkload: stats.activeCases,
      });

      // Track dashboard load
      trackDashboardLoad(startTime.current);

      // Track active experiments
      const activeExperiments = getActiveExperiments();
      activeExperiments.forEach(({ name, variant }) => {
        trackUserInteraction('experiment_view', `${name}_${variant}`);
      });

      // Track mobile optimization
      if (mobile.isMobile) {
        trackUserInteraction('mobile_access', 'dashboard', mobile.breakpoint);
      }
    }
  }, [user.email, isLoading]);

  // Track performance metrics
  React.useEffect(() => {
    if (!isLoading && user.email) {
      const loadTime = performance.now() - startTime.current;
      trackPerformance({ 
        loadTime,
        errorCount: isError ? 1 : 0,
      });
    }
  }, [isLoading, isError]);

  // Get A/B test configurations
  const layoutConfig = getVariantConfig('dashboard_layout');
  const emailConfig = getVariantConfig('email_integration');
  const widgetOrder = getVariantConfig('widget_order');

  // Track errors
  React.useEffect(() => {
    if (error) {
      trackError(error instanceof Error ? error : new Error(String(error)), 'dashboard_load');
    }
  }, [error]);

  // Log dashboard metrics
  React.useEffect(() => {
    if (!isLoading && user.email) {
      const loadTime = dashboardMetrics.endPerformanceMark('dashboard_load', user.email);
      dashboardMetrics.trackPageView(user.email);
      
      logger.info('Dashboard loaded successfully', {
        component: 'DashboardPage',
        action: 'loadDashboardData',
        user: user.email,
        metadata: { loadTime, systemStatus },
      });
    }
  }, [isLoading, user.email, systemStatus]);

  // Handle loading state
  if (isLoading) {
    return (
      <div className="space-y-8">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="animate-pulse">
              <div className="h-24 bg-[var(--muted)] rounded-lg"></div>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="animate-pulse h-64 bg-[var(--muted)] rounded-lg"></div>
          <div className="animate-pulse h-64 bg-[var(--muted)] rounded-lg"></div>
        </div>
      </div>
    );
  }

  // Handle error state
  if (isError) {
    return (
      <div className="space-y-8">
        <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-4">
          <h3 className="font-semibold text-red-500">Dashboard Error</h3>
          <p className="text-sm text-red-500/80">
            Failed to load dashboard data. Please try again later.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="mt-2 px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
          >
            Reload
          </button>
        </div>
      </div>
    );
  }

  return (
    <DashboardErrorBoundary>
      <div className="space-y-8">
        {/* Real-time Collaboration Status */}
        {realtime.isConnected && (
          <div className="rounded-lg border border-green-500/20 bg-green-500/10 p-3 flex items-center gap-3">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <div className="flex-1">
              <p className="text-sm text-green-500">
                🟢 Real-time collaboration active • {realtime.onlineUsersCount} users online
              </p>
            </div>
          </div>
        )}

        {/* AI Insights Banner */}
        {ai.insights && ai.insights.insights.length > 0 && (
          <div className="rounded-lg border border-blue-500/20 bg-blue-500/10 p-4">
            <h3 className="font-semibold text-blue-500 mb-2">🤖 AI Insights</h3>
            <div className="space-y-2">
              {ai.insights.insights.slice(0, 2).map((insight) => (
                <div key={insight.id} className="text-sm text-blue-500/80">
                  <span className="font-medium">{insight.title}:</span> {insight.description}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Mobile Optimization Indicator */}
        {mobile.isMobile && (
          <div className="rounded-lg border border-purple-500/20 bg-purple-500/10 p-3">
            <p className="text-sm text-purple-500">
              📱 Mobile optimized • {mobile.getNavigationStyle()} navigation • {mobile.getInteractionMode()} interactions
            </p>
          </div>
        )}

        {/* System Status Banner */}
        {systemStatus === 'degraded' && (
          <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/10 p-4 flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-yellow-500" />
            <div>
              <h3 className="font-semibold text-yellow-500">System Partial Outage</h3>
              <p className="text-sm text-yellow-500/80">
                Some data streams are currently unavailable. The dashboard is showing partial data.
              </p>
            </div>
          </div>
        )}

      {/* Admin-only widgets */}
      {isZero && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-in fade-in slide-in-from-top-4 duration-700">
            <div className="flex flex-col gap-6">
              <Link
                href="/dashboard/analytics"
                className="group aspect-square flex flex-col items-center justify-center p-6 rounded-xl border-2 border-sky-500/40 bg-sky-500/10 hover:border-sky-400 hover:bg-sky-500/15 transition-all duration-300"
              >
                <div className="p-4 rounded-lg bg-sky-500/20 group-hover:bg-sky-500/30 transition-colors mb-4">
                  <BarChart3 className="w-10 h-10 text-sky-400" />
                </div>
                <h3 className="font-semibold text-[var(--foreground)] text-center">Analytics Dashboard</h3>
                <p className="text-sm text-[var(--foreground-muted)] text-center mt-1">
                  Full system metrics
                </p>
                <div className="text-sky-400 mt-4 group-hover:translate-x-1 transition-transform">
                  →
                </div>
              </Link>

              <div className="rounded-xl border-2 border-sky-500/40 bg-sky-500/10 p-1">
                <AiPulseWidget
                  systemAppStatus={systemStatus}
                  oracleStatus={isHealthy ? 'active' : 'inactive'}
                />
              </div>
            </div>

            <div className="rounded-xl border-2 border-sky-500/40 bg-sky-500/10 p-1 h-fit">
              <AutoCRMWidget />
            </div>
          </div>

          <FinancialRealityWidget 
            revenue={{
              total_revenue: 0,
              paid_revenue: 0,
              outstanding_revenue: 0,
            }} 
            growth={0} 
          />
        </>
      )}

      {/* Team widgets */}
      {!isZero && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-in fade-in slide-in-from-top-4 duration-700">
          <AutoCRMWidget />
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
        <div onClick={() => trackWidgetInteraction('stats_card', 'active_cases')}>
          <StatsCard
            title="Active Cases"
            value={stats.activeCases}
            icon={FolderKanban}
            href="/cases"
            accentColor="amber"
          />
        </div>
        <div onClick={() => trackWidgetInteraction('stats_card', 'critical_deadlines')}>
          <StatsCard
            title="Critical Deadlines"
            value={stats.criticalDeadlines}
            icon={AlertTriangle}
            href="/cases"
            variant={stats.criticalDeadlines > 0 ? 'warning' : 'default'}
            accentColor="purple"
          />
        </div>
        <div onClick={() => trackWidgetInteraction('stats_card', 'unread_signals')}>
          <StatsCard
            title="Unread Signals"
            value={totalUnread}
            icon={MessageCircle}
            href="/whatsapp"
            variant={totalUnread > 0 ? 'danger' : 'default'}
            accentColor="emerald"
          />
        </div>
        <div onClick={() => trackWidgetInteraction('stats_card', 'session_time')}>
          <StatsCard
            title="Session Time"
            value={stats.hoursWorked}
            icon={Clock}
            href="/team"
            accentColor="cyan"
          />
        </div>
      </div>

      {/* Email Stats Card (if connected) */}
      {emailStats.connected && (
        <div className="grid grid-cols-1 gap-6">
          <div onClick={() => {
            trackWidgetInteraction('email_stats', 'unread_emails');
            trackEmailAction('read', emailStats.unread_count);
          }}>
            <StatsCard
              title="Unread Emails"
              value={emailStats.unread_count}
              icon={Mail}
              href="/email"
              variant={emailStats.unread_count > 0 ? 'danger' : 'default'}
              accentColor="blue"
            />
          </div>
        </div>
      )}

      {/* Data Previews */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <PratichePreview 
          pratiche={practices as any} 
          isLoading={isLoading}
        />
        <WhatsAppPreview
          messages={interactions}
          isLoading={isLoading}
          onDelete={async (id) => {
            try {
              trackWidgetInteraction('whatsapp_preview', `message_${id}`);
              await api.crm.deleteInteraction(Number.parseInt(id, 10), user.email);
              trackUserInteraction('delete_message', 'whatsapp', id);
              // Track funnel step completion
              funnel.completeStep(user.email, 'dashboard_engagement', 'delete_message', true);
              // Send real-time update
              realtime.sendDashboardUpdate('delete', 'case', id);
              // Note: In a real implementation, you'd want to refetch the data
              // For now, this is handled by React Query's cache invalidation
            } catch (error) {
              const errorMessage = error instanceof Error ? error.message : String(error);
              trackError(error instanceof Error ? error : new Error(String(error)), 'delete_interaction');
              funnel.completeStep(user.email, 'dashboard_engagement', 'delete_message', false, errorMessage);
              logger.error('Failed to delete interaction', {
                component: 'DashboardPage',
                action: 'deleteInteraction',
                user: user.email,
                metadata: { interactionId: id },
              }, error instanceof Error ? error : new Error(String(error)));
            }
          }}
        />
      </div>

      {/* Advanced Features Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* AI Predictions */}
        {ai.insights && (
          <div className="rounded-lg border border-blue-500/20 bg-blue-500/10 p-4">
            <h3 className="font-semibold text-blue-500 mb-3">🤖 AI Predictions</h3>
            <div className="space-y-2 text-sm">
              <div className="text-blue-500/80">
                <span className="font-medium">Cases Next Month:</span> {ai.insights.predictions.casesNextMonth}
              </div>
              <div className="text-blue-500/80">
                <span className="font-medium">Revenue Forecast:</span> ${ai.insights.predictions.revenueNextMonth.toLocaleString()}
              </div>
              <div className="text-blue-500/80">
                <span className="font-medium">Churn Risk:</span> {(ai.insights.predictions.clientChurnRisk * 100).toFixed(1)}%
              </div>
            </div>
          </div>
        )}

        {/* Funnel Analytics */}
        <div className="rounded-lg border border-green-500/20 bg-green-500/10 p-4">
          <h3 className="font-semibold text-green-500 mb-3">📊 Funnel Analytics</h3>
          <div className="space-y-2 text-sm">
            <div className="text-green-500/80">
              <span className="font-medium">Active Users:</span> {funnel.getCompletionRate('dashboard_engagement') > 0 ? '1' : '0'}
            </div>
            <div className="text-green-500/80">
              <span className="font-medium">Completion Rate:</span> {(funnel.getCompletionRate('dashboard_engagement') * 100).toFixed(1)}%
            </div>
            <div className="text-green-500/80">
              <span className="font-medium">Avg Time:</span> {funnel.getAverageCompletionTime('dashboard_engagement')}s
            </div>
          </div>
        </div>

        {/* Mobile Optimization Stats */}
        {mobile.isMobile && (
          <div className="rounded-lg border border-purple-500/20 bg-purple-500/10 p-4">
            <h3 className="font-semibold text-purple-500 mb-3">📱 Mobile Stats</h3>
            <div className="space-y-2 text-sm">
              <div className="text-purple-500/80">
                <span className="font-medium">Layout:</span> {mobile.getMobileConfig('mobile_layout').layout || 'stacked'}
              </div>
              <div className="text-purple-500/80">
                <span className="font-medium">Navigation:</span> {mobile.getNavigationStyle()}
              </div>
              <div className="text-purple-500/80">
                <span className="font-medium">Interactions:</span> {mobile.getInteractionMode()}
              </div>
            </div>
          </div>
        )}
      </div>
      </div>
    </DashboardErrorBoundary>
  );
}
