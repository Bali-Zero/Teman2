'use client';

/**
 * Portal Dashboard Page
 *
 * Usa React Query per caching e ottimizzazione
 */

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  CheckCircle2,
  AlertTriangle,
  Clock,
  ChevronRight,
  FileText,
  MessageCircle,
  Briefcase,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { usePortalDashboard, usePortalTimeline } from '@/hooks';
import { PortalCardSkeleton, PortalPageLoader, PortalListSkeleton } from '@/components/portal';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import type { TimelineEntry } from '@/lib/api/types/timeline.types';

export default function PortalHomePage() {
  const router = useRouter();
  const { data: dashboard, isLoading: isLoadingDashboard, isError, error } = usePortalDashboard();
  const { data: timelineData, isLoading: isLoadingTimeline } = usePortalTimeline(20);

  const timeline = timelineData?.entries || [];
  const [showAllTimeline, setShowAllTimeline] = useState(false);
  const TIMELINE_PREVIEW_COUNT = 5;
  const visibleTimeline = showAllTimeline ? timeline : timeline.slice(0, TIMELINE_PREVIEW_COUNT);

  if (isLoadingDashboard || isLoadingTimeline) {
    return (
      <div className="space-y-8">
        <section>
          <div
            className="h-8 rounded w-48 mb-2 animate-pulse"
            style={{ background: 'var(--glass-rim)' }}
          />
          <div
            className="h-4 rounded w-64 animate-pulse"
            style={{ background: 'var(--glass-rim)' }}
          />
        </section>

        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <PortalCardSkeleton key={i} className="h-32" />
          ))}
        </section>

        <section className="space-y-4">
          <div
            className="h-6 rounded w-32 animate-pulse"
            style={{ background: 'var(--glass-rim)' }}
          />
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
          <p className="text-[var(--foreground-muted)]">Here is your Bali life overview.</p>
        </section>

        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Unable to load dashboard</AlertTitle>
          <AlertDescription>
            {error instanceof Error
              ? error.message
              : 'An unexpected error occurred. Please try again.'}
          </AlertDescription>
        </Alert>

        <Button onClick={() => window.location.reload()}>Retry</Button>
      </div>
    );
  }

  // Default empty state
  const defaultDashboard = dashboard || {
    visa: {
      status: 'none' as const,
      type: null,
      expiryDate: null,
      daysRemaining: null,
    },
    company: {
      status: 'none' as const,
      primaryCompanyName: null,
      totalCompanies: 0,
    },
    taxes: {
      status: 'compliant' as const,
      nextDeadline: null,
      daysToDeadline: null,
    },
    documents: { total: 0, pending: 0 },
    messages: { unread: 0 },
    actions: [],
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Welcome Section */}
      <section>
        <h1 className="text-3xl font-bold tracking-tight lux-text-gradient">Welcome Back</h1>
        <p className="text-[var(--tx-secondary)] mt-1">Here is your Bali life overview.</p>
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
          label={
            defaultDashboard.taxes.nextDeadline
              ? new Date(defaultDashboard.taxes.nextDeadline).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                })
              : 'All Good'
          }
          subLabel={
            defaultDashboard.taxes.daysToDeadline
              ? `${defaultDashboard.taxes.daysToDeadline} days`
              : 'Up to date'
          }
          onClick={() => router.push('/portal/taxes')}
        />
      </section>

      {/* Quick Stats Bar */}
      {(defaultDashboard.documents.pending > 0 || defaultDashboard.messages.unread > 0) && (
        <section className="flex flex-wrap gap-3">
          {defaultDashboard.documents.pending > 0 && (
            <div
              onClick={() => router.push('/portal/process')}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg border cursor-pointer transition-all hover:scale-[1.01]"
              style={{
                background: 'rgba(245,158,11,0.06)',
                borderColor: 'rgba(245,158,11,0.2)',
              }}
            >
              <FileText className="w-4 h-4 text-amber-400" />
              <span className="text-sm font-medium text-amber-400">
                {defaultDashboard.documents.pending} document
                {defaultDashboard.documents.pending !== 1 ? 's' : ''} pending
              </span>
            </div>
          )}
          {defaultDashboard.messages.unread > 0 && (
            <div
              onClick={() => router.push('/portal/messages')}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg border cursor-pointer transition-all hover:scale-[1.01]"
              style={{
                background: 'rgba(59,130,246,0.06)',
                borderColor: 'rgba(59,130,246,0.2)',
              }}
            >
              <MessageCircle className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-medium text-blue-400">
                {defaultDashboard.messages.unread} unread message
                {defaultDashboard.messages.unread !== 1 ? 's' : ''}
              </span>
            </div>
          )}
        </section>
      )}

      {/* Action Items */}
      {defaultDashboard.actions.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--bz-text-1)' }}>
            Action Required
          </h2>
          <div className="space-y-2">
            {defaultDashboard.actions.map((action) => (
              <div
                key={action.id}
                onClick={() => router.push(action.href)}
                className={cn(
                  'flex items-center justify-between p-4 rounded-lg border cursor-pointer transition-all hover:scale-[1.01]',
                  action.priority === 'high'
                    ? 'bg-[rgba(244,63,94,0.1)] border-[rgba(244,63,94,0.2)] text-[var(--neon-rose)]'
                    : action.priority === 'medium'
                      ? 'bg-[rgba(245,158,11,0.1)] border-[rgba(245,158,11,0.2)] text-[var(--neon-amber)]'
                      : 'bg-[rgba(59,130,246,0.1)] border-[rgba(59,130,246,0.2)] text-[var(--neon-blue)]'
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
        <h2 className="text-lg font-semibold flex items-center gap-2 text-[var(--tx-primary)] mb-6">
          <Clock className="w-5 h-5 text-[var(--bz-copper)]" />
          Timeline
        </h2>

        <div className="relative border-l-2 ml-3 space-y-8 pb-10 border-[var(--glass-rim)]">
          {visibleTimeline.map((entry: TimelineEntry, index: number) => (
            <TimelineItem
              key={entry.id}
              entry={entry}
              isLast={index === visibleTimeline.length - 1}
            />
          ))}

          {timeline.length === 0 && (
            <div className="pl-6 py-4 italic" style={{ color: 'var(--bz-text-2)' }}>
              No activity yet. Your journey starts here.
            </div>
          )}
        </div>

        {!showAllTimeline && timeline.length > TIMELINE_PREVIEW_COUNT && (
          <button
            onClick={() => setShowAllTimeline(true)}
            className="w-full text-center text-xs py-2 rounded-lg transition-opacity hover:opacity-80"
            style={{ color: 'var(--bz-accent-warm)', background: 'rgba(201,169,110,0.06)' }}
          >
            Show {timeline.length - TIMELINE_PREVIEW_COUNT} more events
          </button>
        )}
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
  onClick,
}: {
  title: string;
  status:
    | 'active'
    | 'warning'
    | 'expired'
    | 'pending'
    | 'none'
    | 'compliant'
    | 'attention'
    | 'overdue';
  label: string;
  subLabel?: string;
  expiry?: string | null;
  daysRemaining?: number | null;
  onClick?: () => void;
}) {
  const getStatusStyle = (s: string) => {
    switch (s) {
      case 'active':
      case 'compliant':
        return 'bg-[rgba(16,185,129,0.04)] text-[var(--neon-emerald)] border-[rgba(16,185,129,0.2)]';
      case 'warning':
      case 'attention':
        return 'bg-[rgba(245,158,11,0.04)] text-[var(--neon-amber)] border-[rgba(245,158,11,0.2)]';
      case 'expired':
      case 'overdue':
        return 'bg-[rgba(244,63,94,0.04)] text-[var(--neon-rose)] border-[rgba(244,63,94,0.2)]';
      default:
        return 'bg-[rgba(255,255,255,0.02)] text-[var(--tx-secondary)] border-[var(--glass-rim)]';
    }
  };

  const getIcon = (s: string) => {
    switch (s) {
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

  const getExpiryInfo = () => {
    if (!expiry) return { text: subLabel || '', color: '' };
    const date = new Date(expiry);
    const formatted = date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
    if (daysRemaining !== null && daysRemaining !== undefined) {
      if (daysRemaining < 0)
        return { text: `Expired ${Math.abs(daysRemaining)}d ago`, color: 'text-red-400' };
      if (daysRemaining === 0) return { text: 'Expires today', color: 'text-red-400' };
      if (daysRemaining <= 30)
        return { text: `⏰ ${daysRemaining}d left`, color: 'text-amber-400' };
      if (daysRemaining <= 90)
        return { text: `⏰ ${daysRemaining}d left`, color: 'text-yellow-300' };
    }
    return { text: `Expires: ${formatted}`, color: 'text-emerald-400' };
  };
  const expiryInfo = getExpiryInfo();

  return (
    <div
      onClick={onClick}
      className={cn(
        'crystal-stat-card cursor-pointer !flex !flex-col border transition-all duration-200 hover:scale-[1.02] hover:shadow-lg',
        getStatusStyle(status)
      )}
    >
      <div className="flex justify-between items-start mb-2">
        <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--tx-secondary)]">
          {title}
        </span>
        {getIcon(status)}
      </div>
      <div className="font-bold text-2xl font-mono text-[var(--tx-pure)] leading-tight truncate">
        {label}
      </div>
      <div
        className={cn('text-[10px] uppercase font-bold tracking-widest mt-2', expiryInfo.color)}
        title={
          expiry
            ? new Date(expiry).toLocaleDateString('en-US', {
                month: 'long',
                day: 'numeric',
                year: 'numeric',
              })
            : undefined
        }
      >
        {expiryInfo.text}
      </div>
    </div>
  );
}

function TimelineItem({ entry, isLast }: { entry: TimelineEntry; isLast: boolean }) {
  const isFuture =
    'isFuture' in entry ? Boolean((entry as unknown as { isFuture?: boolean }).isFuture) : false;

  const getIcon = () => {
    switch (entry.type) {
      case 'message':
        return <MessageCircle className="w-4 h-4" />;
      case 'document':
        return <FileText className="w-4 h-4" />;
      case 'practice':
        return <Briefcase className="w-4 h-4" />;
      case 'deadline':
        return <AlertTriangle className="w-4 h-4" />;
      default:
        return <Clock className="w-4 h-4" />;
    }
  };

  const getBgColor = () => {
    if (isFuture) return 'bg-[rgba(245,158,11,0.15)] text-[var(--neon-amber)]';
    switch (entry.type) {
      case 'message':
        return 'bg-[rgba(59,130,246,0.15)] text-[var(--neon-blue)]';
      case 'deadline':
        return 'bg-[rgba(244,63,94,0.15)] text-[var(--neon-rose)]';
      default:
        return 'text-[var(--tx-secondary)]';
    }
  };

  const getDotStyle = (): React.CSSProperties => {
    if (isFuture)
      return {
        background: 'rgba(245,158,11,0.1)',
        color: 'var(--neon-amber)',
        borderColor: 'var(--neon-amber)',
      };
    switch (entry.type) {
      case 'message':
        return {
          background: 'rgba(59,130,246,0.1)',
          color: 'var(--neon-blue)',
          borderColor: 'var(--neon-blue)',
        };
      case 'deadline':
        return {
          background: 'rgba(244,63,94,0.1)',
          color: 'var(--neon-rose)',
          borderColor: 'var(--neon-rose)',
        };
      default:
        return {
          background: 'var(--glass-rim)',
          color: 'var(--tx-secondary)',
          borderColor: 'rgba(255,255,255,0.1)',
        };
    }
  };

  return (
    <div className="relative pl-6">
      <div
        className="absolute -left-[9px] top-0 w-4 h-4 rounded-full flex items-center justify-center border-2 border-[var(--anthracite-base)] shadow-[0_0_10px_currentColor]"
        style={getDotStyle()}
      >
        {/* Dot only */}
      </div>

      <div
        className="crystal-stat-card !border !p-4 !shadow-none"
        style={{
          background: isFuture ? 'rgba(245,158,11,0.02)' : 'rgba(255,255,255,0.02)',
          borderColor: isFuture ? 'rgba(245,158,11,0.2)' : 'var(--glass-rim)',
        }}
      >
        <div className="flex items-center gap-2 mb-2">
          <div
            className={cn(
              'p-1.5 rounded-lg border border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)]',
              getBgColor()
            )}
          >
            {getIcon()}
          </div>
          <span
            className="text-[10px] font-bold uppercase tracking-widest text-[var(--tx-secondary)]"
            title={new Date(entry.occurredAt).toLocaleDateString('en-US', {
              weekday: 'long',
              month: 'long',
              day: 'numeric',
              year: 'numeric',
            })}
          >
            {new Date(entry.occurredAt).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}
            {isFuture && ' (Upcoming)'}
          </span>
          {(() => {
            const diff = Math.round((new Date(entry.occurredAt).getTime() - Date.now()) / 86400000);
            if (diff === 0)
              return (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-semibold">
                  Today
                </span>
              );
            if (diff > 0)
              return (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 font-semibold">
                  ⏰ In {diff}d
                </span>
              );
            const abs = Math.abs(diff);
            if (abs <= 7)
              return (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[rgba(255,255,255,0.05)] text-[var(--bz-text-2)] font-semibold">
                  {abs}d ago
                </span>
              );
            if (abs <= 30)
              return (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[rgba(255,255,255,0.05)] text-[var(--bz-text-2)] font-semibold">
                  {Math.floor(abs / 7)}w ago
                </span>
              );
            return null;
          })()}
        </div>

        <h3 className="font-bold text-[var(--tx-pure)] text-sm">{entry.title}</h3>
        <p className="text-xs mt-1.5 text-[var(--tx-secondary)] line-clamp-2">
          {entry.description}
        </p>

        {entry.type === 'message' && entry.status === 'team_to_client' && (
          <div className="mt-3 text-[10px] font-bold uppercase tracking-widest flex items-center text-[var(--bz-copper)] hover:text-white transition-colors cursor-pointer w-fit inline-flex">
            Reply <ChevronRight className="w-3 h-3 ml-1" />
          </div>
        )}
      </div>
    </div>
  );
}
