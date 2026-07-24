"use client";

/**
 * Portal Practice Detail — single practice timeline.
 *
 * WS3 slice 4 (GARUDA Day Edition, 2026-07-24): day-theme token alignment,
 * mirroring slice 1 (portal home, PR 3050) and slice 2 (matters, PR 3051).
 * Masthead = Cormorant serif (--font-serif) in --tx-pure. Copper accents
 * read --bz-copper-text (armed in globals.css by slice 1, with the
 * --tx-secondary fallback keeping AA until that merges). State colors
 * read the semantic --state-* tokens (WS2 operative-light AA overrides).
 * No hardcoded hexes.
 */

import { useState, use } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { useProcessTimeline } from "@/hooks/useProcessTimeline";
import { ProcessTimeline } from "@/components/portal/process/ProcessTimeline";
import { StepDetailDrawer } from "@/components/portal/process/StepDetailDrawer";
import { TimelineSkeleton } from "@/components/portal/process/TimelineSkeleton";
import { BlockedStateCTA } from "@/components/portal/process/BlockedStateCTA";
import { ProcessErrorBoundary } from "@/components/portal/process/ProcessErrorBoundary";
import type { ProcessStep } from "@/lib/schemas/process";

interface Props {
  params: Promise<{ practiceId: string }>;
}

export default function PracticeDetailPage({ params }: Props) {
  const { practiceId } = use(params);
  const { data, error, isLoading, mutate } = useProcessTimeline(practiceId);
  const [selected, setSelected] = useState<ProcessStep | null>(null);

  const isBlocked = data?.current_status === "cancelled";

  return (
    <ProcessErrorBoundary>
      <main className="max-w-3xl mx-auto px-4 py-6">
        <Link
          href="/portal/process"
          className="inline-flex items-center gap-1 text-xs text-[var(--bz-copper-text,var(--tx-secondary))] hover:text-[var(--tx-pure)] mb-6 uppercase tracking-[2px]"
        >
          <ArrowLeft className="w-3 h-3" aria-hidden />
          All practices
        </Link>

        {data && (
          <header className="mb-6">
            <div
              aria-hidden="true"
              className="w-14 h-[3px] rounded-sm mb-4 bg-[var(--bz-copper)]"
            />
            <h1
              className="text-2xl font-semibold text-[var(--tx-pure)]"
              style={{ fontFamily: "var(--font-serif)" }}
            >
              {data.practice_name ?? "Practice"}
            </h1>
            {data.practice_category && (
              <p className="text-xs text-[var(--bz-copper-text,var(--tx-secondary))] uppercase tracking-[2px] mt-1">
                {data.practice_category}
              </p>
            )}
          </header>
        )}

        {isLoading && <TimelineSkeleton count={4} />}

        {error && !isLoading && (
          <div
            role="alert"
            className="rounded-lg p-4 border text-sm"
            style={{ borderColor: "var(--bz-border)" }}
          >
            <p className="mb-2 text-[var(--tx-primary)]">
              Unable to load the timeline.
            </p>
            <button
              onClick={() => mutate()}
              className="text-xs uppercase tracking-[2px] text-[var(--bz-copper-text,var(--tx-secondary))] hover:underline"
            >
              Retry
            </button>
          </div>
        )}

        {data && (
          <>
            {isBlocked && (
              <div className="mb-6">
                <BlockedStateCTA
                  practiceId={practiceId}
                  reason={data.assigned_to ?? null}
                />
              </div>
            )}
            <ProcessTimeline steps={data.steps} onSelect={setSelected} />
          </>
        )}

        <StepDetailDrawer
          step={selected}
          open={selected !== null}
          onClose={() => setSelected(null)}
        />
      </main>
    </ProcessErrorBoundary>
  );
}
