'use client';

import React, { useEffect, useState } from 'react';
import {
  Loader2,
  ClipboardCheck,
  AlertTriangle,
  CheckCircle,
  Clock,
  Eye,
  Calendar,
  Filter,
  Plus,
} from 'lucide-react';
import Link from 'next/link';
import { useToast } from '@/components/ui/toast';
import { logger } from '@/lib/logger';
import { lkpmApi } from '@/lib/api/workspace/lkpm.api';
import type { LKPMBatchItem, LKPMDeadline } from '@/lib/api/portal/portal.types';

const QUARTERS = ['Q1', 'Q2', 'Q3', 'Q4'] as const;
type StatusFilter = 'all' | 'draft' | 'validated' | 'approved' | 'submitted';

export default function LKPMBatchPage() {
  const { error, success } = useToast();
  const currentYear = new Date().getFullYear();
  const currentQuarter = `Q${Math.ceil((new Date().getMonth() + 1) / 3)}`;

  const [quarter, setQuarter] = useState<string>(currentQuarter);
  const [year, setYear] = useState<number>(currentYear);
  const [items, setItems] = useState<LKPMBatchItem[]>([]);
  const [deadlines, setDeadlines] = useState<LKPMDeadline[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [validatingId, setValidatingId] = useState<number | null>(null);

  useEffect(() => {
    loadData();
  }, [quarter, year]);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [batchData, deadlineData] = await Promise.all([
        lkpmApi.getBatch(quarter, year),
        lkpmApi.getDeadlines(),
      ]);
      setItems(batchData.items);
      setDeadlines(deadlineData);
    } catch (err) {
      error('Failed to load LKPM batch', 'Please try again');
      logger.error(`Failed to load LKPM batch ${quarter} ${year}`, {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleValidate = async (draftId: number) => {
    setValidatingId(draftId);
    try {
      const result = await lkpmApi.validateDraft(draftId);
      success(
        'Validation complete',
        result.is_valid ? 'All checks passed' : `${result.red_count} issues found`
      );
      loadData();
    } catch (err) {
      error('Validation failed', 'Please try again');
      logger.error(`LKPM validation failed ${draftId}`, {}, err as Error);
    } finally {
      setValidatingId(null);
    }
  };

  const handleMarkSubmitted = async (draftId: number) => {
    try {
      await lkpmApi.markSubmitted(draftId);
      success('Marked as submitted', 'LKPM report has been marked as submitted to OSS');
      loadData();
    } catch (err) {
      error('Failed to mark submitted', 'Please try again');
      logger.error(`LKPM mark submitted failed ${draftId}`, {}, err as Error);
    }
  };

  const filteredItems =
    statusFilter === 'all' ? items : items.filter((item) => item.status === statusFilter);

  const counts = {
    total: items.length,
    submitted: items.filter((i) => i.status === 'submitted').length,
    pending: items.filter((i) => i.status !== 'submitted').length,
    redAlerts: items.reduce((sum, i) => sum + i.red_alerts, 0),
  };

  const formatIDR = (amount: number) =>
    new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
    }).format(amount);

  const nextDeadline = deadlines.find((d) => d.quarter === quarter && d.year === year);

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin" style={{ color: 'var(--bz-accent-warm)' }} />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">LKPM Reports</h1>
          <p style={{ color: 'var(--bz-text-2)' }}>
            Quarterly investment activity report batch management
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/lkpm/submit"
            className="px-4 py-2 rounded-lg text-sm font-medium text-white flex items-center gap-2"
            style={{ background: 'var(--bz-accent-warm)' }}
          >
            <Plus className="w-4 h-4" />
            Submit Data
          </Link>
          <select
            value={quarter}
            onChange={(e) => setQuarter(e.target.value)}
            className="rounded-lg border px-3 py-2 text-sm backdrop-blur-md"
            style={{
              background: 'rgba(35,35,40,0.6)',
              borderColor: 'rgba(255,255,255,0.05)',
            }}
          >
            {QUARTERS.map((q) => (
              <option key={q} value={q}>
                {q}
              </option>
            ))}
          </select>
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="rounded-lg border px-3 py-2 text-sm backdrop-blur-md"
            style={{
              background: 'rgba(35,35,40,0.6)',
              borderColor: 'rgba(255,255,255,0.05)',
            }}
          >
            {[currentYear, currentYear - 1, currentYear - 2].map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>
      </section>

      {/* Red Alert Bar */}
      {counts.redAlerts > 0 && (
        <section
          className="rounded-lg border p-4 flex items-center gap-2"
          style={{
            background: 'rgba(239,68,68,0.08)',
            borderColor: 'rgba(239,68,68,0.3)',
          }}
        >
          <AlertTriangle className="w-5 h-5" style={{ color: '#f87171' }} />
          <span className="text-sm font-medium">
            {counts.redAlerts} critical alert{counts.redAlerts !== 1 ? 's' : ''} across all clients
          </span>
        </section>
      )}

      {/* Deadline Banner */}
      {nextDeadline && (
        <section
          className="rounded-lg border p-4 flex items-center gap-2"
          style={
            nextDeadline.is_overdue
              ? {
                  background: 'rgba(239,68,68,0.08)',
                  borderColor: 'rgba(239,68,68,0.3)',
                }
              : nextDeadline.days_remaining <= 14
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
              color: nextDeadline.is_overdue
                ? '#f87171'
                : nextDeadline.days_remaining <= 14
                  ? '#fbbf24'
                  : '#34d399',
            }}
          />
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm">
              {nextDeadline.is_overdue ? 'OVERDUE — Deadline was' : 'Deadline:'}
              {' '}
              {new Date(nextDeadline.deadline).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })}
            </span>
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${
                nextDeadline.is_overdue
                  ? 'bg-red-500/15 text-red-400'
                  : nextDeadline.days_remaining <= 14
                    ? 'bg-amber-500/15 text-amber-400'
                    : 'bg-emerald-500/10 text-emerald-400'
              }`}
            >
              {nextDeadline.is_overdue
                ? `${Math.abs(nextDeadline.days_remaining)}d overdue`
                : nextDeadline.days_remaining === 0
                  ? 'today'
                  : `⏰ ${nextDeadline.days_remaining}d left`}
            </span>
          </div>
        </section>
      )}

      {/* KPI Cards */}
      <section className="grid grid-cols-4 gap-4">
        <KPICard label="Total Clients" value={counts.total} icon={ClipboardCheck} />
        <KPICard label="Submitted" value={counts.submitted} icon={CheckCircle} color="#34d399" />
        <KPICard label="Pending" value={counts.pending} icon={Clock} color="#fbbf24" />
        <KPICard label="Red Alerts" value={counts.redAlerts} icon={AlertTriangle} color="#f87171" />
      </section>

      {/* Filter Bar */}
      <section className="flex items-center gap-2">
        <Filter className="w-4 h-4" style={{ color: 'var(--bz-text-2)' }} />
        {(['all', 'draft', 'validated', 'approved', 'submitted'] as const).map((filter) => (
          <button
            key={filter}
            onClick={() => setStatusFilter(filter)}
            className="px-3 py-1.5 rounded-full text-xs font-medium capitalize transition-colors"
            style={
              statusFilter === filter
                ? {
                    background:
                      'linear-gradient(135deg, var(--bz-accent-warm) 0%, rgba(212, 132, 90, 0.8) 100%)',
                    color: 'white',
                    boxShadow: '0 4px 15px rgba(212, 132, 90, 0.3)',
                  }
                : {
                    background: 'rgba(35,35,40,0.6)',
                    backdropFilter: 'blur(12px)',
                    color: 'var(--bz-text-2)',
                    border: '1px solid rgba(255,255,255,0.05)',
                  }
            }
          >
            {filter}
          </button>
        ))}
      </section>

      {/* Batch Table */}
      <section
        className="rounded-xl border shadow-2xl backdrop-blur-xl overflow-hidden"
        style={{
          background: 'linear-gradient(145deg, rgba(32,32,36,0.7) 0%, rgba(22,22,26,0.4) 100%)',
          borderColor: 'rgba(255, 255, 255, 0.05)',
        }}
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr
                className="border-b text-xs"
                style={{
                  borderColor: 'var(--bz-border)',
                  color: 'var(--bz-text-2)',
                }}
              >
                <th className="text-left px-4 py-3">Company</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-right px-4 py-3">Realized Total</th>
                <th className="text-center px-4 py-3">Alerts</th>
                <th className="text-right px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: 'var(--bz-border)' }}>
              {filteredItems.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-8 text-center text-sm"
                    style={{ color: 'var(--bz-text-2)' }}
                  >
                    No reports found for {quarter} {year}
                  </td>
                </tr>
              ) : (
                filteredItems.map((item) => (
                  <tr key={item.id} className="hover:bg-[rgba(255,255,255,0.05)] transition-colors">
                    <td className="px-4 py-3 font-medium">{item.company_name}</td>
                    <td className="px-4 py-3">
                      <BatchStatusBadge status={item.status} />
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-xs">
                      {formatIDR(item.realized_total)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        {item.red_alerts > 0 && (
                          <span
                            className="px-1.5 py-0.5 rounded text-xs font-medium"
                            style={{
                              background: 'rgba(239,68,68,0.12)',
                              color: '#f87171',
                            }}
                          >
                            {item.red_alerts}
                          </span>
                        )}
                        {item.yellow_alerts > 0 && (
                          <span
                            className="px-1.5 py-0.5 rounded text-xs font-medium"
                            style={{
                              background: 'rgba(245,158,11,0.12)',
                              color: '#fbbf24',
                            }}
                          >
                            {item.yellow_alerts}
                          </span>
                        )}
                        {item.red_alerts === 0 && item.yellow_alerts === 0 && (
                          <CheckCircle className="w-4 h-4" style={{ color: '#34d399' }} />
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        {item.status === 'draft' && (
                          <button
                            onClick={() => handleValidate(item.id)}
                            disabled={validatingId === item.id}
                            className="px-2 py-1 rounded text-xs font-medium"
                            style={{
                              background: 'rgba(59,130,246,0.12)',
                              color: '#60a5fa',
                            }}
                          >
                            {validatingId === item.id ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              'Validate'
                            )}
                          </button>
                        )}
                        {item.status === 'approved' && (
                          <button
                            onClick={() => handleMarkSubmitted(item.id)}
                            className="px-2 py-1 rounded text-xs font-medium"
                            style={{
                              background: 'rgba(16,185,129,0.12)',
                              color: '#34d399',
                            }}
                          >
                            Mark Submitted
                          </button>
                        )}
                        <Link
                          href={`/lkpm/${item.id}`}
                          className="px-2 py-1 rounded text-xs font-medium flex items-center gap-1"
                          style={{
                            background: 'rgba(255,255,255,0.05)',
                            color: 'var(--bz-text-2)',
                          }}
                        >
                          <Eye className="w-3 h-3" />
                          View
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function KPICard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: number;
  icon: React.ElementType;
  color?: string;
}) {
  return (
    <div
      className="rounded-xl border p-4 shadow-xl backdrop-blur-md transition-all duration-300 hover:shadow-2xl hover:-translate-y-1"
      style={{
        background: 'linear-gradient(145deg, rgba(35,35,40,0.6) 0%, rgba(25,25,30,0.3) 100%)',
        borderColor: 'rgba(255, 255, 255, 0.05)',
      }}
    >
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4" style={{ color: color || 'var(--bz-accent-warm)' }} />
        <span className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
          {label}
        </span>
      </div>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  );
}

function BatchStatusBadge({
  status,
}: {
  status: string;
}) {
  const config: Record<string, { label: string; style: React.CSSProperties }> = {
    draft: {
      label: 'Draft',
      style: { background: 'rgba(245,158,11,0.12)', color: '#fbbf24' },
    },
    validated: {
      label: 'Validated',
      style: { background: 'rgba(59,130,246,0.12)', color: '#60a5fa' },
    },
    client_review: {
      label: 'Client Review',
      style: { background: 'rgba(168,85,247,0.12)', color: '#a78bfa' },
    },
    approved: {
      label: 'Approved',
      style: { background: 'rgba(16,185,129,0.12)', color: '#34d399' },
    },
    submitted: {
      label: 'Submitted',
      style: { background: 'rgba(16,185,129,0.12)', color: '#34d399' },
    },
    archived: {
      label: 'Archived',
      style: { background: 'rgba(107,114,128,0.12)', color: '#9ca3af' },
    },
  };

  const { label, style } = config[status] ?? config.draft;
  return (
    <span className="px-2 py-1 rounded-full text-xs font-medium" style={style}>
      {label}
    </span>
  );
}
