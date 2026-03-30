'use client';

import React, { useEffect, useState } from 'react';
import {
  DollarSign,
  Calendar,
  AlertTriangle,
  CheckCircle,
  Clock,
  FileText,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/utils';
import { logger } from '@/lib/logger';
import type { TaxOverview, TaxObligation, TaxHistoryItem } from '@/lib/api/portal/portal.types';
import { StatusBadge } from '@/components/portal';

export default function TaxesPage() {
  const { error } = useToast();
  const [taxData, setTaxData] = useState<TaxOverview | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadTaxData();
  }, []);

  const loadTaxData = async () => {
    try {
      setIsLoading(true);
      const data = await api.portal.getTaxOverview();
      setTaxData(data);
    } catch (err) {
      error('Failed to load tax information', 'Please try again later');
      logger.error('Failed to load portal tax data', {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <section>
          <div
            className="h-7 w-40 rounded animate-pulse"
            style={{ background: 'var(--bz-border)' }}
          />
          <div
            className="h-4 w-60 rounded mt-2 animate-pulse"
            style={{ background: 'var(--bz-border)', opacity: 0.5 }}
          />
        </section>
        <div className="grid grid-cols-2 gap-3">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="rounded-xl border p-4 h-20 animate-pulse"
              style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}
            />
          ))}
        </div>
        <div
          className="rounded-xl border p-6 space-y-3 animate-pulse"
          style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}
        >
          <div className="h-5 w-36 rounded" style={{ background: 'var(--bz-border)' }} />
          {[1, 2, 3].map((i) => (
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

  if (!taxData) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <section>
          <h1 className="text-2xl font-bold tracking-tight">Tax Overview</h1>
          <p style={{ color: 'var(--bz-text-2)' }}>Your tax obligations and history</p>
        </section>
        <section
          className="rounded-xl border border-dashed p-12 text-center"
          style={{
            background: 'rgba(30,30,35,0.7)',
            borderColor: 'rgba(255,255,255,0.05)',
            backdropFilter: 'blur(24px)',
          }}
        >
          <DollarSign
            className="w-16 h-16 mx-auto mb-4 opacity-30"
            style={{ color: 'var(--bz-text-2)' }}
          />
          <h2 className="text-lg font-semibold" style={{ color: 'var(--bz-text-2)' }}>
            No tax data available
          </h2>
          <p className="text-sm mt-1" style={{ color: 'var(--bz-text-3)' }}>
            Tax information will appear here once your company is set up.
          </p>
        </section>
      </div>
    );
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
    }).format(amount);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Tax Overview</h1>
        <p style={{ color: 'var(--bz-text-2)' }}>Your tax obligations and history</p>
      </section>

      {/* Summary Card */}
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
            <DollarSign className="w-5 h-5" style={{ color: 'var(--bz-accent-warm)' }} />
            <h2 className="text-lg font-semibold">Tax Status</h2>
          </div>
          <StatusBadge status={taxData.summary.status} />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 rounded-lg" style={{ background: 'rgba(255,255,255,0.03)' }}>
            <p className="text-xs mb-1" style={{ color: 'var(--bz-text-2)' }}>
              Total Due
            </p>
            <p className="text-lg font-bold">
              {taxData.summary.totalDue > 0 ? formatCurrency(taxData.summary.totalDue) : 'Rp 0'}
            </p>
          </div>

          <div className="p-4 rounded-lg" style={{ background: 'rgba(255,255,255,0.03)' }}>
            <p className="text-xs mb-1" style={{ color: 'var(--bz-text-2)' }}>
              Next Deadline
            </p>
            {taxData.summary.nextDeadline ? (
              (() => {
                const dl = new Date(taxData.summary.nextDeadline);
                const daysLeft = Math.ceil((dl.getTime() - Date.now()) / 86400000);
                const chipColor =
                  daysLeft <= 0
                    ? 'bg-red-500/15 text-red-400'
                    : daysLeft <= 7
                      ? 'bg-red-500/10 text-red-400'
                      : daysLeft <= 30
                        ? 'bg-amber-500/10 text-amber-400'
                        : 'bg-emerald-500/10 text-emerald-400';
                const chipLabel =
                  daysLeft <= 0
                    ? `${Math.abs(daysLeft)}d overdue`
                    : daysLeft === 0
                      ? 'today'
                      : daysLeft === 1
                        ? 'tomorrow'
                        : daysLeft <= 365
                          ? `⏰ ${daysLeft}d left`
                          : `${Math.floor(daysLeft / 30)}mo left`;
                return (
                  <div className="flex items-baseline gap-2 flex-wrap">
                    <p className="text-lg font-bold">
                      {dl.toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </p>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${chipColor}`}
                    >
                      {chipLabel}
                    </span>
                  </div>
                );
              })()
            ) : (
              <p className="text-lg font-bold">None</p>
            )}
          </div>
        </div>

        {/* Days to Deadline */}
        {taxData.summary.daysToDeadline !== null && (
          <div
            className="mt-4 p-4 rounded-lg flex items-center gap-3 border"
            style={
              taxData.summary.daysToDeadline <= 7
                ? {
                    background: 'rgba(239,68,68,0.08)',
                    borderColor: 'rgba(239,68,68,0.3)',
                  }
                : taxData.summary.daysToDeadline <= 30
                  ? {
                      background: 'rgba(245,158,11,0.08)',
                      borderColor: 'rgba(245,158,11,0.3)',
                    }
                  : {
                      background: 'rgba(16,185,129,0.06)',
                      borderColor: 'rgba(16,185,129,0.25)',
                    }
            }
          >
            <Calendar
              className="w-5 h-5"
              style={{
                color:
                  taxData.summary.daysToDeadline <= 7
                    ? '#f87171'
                    : taxData.summary.daysToDeadline <= 30
                      ? '#fbbf24'
                      : '#34d399',
              }}
            />
            <div className="flex-1">
              <div className="flex items-baseline gap-2">
                <span
                  className="text-2xl font-bold font-mono"
                  style={{
                    color:
                      taxData.summary.daysToDeadline <= 7
                        ? '#f87171'
                        : taxData.summary.daysToDeadline <= 30
                          ? '#fbbf24'
                          : '#34d399',
                  }}
                >
                  {taxData.summary.daysToDeadline}
                </span>
                <span className="text-sm font-semibold" style={{ color: 'var(--bz-text-1)' }}>
                  days to deadline
                </span>
              </div>
              <p className="text-xs mt-0.5" style={{ color: 'var(--bz-text-2)' }}>
                {taxData.summary.daysToDeadline <= 7
                  ? 'Please file immediately to avoid penalties.'
                  : taxData.summary.daysToDeadline <= 30
                    ? 'Action required soon — we will remind you.'
                    : 'No immediate action required.'}
              </p>
            </div>
          </div>
        )}
      </section>

      {/* Current Obligations */}
      {taxData.obligations && taxData.obligations.length > 0 && (
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
            <h2 className="text-lg font-semibold">Current Obligations</h2>
          </div>

          <div className="space-y-3">
            {taxData.obligations.map((obligation) => (
              <ObligationCard
                key={obligation.id}
                obligation={obligation}
                formatCurrency={formatCurrency}
              />
            ))}
          </div>
        </section>
      )}

      {/* Tax History */}
      {taxData.history && taxData.history.length > 0 && (
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{
            background: 'rgba(30,30,35,0.7)',
            borderColor: 'rgba(255,255,255,0.05)',
            backdropFilter: 'blur(24px)',
          }}
        >
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5" style={{ color: 'var(--bz-accent-warm)' }} />
            <h2 className="text-lg font-semibold">Filing History</h2>
          </div>

          <div className="space-y-2">
            {taxData.history.map((item) => (
              <HistoryCard key={item.id} item={item} formatCurrency={formatCurrency} />
            ))}
          </div>
        </section>
      )}

      {/* Help Notice */}
      <section
        className="rounded-lg border p-4"
        style={{
          background: 'rgba(201,169,110,0.06)',
          borderColor: 'rgba(201,169,110,0.3)',
        }}
      >
        <p className="text-sm" style={{ color: 'var(--bz-accent-warm)' }}>
          Need help with your taxes? Contact your account manager or reach out via Chat for
          assistance.
        </p>
      </section>
    </div>
  );
}

function ObligationCard({
  obligation,
  formatCurrency,
}: {
  obligation: TaxObligation;
  formatCurrency: (amount: number) => string;
}) {
  const getStatusStyle = (status: string): React.CSSProperties => {
    switch (status) {
      case 'filed':
        return { background: 'rgba(16,185,129,0.12)', color: '#34d399' };
      case 'pending':
        return { background: 'rgba(245,158,11,0.12)', color: '#fbbf24' };
      case 'overdue':
        return { background: 'rgba(239,68,68,0.12)', color: '#f87171' };
      default:
        return {
          background: 'rgba(255,255,255,0.05)',
          color: 'var(--bz-text-2)',
        };
    }
  };

  return (
    <div
      className="rounded-lg border p-4 transition-colors"
      style={{
        background: 'rgba(255,255,255,0.03)',
        borderColor: 'rgba(255,255,255,0.05)',
      }}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-sm">{obligation.name}</h3>
          <p className="text-xs mt-0.5" style={{ color: 'var(--bz-text-2)' }}>
            {obligation.type} • {obligation.period}
          </p>
        </div>
        <span
          className="text-xs px-2 py-1 rounded-full font-medium whitespace-nowrap"
          style={getStatusStyle(obligation.status)}
        >
          {obligation.status}
        </span>
      </div>

      <div
        className="flex items-center justify-between pt-2 border-t"
        style={{ borderColor: 'var(--bz-border)' }}
      >
        <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--bz-text-2)' }}>
          <Calendar className="w-3.5 h-3.5" />
          Due:{' '}
          {new Date(obligation.dueDate).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
          })}
          {(() => {
            const daysLeft = Math.ceil(
              (new Date(obligation.dueDate).getTime() - Date.now()) / 86400000
            );
            const chipColor =
              daysLeft <= 0
                ? 'bg-red-500/15 text-red-400'
                : daysLeft <= 7
                  ? 'bg-red-500/10 text-red-400'
                  : daysLeft <= 30
                    ? 'bg-amber-500/10 text-amber-400'
                    : undefined;
            const chipLabel =
              daysLeft <= 0
                ? `${Math.abs(daysLeft)}d overdue`
                : daysLeft === 0
                  ? 'today'
                  : daysLeft <= 365
                    ? `⏰ ${daysLeft}d left`
                    : `${Math.floor(daysLeft / 30)}mo left`;
            return chipColor ? (
              <span className={`ml-1 px-1.5 py-0.5 rounded-full font-semibold ${chipColor}`}>
                {chipLabel}
              </span>
            ) : null;
          })()}
        </div>
        {obligation.amount && (
          <span className="text-sm font-bold">{formatCurrency(obligation.amount)}</span>
        )}
      </div>
    </div>
  );
}

function HistoryCard({
  item,
  formatCurrency,
}: {
  item: TaxHistoryItem;
  formatCurrency: (amount: number) => string;
}) {
  return (
    <div
      className="rounded-lg border p-3"
      style={{
        background: 'rgba(255,255,255,0.03)',
        borderColor: 'rgba(255,255,255,0.05)',
      }}
    >
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{item.name}</p>
          <p className="text-xs mt-0.5" style={{ color: 'var(--bz-text-2)' }}>
            {item.period} • Filed:{' '}
            {new Date(item.filedDate).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}
            {(() => {
              const ageDays = Math.floor(
                (Date.now() - new Date(item.filedDate).getTime()) / 86400000
              );
              if (ageDays < 7) return null;
              const label =
                ageDays >= 365
                  ? `${Math.floor(ageDays / 365)}y ago`
                  : ageDays >= 30
                    ? `${Math.floor(ageDays / 30)}mo ago`
                    : `${ageDays}d ago`;
              return (
                <span
                  className="ml-1.5 px-1.5 py-0.5 rounded-full text-[10px]"
                  style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--bz-text-3)' }}
                >
                  {label}
                </span>
              );
            })()}
          </p>
        </div>
        <div className="text-right">
          <p className="text-sm font-bold">{formatCurrency(item.amount)}</p>
          <div className="flex items-center gap-1 justify-end mt-0.5">
            <CheckCircle className="w-3 h-3" style={{ color: '#34d399' }} />
            <span className="text-xs" style={{ color: '#34d399' }}>
              Paid
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
