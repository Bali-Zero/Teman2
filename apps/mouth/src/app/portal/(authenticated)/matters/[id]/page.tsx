"use client";

/**
 * Portal Matter Detail — single matter with approved intelligence panel.
 *
 * SAETTA-R19P W4 (2026-09-13): concept-F "RAPI" presentation pass. Same data,
 * same hooks, same branches — new clothes. Four colour meanings: slate
 * (--state-info) = ours/moving, copper (--bz-copper*) = needs you, forest
 * (--state-success) = done/healthy and the only button fill, muted
 * (--tx-secondary) = waiting. Hairlines instead of tinted boxes, Fraunces
 * (--font-serif) headlines, and the "Where it stands" column first on mobile.
 * No route, field, hook or fetch changed.
 */

import { useParams } from "next/navigation";
import Link from "next/link";
import { AlertTriangle, Archive, MessageSquare } from "lucide-react";
import { usePortalMatter } from "@/hooks";
import { PortalBackButton } from "@/components/portal";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import type { PortalApprovedIntelligence } from "@/lib/api/portal/portal.types";
import { usePortalDateFormat } from "@/lib/format/usePortalDateFormat";

/** 650 / 10px / 0.14em uppercase — the one label style of the concept. */
const EYEBROW =
  "text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--tx-secondary)]";
/** Fraunces 450, the only headline face. */
const SERIF = {
  fontFamily: "var(--font-serif)",
  fontWeight: 450,
} as const;
/** Copper never fills a control: the alert keeps its shape, loses the red. */
const ALERT_TONE =
  "border-[var(--bz-border-hover)] text-[var(--state-danger)] [&>svg]:text-[var(--state-danger)]";

function parseMatterId(value: string | string[] | undefined): number | null {
  const raw = Array.isArray(value) ? value[0] : value;
  const parsed = Number(raw);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function formatReviewedAt(
  value: string | null,
  formatDate: (
    value: string | Date | null | undefined,
    options?: Intl.DateTimeFormatOptions,
  ) => string,
): string | null {
  if (!value) return null;
  return (
    formatDate(value, {
      month: "short",
      day: "numeric",
      year: "numeric",
    }) || null
  );
}

/** Day count read off the deadline already returned — a word, never a red. */
function formatDayCount(value: string | null): string | null {
  if (!value) return null;
  const due = new Date(value);
  if (Number.isNaN(due.getTime())) return null;
  const days = Math.round((due.getTime() - Date.now()) / 86_400_000);
  if (days > 1) return `${days} days`;
  if (days === 1) return "Tomorrow";
  if (days === 0) return "Today";
  return "Overdue";
}

type StatusTone = "ours" | "ok" | "you" | "wait";

const TONE_CLASS: Record<StatusTone, string> = {
  ours: "text-[var(--state-info)] border-[var(--state-info)]/35",
  ok: "text-[var(--state-success)] border-[var(--state-success)]/35",
  you: "text-[var(--bz-copper-text)] border-[var(--bz-copper-text)]/40",
  wait: "text-[var(--tx-secondary)] border-[var(--bz-border-hover)]",
};

function statusTone(...values: (string | null | undefined)[]): StatusTone {
  const text = values.filter(Boolean).join(" ").toLowerCase();
  if (/complete|approved|done|issued|active/.test(text)) return "ok";
  if (/wait|need|action|client/.test(text)) return "you";
  if (/progress|review|submit|process/.test(text)) return "ours";
  return "wait";
}

function StatusPill({
  label,
  tone,
  className,
}: {
  label: string;
  tone: StatusTone;
  className?: string;
}) {
  return (
    <Badge
      variant="outline"
      className={`h-6 gap-[7px] px-[10px] text-[10px] font-semibold uppercase tracking-[0.12em] ${TONE_CLASS[tone]} ${className ?? ""}`}
    >
      <span
        aria-hidden="true"
        className="h-1.5 w-1.5 shrink-0 rounded-full bg-current"
      />
      {label}
    </Badge>
  );
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
      <div className="grid gap-6 md:grid-cols-[1fr_300px]">
        <div
          className="h-56 animate-pulse rounded-lg border"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
          }}
        />
        <div
          className="h-56 animate-pulse rounded-lg border"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
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
  const { formatDate } = usePortalDateFormat();
  const reviewedAt = formatReviewedAt(
    intelligence.last_reviewed_at,
    formatDate,
  );

  if (!intelligence.available) {
    return (
      <section
        className="rounded-lg border p-6"
        style={{
          background: "var(--bz-card)",
          borderColor: "var(--bz-border)",
        }}
      >
        <p className={EYEBROW}>The file · what we know for certain</p>
        <h2
          className="mt-4 text-[22px] leading-[1.35] tracking-[-0.015em] text-[var(--tx-pure)]"
          style={SERIF}
        >
          No approved summary yet
        </h2>
        <p className="mt-3 max-w-[62ch] text-sm leading-7 text-[var(--tx-secondary)]">
          Your Bali Zero team will publish a client-ready summary after review.
        </p>
        <div
          className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t pt-4 text-xs text-[var(--tx-secondary)]"
          style={{ borderColor: "var(--bz-border)" }}
        >
          <span>Facts are checked by your team before they appear here.</span>
          <Link
            href="/portal/vault"
            prefetch={false}
            className="font-semibold text-[var(--bz-copper-text)]"
          >
            Open the Vault
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section
      className="rounded-lg border p-6"
      style={{
        background: "var(--bz-card)",
        borderColor: "var(--bz-border)",
      }}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className={EYEBROW}>The file · what we know for certain</h2>
          {intelligence.company_name && (
            <p className="mt-2 text-sm text-[var(--tx-secondary)]">
              {intelligence.company_name}
            </p>
          )}
        </div>
        {reviewedAt && (
          <span
            className="inline-flex shrink-0 -rotate-2 items-center gap-2 self-start rounded-[2px] border border-[var(--state-success)] px-2.5 py-1.5 text-[9px] font-semibold uppercase tracking-[0.16em] text-[var(--state-success)]"
            style={{ background: "var(--bz-card)" }}
          >
            <span
              aria-hidden="true"
              className="h-1.5 w-1.5 rounded-full bg-[var(--state-success)]"
            />
            Reviewed · Bali Zero · {reviewedAt}
          </span>
        )}
      </div>

      {intelligence.summary && (
        <p
          className="mt-5 border-b pb-5 text-[19px] leading-[1.35] tracking-[-0.015em] text-[var(--tx-pure)] sm:text-[22px]"
          style={{ ...SERIF, borderColor: "var(--bz-border)" }}
        >
          {intelligence.summary}
        </p>
      )}

      {intelligence.facts.length > 0 && (
        <dl className="mt-1.5 grid grid-cols-1 gap-x-6 sm:grid-cols-2">
          {intelligence.facts.map((fact) => (
            <div
              key={`${fact.category}-${fact.label}`}
              className="border-b py-3.5"
              style={{ borderColor: "var(--bz-border)" }}
            >
              <dt className={EYEBROW}>{fact.label}</dt>
              <dd className="mt-0.5 text-sm font-semibold leading-6 text-[var(--bz-text-1)]">
                {fact.detail}
              </dd>
            </div>
          ))}
        </dl>
      )}

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 text-xs text-[var(--tx-secondary)]">
        <span>Facts are checked by your team before they appear here.</span>
        <Link
          href="/portal/vault"
          prefetch={false}
          className="font-semibold text-[var(--bz-copper-text)]"
        >
          Open the Vault
        </Link>
      </div>
    </section>
  );
}

