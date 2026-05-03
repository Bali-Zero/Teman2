"use client";
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
          className="inline-flex items-center gap-1 text-xs text-[#c9a96e]/60 hover:text-[#c9a96e] mb-6 uppercase tracking-[2px]"
        >
          <ArrowLeft className="w-3 h-3" aria-hidden />
          All practices
        </Link>

        {data && (
          <header className="mb-6">
            <h1 className="text-2xl font-light text-[#f0ece4]">
              {data.practice_name ?? "Practice"}
            </h1>
            {data.practice_category && (
              <p className="text-xs text-[#c9a96e]/60 uppercase tracking-[2px] mt-1">
                {data.practice_category}
              </p>
            )}
          </header>
        )}

        {isLoading && <TimelineSkeleton count={4} />}

        {error && !isLoading && (
          <div
            role="alert"
            className="rounded-lg p-4 border border-white/10 text-sm"
          >
            <p className="mb-2 text-[#f0ece4]">Unable to load the timeline.</p>
            <button
              onClick={() => mutate()}
              className="text-xs uppercase tracking-[2px] text-[#d4845a] hover:underline"
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
