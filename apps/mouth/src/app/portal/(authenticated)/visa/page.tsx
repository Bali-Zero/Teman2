'use client';

import React, { useEffect, useState } from 'react';
import { Loader2, Plane, Calendar, CheckCircle, AlertTriangle, FileText, Clock } from 'lucide-react';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/utils';
import type { VisaInfo, VisaHistoryItem, PortalDocument } from '@/lib/api/portal/portal.types';

export default function VisaPage() {
  const { error } = useToast();
  const [visaInfo, setVisaInfo] = useState<VisaInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadVisaInfo();
  }, []);

  const loadVisaInfo = async () => {
    try {
      setIsLoading(true);
      const data = await api.portal.getVisaStatus();
      setVisaInfo(data);
    } catch (err) {
      error('Failed to load visa information', 'Please try again later');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!visaInfo) return null;

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Immigration Status</h1>
        <p className="text-muted-foreground">Your visa and permit information</p>
      </section>

      {/* Current Visa */}
      {visaInfo.current ? (
        <section className="rounded-xl border bg-card p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Plane className="w-5 h-5 text-primary" />
              <h2 className="text-lg font-semibold">Current Visa</h2>
            </div>
            <StatusBadge status={visaInfo.current.status} />
          </div>

          <div className="space-y-3">
            <InfoRow label="Visa Type" value={visaInfo.current.type} />
            <InfoRow label="Permit Number" value={visaInfo.current.permitNumber} />
            <InfoRow label="Sponsor" value={visaInfo.current.sponsor} />
            
            <div className="pt-3 border-t">
              <InfoRow
                label="Issue Date"
                value={new Date(visaInfo.current.issueDate).toLocaleDateString('en-US', {
                  month: 'long',
                  day: 'numeric',
                  year: 'numeric',
                })}
              />
              <InfoRow
                label="Expiry Date"
                value={new Date(visaInfo.current.expiryDate).toLocaleDateString('en-US', {
                  month: 'long',
                  day: 'numeric',
                  year: 'numeric',
                })}
              />
            </div>
          </div>

          {/* Days Remaining Banner */}
          {visaInfo.current.daysRemaining !== null && (
            <div
              className={cn(
                'mt-4 p-4 rounded-lg flex items-center gap-3',
                visaInfo.current.daysRemaining <= 30
                  ? 'bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800'
                  : visaInfo.current.daysRemaining <= 60
                  ? 'bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800'
                  : 'bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800'
              )}
            >
              <Clock
                className={cn(
                  'w-5 h-5',
                  visaInfo.current.daysRemaining <= 30
                    ? 'text-red-600 dark:text-red-400'
                    : visaInfo.current.daysRemaining <= 60
                    ? 'text-amber-600 dark:text-amber-400'
                    : 'text-emerald-600 dark:text-emerald-400'
                )}
              />
              <div className="flex-1">
                <p className="text-sm font-semibold">
                  {visaInfo.current.daysRemaining} days remaining
                </p>
                <p className="text-xs text-muted-foreground">
                  {visaInfo.current.daysRemaining <= 30
                    ? 'Please contact us to renew your visa'
                    : visaInfo.current.daysRemaining <= 60
                    ? 'Renewal recommended soon'
                    : 'Your visa is valid'}
                </p>
              </div>
            </div>
          )}
        </section>
      ) : (
        <section className="rounded-xl border border-dashed bg-card p-8 text-center">
          <Plane className="w-12 h-12 mx-auto mb-3 text-muted-foreground opacity-30" />
          <p className="text-muted-foreground">No active visa information</p>
        </section>
      )}

      {/* Documents */}
      {visaInfo.documents && visaInfo.documents.length > 0 && (
        <section className="rounded-xl border bg-card p-6 space-y-4">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold">Related Documents</h2>
          </div>

          <div className="space-y-2">
            {visaInfo.documents.map((doc) => (
              <DocumentCard key={doc.id} document={doc} />
            ))}
          </div>
        </section>
      )}

      {/* History */}
      {visaInfo.history && visaInfo.history.length > 0 && (
        <section className="rounded-xl border bg-card p-6 space-y-4">
          <div className="flex items-center gap-2">
            <Calendar className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold">Visa History</h2>
          </div>

          <div className="space-y-3">
            {visaInfo.history.map((item) => (
              <HistoryCard key={item.id} item={item} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// Sub-components
function StatusBadge({ status }: { status: 'active' | 'pending' | 'expired' }) {
  const config = {
    active: {
      icon: CheckCircle,
      label: 'Active',
      className: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
    },
    pending: {
      icon: Clock,
      label: 'Pending',
      className: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    },
    expired: {
      icon: AlertTriangle,
      label: 'Expired',
      className: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    },
  };

  const { icon: Icon, label, className } = config[status];

  return (
    <div className={cn('px-3 py-1.5 rounded-full flex items-center gap-1.5 text-xs font-medium', className)}>
      <Icon className="w-3.5 h-3.5" />
      {label}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium text-right">{value}</span>
    </div>
  );
}

function DocumentCard({ document }: { document: PortalDocument }) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'verified':
        return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400';
      case 'pending':
        return 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400';
      case 'expired':
        return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400';
      default:
        return 'bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-400';
    }
  };

  return (
    <div className="rounded-lg border p-3 hover:bg-muted/50 transition-colors">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-md bg-primary/10">
          <FileText className="w-4 h-4 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{document.name}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium', getStatusColor(document.status))}>
              {document.status}
            </span>
            <span className="text-xs text-muted-foreground">{document.size}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function HistoryCard({ item }: { item: VisaHistoryItem }) {
  return (
    <div className="rounded-lg border p-3 bg-neutral-50 dark:bg-neutral-900">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium">{item.type}</p>
          <p className="text-xs text-muted-foreground mt-0.5">{item.period}</p>
        </div>
        <span
          className={cn(
            'text-xs px-2 py-1 rounded-full font-medium',
            item.status === 'completed'
              ? 'bg-neutral-200 text-neutral-700 dark:bg-neutral-700 dark:text-neutral-300'
              : 'bg-neutral-300 text-neutral-800 dark:bg-neutral-600 dark:text-neutral-200'
          )}
        >
          {item.status}
        </span>
      </div>
    </div>
  );
}
