'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  Sparkles,
  Users,
  FolderKanban,
  TrendingUp,
  CheckCircle2,
  Activity,
  Plus,
  UserPlus,
  ArrowRight,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import type { AutoCRMStats, CreateClientParams } from '@/lib/api/crm/crm.types';

interface AutoCRMWidgetV2Props {
  className?: string;
}

/**
 * AutoCRMWidgetV2 - Improved AUTO CRM widget with:
 * - Full CSS variables (no hardcoded white/opacity colors)
 * - Better accessibility
 * - Consistent with Design System v2.0
 */
export function AutoCRMWidgetV2({ className }: AutoCRMWidgetV2Props) {
  const router = useRouter();
  const [stats, setStats] = useState<AutoCRMStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showQuickCreate, setShowQuickCreate] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [quickForm, setQuickForm] = useState<CreateClientParams>({
    full_name: '',
    email: '',
    phone: '',
    nationality: '',
  });

  useEffect(() => {
    const loadStats = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const data = await api.crm.getAutoCRMStats(7);
        setStats(data);
      } catch (err) {
        console.error('Failed to load AUTO CRM stats:', err);
        setError('Failed to load statistics');
      } finally {
        setIsLoading(false);
      }
    };

    loadStats();
    const interval = setInterval(loadStats, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const handleQuickCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickForm.full_name.trim()) {
      alert('Name is required');
      return;
    }

    setIsCreating(true);
    try {
      const user = await api.getProfile();
      await api.crm.createClient(quickForm, user.email);
      setQuickForm({ full_name: '', email: '', phone: '', nationality: '' });
      setShowQuickCreate(false);
      const data = await api.crm.getAutoCRMStats(7);
      setStats(data);
      router.push('/clients');
    } catch (err) {
      console.error('Failed to create client:', err);
      const message = err instanceof Error ? err.message : 'Unknown error';
      const detail = (err as Record<string, unknown>).detail;
      alert(`Failed to create client: ${detail || message}`);
    } finally {
      setIsCreating(false);
    }
  };

  // Loading state
  if (isLoading && !stats) {
    return (
      <div
        className={cn(
          'rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-6',
          className
        )}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-[var(--foreground)] uppercase tracking-wider flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[var(--accent)]" aria-hidden="true" />
            AUTO CRM
          </h3>
        </div>
        <div className="text-sm text-[var(--foreground-muted)]">Loading statistics...</div>
      </div>
    );
  }

  // Error state
  if (error && !stats) {
    return (
      <div
        className={cn(
          'rounded-xl border border-[var(--error)]/30 bg-[var(--error-muted)] p-6',
          className
        )}
        role="alert"
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-[var(--foreground)] uppercase tracking-wider flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[var(--accent)]" aria-hidden="true" />
            AUTO CRM
          </h3>
        </div>
        <div className="text-sm text-[var(--error)]">{error}</div>
      </div>
    );
  }

  if (!stats) return null;

  const successRate =
    stats.total_extractions > 0
      ? Math.round((stats.successful_extractions / stats.total_extractions) * 100)
      : 0;

  const getSuccessRateColor = (rate: number) => {
    if (rate >= 80) return 'text-[var(--success)]';
    if (rate >= 60) return 'text-[var(--warning)]';
    return 'text-[var(--error)]';
  };

  return (
    <div
      className={cn(
        'rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-6',
        'transition-all duration-[var(--transition-normal)]',
        'hover:border-[var(--border-hover)]',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-[var(--foreground)] uppercase tracking-wider flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-[var(--accent)]" aria-hidden="true" />
          AUTO CRM
        </h3>
        <div className="flex items-center gap-2">
          <div
            className="w-2 h-2 rounded-full bg-[var(--success)] motion-safe:animate-pulse"
            role="status"
            aria-label="System active"
          />
          <span className="text-xs text-[var(--foreground-muted)]">Active</span>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="mb-4 flex gap-2">
        <Button
          size="sm"
          variant="outline"
          className="flex-1 bg-[var(--background-elevated)] border-[var(--border)] text-[var(--foreground)] hover:bg-[var(--background-hover)] focus-ring"
          onClick={() => router.push('/clients/new')}
        >
          <UserPlus className="w-3 h-3 mr-1" aria-hidden="true" />
          New Client
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="flex-1 bg-[var(--background-elevated)] border-[var(--border)] text-[var(--foreground)] hover:bg-[var(--background-hover)] focus-ring"
          onClick={() => router.push('/cases')}
        >
          <FolderKanban className="w-3 h-3 mr-1" aria-hidden="true" />
          Practices
        </Button>
      </div>

      {/* Quick Create Form */}
      {showQuickCreate && (
        <div className="mb-4 p-3 rounded-lg bg-[var(--background-elevated)] border border-[var(--border)]">
          <form onSubmit={handleQuickCreate} className="space-y-2">
            <input
              type="text"
              placeholder="Full Name *"
              value={quickForm.full_name}
              onChange={(e) => setQuickForm({ ...quickForm, full_name: e.target.value })}
              className={cn(
                'w-full px-3 py-2 text-sm rounded-lg',
                'bg-[var(--background)] border border-[var(--border)]',
                'text-[var(--foreground)] placeholder:text-[var(--foreground-muted)]',
                'focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent'
              )}
              required
              aria-label="Full name (required)"
            />
            <div className="grid grid-cols-2 gap-2">
              <input
                type="email"
                placeholder="Email"
                value={quickForm.email}
                onChange={(e) => setQuickForm({ ...quickForm, email: e.target.value })}
                className={cn(
                  'px-3 py-2 text-sm rounded-lg',
                  'bg-[var(--background)] border border-[var(--border)]',
                  'text-[var(--foreground)] placeholder:text-[var(--foreground-muted)]',
                  'focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent'
                )}
                aria-label="Email address"
              />
              <input
                type="tel"
                placeholder="Phone"
                value={quickForm.phone}
                onChange={(e) => setQuickForm({ ...quickForm, phone: e.target.value })}
                className={cn(
                  'px-3 py-2 text-sm rounded-lg',
                  'bg-[var(--background)] border border-[var(--border)]',
                  'text-[var(--foreground)] placeholder:text-[var(--foreground-muted)]',
                  'focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:border-transparent'
                )}
                aria-label="Phone number"
              />
            </div>
            <div className="flex gap-2">
              <Button
                type="submit"
                size="sm"
                className="flex-1 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white"
                disabled={isCreating}
              >
                {isCreating ? (
                  <>
                    <Loader2 className="w-3 h-3 mr-1 animate-spin" aria-hidden="true" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Plus className="w-3 h-3 mr-1" aria-hidden="true" />
                    Create
                  </>
                )}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="bg-[var(--background-elevated)] border-[var(--border)] text-[var(--foreground)] hover:bg-[var(--background-hover)]"
                onClick={() => {
                  setShowQuickCreate(false);
                  setQuickForm({ full_name: '', email: '', phone: '', nationality: '' });
                }}
              >
                Cancel
              </Button>
            </div>
          </form>
        </div>
      )}

      {!showQuickCreate && (
        <Button
          size="sm"
          variant="ghost"
          className="w-full mb-4 bg-[var(--background-elevated)] hover:bg-[var(--background-hover)] text-[var(--foreground)] focus-ring"
          onClick={() => setShowQuickCreate(true)}
        >
          <Plus className="w-3 h-3 mr-1" aria-hidden="true" />
          Quick Create Client
        </Button>
      )}

      {/* Stats */}
      <div className="space-y-3">
        {/* Success Rate */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-[var(--info)]" aria-hidden="true" />
            <span className="text-sm text-[var(--foreground-secondary)]">Success Rate</span>
          </div>
          <span className={cn('text-sm font-medium', getSuccessRateColor(successRate))}>
            {successRate}%
          </span>
        </div>

        {/* Total Extractions */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-[var(--accent)]" aria-hidden="true" />
            <span className="text-sm text-[var(--foreground-secondary)]">Total Extractions</span>
          </div>
          <span className="text-sm font-medium text-[var(--foreground)]">
            {stats.total_extractions}
          </span>
        </div>

        {/* Clients Created */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-[var(--info)]" aria-hidden="true" />
            <span className="text-sm text-[var(--foreground-secondary)]">Clients Created</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-[var(--success)]">{stats.clients_created}</span>
            {stats.clients_created > 0 && (
              <button
                onClick={() => router.push('/clients')}
                className="text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors focus-ring rounded"
                aria-label="View all clients"
              >
                <ArrowRight className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Practices Created */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FolderKanban className="w-4 h-4 text-[var(--warning)]" aria-hidden="true" />
            <span className="text-sm text-[var(--foreground-secondary)]">Practices Created</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-[var(--success)]">
              {stats.practices_created}
            </span>
            {stats.practices_created > 0 && (
              <button
                onClick={() => router.push('/cases')}
                className="text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors focus-ring rounded"
                aria-label="View all practices"
              >
                <ArrowRight className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Last 24h Activity */}
        <div className="pt-3 border-t border-[var(--border)]">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-[var(--success)]" aria-hidden="true" />
            <span className="text-xs font-semibold text-[var(--foreground-muted)] uppercase tracking-wider">
              Last 24h
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div>
              <div className="text-[var(--foreground-muted)]">Extractions</div>
              <div className="text-[var(--foreground)] font-medium">{stats.last_24h.extractions}</div>
            </div>
            <div>
              <div className="text-[var(--foreground-muted)]">Clients</div>
              <div className="text-[var(--foreground)] font-medium">{stats.last_24h.clients}</div>
            </div>
            <div>
              <div className="text-[var(--foreground-muted)]">Practices</div>
              <div className="text-[var(--foreground)] font-medium">{stats.last_24h.practices}</div>
            </div>
          </div>
        </div>

        {/* Confidence Score */}
        {stats.extraction_confidence_avg !== null && (
          <div className="flex items-center justify-between pt-3 border-t border-[var(--border)]">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-[var(--success)]" aria-hidden="true" />
              <span className="text-sm text-[var(--foreground-secondary)]">Avg Confidence</span>
            </div>
            <span
              className={cn(
                'text-sm font-medium',
                stats.extraction_confidence_avg >= 0.7
                  ? 'text-[var(--success)]'
                  : stats.extraction_confidence_avg >= 0.5
                    ? 'text-[var(--warning)]'
                    : 'text-[var(--error)]'
              )}
            >
              {Math.round(stats.extraction_confidence_avg * 100)}%
            </span>
          </div>
        )}

        {/* Quick Links */}
        <div className="pt-3 border-t border-[var(--border)]">
          <div className="flex gap-2">
            <button
              onClick={() => router.push('/clients')}
              className={cn(
                'flex-1 text-xs px-2 py-1.5 rounded-lg',
                'bg-[var(--background-elevated)] hover:bg-[var(--background-hover)]',
                'text-[var(--foreground-secondary)] hover:text-[var(--foreground)]',
                'transition-colors focus-ring'
              )}
            >
              View All Clients
            </button>
            <button
              onClick={() => router.push('/cases')}
              className={cn(
                'flex-1 text-xs px-2 py-1.5 rounded-lg',
                'bg-[var(--background-elevated)] hover:bg-[var(--background-hover)]',
                'text-[var(--foreground-secondary)] hover:text-[var(--foreground)]',
                'transition-colors focus-ring'
              )}
            >
              View Practices
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AutoCRMWidgetV2;
