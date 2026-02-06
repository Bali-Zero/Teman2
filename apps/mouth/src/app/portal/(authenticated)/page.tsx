'use client';

/**
 * Portal Dashboard Page
 * 
 * Usa React Query per caching e ottimizzazione
 */

import React from 'react';
import { useRouter } from 'next/navigation';
import { 
  CheckCircle2, 
  AlertTriangle, 
  Clock, 
  ChevronRight,
  FileText,
  MessageCircle,
  Briefcase
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { usePortalDashboard, usePortalTimeline } from '@/hooks';
import { PortalCardSkeleton, PortalPageLoader } from '@/components/portal';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import type { TimelineEntry } from '@/lib/api/types/timeline.types';

export default function PortalHomePage() {
  const router = useRouter();
  const { data: dashboard, isLoading: isLoadingDashboard, isError, error } = usePortalDashboard();
  const { data: timelineData, isLoading: isLoadingTimeline } = usePortalTimeline(20);

  const timeline = timelineData?.entries || [];

  if (isLoadingDashboard || isLoadingTimeline) {
    return (
      <div className="space-y-8">
        <section>
          <div className="h-8 bg-gray-700 rounded w-48 mb-2 animate-pulse" />
          <div className="h-4 bg-gray-700 rounded w-64 animate-pulse" />
        </section>

        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <PortalCardSkeleton key={i} className="h-32" />
          ))}
        </section>

        <section className="space-y-4">
          <div className="h-6 bg-gray-700 rounded w-32 animate-pulse" />
          <PortalListSkeleton count={5} />
        </section>
      </div>
    );
  }

  // Show error state
  if (isError) {
    return (
      <div className="space-y-6">
        <section>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--foreground)]">
            Welcome Back
          </h1>
          <p className="text-[var(--foreground-muted)]">
            Here is your Bali life overview.
          </p>
        </section>

        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Unable to load dashboard</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : 'An unexpected error occurred. Please try again.'}
          </AlertDescription>
        </Alert>

        <Button onClick={() => window.location.reload()}>
          Retry
        </Button>
      </div>
    );
  }

  // Default empty state
  const defaultDashboard = dashboard || {
    visa: { status: 'none' as const, type: null, expiryDate: null, daysRemaining: null },
    company: { status: 'none' as const, primaryCompanyName: null, totalCompanies: 0 },
    taxes: { status: 'compliant' as const, nextDeadline: null, daysToDeadline: null },
    documents: { total: 0, pending: 0 },
    messages: { unread: 0 },
    actions: [],
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Welcome Section */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight text-[var(--foreground)]">
          Welcome Back
        </h1>
        <p className="text-[var(--foreground-muted)]">
          Here is your Bali life overview.
        </p>
      </section>

      {/* Status Cards (Traffic Lights) */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatusCard 
          title="Immigration"
          status={defaultDashboard.visa.status}
          label={defaultDashboard.visa.type || 'No Visa'}
          expiry={defaultDashboard.visa.expiryDate}
          daysRemaining={defaultDashboard.visa.daysRemaining}
          onClick={() => router.push('/portal/visa')}
        />
        <StatusCard 
          title="Company"
          status={defaultDashboard.company.status}
          label={defaultDashboard.company.primaryCompanyName || 'No Company'}
          subLabel={`${defaultDashboard.company.totalCompanies} compan${defaultDashboard.company.totalCompanies !== 1 ? 'ies' : 'y'}`}
          onClick={() => router.push('/portal/vault')}
        />
        <StatusCard 
          title="Tax"
          status={defaultDashboard.taxes.status}
          label={defaultDashboard.taxes.nextDeadline 
            ? new Date(defaultDashboard.taxes.nextDeadline).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) 
            : 'All Good'}
          subLabel={defaultDashboard.taxes.daysToDeadline 
            ? `${defaultDashboard.taxes.daysToDeadline} days` 
            : 'Up to date'}
          onClick={() => router.push('/portal/taxes')}
        />
      </section>

      {/* Action Items */}
      {defaultDashboard.actions.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-[var(--foreground)]">
            Action Required
          </h2>
          <div className="space-y-2">
            {defaultDashboard.actions.map((action) => (
              <div
                key={action.id}
                onClick={() => router.push(action.href)}
                className={cn(
                  "flex items-center justify-between p-4 rounded-lg border cursor-pointer transition-all hover:scale-[1.01]",
                  action.priority === 'high' 
                    ? 'bg-red-500/10 border-red-500/20 text-red-400' 
                    : action.priority === 'medium'
                    ? 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400'
                    : 'bg-blue-500/10 border-blue-500/20 text-blue-400'
                )}
              >
                <div>
                  <h3 className="font-medium">{action.title}</h3>
                  <p className="text-sm opacity-80">{action.description}</p>
                </div>
                <ChevronRight className="w-5 h-5" />
              </div>
            ))}
          </div>
        </section>
      )}

      {/* The Timeline */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold flex items-center gap-2 text-[var(--foreground)]">
          <Clock className="w-5 h-5 text-[var(--accent)]" />
          Timeline
        </h2>
        
        <div className="relative border-l-2 border-[var(--border)] ml-3 space-y-8 pb-10">
          {timeline.map((entry: TimelineEntry, index: number) => (
            <TimelineItem 
              key={entry.id} 
              entry={entry} 
              isLast={index === timeline.length - 1} 
            />
          ))}
          
          {timeline.length === 0 && (
            <div className="pl-6 py-4 text-[var(--foreground-muted)] italic">
              No activity yet. Your journey starts here.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function StatusCard({ 
  title, 
  status, 
  label, 
  subLabel, 
  expiry,
  daysRemaining,
  onClick 
}: { 
  title: string, 
  status: 'active' | 'warning' | 'expired' | 'pending' | 'none' | 'compliant' | 'attention' | 'overdue',
  label: string,
  subLabel?: string,
  expiry?: string | null,
  daysRemaining?: number | null,
  onClick?: () => void
}) {
  const getStatusColor = (s: string) => {
    switch(s) {
      case 'active':
      case 'compliant': 
        return 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20';
      case 'warning':
      case 'attention': 
        return 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20';
      case 'expired':
      case 'overdue': 
        return 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20';
      default: 
        return 'bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400 border-transparent';
    }
  };

  const getIcon = (s: string) => {
    switch(s) {
      case 'active':
      case 'compliant': 
        return <CheckCircle2 className="w-5 h-5" />;
      case 'warning':
      case 'attention':
      case 'expired':
      case 'overdue': 
        return <AlertTriangle className="w-5 h-5" />;
      default: 
        return <Clock className="w-5 h-5" />;
    }
  };

  const formatExpiry = () => {
    if (!expiry) return subLabel;
    const date = new Date(expiry);
    const formatted = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    if (daysRemaining !== null && daysRemaining !== undefined) {
      if (daysRemaining < 0) return `Expired ${Math.abs(daysRemaining)} days ago`;
      if (daysRemaining === 0) return 'Expires today';
      if (daysRemaining <= 30) return `${daysRemaining} days remaining`;
    }
    return `Expires: ${formatted}`;
  };

  return (
    <div 
      onClick={onClick}
      className={cn(
        "rounded-xl border p-4 cursor-pointer transition-all hover:scale-[1.02] active:scale-[0.98]",
        getStatusColor(status)
      )}
    >
      <div className="flex justify-between items-start mb-2">
        <span className="text-xs font-semibold uppercase tracking-wider opacity-70">{title}</span>
        {getIcon(status)}
      </div>
      <div className="font-bold text-lg leading-tight truncate">{label}</div>
      <div className="text-xs mt-1 opacity-80">
        {formatExpiry()}
      </div>
    </div>
  );
}

function TimelineItem({ entry, isLast }: { entry: TimelineEntry, isLast: boolean }) {
  const isFuture = (entry as any).isFuture;
  
  const getIcon = () => {
    switch(entry.type) {
      case 'message': return <MessageCircle className="w-4 h-4" />;
      case 'document': return <FileText className="w-4 h-4" />;
      case 'practice': return <Briefcase className="w-4 h-4" />;
      case 'deadline': return <AlertTriangle className="w-4 h-4" />;
      default: return <Clock className="w-4 h-4" />;
    }
  };

  const getBgColor = () => {
    if (isFuture) return 'bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400';
    switch(entry.type) {
      case 'message': return 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400';
      case 'deadline': return 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400';
      default: return 'bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400';
    }
  };

  return (
    <div className="relative pl-6">
      <div className={cn(
        "absolute -left-[9px] top-0 w-4 h-4 rounded-full flex items-center justify-center border-2 border-background",
        getBgColor()
      )}>
        {/* Dot only */}
      </div>
      
      <div className={cn(
        "rounded-lg border p-3 transition-colors hover:bg-muted/50",
        isFuture ? "border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/10" : "bg-card"
      )}>
        <div className="flex items-center gap-2 mb-1">
          <div className={cn("p-1 rounded-md", getBgColor())}>
            {getIcon()}
          </div>
          <span className="text-xs text-muted-foreground font-medium">
            {new Date(entry.occurredAt).toLocaleDateString(undefined, { 
              month: 'short', day: 'numeric', year: 'numeric' 
            })}
            {isFuture && " (Upcoming)"}
          </span>
        </div>
        
        <h3 className="font-semibold text-sm">{entry.title}</h3>
        <p className="text-sm text-muted-foreground mt-0.5 line-clamp-2">
          {entry.description}
        </p>

        {entry.type === 'message' && (entry.status === 'team_to_client') && (
          <div className="mt-2 text-xs font-medium text-primary flex items-center">
            Reply <ChevronRight className="w-3 h-3 ml-0.5" />
          </div>
        )}
      </div>
    </div>
  );
}

// Import for the skeleton component
import { PortalListSkeleton } from '@/components/portal';
