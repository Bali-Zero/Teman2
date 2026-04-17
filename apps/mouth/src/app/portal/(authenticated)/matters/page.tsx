'use client';

/**
 * Portal Matters — V2 matter-first list.
 *
 * Renders a vertical stack of <MatterCard> per client matter (visa/company/
 * tax/property/other). Data from /api/portal/matters.
 */

import Link from 'next/link';
import { MatterCard } from '@balizero/core';
import { usePortalMatters } from '@/hooks';
import { PortalListSkeleton } from '@/components/portal';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { AlertTriangle } from 'lucide-react';

export default function PortalMattersPage() {
  const { data, isLoading, isError, error } = usePortalMatters();

  if (isLoading) {
    return (
      <div className="space-y-6 p-6">
        <h1 className="text-2xl font-bold tracking-tight lux-text-gradient">Your matters</h1>
        <PortalListSkeleton count={5} />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6 p-6">
        <h1 className="text-2xl font-bold tracking-tight lux-text-gradient">Your matters</h1>
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Unable to load matters</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : 'An unexpected error occurred.'}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const matters = data?.matters ?? [];

  return (
    <div className="space-y-6 p-6">
      <section>
        <h1 className="text-2xl font-bold tracking-tight lux-text-gradient">Your matters</h1>
        <p className="text-sm text-[var(--tx-secondary)] mt-1">
          Visa, company, tax, property — everything we're working on for you.
        </p>
      </section>

      {matters.length === 0 ? (
        <Alert>
          <AlertTitle>No open matters</AlertTitle>
          <AlertDescription>
            When we start working on something for you, it will appear here.
          </AlertDescription>
        </Alert>
      ) : (
        <section className="flex flex-col gap-3">
          {matters.map((m) => (
            <MatterCard
              key={m.id}
              title={m.title}
              type={m.type}
              progressPercent={m.progress}
              pendingDocs={m.pending_docs}
              nextDeadline={m.next_deadline ? new Date(m.next_deadline) : undefined}
              nextStep={m.next_step ?? undefined}
              action={
                <Link
                  href={`/portal/matters/${m.id}`}
                  className="text-[10px] uppercase tracking-widest font-bold text-[var(--bz-copper)] hover:text-white transition-colors"
                >
                  Open →
                </Link>
              }
            />
          ))}
        </section>
      )}
    </div>
  );
}
