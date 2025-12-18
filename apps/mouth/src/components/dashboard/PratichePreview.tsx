'use client';

import React from 'react';
import Link from 'next/link';
import { ChevronRight, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface PraticaPreview {
  id: number;
  title: string;
  client: string;
  status: 'inquiry' | 'quotation' | 'in_progress' | 'documents' | 'completed';
  daysRemaining?: number;
  completedAt?: string;
}

interface PratichePreviewProps {
  pratiche: PraticaPreview[];
  isLoading?: boolean;
}

const statusConfig = {
  inquiry: {
    label: 'Inquiry',
    color: 'text-[var(--foreground-muted)]',
    bg: 'bg-[var(--foreground-muted)]/10',
    dot: 'bg-[var(--foreground-muted)]',
  },
  quotation: {
    label: 'Quotation',
    color: 'text-[var(--warning)]',
    bg: 'bg-[var(--warning)]/10',
    dot: 'bg-[var(--warning)]',
  },
  in_progress: {
    label: 'In Progress',
    color: 'text-[var(--accent)]',
    bg: 'bg-[var(--accent)]/10',
    dot: 'bg-[var(--accent)]',
  },
  documents: {
    label: 'Documents',
    color: 'text-[var(--warning)]',
    bg: 'bg-[var(--warning)]/10',
    dot: 'bg-[var(--warning)]',
  },
  completed: {
    label: 'Completed',
    color: 'text-[var(--success)]',
    bg: 'bg-[var(--success)]/10',
    dot: 'bg-[var(--success)]',
  },
};

export function PratichePreview({ pratiche, isLoading }: PratichePreviewProps) {
  if (isLoading) {
    return (
      <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="h-5 w-32 bg-[var(--background-elevated)] rounded animate-pulse" />
          <div className="h-4 w-20 bg-[var(--background-elevated)] rounded animate-pulse" />
        </div>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-16 bg-[var(--background-elevated)]/50 rounded-lg animate-pulse"
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-[var(--foreground)]">
          Le Mie Pratiche
        </h2>
        <Link
          href="/pratiche"
          className="text-sm text-[var(--accent)] hover:text-[var(--accent-hover)] transition-colors flex items-center gap-1"
        >
          Tutte
          <ChevronRight className="w-4 h-4" />
        </Link>
      </div>

      {/* Pratiche List */}
      <div className="space-y-2">
        {pratiche.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-sm text-[var(--foreground-muted)]">
              Nessuna pratica assegnata
            </p>
          </div>
        ) : (
          pratiche.map((pratica) => {
            const config = statusConfig[pratica.status];
            return (
              <Link
                key={pratica.id}
                href={`/pratiche/${pratica.id}`}
                className="block p-3 rounded-lg border border-[var(--border)] hover:border-[var(--border-hover)] hover:bg-[var(--background-elevated)]/30 transition-all"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[var(--foreground)] truncate">
                      {pratica.title}
                    </p>
                    <p className="text-xs text-[var(--foreground-muted)] truncate">
                      {pratica.client}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span
                      className={cn(
                        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium',
                        config.bg,
                        config.color
                      )}
                    >
                      <span className={cn('w-1.5 h-1.5 rounded-full', config.dot)} />
                      {config.label}
                    </span>
                    {pratica.status !== 'completed' && pratica.daysRemaining !== undefined && (
                      <span
                        className={cn(
                          'text-xs flex items-center gap-1',
                          pratica.daysRemaining <= 3
                            ? 'text-[var(--error)]'
                            : pratica.daysRemaining <= 7
                            ? 'text-[var(--warning)]'
                            : 'text-[var(--foreground-muted)]'
                        )}
                      >
                        <Clock className="w-3 h-3" />
                        {pratica.daysRemaining} giorni
                      </span>
                    )}
                    {pratica.status === 'completed' && pratica.completedAt && (
                      <span className="text-xs text-[var(--foreground-muted)]">
                        {pratica.completedAt}
                      </span>
                    )}
                  </div>
                </div>
              </Link>
            );
          })
        )}
      </div>
    </div>
  );
}