export default function PortalMatterDetailPage() {
  const params = useParams<{ id?: string | string[] }>();
  const matterId = parseMatterId(params?.id);
  const { data, isLoading, isError, refetch } = usePortalMatter(matterId);
  const { formatDate } = usePortalDateFormat();

  if (!matterId) {
    return (
      <div className="space-y-6 p-6">
        <PortalBackButton href="/portal/matters" label="Matters" />
        <Alert variant="destructive" className={ALERT_TONE}>
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
        <Alert variant="destructive" className={ALERT_TONE}>
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Unable to load matter</AlertTitle>
          <AlertDescription>
            We could not verify this matter. Check your connection and try
            again.
          </AlertDescription>
        </Alert>
        <Button onClick={() => void refetch()} variant="outline">
          Retry
        </Button>
      </div>
    );
  }

  const needs = [
    ...data.pending_docs,
    ...data.approved_intelligence.missing_items,
  ];
  const steps = [
    ...(data.next_step ? [data.next_step] : []),
    ...data.approved_intelligence.next_steps,
  ];
  const deadlineText = data.next_deadline
    ? (formatReviewedAt(data.next_deadline, formatDate) ?? data.next_deadline)
    : null;
  const dayCount = formatDayCount(data.next_deadline);

  return (
    <div className="space-y-8 p-6">
      <PortalBackButton
        href="/portal/matters"
        label="Matters"
        className="uppercase tracking-[0.06em] font-semibold"
      />

      <section>
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill
            label={data.type}
            tone="wait"
            className="capitalize tracking-[0.12em]"
          />
          <StatusPill
            label={data.status_label}
            tone={statusTone(data.status, data.status_label)}
          />
        </div>
        <p className={`${EYEBROW} mt-4 tabular-nums`}>Matter {data.id}</p>
        <h1
          className="mt-2.5 max-w-[22ch] text-[clamp(34px,3.6vw,46px)] leading-[1.06] tracking-[-0.03em] text-[var(--tx-pure)]"
          style={SERIF}
        >
          {data.title}
        </h1>
        <p className="mt-3 max-w-[62ch] text-sm leading-7 text-[var(--tx-secondary)]">
          {data.description}
        </p>
      </section>

      <section className="grid items-start gap-6 md:grid-cols-[1fr_300px]">
        <ApprovedIntelligencePanel intelligence={data.approved_intelligence} />

        <aside
          aria-label="Where it stands"
          className="order-first flex flex-col gap-6 md:order-none md:sticky md:top-[calc(64px+24px)]"
        >
          <div>
            <h2 className={EYEBROW}>Progress</h2>
            <p
              className="mt-2 text-[28px] leading-none tracking-[-0.02em] tabular-nums text-[var(--tx-pure)]"
              style={SERIF}
            >
              {data.progress}%
            </p>
            <Progress
              value={data.progress}
              className="mt-2.5 h-1 rounded-sm bg-[var(--glass-rim)]"
              indicatorClassName="bg-[var(--state-info)]"
            />
          </div>

          {deadlineText && (
            <div>
              <h2 className={EYEBROW}>Next deadline</h2>
              <div
                className="mt-2 flex items-center justify-between gap-3 rounded border px-3.5 py-3"
                style={{ borderColor: "var(--bz-border-hover)" }}
              >
                <span className="text-sm font-semibold tabular-nums text-[var(--bz-text-1)]">
                  {deadlineText}
                </span>
                {dayCount && (
                  <span
                    className="shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] tabular-nums text-[var(--tx-secondary)]"
                    style={{ borderColor: "var(--bz-border)" }}
                  >
                    {dayCount}
                  </span>
                )}
              </div>
            </div>
          )}

          {needs.length > 0 && (
            <div>
              <h2 className={EYEBROW}>We need from you</h2>
              <ul className="mt-1.5">
                {needs.map((item, index) => (
                  <li
                    key={`need-${index}-${item}`}
                    className="flex items-start gap-2.5 border-t py-2.5 text-sm font-semibold leading-6 text-[var(--bz-copper-text)]"
                    style={{ borderColor: "var(--bz-border)" }}
                  >
                    <span
                      aria-hidden="true"
                      className="mt-2 h-2 w-2 shrink-0 rounded-full bg-[var(--bz-copper)]"
                    />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              <Link
                href="/portal/vault"
                prefetch={false}
                className="mt-3.5 flex h-12 w-full items-center justify-center gap-2 rounded bg-[var(--state-success)] text-[13px] font-semibold tracking-[0.02em] text-white"
              >
                <Archive className="h-4 w-4" />
                Open the Vault
              </Link>
            </div>
          )}

          {steps.length > 0 && (
            <div>
              <h2 className={EYEBROW}>What happens next</h2>
              <ol className="mt-1.5">
                {steps.map((item, index) => (
                  <li
                    key={`next-${index}-${item}`}
                    className={`grid grid-cols-[28px_1fr] gap-2.5 border-t py-2.5 text-sm leading-6 ${
                      index === 0
                        ? "text-[var(--bz-text-1)]"
                        : "text-[var(--tx-secondary)]"
                    }`}
                    style={{ borderColor: "var(--bz-border)" }}
                  >
                    <span
                      aria-hidden="true"
                      className={`text-[20px] leading-[1.2] tabular-nums ${
                        index === 0
                          ? "text-[var(--bz-copper-text)]"
                          : "text-[var(--tx-tertiary)]"
                      }`}
                      style={SERIF}
                    >
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span>{item}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </aside>
      </section>

      <section
        className="flex flex-col items-start justify-between gap-5 rounded-lg border p-6 sm:flex-row sm:items-center"
        style={{
          background: "var(--bz-card)",
          borderColor: "var(--bz-border)",
        }}
      >
        <div>
          <p
            className="text-[20px] leading-[1.2] tracking-[-0.015em] text-[var(--tx-pure)]"
            style={SERIF}
          >
            A question about this matter?
          </p>
          <p className="mt-1.5 max-w-[56ch] text-sm leading-7 text-[var(--tx-secondary)]">
            Your Bali Zero team answers in the messages thread, usually within
            one working day.
          </p>
        </div>
        <Link
          href="/portal/messages"
          prefetch={false}
          className="inline-flex h-12 w-full shrink-0 items-center justify-center gap-2 rounded border px-5 text-[13px] font-semibold text-[var(--bz-text-1)] sm:w-auto"
          style={{ borderColor: "var(--bz-border-hover)" }}
        >
          <MessageSquare className="h-4 w-4" />
          Message the team
        </Link>
      </section>
    </div>
  );
}
