'use client';

import React, { useEffect, useState } from 'react';
import {
  Loader2,
  Plane,
  Calendar,
  CheckCircle,
  AlertTriangle,
  FileText,
  Clock,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/utils';
import { logger } from '@/lib/logger';
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
      logger.error('Failed to load portal visa info', {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <section>
          <div
            className="h-7 w-48 rounded animate-pulse"
            style={{ background: 'var(--bz-border)' }}
          />
          <div
            className="h-4 w-64 rounded mt-2 animate-pulse"
            style={{ background: 'var(--bz-border)', opacity: 0.5 }}
          />
        </section>
        <div
          className="rounded-xl border p-6 space-y-4 animate-pulse"
          style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}
        >
          <div className="h-5 w-32 rounded" style={{ background: 'var(--bz-border)' }} />
          <div
            className="h-10 w-full rounded"
            style={{ background: 'var(--bz-border)', opacity: 0.5 }}
          />
          <div className="grid grid-cols-2 gap-3">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-14 rounded"
                style={{ background: 'var(--bz-border)', opacity: 0.4 }}
              />
            ))}
          </div>
        </div>
        <div
          className="rounded-xl border p-6 space-y-3 animate-pulse"
          style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}
        >
          <div className="h-5 w-28 rounded" style={{ background: 'var(--bz-border)' }} />
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-16 rounded"
              style={{ background: 'var(--bz-border)', opacity: 0.4 }}
            />
          ))}
        </div>
      </div>
    );
  }

  if (!visaInfo) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <section>
          <h1 className="text-2xl font-bold tracking-tight">Immigration Status</h1>
          <p style={{ color: 'var(--bz-text-2)' }}>Your visa and permit information</p>
        </section>
        <section
          className="rounded-xl border border-dashed p-12 text-center"
          style={{
            background: 'rgba(30,30,35,0.7)',
            borderColor: 'rgba(255,255,255,0.05)',
            backdropFilter: 'blur(24px)',
          }}
        >
          <Plane
            className="w-16 h-16 mx-auto mb-4 opacity-30"
            style={{ color: 'var(--bz-text-2)' }}
          />
          <h2 className="text-lg font-semibold" style={{ color: 'var(--bz-text-2)' }}>
            No visa information
          </h2>
          <p className="text-sm mt-1" style={{ color: 'var(--bz-text-3)' }}>
            Visa details will appear here once your immigration process begins.
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Immigration Status</h1>
        <p style={{ color: 'var(--bz-text-2)' }}>Your visa and permit information</p>
      </section>

      {/* Current Visa */}
      {visaInfo.current ? (
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{
            background: 'rgba(30,30,35,0.7)',
            borderColor: 'rgba(255,255,255,0.05)',
            backdropFilter: 'blur(24px)',
          }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Plane className="w-5 h-5" style={{ color: 'var(--bz-accent-warm)' }} />
              <h2 className="text-lg font-semibold">Current Visa</h2>
            </div>
            <StatusBadge status={visaInfo.current.status} />
          </div>

          <div className="space-y-3">
            <InfoRow label="Visa Type" value={visaInfo.current.type} />
            <InfoRow label="Permit Number" value={visaInfo.current.permitNumber} />
            <InfoRow label="Sponsor" value={visaInfo.current.sponsor} />

            <div className="pt-3 border-t" style={{ borderColor: 'var(--bz-border)' }}>
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
                chip={
                  visaInfo.current.daysRemaining !== null
                    ? {
                        text:
                          visaInfo.current.daysRemaining <= 0
                            ? `Expired ${Math.abs(visaInfo.current.daysRemaining)}d ago`
                            : visaInfo.current.daysRemaining <= 365
                              ? `⏰ ${visaInfo.current.daysRemaining}d left`
                              : `${Math.floor(visaInfo.current.daysRemaining / 30)}mo left`,
                        color:
                          visaInfo.current.daysRemaining <= 0
                            ? 'bg-red-500/10 text-red-400'
                            : visaInfo.current.daysRemaining <= 60
                              ? 'bg-amber-500/10 text-amber-400'
                              : 'bg-emerald-500/10 text-emerald-400',
                      }
                    : undefined
                }
              />
            </div>
          </div>

          {/* Days Remaining Banner with 2-month Alert */}
          {visaInfo.current.daysRemaining !== null && (
            <div
              className={cn(
                'mt-4 p-4 rounded-lg flex items-start gap-3 border',
                visaInfo.current.daysRemaining <= 60 && 'animate-pulse border-2'
              )}
              style={
                visaInfo.current.daysRemaining <= 60
                  ? {
                      background: 'rgba(239,68,68,0.08)',
                      borderColor: 'rgba(239,68,68,0.4)',
                    }
                  : {
                      background: 'rgba(16,185,129,0.06)',
                      borderColor: 'rgba(16,185,129,0.25)',
                    }
              }
            >
              <Clock
                className="w-5 h-5 mt-0.5"
                style={{
                  color: visaInfo.current.daysRemaining <= 60 ? '#f87171' : '#34d399',
                }}
              />
              <div className="flex-1">
                <div className="flex items-baseline gap-2">
                  <span
                    className="text-2xl font-bold font-mono"
                    style={{
                      color: visaInfo.current.daysRemaining <= 60 ? '#f87171' : '#34d399',
                    }}
                  >
                    {visaInfo.current.daysRemaining}
                  </span>
                  <span
                    className="text-sm font-semibold"
                    style={{
                      color: visaInfo.current.daysRemaining <= 60 ? '#f87171' : '#34d399',
                    }}
                  >
                    days remaining
                  </span>
                </div>
                <p
                  className="text-xs mt-1"
                  style={{
                    color: visaInfo.current.daysRemaining <= 60 ? '#f87171' : 'var(--bz-text-2)',
                    fontWeight: visaInfo.current.daysRemaining <= 60 ? 500 : 400,
                  }}
                >
                  {visaInfo.current.daysRemaining <= 60
                    ? 'Your visa expires in less than 2 months. Please contact us immediately to begin renewal.'
                    : 'Your visa is valid. We will notify you when renewal is needed.'}
                </p>
              </div>
            </div>
          )}
        </section>
      ) : (
        <section
          className="rounded-xl border border-dashed p-8 text-center"
          style={{
            background: 'rgba(30,30,35,0.7)',
            borderColor: 'rgba(255,255,255,0.05)',
            backdropFilter: 'blur(24px)',
          }}
        >
          <Plane
            className="w-12 h-12 mx-auto mb-3 opacity-30"
            style={{ color: 'var(--bz-text-2)' }}
          />
          <p style={{ color: 'var(--bz-text-2)' }}>No active visa information</p>
        </section>
      )}

      {/* Documents */}
      {visaInfo.documents && visaInfo.documents.length > 0 && (
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{
            background: 'rgba(30,30,35,0.7)',
            borderColor: 'rgba(255,255,255,0.05)',
            backdropFilter: 'blur(24px)',
          }}
        >
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5" style={{ color: 'var(--bz-accent-warm)' }} />
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
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{
            background: 'rgba(30,30,35,0.7)',
            borderColor: 'rgba(255,255,255,0.05)',
            backdropFilter: 'blur(24px)',
          }}
        >
          <div className="flex items-center gap-2">
            <Calendar className="w-5 h-5" style={{ color: 'var(--bz-accent-warm)' }} />
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
function StatusBadge({ status }: { status: 'active' | 'pending' | 'warning' | 'expired' }) {
  const config: Record<
    string,
    { icon: React.ElementType; label: string; style: React.CSSProperties }
  > = {
    active: {
      icon: CheckCircle,
      label: 'Active',
      style: { background: 'rgba(16,185,129,0.12)', color: '#34d399' },
    },
    pending: {
      icon: Clock,
      label: 'Pending',
      style: { background: 'rgba(245,158,11,0.12)', color: '#fbbf24' },
    },
    warning: {
      icon: AlertTriangle,
      label: 'Expiring Soon',
      style: { background: 'rgba(245,158,11,0.12)', color: '#fbbf24' },
    },
    expired: {
      icon: AlertTriangle,
      label: 'Expired',
      style: { background: 'rgba(239,68,68,0.12)', color: '#f87171' },
    },
  };

  const { icon: Icon, label, style } = config[status] ?? config.pending;

  return (
    <div
      className="px-3 py-1.5 rounded-full flex items-center gap-1.5 text-xs font-medium"
      style={style}
    >
      <Icon className="w-3.5 h-3.5" />
      {label}
    </div>
  );
}

