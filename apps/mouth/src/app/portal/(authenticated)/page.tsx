'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { 
  Loader2, 
  CheckCircle2, 
  AlertTriangle, 
  Clock, 
  ChevronRight,
  FileText,
  MessageCircle,
  Briefcase
} from 'lucide-react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import type { PortalDashboard } from '@/lib/api/portal/portal.types';
import type { TimelineEntry } from '@/lib/api/types/timeline.types';

export default function PortalHomePage() {
  const router = useRouter();
  const [dashboard, setDashboard] = useState<PortalDashboard | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [dashData, timelineData] = await Promise.all([
          api.portal.getDashboard(),
          api.portal.getTimeline(20)
        ]);
        setDashboard(dashData);
        setTimeline(timelineData.entries);
      } catch (error) {
        console.error('Failed to load portal data', error);
        setHasError(true);
        // If 401/403, middleware/interceptor should handle redirect, 
        // but as a fallback:
        // router.push('/login'); 
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, [router]);

  if (isLoading) {
    return (
      <div className="space-y-8">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
          {[1, 2, 3].map((i) => (
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

  // Show content even if dashboard is null (API errors)
  const defaultDashboard: PortalDashboard = dashboard || {
    visa: { status: 'none', type: null, expiryDate: null, daysRemaining: null },
    company: { status: 'none', primaryCompanyName: null, totalCompanies: 0 },
    taxes: { status: 'compliant', nextDeadline: null, daysToDeadline: null },
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

      {/* Error Message if API failed */}
      {hasError && (
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-4">
          <h3 className="font-semibold text-amber-500">Unable to Load Dashboard Data</h3>
          <p className="text-sm text-amber-500/80 mt-1">
            Some features may be limited. Please try refreshing the page.
          </p>
        </div>
      )}

      {/* Status Cards (Traffic Lights) */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatusCard 
          title="Immigration"
          status={defaultDashboard.visa.status}
          label={defaultDashboard.visa.type || 'No Visa'}
          expiry={defaultDashboard.visa.expiryDate}
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
          label={defaultDashboard.taxes.nextDeadline ? new Date(defaultDashboard.taxes.nextDeadline).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : 'All Good'}
          subLabel={defaultDashboard.taxes.daysToDeadline ? `${defaultDashboard.taxes.daysToDeadline} days` : 'Up to date'}
          onClick={() => router.push('/portal/taxes')}
        />
      </section>

      {/* The Timeline */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold flex items-center gap-2 text-[var(--foreground)]">
          <Clock className="w-5 h-5 text-[var(--accent)]" />
          Timeline
        </h2>
        
        <div className="relative border-l-2 border-[var(--border)] ml-3 space-y-8 pb-10">
          {timeline.map((entry, index) => (
            <TimelineItem key={entry.id} entry={entry} isLast={index === timeline.length - 1} />
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

// Sub-components

function StatusCard({ 
  title, 
  status, 
  label, 
  subLabel, 
  expiry,
  onClick 
}: { 
  title: string, 
  status: 'active' | 'warning' | 'expired' | 'pending' | 'none' | 'compliant' | 'attention' | 'overdue',
  label: string,
  subLabel?: string,
  expiry?: string | null,
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
      <div className="font-bold text-lg leading-tight">{label}</div>
      {(subLabel || expiry) && (
        <div className="text-xs mt-1 opacity-80">
          {subLabel}
          {expiry && `Expires: ${new Date(expiry).toLocaleDateString()}`}
        </div>
      )}
    </div>
  );
}

function TimelineItem({ entry, isLast }: { entry: TimelineEntry, isLast: boolean }) {
  const isFuture = (entry as any).isFuture; // Type assertion since we just added this field
  
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
