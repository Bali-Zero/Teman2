'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { FolderKanban, AlertTriangle, MessageCircle, Clock, BarChart3 } from 'lucide-react';
import {
  StatsCard,
  PratichePreview,
  WhatsAppPreview,
  PraticaPreview,
  WhatsAppMessage,
  AiPulseWidget,
  FinancialRealityWidget,
  NusantaraHealthWidget,
  AutoCRMWidget,
  GrafanaWidget,
} from '@/components/dashboard';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { dashboardMetrics } from '@/lib/metrics/dashboard-metrics';
import type {
  PracticeStats,
  InteractionStats,
  Practice,
  Interaction,
  RenewalAlert,
} from '@/lib/api/crm/crm.types';

interface DashboardStats {
  activeCases: number;
  criticalDeadlines: number;
  whatsappUnread: number;
  hoursWorked: string;
  revenue?: {
    total_revenue: number;
    paid_revenue: number;
    outstanding_revenue: number;
  };
  growth?: number;
}

export default function DashboardPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [userEmail, setUserEmail] = useState<string>('');
  const [systemStatus, setSystemStatus] = useState<'healthy' | 'degraded'>('healthy');
  const [stats, setStats] = useState<DashboardStats>({
    activeCases: 0,
    criticalDeadlines: 0,
    whatsappUnread: 0,
    hoursWorked: '0h 0m',
  });
  const [cases, setCases] = useState<PraticaPreview[]>([]);
  const [whatsappMessages, setWhatsappMessages] = useState<WhatsAppMessage[]>([]);

  useEffect(() => {
    const loadDashboardData = async () => {
      setIsLoading(true);
      dashboardMetrics.startPerformanceMark('dashboard_load');

      try {
        const user = await api.getProfile();
        const email = user.email;
        setUserEmail(email);

        const isZero = email === 'zero@balizero.com';

        const results = await Promise.allSettled([
          api.crm.getPracticeStats().catch((error) => {
            logger.error('Failed to load practice stats', {
              component: 'DashboardPage',
              action: 'loadDashboardData',
            }, error instanceof Error ? error : new Error(String(error)));
            return {
              total_practices: 0,
              active_practices: 0,
              by_status: {},
              by_type: [],
              revenue: { total_revenue: 0, paid_revenue: 0, outstanding_revenue: 0 },
            } as PracticeStats;
          }),
          api.crm.getInteractionStats().catch((error) => {
            logger.error('Failed to load interaction stats', {
              component: 'DashboardPage',
              action: 'loadDashboardData',
            }, error instanceof Error ? error : new Error(String(error)));
            return {
              total_interactions: 0,
              last_7_days: 0,
              by_type: {},
              by_sentiment: {},
              by_team_member: [],
            } as InteractionStats;
          }),
          api.crm.getPractices({ status: 'in_progress', limit: 5 }).catch((error) => {
            logger.error('Failed to load practices', {
              component: 'DashboardPage',
              action: 'loadDashboardData',
            }, error instanceof Error ? error : new Error(String(error)));
            return [] as Practice[];
          }),
          api.crm
            .getInteractions({ interaction_type: 'whatsapp', limit: 5 })
            .catch((error) => {
              logger.error('Failed to load interactions', {
                component: 'DashboardPage',
                action: 'loadDashboardData',
              }, error instanceof Error ? error : new Error(String(error)));
              return [] as Interaction[];
            }),
          api.crm.getUpcomingRenewals(30).catch((error) => {
            logger.error('Failed to load renewals', {
              component: 'DashboardPage',
              action: 'loadDashboardData',
            }, error instanceof Error ? error : new Error(String(error)));
            return [] as RenewalAlert[];
          }),
          api.getClockStatus().catch((error) => {
            logger.error('Failed to load clock status', {
              component: 'DashboardPage',
              action: 'loadDashboardData',
            }, error instanceof Error ? error : new Error(String(error)));
            return { today_hours: 0 };
          }),
          isZero ? api.crm.getRevenueGrowth().catch((error) => {
            logger.error('Failed to load revenue growth', {
              component: 'DashboardPage',
              action: 'loadDashboardData',
            }, error instanceof Error ? error : new Error(String(error)));
            return null;
          }) : Promise.resolve(null),
        ]);

        // Check for failures to determine system status
        const hasFailures = results.some((r) => r.status === 'rejected');
        setSystemStatus(hasFailures ? 'degraded' : 'healthy');

        const defaultPracticeStats: PracticeStats = {
          total_practices: 0,
          active_practices: 0,
          by_status: {},
          by_type: [],
          revenue: { total_revenue: 0, paid_revenue: 0, outstanding_revenue: 0 },
        };

        const defaultInteractionStats: InteractionStats = {
          total_interactions: 0,
          last_7_days: 0,
          by_type: {},
          by_sentiment: {},
          by_team_member: [],
        };

        const practiceStats = results[0].status === 'fulfilled' 
          ? (results[0].value as PracticeStats) 
          : defaultPracticeStats;
        
        const interactionStats = results[1].status === 'fulfilled'
          ? (results[1].value as InteractionStats)
          : defaultInteractionStats;
        const activePractices = results[2].status === 'fulfilled' ? (results[2].value as Practice[]) : [];
        const recentInteractions = results[3].status === 'fulfilled' ? (results[3].value as Interaction[]) : [];
        const renewals = results[4].status === 'fulfilled' ? (results[4].value as RenewalAlert[]) : [];
        const clockStatus = results[5].status === 'fulfilled' ? results[5].value : { today_hours: 0 };
        const revenueGrowth = results[6].status === 'fulfilled' ? results[6].value : null;

        const mappedCases: PraticaPreview[] = activePractices.map((p) => ({
          id: p.id,
          title: p.practice_type_code?.toUpperCase().replaceAll('_', ' ') || 'Case',
          client: p.client_name || 'Unknown Client',
          status: p.status as PraticaPreview['status'],
          daysRemaining: p.expiry_date
            ? Math.ceil((new Date(p.expiry_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
            : undefined,
        }));

        const mappedMessages: WhatsAppMessage[] = recentInteractions.map((i) => ({
          id: i.id.toString(),
          contactName: i.client_name || 'Anonymous',
          message: i.summary || i.full_content || 'No content',
          timestamp: new Date(i.created_at).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          }),
          isRead: i.read_receipt === true,
          hasAiSuggestion: !!i.conversation_id,
          practiceId: i.practice_id,
        }));

        setStats({
          activeCases: practiceStats.active_practices,
          criticalDeadlines: renewals.length,
          whatsappUnread: interactionStats.by_type['whatsapp'] || 0,
          hoursWorked: `${Math.floor(clockStatus.today_hours)}h ${Math.round((clockStatus.today_hours % 1) * 60)}m`,
          revenue: revenueGrowth?.current_month,
          growth: revenueGrowth?.growth_percentage,
        });

        setCases(mappedCases);
        setWhatsappMessages(mappedMessages);
        
        const loadTime = dashboardMetrics.endPerformanceMark('dashboard_load', email);
        dashboardMetrics.trackPageView(email);
        
        logger.info('Dashboard loaded successfully', {
          component: 'DashboardPage',
          action: 'loadDashboardData',
          user: email,
          metadata: { loadTime, systemStatus },
        });
      } catch (error) {
        logger.error('Critical error loading dashboard data', {
          component: 'DashboardPage',
          action: 'loadDashboardData',
          user: userEmail,
        }, error instanceof Error ? error : new Error(String(error)));
        setSystemStatus('degraded');
        dashboardMetrics.trackError('dashboard_load_failed', error instanceof Error ? error.message : 'Unknown error', userEmail);
      } finally {
        setIsLoading(false);
        dashboardMetrics.endPerformanceMark('dashboard_load', userEmail);
      }
    };

    loadDashboardData();
  }, []);

  const isZero = userEmail === 'zero@balizero.com';

  return (
    <div className="space-y-8">
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

      {isZero && !isLoading && (
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
                  oracleStatus={systemStatus === 'healthy' ? 'active' : 'inactive'}
                />
              </div>
            </div>

            <div className="rounded-xl border-2 border-sky-500/40 bg-sky-500/10 p-1 h-fit">
              <AutoCRMWidget />
            </div>
          </div>

          {stats.revenue && (
            <div className="animate-in fade-in slide-in-from-top-4 duration-700 delay-100">
              <FinancialRealityWidget revenue={stats.revenue} growth={stats.growth || 0} />
            </div>
          )}

          <NusantaraHealthWidget className="animate-in fade-in slide-in-from-top-4 duration-700 delay-150" />
          <GrafanaWidget className="animate-in fade-in slide-in-from-top-4 duration-700 delay-200" />
        </>
      )}

      {!isZero && !isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-in fade-in slide-in-from-top-4 duration-700">
          <AutoCRMWidget />
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
        <StatsCard
          title="Active Cases"
          value={isLoading ? '-' : stats.activeCases}
          icon={FolderKanban}
          href="/cases"
          accentColor="amber"
        />
        <StatsCard
          title="Critical Deadlines"
          value={isLoading ? '-' : stats.criticalDeadlines}
          icon={AlertTriangle}
          href="/cases"
          variant={stats.criticalDeadlines > 0 ? 'warning' : 'default'}
          accentColor="purple"
        />
        <StatsCard
          title="Unread Signals"
          value={isLoading ? '-' : stats.whatsappUnread}
          icon={MessageCircle}
          href="/whatsapp"
          variant={stats.whatsappUnread > 0 ? 'danger' : 'default'}
          accentColor="emerald"
        />
        <StatsCard
          title="Session Time"
          value={isLoading ? '-' : stats.hoursWorked}
          icon={Clock}
          href="/team"
          accentColor="cyan"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <PratichePreview pratiche={cases} isLoading={isLoading} />
        <WhatsAppPreview
          messages={whatsappMessages}
          isLoading={isLoading}
          onDelete={async (id) => {
            try {
              await api.crm.deleteInteraction(Number.parseInt(id, 10), userEmail);
              setWhatsappMessages(prev => prev.filter(m => m.id !== id));
              setStats(prev => ({
                ...prev,
                whatsappUnread: Math.max(0, prev.whatsappUnread - 1),
              }));
            } catch (error) {
              logger.error('Failed to delete interaction', {
                component: 'DashboardPage',
                action: 'deleteInteraction',
                user: userEmail,
                metadata: { interactionId: id },
              }, error instanceof Error ? error : new Error(String(error)));
            }
          }}
        />
      </div>
    </div>
  );
}
