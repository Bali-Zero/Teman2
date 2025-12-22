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
} from '@/components/dashboard';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { api } from '@/lib/api';
import type { PracticeStats, InteractionStats } from '@/lib/api/crm/crm.types';

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
  monthlyGrowth?: number;
}

type SystemStatus = 'healthy' | 'degraded' | 'down';

export default function DashboardPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [systemStatus, setSystemStatus] = useState<SystemStatus>('healthy');
  const [userEmail, setUserEmail] = useState<string>('');
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
      // Check authentication first
      if (!api.isAuthenticated()) {
        window.location.href = '/login';
        return;
      }

      setIsLoading(true);
      setSystemStatus('healthy');

      try {
        // Get user profile for role-based visibility
        const user = await api.getProfile().catch(() => null);
        if (!user) {
          // If profile fetch fails, redirect to login
          window.location.href = '/login';
          return;
        }
        const currentUserEmail = user?.email || '';
        setUserEmail(currentUserEmail);
        const isZero = currentUserEmail === 'zero@balizero.com';

        // Fetch real data in parallel
        const results = await Promise.allSettled([
          api.crm.getPracticeStats(),
          api.crm.getInteractionStats(),
          api.crm.getPractices({ status: 'in_progress', limit: 5 }),
          api.crm.getInteractions({ interaction_type: 'whatsapp', limit: 5 }),
          api.crm.getUpcomingRenewals(30), // [NEW] For Critical Deadlines
          api.getClockStatus(),
          // [ROLE BASED] Revenue growth stats only for Zero
          isZero ? api.crm.getRevenueGrowth() : Promise.resolve(null),
        ]);

        // Check for failures to set system status
        const hasFailures = results.some((r) => r.status === 'rejected');
        if (hasFailures) {
          setSystemStatus('degraded');
        }

        // Extract results with fallbacks
        const practiceStats =
          results[0].status === 'fulfilled'
            ? (results[0].value as PracticeStats)
            : ({
                active_practices: 0,
                revenue: { total_revenue: 0, paid_revenue: 0, outstanding_revenue: 0 },
              } as PracticeStats);

        const interactionStats =
          results[1].status === 'fulfilled'
            ? (results[1].value as InteractionStats)
            : ({
                total_interactions: 0,
                by_type: {},
                by_sentiment: {},
                by_team_member: [],
                last_7_days: 0,
              } as InteractionStats);

        const activePractices = results[2].status === 'fulfilled' ? results[2].value : [];
        const recentInteractions = results[3].status === 'fulfilled' ? results[3].value : [];
        const upcomingRenewals = results[4].status === 'fulfilled' ? results[4].value : [];
        const clockStatus =
          results[5].status === 'fulfilled' ? results[5].value : { today_hours: 0 };

        // Revenue growth stats (only for Zero)
        const revenueGrowthData =
          isZero && results[6].status === 'fulfilled'
            ? (results[6].value as {
                current_month: {
                  total_revenue: number;
                  paid_revenue: number;
                  outstanding_revenue: number;
                };
                previous_month: {
                  total_revenue: number;
                  paid_revenue: number;
                  outstanding_revenue: number;
                };
                growth_percentage: number;
                monthly_breakdown: Array<{
                  month: string;
                  total_revenue: number;
                  paid_revenue: number;
                  outstanding_revenue: number;
                  practice_count: number;
                }>;
              })
            : undefined;

        // Transform Practices for UI
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const mappedCases: PraticaPreview[] = (activePractices || []).map((p: any) => ({
          id: p.id,
          title: `${p.practice_type_code || 'Case'} - ${p.client_name || 'Client'}`,
          client: p.client_name || 'Unknown',
          status: p.status,
          daysRemaining: p.expiry_date
            ? Math.ceil((new Date(p.expiry_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24))
            : undefined,
        }));

        // Transform Interactions for UI with real read receipts
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const mappedMessages: WhatsAppMessage[] = (recentInteractions || []).map((i: any) => ({
          id: i.id.toString(),
          contactName: i.client_name || i.interaction_type,
          message: i.summary || i.full_content || 'No content',
          timestamp: new Date(i.created_at || i.interaction_date).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          }),
          isRead: i.read_receipt === true, // [FIXED] Use real read_receipt instead of sentiment proxy
          hasAiSuggestion: false,
          practiceId: i.practice_id,
        }));

        setStats({
          activeCases: practiceStats.active_practices || 0,
          criticalDeadlines: upcomingRenewals.length || 0,
          whatsappUnread: interactionStats.by_type?.['whatsapp'] || 0,
          hoursWorked: `${Math.floor(clockStatus.today_hours || 0)}h ${Math.round(((clockStatus.today_hours || 0) % 1) * 60)}m`,
          revenue: revenueGrowthData?.current_month,
          monthlyGrowth: revenueGrowthData?.growth_percentage,
        });

        setCases(mappedCases);
        setWhatsappMessages(mappedMessages);
      } catch (error) {
        console.error('Dashboard load failed', error);
        setSystemStatus('degraded');
      } finally {
        setIsLoading(false);
      }
    };

    loadDashboardData();
  }, []);

  const isZero = userEmail === 'zero@balizero.com';

  return (
    <div className="space-y-8">
      {/* System Error Banner */}
      {systemStatus === 'degraded' && (
        <Alert variant="destructive" className="border-yellow-500/20 bg-yellow-500/10">
          <AlertTitle>System Partial Outage</AlertTitle>
          <AlertDescription>Some data streams are currently unavailable.</AlertDescription>
        </Alert>
      )}

      {/* ZERO EXCLUSIVE WIDGETS */}
      {isZero && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <AiPulseWidget
            systemAppStatus={systemStatus}
            oracleStatus={(() => {
              if (systemStatus === 'healthy') return 'active';
              if (systemStatus === 'down') return 'error';
              return 'inactive';
            })()}
          />
          {stats.revenue && (
            <FinancialRealityWidget revenue={stats.revenue} growth={stats.monthlyGrowth || 0} />
          )}
        </div>
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
          href="/pratiche/scadenze"
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
          href="/team/timesheet"
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
