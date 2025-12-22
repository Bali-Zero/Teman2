'use client';

import React, { useState, useEffect } from 'react';
import { FolderKanban, AlertTriangle, MessageCircle, Clock } from 'lucide-react';
import {
  StatsCard,
  PratichePreview,
  WhatsAppPreview,
  PraticaPreview,
  WhatsAppMessage,
  AiPulseWidget,
  FinancialRealityWidget,
  NusantaraHealthWidget,
} from '@/components/dashboard';
import { api } from '@/lib/api';
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

      try {
        const user = await api.getProfile();
        const email = user.email;
        setUserEmail(email);

        const isZero = email === 'zero@balizero.com';

        // Fetch real data in parallel with error tracking
        const results = await Promise.allSettled([
          api.crm.getPracticeStats().catch(
            () =>
              ({
                total_practices: 0,
                active_practices: 0,
                by_status: {},
                by_type: [],
                revenue: { total_revenue: 0, paid_revenue: 0, outstanding_revenue: 0 },
              }) as PracticeStats
          ),
          api.crm.getInteractionStats().catch(
            () =>
              ({
                total_interactions: 0,
                last_7_days: 0,
                by_type: {},
                by_sentiment: {},
                by_team_member: [],
              }) as InteractionStats
          ),
          api.crm.getPractices({ status: 'in_progress', limit: 5 }).catch(() => [] as Practice[]),
          api.crm
            .getInteractions({ interaction_type: 'whatsapp', limit: 5 })
            .catch(() => [] as Interaction[]),
          api.crm.getUpcomingRenewals(30).catch(() => [] as RenewalAlert[]),
          api.getClockStatus().catch(() => ({ today_hours: 0 })),
          isZero ? api.crm.getRevenueGrowth().catch(() => null) : Promise.resolve(null),
        ]);

        // Check for failures to determine system status
        const hasFailures = results.some((r) => r.status === 'rejected');
        setSystemStatus(hasFailures ? 'degraded' : 'healthy');

        const practiceStats =
          results[0].status === 'fulfilled'
            ? (results[0].value as PracticeStats)
            : ({
                total_practices: 0,
                active_practices: 0,
                by_status: {},
                by_type: [],
                revenue: { total_revenue: 0, paid_revenue: 0, outstanding_revenue: 0 },
              } as PracticeStats);
        const interactionStats =
          results[1].status === 'fulfilled'
            ? (results[1].value as InteractionStats)
            : ({
                total_interactions: 0,
                last_7_days: 0,
                by_type: {},
                by_sentiment: {},
                by_team_member: [],
              } as InteractionStats);
        const activePractices =
          results[2].status === 'fulfilled' ? (results[2].value as Practice[]) : [];
        const recentInteractions =
          results[3].status === 'fulfilled' ? (results[3].value as Interaction[]) : [];
        const renewals =
          results[4].status === 'fulfilled' ? (results[4].value as RenewalAlert[]) : [];
        const clockStatus =
          results[5].status === 'fulfilled' ? results[5].value : { today_hours: 0 };
        const revenueGrowth = results[6].status === 'fulfilled' ? results[6].value : null;

        // Transform Practices for UI
        const mappedCases: PraticaPreview[] = activePractices.map((p) => ({
          id: p.id,
          title: p.practice_type_code?.toUpperCase().replace(/_/g, ' ') || 'Case',
          client: p.client_name || 'Unknown Client',
          status: p.status as PraticaPreview['status'],
          daysRemaining: p.expiry_date
            ? Math.ceil((new Date(p.expiry_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
            : undefined,
        }));

        // Transform Interactions for UI
        const mappedMessages: WhatsAppMessage[] = recentInteractions.map((i) => ({
          id: i.id.toString(),
          contactName: i.client_name || 'Anonymous',
          message: i.summary || i.full_content || 'No content',
          timestamp: new Date(i.created_at).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          }),
          isRead: i.read_receipt === true, // Use real read_receipt field from database
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
      } catch (error) {
        console.error('Failed to load dashboard data', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadDashboardData();
  }, []);

  const isZero = userEmail === 'zero@balizero.com';

  return (
    <div className="space-y-8">
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

      {/* Zero-Only Command Deck Widgets */}
      {isZero && !isLoading && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-in fade-in slide-in-from-top-4 duration-700">
            <AiPulseWidget
              systemAppStatus={systemStatus}
              oracleStatus={systemStatus === 'healthy' ? 'active' : 'inactive'}
            />
            {stats.revenue && (
              <FinancialRealityWidget revenue={stats.revenue} growth={stats.growth || 0} />
            )}
          </div>
          {/* Nusantara System Health Map */}
          <NusantaraHealthWidget className="animate-in fade-in slide-in-from-top-4 duration-700 delay-150" />
        </>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
        <StatsCard
          title="Active Cases"
          value={isLoading ? '-' : stats.activeCases}
          icon={FolderKanban}
          href="/pratiche"
        />
        <StatsCard
          title="Critical Deadlines"
          value={isLoading ? '-' : stats.criticalDeadlines}
          icon={AlertTriangle}
          href="/pratiche"
          variant={stats.criticalDeadlines > 0 ? 'warning' : 'default'}
        />
        <StatsCard
          title="Unread Signals"
          value={isLoading ? '-' : stats.whatsappUnread}
          icon={MessageCircle}
          href="/whatsapp"
          variant={stats.whatsappUnread > 0 ? 'danger' : 'default'}
        />
        <StatsCard
          title="Session Time"
          value={isLoading ? '-' : stats.hoursWorked}
          icon={Clock}
          href="/team"
        />
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Pratiche Preview */}
        <PratichePreview pratiche={cases} isLoading={isLoading} />

        {/* WhatsApp Preview */}
        <WhatsAppPreview messages={whatsappMessages} isLoading={isLoading} />
      </div>
    </div>
  );
}
