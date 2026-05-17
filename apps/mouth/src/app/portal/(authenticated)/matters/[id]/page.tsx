"use client";

import { useParams } from "next/navigation";
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileText,
  ShieldCheck,
} from "lucide-react";
import { usePortalMatter } from "@/hooks";
import { PortalBackButton } from "@/components/portal";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import type { PortalApprovedIntelligence } from "@/lib/api/portal/portal.types";

function parseMatterId(value: string | string[] | undefined): number | null {
  const raw = Array.isArray(value) ? value[0] : value;
  const parsed = Number(raw);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function formatReviewedAt(value: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function LoadingState() {
  return (
    <div className="space-y-6 p-6">
      <div
        className="h-5 w-28 animate-pulse rounded"
        style={{ background: "var(--glass-rim)" }}
      />
      <div
        className="h-10 w-64 animate-pulse rounded"
        style={{ background: "var(--glass-rim)" }}
      />
      <div className="grid gap-4 md:grid-cols-[1fr_280px]">
        <div
          className="h-56 animate-pulse rounded-lg border"
          style={{
            background: "rgba(30,30,35,0.7)",
            borderColor: "rgba(255,255,255,0.05)",
          }}
        />
        <div
          className="h-56 animate-pulse rounded-lg border"
          style={{
            background: "rgba(30,30,35,0.7)",
            borderColor: "rgba(255,255,255,0.05)",
          }}
        />
      </div>
    </div>
  );
}

function ApprovedIntelligencePanel({
  intelligence,
}: {
  intelligence: PortalApprovedIntelligence;
}) {
  const reviewedAt = formatReviewedAt(intelligence.last_reviewed_at);

  if (!intelligence.available) {
    return (
      <section
        className="rounded-lg border p-5"
        style={{
          background: "rgba(30,30,35,0.7)",
          borderColor: "rgba(255,255,255,0.05)",
        }}
      >
        <div className="flex items-start gap-3">
          <Clock3 className="mt-0.5 h-5 w-5 text-amber-300" />
          <div>
            <h2 className="text-lg font-semibold text-[var(--bz-text-1)]">
              No approved summary yet
            </h2>
            <p className="mt-2 text-sm leading-6 text-[var(--tx-secondary)]">
              Your Bali Zero team will publish a client-ready summary after
              review.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section
      className="rounded-lg border p-5"
      style={{
        background: "rgba(30,30,35,0.7)",
        borderColor: "rgba(255,255,255,0.05)",
      }}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-[var(--bz-text-1)]">
            <ShieldCheck className="h-5 w-5 text-emerald-300" />
            Approved Intelligence
          </h2>
          {intelligence.company_name && (
            <p className="mt-1 text-sm text-[var(--tx-secondary)]">
              {intelligence.company_name}
            </p>
          )}
        </div>
        <Badge className="border-emerald-500/20 bg-emerald-500/10 text-emerald-200">
          Approved
        </Badge>
      </div>

      {intelligence.summary && (
        <p className="mt-4 text-sm leading-6 text-[var(--bz-text-1)]">
          {intelligence.summary}
        </p>
      )}
      {reviewedAt && (
        <p className="mt-2 text-xs text-[var(--tx-secondary)]">
          Reviewed {reviewedAt}
        </p>
      )}

      {intelligence.facts.length > 0 && (
        <div className="mt-5 divide-y divide-white/[0.06]">
          {intelligence.facts.map((fact) => (
            <div
              key={`${fact.category}-${fact.label}`}
              className="py-3 first:pt-0 last:pb-0"
            >
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-medium text-[var(--bz-text-1)]">
                  {fact.label}
                </p>
                <span className="rounded bg-white/[0.08] px-2 py-0.5 text-[10px] uppercase tracking-wider text-[var(--tx-secondary)]">
                  {fact.confidence}
                </span>
              </div>
              <p className="mt-2 text-sm leading-6 text-[var(--tx-secondary)]">
                {fact.detail}
              </p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default function PortalMatterDetailPage() {
  const params = useParams<{ id?: string | string[] }>();
  const matterId = parseMatterId(params?.id);
  const { data, isLoading, isError, error } = usePortalMatter(matterId);

  if (!matterId) {
    return (
      <div className="space-y-6 p-6">
        <PortalBackButton href="/portal/matters" label="Matters" />
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Unable to load matter</AlertTitle>
          <AlertDescription>Invalid matter id.</AlertDescription>
        </Alert>
      </div>
    );
  }

  if (isLoading) return <LoadingState />;

  if (isError || !data) {
    return (
      <div className="space-y-6 p-6">
        <PortalBackButton href="/portal/matters" label="Matters" />
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Unable to load matter</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : "Please try again later."}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <PortalBackButton href="/portal/matters" label="Matters" />

      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            variant="outline"
            className="capitalize text-[var(--tx-secondary)]"
          >
            {data.type}
          </Badge>
          <Badge className="border-emerald-500/20 bg-emerald-500/10 text-emerald-200">
            {data.status_label}
          </Badge>
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight lux-text-gradient">
            {data.title}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--tx-secondary)]">
            {data.description}
          </p>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-[1fr_280px]">
        <ApprovedIntelligencePanel intelligence={data.approved_intelligence} />

        <aside
          className="space-y-4 rounded-lg border p-4"
          style={{
            background: "rgba(30,30,35,0.7)",
            borderColor: "rgba(255,255,255,0.05)",
          }}
        >
          <div>
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-[var(--bz-text-1)]">
                Progress
              </span>
              <span className="text-[var(--tx-secondary)]">
                {data.progress}%
              </span>
            </div>
            <Progress
              value={data.progress}
              className="mt-2 h-2 bg-white/[0.08]"
              indicatorClassName="bg-[var(--bz-accent-warm)]"
            />
          </div>

          {data.next_deadline && (
            <div
              className="border-t pt-3"
              style={{ borderColor: "rgba(255,255,255,0.06)" }}
            >
              <p className="text-xs uppercase tracking-wider text-[var(--tx-secondary)]">
                Next deadline
              </p>
              <p className="mt-1 text-sm font-medium text-[var(--bz-text-1)]">
                {formatReviewedAt(data.next_deadline) ?? data.next_deadline}
              </p>
            </div>
          )}

          {(data.pending_docs.length > 0 ||
            data.approved_intelligence.missing_items.length > 0) && (
            <div>
              <p className="flex items-center gap-2 text-sm font-semibold text-[var(--bz-text-1)]">
                <FileText className="h-4 w-4 text-amber-300" />
                What we still need
              </p>
              <ul className="mt-2 space-y-2 text-sm leading-6 text-[var(--tx-secondary)]">
                {[
                  ...data.pending_docs,
                  ...data.approved_intelligence.missing_items,
                ].map((item, index) => (
                  <li key={`need-${index}-${item}`}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {(data.next_step ||
            data.approved_intelligence.next_steps.length > 0) && (
            <div>
              <p className="flex items-center gap-2 text-sm font-semibold text-[var(--bz-text-1)]">
                <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                Next steps
              </p>
              <ul className="mt-2 space-y-2 text-sm leading-6 text-[var(--tx-secondary)]">
                {[
                  ...(data.next_step ? [data.next_step] : []),
                  ...data.approved_intelligence.next_steps,
                ].map((item, index) => (
                  <li key={`next-${index}-${item}`}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </section>
    </div>
  );
}
