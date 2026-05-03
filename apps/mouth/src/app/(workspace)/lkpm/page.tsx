'use client';

import React, { useCallback, useEffect, useState } from 'react';
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
  Key,
  KeyRound,
  Copy,
} from 'lucide-react';
import Link from 'next/link';
import { useToast } from '@/components/ui/toast';
import { logger } from '@/lib/logger';
import { lkpmApi } from '@/lib/api/workspace/lkpm.api';
import type {
  LKPMBatchItem,
  LKPMDeadline,
  LKPMOSSCredentials,
} from '@/lib/api/portal/portal.types';

// Tax consultants — kept in sync with backend migration 093.
const TAX_CONSULTANTS: { value: string; label: string }[] = [
  { value: 'veronika.tax@balizero.com', label: 'Veronika' },
  { value: 'kadek.tax@balizero.com', label: 'Kadek' },
  { value: 'dewaayu.tax@balizero.com', label: 'Dewa Ayu' },
  { value: 'angel.tax@balizero.com', label: 'Angel' },
  { value: 'faisha.tax@balizero.com', label: 'Faisha' },
];

const consultantLabel = (email: string | null | undefined) =>
  email ? TAX_CONSULTANTS.find((c) => c.value === email)?.label ?? email.split('@')[0] : null;

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
  const [assigningId, setAssigningId] = useState<number | null>(null);
  const [credsLoadingId, setCredsLoadingId] = useState<number | null>(null);
  // draft_id -> credentials object (shown inline below the row)
  const [openCreds, setOpenCreds] = useState<Record<number, LKPMOSSCredentials>>({});

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

  const handleAssign = async (draftId: number, newAssignee: string) => {
    const value = newAssignee === '' ? null : newAssignee;
    setAssigningId(draftId);
    // Optimistic update
    setItems((prev) =>
      prev.map((it) => (it.id === draftId ? { ...it, lkpm_assigned_to: value } : it)),
    );
    try {
      await lkpmApi.assignReport(draftId, value);
      success(
        'Assignment updated',
        value ? `Assigned to ${consultantLabel(value)}` : 'Assignment cleared',
      );
    } catch (err) {
      error('Failed to update assignment', 'Please try again');
      logger.error(`LKPM assign failed ${draftId}`, {}, err as Error);
      loadData(); // refresh to revert optimistic change
    } finally {
      setAssigningId(null);
    }
  };

  const handleToggleCreds = async (item: LKPMBatchItem) => {
    // Toggle closed if already open
    if (openCreds[item.id]) {
      setOpenCreds((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
      return;
    }
    setCredsLoadingId(item.id);
    try {
      const creds = await lkpmApi.getCredentials(item.client_id);
      setOpenCreds((prev) => ({ ...prev, [item.id]: creds }));
    } catch (err) {
      error('Failed to load credentials', (err as Error).message || 'Check access rights');
      logger.error(`LKPM creds fetch failed client=${item.client_id}`, {}, err as Error);
    } finally {
      setCredsLoadingId(null);
    }
  };

  const handleCopy = useCallback(
    async (text: string, label: string) => {
      try {
        await navigator.clipboard.writeText(text);
        success('Copied', `${label} copied to clipboard`);
      } catch {
        error('Copy failed', 'Your browser blocked clipboard access');
      }
    },
    [success, error],
  );

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
                <th className="text-left px-4 py-3">Assigned to</th>
                <th className="text-center px-4 py-3">OSS</th>
                <th className="text-right px-4 py-3">Realized Total</th>
                <th className="text-center px-4 py-3">Alerts</th>
                <th className="text-right px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: 'var(--bz-border)' }}>
              {filteredItems.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-4 py-8 text-center text-sm"
                    style={{ color: 'var(--bz-text-2)' }}
                  >
                    No reports found for {quarter} {year}
                  </td>
                </tr>
              ) : (
                filteredItems.map((item) => (
                  <React.Fragment key={item.id}>
                  <tr className="hover:bg-[rgba(255,255,255,0.05)] transition-colors">
                    <td className="px-4 py-3 font-medium">{item.company_name}</td>
                    <td className="px-4 py-3">
                      <BatchStatusBadge status={item.status} />
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={item.lkpm_assigned_to ?? ''}
                        onChange={(e) => handleAssign(item.id, e.target.value)}
                        disabled={assigningId === item.id}
                        className="rounded border px-2 py-1 text-xs backdrop-blur-md"
                        style={{
                          background: 'rgba(35,35,40,0.6)',
                          borderColor: 'rgba(255,255,255,0.05)',
                          color: item.lkpm_assigned_to ? 'var(--bz-text-1)' : 'var(--bz-text-2)',
                        }}
                        aria-label={`Assign ${item.company_name} tax consultant`}
                      >
                        <option value="">— none —</option>
                        {TAX_CONSULTANTS.map((c) => (
                          <option key={c.value} value={c.value}>
                            {c.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <button
                        onClick={() => handleToggleCreds(item)}
                        disabled={credsLoadingId === item.id}
                        className="px-2 py-1 rounded text-xs font-medium inline-flex items-center gap-1"
                        style={{
                          background: openCreds[item.id]
                            ? 'rgba(212, 132, 90, 0.2)'
                            : 'rgba(255,255,255,0.05)',
                          color: openCreds[item.id] ? '#d4845a' : 'var(--bz-text-2)',
                        }}
                        aria-label="Show OSS credentials"
                        aria-expanded={!!openCreds[item.id]}
                      >
                        {credsLoadingId === item.id ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : openCreds[item.id] ? (
                          <>
                            <KeyRound className="w-3 h-3" />
                            Hide
                          </>
                        ) : (
                          <>
                            <Key className="w-3 h-3" />
                            Show
                          </>
                        )}
                      </button>
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
                  {openCreds[item.id] && (
                    <tr>
                      <td
                        colSpan={7}
                        className="px-4 py-3"
                        style={{
                          background: 'rgba(212, 132, 90, 0.06)',
                          borderLeft: '3px solid var(--bz-accent-warm)',
                        }}
                      >
                        <div className="flex items-center gap-4 flex-wrap text-xs">
                          <span
                            className="font-semibold uppercase tracking-wide"
                            style={{ color: '#d4845a' }}
                          >
                            OSS Credentials
                          </span>
                          <div className="flex items-center gap-2">
                            <span style={{ color: 'var(--bz-text-2)' }}>Username:</span>
                            <code
                              className="font-mono px-2 py-0.5 rounded"
                              style={{ background: 'rgba(0,0,0,0.3)', color: 'var(--bz-text-1)' }}
                            >
                              {openCreds[item.id].oss_username ?? '—'}
                            </code>
                            {openCreds[item.id].oss_username && (
                              <button
                                onClick={() =>
                                  handleCopy(openCreds[item.id].oss_username!, 'Username')
                                }
                                className="p-1 rounded hover:bg-[rgba(255,255,255,0.08)]"
                                aria-label="Copy username"
                              >
                                <Copy className="w-3 h-3" />
                              </button>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <span style={{ color: 'var(--bz-text-2)' }}>Password:</span>
                            <code
                              className="font-mono px-2 py-0.5 rounded"
                              style={{ background: 'rgba(0,0,0,0.3)', color: 'var(--bz-text-1)' }}
                            >
                              {openCreds[item.id].oss_password ?? '—'}
                            </code>
                            {openCreds[item.id].oss_password && (
                              <button
                                onClick={() =>
                                  handleCopy(openCreds[item.id].oss_password!, 'Password')
                                }
                                className="p-1 rounded hover:bg-[rgba(255,255,255,0.08)]"
                                aria-label="Copy password"
                              >
                                <Copy className="w-3 h-3" />
                              </button>
                            )}
                          </div>
                          {openCreds[item.id].oss_creds_updated_at && (
                            <span style={{ color: 'var(--bz-text-2)' }}>
                              Updated:{' '}
                              {new Date(openCreds[item.id].oss_creds_updated_at!).toLocaleDateString(
                                'en-GB',
                              )}
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                  </React.Fragment>
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