function InfoRow({
  label,
  value,
  chip,
}: {
  label: string;
  value: string;
  chip?: { text: string; color: string };
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-sm" style={{ color: 'var(--bz-text-2)' }}>
        {label}
      </span>
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-right">{value}</span>
        {chip && (
          <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${chip.color}`}>
            {chip.text}
          </span>
        )}
      </div>
    </div>
  );
}

function DocumentCard({ document }: { document: PortalDocument }) {
  const getStatusStyle = (status: string): React.CSSProperties => {
    switch (status) {
      case 'verified':
        return { background: 'rgba(16,185,129,0.12)', color: '#34d399' };
      case 'pending':
        return { background: 'rgba(245,158,11,0.12)', color: '#fbbf24' };
      case 'expired':
        return { background: 'rgba(239,68,68,0.12)', color: '#f87171' };
      default:
        return {
          background: 'rgba(255,255,255,0.03)',
          color: 'var(--bz-text-2)',
        };
    }
  };

  return (
    <div
      className="rounded-lg border p-3 transition-colors"
      style={{
        background: 'rgba(255,255,255,0.03)',
        borderColor: 'rgba(255,255,255,0.05)',
      }}
    >
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-md" style={{ background: 'rgba(201,169,110,0.1)' }}>
          <FileText className="w-4 h-4" style={{ color: 'var(--bz-accent-warm)' }} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{document.name}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <span
              className="text-xs px-2 py-0.5 rounded-full font-medium"
              style={getStatusStyle(document.status)}
            >
              {document.status}
            </span>
            <span className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
              {document.size}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function HistoryCard({ item }: { item: VisaHistoryItem }) {
  const statusStyle = (() => {
    const s = item.status?.toLowerCase();
    if (s === 'active' || s === 'approved' || s === 'completed')
      return { background: 'rgba(16,185,129,0.12)', color: '#34d399' };
    if (s === 'expired' || s === 'rejected' || s === 'cancelled')
      return { background: 'rgba(239,68,68,0.12)', color: '#f87171' };
    if (s === 'pending' || s === 'processing')
      return { background: 'rgba(245,158,11,0.12)', color: '#fbbf24' };
    return { background: 'rgba(255,255,255,0.05)', color: 'var(--bz-text-2)' };
  })();

  return (
    <div
      className="rounded-lg border p-3 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
      style={{
        background: 'rgba(255,255,255,0.03)',
        borderColor: 'rgba(255,255,255,0.05)',
      }}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium">{item.type}</p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--bz-text-2)' }}>
            {item.period}
          </p>
        </div>
        <span className="text-xs px-2 py-1 rounded-full font-medium" style={statusStyle}>
          {item.status}
        </span>
      </div>
    </div>
  );
}
