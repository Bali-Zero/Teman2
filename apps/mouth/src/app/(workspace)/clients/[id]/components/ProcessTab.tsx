'use client';

import React, { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  Plus,
  FolderOpen,
  Calendar,
  Eye,
  Trash2,
  DollarSign,
  ArrowUpCircle,
  ArrowDownCircle,
  MinusCircle,
  SlidersHorizontal,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import type { ClientProfile } from '@/lib/api/crm/crm.types';
import { STATUS_COLORS, ALERT_COLORS } from './constants';
import { formatCurrency } from './utils';

const PRIORITY_STYLES: Record<string, { icon: typeof ArrowUpCircle; color: string }> = {
  urgent: { icon: ArrowUpCircle, color: 'text-red-500' },
  high: { icon: ArrowUpCircle, color: 'text-orange-400' },
  medium: { icon: MinusCircle, color: 'text-yellow-400' },
  low: { icon: ArrowDownCircle, color: 'text-blue-400' },
};

const PAYMENT_STYLES: Record<string, string> = {
  paid: 'bg-green-500/20 text-green-400',
  partial: 'bg-yellow-500/20 text-yellow-400',
  unpaid: 'bg-red-500/20 text-red-400',
  pending: 'bg-orange-500/20 text-orange-400',
};

export function ProcessTab({
  clientId,
  practices,
  formatDate,
  onRefresh,
}: {
  clientId: number;
  practices: ClientProfile['practices'];
  formatDate: (d: string) => string;
  onRefresh: () => void;
}) {
  const router = useRouter();
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set());
  const [sortBy, setSortBy] = useState<'default' | 'priority' | 'expiry' | 'amount'>('default');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  const activeStatuses = Array.from(new Set(practices.map((p) => p.status)));

  const revenueSummary = useMemo(() => {
    const total = practices.reduce((sum, p) => sum + (p.actual_price || p.quoted_price || 0), 0);
    const paid = practices
      .filter((p) => p.payment_status === 'paid')
      .reduce((sum, p) => sum + (p.actual_price || p.quoted_price || 0), 0);
    const outstanding = total - paid;
    return { total, paid, outstanding };
  }, [practices]);

  const sortedPractices = useMemo(() => {
    let list = [...practices];
    if (filterStatus !== 'all') list = list.filter((p) => p.status === filterStatus);
    if (sortBy === 'priority') {
      const order: Record<string, number> = { urgent: 0, high: 1, medium: 2, normal: 3, low: 4 };
      list.sort((a, b) => (order[a.priority || 'normal'] ?? 3) - (order[b.priority || 'normal'] ?? 3));
    } else if (sortBy === 'expiry') {
      list.sort((a, b) => {
        if (!a.expiry_date) return 1;
        if (!b.expiry_date) return -1;
        return new Date(a.expiry_date).getTime() - new Date(b.expiry_date).getTime();
      });
    } else if (sortBy === 'amount') {
      list.sort((a, b) => {
        const aAmt = a.actual_price || a.quoted_price || 0;
        const bAmt = b.actual_price || b.quoted_price || 0;
        return bAmt - aAmt;
      });
    }
    return list;
  }, [practices, sortBy, filterStatus]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--bz-text-1)]">
          All Process
          {filterStatus !== 'all' && (
            <span className="ml-2 text-xs text-[var(--bz-text-2)] font-normal">
              ({sortedPractices.length} of {practices.length})
            </span>
          )}
        </h3>
        <Button
          size="sm"
          className="gap-2"
          onClick={() => router.push(`/process/new?client_id=${clientId}`)}
        >
          <Plus className="w-4 h-4" />
          New Process
        </Button>
      </div>

      {/* Revenue Summary Bar */}
      {practices.length > 0 && revenueSummary.total > 0 && (
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-lg bg-[var(--bz-surface)] border border-[var(--bz-border)] p-3">
            <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-0.5">
              Total Value
            </p>
            <p className="text-sm font-bold text-[var(--bz-text-1)]">
              {formatCurrency(revenueSummary.total)}
            </p>
          </div>
          <div className="rounded-lg bg-green-500/10 border border-green-500/20 p-3">
            <p className="text-[10px] uppercase tracking-wider text-green-400 mb-0.5">Paid</p>
            <p className="text-sm font-bold text-green-400">
              {formatCurrency(revenueSummary.paid)}
            </p>
          </div>
          <div
            className={`rounded-lg p-3 border ${revenueSummary.outstanding > 0 ? 'bg-orange-500/10 border-orange-500/20' : 'bg-[var(--bz-surface)] border-[var(--bz-border)]'}`}
          >
            <p
              className={`text-[10px] uppercase tracking-wider mb-0.5 ${revenueSummary.outstanding > 0 ? 'text-orange-400' : 'text-[var(--bz-text-2)]'}`}
            >
              Outstanding
            </p>
            <p
              className={`text-sm font-bold ${revenueSummary.outstanding > 0 ? 'text-orange-400' : 'text-[var(--bz-text-1)]'}`}
            >
              {formatCurrency(revenueSummary.outstanding)}
            </p>
          </div>
        </div>
      )}

      {practices.length > 1 && (
        <div className="flex items-center gap-2 flex-wrap">
          <SlidersHorizontal className="w-3.5 h-3.5 text-[var(--bz-text-2)] shrink-0" />
          <div className="flex items-center gap-1 flex-wrap">
            {(['all', ...activeStatuses] as string[]).map((s) => (
              <button
                key={s}
                onClick={() => setFilterStatus(s)}
                className={`text-xs px-2 py-1 rounded-full transition-colors ${
                  filterStatus === s
                    ? 'bg-[var(--bz-accent)] text-white'
                    : 'bg-[var(--bz-surface)] text-[var(--bz-text-2)] hover:bg-[var(--bz-card)]'
                }`}
              >
                {s === 'all' ? 'All' : s.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-1">
            {(['default', 'priority', 'expiry', 'amount'] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSortBy(s)}
                className={`text-xs px-2 py-1 rounded transition-colors ${
                  sortBy === s
                    ? 'bg-[var(--bz-accent)]/20 text-[var(--bz-accent)]'
                    : 'text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)]'
                }`}
              >
                {s === 'default' ? 'Date' : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
        </div>
      )}

      {practices.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[rgba(255,255,255,0.1)] bg-[rgba(26,26,30,0.5)] backdrop-blur-sm p-12 text-center shadow-xl">
          <FolderOpen className="w-12 h-12 mx-auto text-[var(--bz-text-2)] mb-3 opacity-50" />
          <p className="text-[var(--bz-text-2)]">No process yet</p>
        </div>
      ) : sortedPractices.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[rgba(255,255,255,0.1)] bg-[rgba(26,26,30,0.5)] backdrop-blur-sm p-8 text-center">
          <p className="text-[var(--bz-text-2)] text-sm">No processes match this filter</p>
          <button
            onClick={() => setFilterStatus('all')}
            className="text-xs text-[var(--bz-accent)] mt-2 hover:underline"
          >
            Clear filter
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {sortedPractices.map((practice) => (
            <div
              key={practice.id}
              className="rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] p-4 hover:border-[var(--bz-accent)]/50 transition-colors group"
            >
              <div className="flex items-center justify-between mb-2">
                <div
                  className="flex-1 cursor-pointer min-w-0"
                  onClick={() => router.push(`/process/${practice.id}`)}
                >
                  <div className="flex items-center gap-2">
                    {practice.priority &&
                      PRIORITY_STYLES[practice.priority] &&
                      (() => {
                        const { icon: PIcon, color } = PRIORITY_STYLES[practice.priority!];
                        return <PIcon className={`w-3.5 h-3.5 shrink-0 ${color}`} />;
                      })()}
                    <span className="text-sm font-medium text-[var(--bz-text-1)] truncate">
                      {practice.practice_type_name}
                    </span>
                    <span className="text-xs text-[var(--bz-text-2)] shrink-0">#{practice.id}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span
                    className={`text-xs px-2 py-1 rounded-full ${
                      STATUS_COLORS[practice.status] || 'bg-gray-500/20 text-gray-400'
                    }`}
                  >
                    {practice.status.replace(/_/g, ' ')}
                  </span>
                  {/* View/Delete buttons - show on hover */}
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        router.push(`/process/${practice.id}`);
                      }}
                      className="p-1 rounded hover:bg-[var(--bz-card)] text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)]"
                      title="View process"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        if (deletingIds.has(practice.id)) return;
                        if (
                          !window.confirm(
                            `Delete process "${practice.practice_type_name}"?\n\nThis will mark the process as cancelled.`
                          )
                        )
                          return;
                        setDeletingIds((prev) => new Set(prev).add(practice.id));
                        try {
                          const user = await api.getProfile();
                          await api.crm.deletePractice(practice.id, user.email);
                          toast.success('Process deleted');
                          onRefresh();
                        } catch (err) {
                          toast.error('Error', {
                            description: (err as Error).message,
                          });
                          setDeletingIds((prev) => {
                            const next = new Set(prev);
                            next.delete(practice.id);
                            return next;
                          });
                        }
                      }}
                      disabled={deletingIds.has(practice.id)}
                      className="p-1 rounded hover:bg-red-500/20 text-[var(--bz-text-2)] hover:text-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
                      title="Delete process"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-wrap mt-1">
                {practice.expiry_date && (
                  <div
                    className={`text-xs inline-flex items-center gap-1 px-2 py-0.5 rounded ${
                      ALERT_COLORS[practice.alert_color || 'green']
                    }`}
                  >
                    <Calendar className="w-3 h-3" />
                    Expires: {formatDate(practice.expiry_date)}
                  </div>
                )}
                {(practice.quoted_price || practice.actual_price) && (
                  <div className="text-xs inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[var(--bz-base)] text-[var(--bz-text-2)]">
                    <DollarSign className="w-3 h-3" />
                    {practice.actual_price
                      ? formatCurrency(practice.actual_price)
                      : formatCurrency(practice.quoted_price!)}
                  </div>
                )}
                {practice.payment_status && (
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${
                      PAYMENT_STYLES[practice.payment_status] || 'bg-gray-500/20 text-gray-400'
                    }`}
                  >
                    {practice.payment_status}
                  </span>
                )}
                {practice.updated_at &&
                  (() => {
                    const ageDays = Math.floor(
                      (Date.now() - new Date(practice.updated_at!).getTime()) / 86400000
                    );
                    if (ageDays < 2) return null;
                    const label =
                      ageDays >= 30
                        ? `${Math.floor(ageDays / 30)}mo`
                        : ageDays >= 7
                          ? `${Math.floor(ageDays / 7)}w`
                          : `${ageDays}d`;
                    return (
                      <span
                        className="text-[10px] px-1.5 py-0.5 rounded tabular-nums"
                        style={{
                          background:
                            ageDays > 14 ? 'rgba(239,68,68,0.10)' : 'rgba(255,255,255,0.04)',
                          color: ageDays > 14 ? '#f87171' : 'var(--bz-text-2)',
                        }}
                        title={`Last updated ${ageDays} days ago`}
                      >
                        {label} ago
                      </span>
                    );
                  })()}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
