"use client";

/**
 * Portal Dashboard Page
 *
 * Usa React Query per caching e ottimizzazione
 *
 * SAETTA-R19P W3 (2026-09-13): concept-F "RAPI" presentation pass. Same data
 * flow, same seven sections in the same order — paper/hairline dressing:
 * copper rule + serif masthead, one "next move" band + numbered matter index,
 * three status columns in one frame, quiet chips, numbered actions whose
 * priority is a WORD, and a hairline activity spine. Four colour meanings
 * only: forest = done (--state-success), slate = ours (--state-info), copper =
 * needs you (--bz-copper*), muted = waiting (--tx-secondary). No filled
 * danger/warning rows anywhere on this page.
 */

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import {
  AlertTriangle,
  ChevronRight,
  FileText,
  MessageCircle,
  RefreshCw,
  UserRoundX,
} from "lucide-react";

const TimelineItem = dynamic(
  () => import("./_components/TimelineItem").then((m) => m.TimelineItem),
  { ssr: false },
);
import { cn } from "@/lib/utils";
import {
  usePortalDashboard,
  usePortalDashboardSummary,
  usePortalTimeline,
} from "@/hooks";
import {
  PortalCardSkeleton,
  PortalEmptyState,
  PortalListSkeleton,
  PracticeRecapCard,
} from "@/components/portal";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { TimelineEntry } from "@/lib/api/types/timeline.types";
import type { DashboardSummary } from "@/lib/api/portal/portal.types";
import { DeadlineBadge } from "@balizero/core";
import { usePortalDateFormat } from "@/lib/format/usePortalDateFormat";

// ── R19 presentation primitives (page-local, nothing shared is restyled) ──
const SERIF: React.CSSProperties = {
  fontFamily: "var(--font-serif)",
  fontWeight: 450,
};
const EYEBROW =
  "text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--tx-secondary)]";
const SECTION_H2 = "text-[24px] leading-[1.14] tracking-[-0.02em]";
const HAIRLINE = "border border-[var(--bz-border)]";
const CARD = `rounded-lg bg-[var(--bz-surface)] ${HAIRLINE}`;
const FOCUS =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-copper)]";

type PillTone = "ok" | "ours" | "you" | "wait";

const PILL_TONE: Record<PillTone, string> = {
  ok: "text-[var(--state-success)] border-[var(--state-success)]",
  ours: "text-[var(--state-info)] border-[var(--state-info)]",
  you: "text-[var(--bz-copper-text)] border-[var(--bz-copper)]",
  wait: "text-[var(--tx-secondary)] border-[var(--bz-border-hover)]",
};

/** Outlined status pill — one vocabulary, four words, never a filled state. */
function StatePill({ tone, label }: { tone: PillTone; label: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-[7px] whitespace-nowrap rounded-full border px-[10px] text-[10px] font-semibold uppercase tracking-[0.12em]",
        PILL_TONE[tone],
      )}
    >
      <span
        aria-hidden="true"
        className="h-1.5 w-1.5 rounded-full bg-current"
      />
      {label}
    </span>
  );
}

function Masthead() {
  return (
    <section>
      <div
        aria-hidden="true"
        className="w-14 h-[3px] rounded-sm mb-4 bg-[var(--bz-copper)]"
      />
      <h1
        className="text-[clamp(34px,3.4vw,44px)] leading-[1.06] tracking-[-0.03em] text-[var(--tx-pure)]"
        style={SERIF}
      >
        Welcome back.
      </h1>
      <p className="mt-2 text-[var(--tx-secondary)]">
        Here is your Bali life overview.
      </p>
    </section>
  );
}

function SectionHead({
  title,
  linkLabel,
  href,
}: {
  title: string;
  linkLabel: string;
  href: string;
}) {
  return (
    <div className="mb-3.5 flex items-baseline justify-between gap-4">
      <h2 className={cn(SECTION_H2, "text-[var(--tx-pure)]")} style={SERIF}>
        {title}
      </h2>
      <a
        href={href}
        className="text-xs font-semibold text-[var(--bz-copper-text)] hover:text-[var(--tx-pure)] transition-colors"
      >
        {linkLabel}
      </a>
    </div>
  );
}

const pad2 = (n: number) => String(n).padStart(2, "0");

/** practice status codes (inquiry / in_progress / waiting_documents) as words */
function matterState(status: string | null, pending: string | null) {
  if (pending || status === "waiting_documents")
    return {
      tone: "you" as PillTone,
      label: "Needs you",
      sentence: "Waiting for documents from you.",
    };
  if (status === "in_progress")
    return {
      tone: "ours" as PillTone,
      label: "In progress",
      sentence: "In progress with your team.",
    };
  return {
    tone: "wait" as PillTone,
    label: "Pending",
    sentence: "Open with your team.",
  };
}

function getStatusCode(error: unknown): number | undefined {
  if (!error || typeof error !== "object") return undefined;

  const candidate = error as { statusCode?: unknown; status?: unknown };
  if (typeof candidate.statusCode === "number") return candidate.statusCode;
  if (typeof candidate.status === "number") return candidate.status;
  return undefined;
}

function isClientConnectionError(error: unknown): boolean {
  return getStatusCode(error) === 404;
}

export default function PortalHomePage() {
  const router = useRouter();
  const { formatDate } = usePortalDateFormat();
  const dashboardQuery = usePortalDashboard();
  const summaryQuery = usePortalDashboardSummary();
  const timelineQuery = usePortalTimeline(20);

  const { data: dashboard, isLoading: isLoadingDashboard } = dashboardQuery;
  const { data: summary } = summaryQuery;
  const { data: timelineData, isLoading: isLoadingTimeline } = timelineQuery;

  const timeline = timelineData?.entries || [];
  const [showAllTimeline, setShowAllTimeline] = useState(false);
  const TIMELINE_PREVIEW_COUNT = 5;
  const visibleTimeline = showAllTimeline
    ? timeline
    : timeline.slice(0, TIMELINE_PREVIEW_COUNT);

  const portalQueries = [dashboardQuery, summaryQuery, timelineQuery];
  const clientConnectionMissing = portalQueries.some(
    (query) => query.isError && isClientConnectionError(query.error),
  );
  const unexpectedError = portalQueries.find(
    (query) => query.isError && !isClientConnectionError(query.error),
  )?.error;
  const retryPortalData = () => {
    void Promise.all(portalQueries.map((query) => query.refetch()));
  };

  if (clientConnectionMissing) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <Masthead />

        <PortalEmptyState
          icon={UserRoundX}
          title="Client profile connection needed"
          description="Your portal account is signed in, but it is not connected to an active client profile yet. Contact your Bali Zero team to complete the connection, then try again."
        />

        <Button onClick={retryPortalData}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Try again
        </Button>
      </div>
    );
  }

  if (isLoadingDashboard || isLoadingTimeline) {
    return (
      <div className="space-y-8">
        <section>
          <div
            className="h-8 rounded w-48 mb-2 animate-pulse"
            style={{ background: "var(--glass-rim)" }}
          />
          <div
            className="h-4 rounded w-64 animate-pulse"
            style={{ background: "var(--glass-rim)" }}
          />
        </section>

        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <PortalCardSkeleton key={i} className="h-32" />
          ))}
        </section>

        <section className="space-y-4">
          <div
            className="h-6 rounded w-32 animate-pulse"
            style={{ background: "var(--glass-rim)" }}
          />
          <PortalListSkeleton count={5} />
        </section>
      </div>
    );
  }

  // Show error state
  if (unexpectedError) {
    return (
      <div className="space-y-6">
        <Masthead />

        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Unable to load dashboard</AlertTitle>
          <AlertDescription>
            We couldn&apos;t load all of your portal information. Please try
            again.
          </AlertDescription>
        </Alert>

        <Button onClick={retryPortalData}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Retry
        </Button>
      </div>
    );
  }

  // Default empty state
  const defaultDashboard = dashboard || {
    visa: {
      status: "none" as const,
      type: null,
      expiryDate: null,
      daysRemaining: null,
    },
    company: {
      status: "none" as const,
      primaryCompanyName: null,
      totalCompanies: 0,
    },
    taxes: {
      status: "none" as const,
      nextDeadline: null,
      daysToDeadline: null,
    },
    documents: { total: 0, pending: 0 },
    messages: { unread: 0 },
    actions: [],
  };

  return (
    <div className="space-y-9 animate-in fade-in duration-500">
      {/* 1 · masthead — copper rule + serif headline + the existing subtitle */}
      <Masthead />

      {/* 2 · matters: one next move + the numbered index of the others */}
      <HeroCards
        summary={summary}
        onOpenMatter={(id) => router.push(`/portal/matters/${id}`)}
      />

      {/* 3 · the team's recap sentence */}
      <PracticeRecapCard recap={summary?.recap} />

      {/* 4 · three status columns inside one hairline frame */}
      <section
        className={cn(
          CARD,
          "grid grid-cols-1 divide-y divide-[var(--bz-border)] overflow-hidden md:grid-cols-3 md:divide-x md:divide-y-0",
        )}
      >
        <StatusCard
          title="Immigration"
          aria-label="Immigration status"
          status={defaultDashboard.visa.status}
          label={defaultDashboard.visa.type || "No Visa"}
          expiry={defaultDashboard.visa.expiryDate}
          daysRemaining={defaultDashboard.visa.daysRemaining}
          onClick={() => router.push("/portal/visa")}
        />
        <StatusCard
          title="Company"
          aria-label="Company status"
          status={defaultDashboard.company.status}
          label={defaultDashboard.company.primaryCompanyName || "No Company"}
          subLabel={`${defaultDashboard.company.totalCompanies} compan${defaultDashboard.company.totalCompanies !== 1 ? "ies" : "y"}`}
          onClick={() => router.push("/portal/companies")}
        />
        <StatusCard
          title="Tax"
          aria-label="Tax status"
          status={defaultDashboard.taxes.status}
          label={
            defaultDashboard.taxes.nextDeadline
              ? formatDate(defaultDashboard.taxes.nextDeadline, {
                  month: "short",
                  day: "numeric",
                })
              : "No Deadline"
          }
          subLabel={
            defaultDashboard.taxes.daysToDeadline
              ? `${defaultDashboard.taxes.daysToDeadline} days`
              : "None tracked"
          }
          onClick={() => router.push("/portal/taxes")}
        />
      </section>

      {/* 5 · quick stats — two quiet chips, same conditions and handlers */}
      {(defaultDashboard.documents.pending > 0 ||
        defaultDashboard.messages.unread > 0) && (
        <section className="flex flex-wrap gap-2.5">
          {defaultDashboard.documents.pending > 0 && (
            <button
              type="button"
              onClick={() => {
                window.location.href = "/portal/process";
              }}
              className={cn(
                "flex h-10 items-center gap-2 rounded-full border border-[var(--tx-tertiary)] px-4 text-[13px] font-semibold text-[var(--tx-primary)] transition-colors hover:bg-[var(--bz-surface)]",
                FOCUS,
              )}
            >
              <FileText className="h-4 w-4 text-[var(--bz-copper)]" />
              {defaultDashboard.documents.pending} document
              {defaultDashboard.documents.pending !== 1 ? "s" : ""} pending
            </button>
          )}
          {defaultDashboard.messages.unread > 0 && (
            <button
              type="button"
              onClick={() => {
                window.location.href = "/portal/messages";
              }}
              className={cn(
                "flex h-10 items-center gap-2 rounded-full border border-[var(--tx-tertiary)] px-4 text-[13px] font-semibold text-[var(--tx-primary)] transition-colors hover:bg-[var(--bz-surface)]",
                FOCUS,
              )}
            >
              <MessageCircle className="h-4 w-4 text-[var(--bz-copper)]" />
              {defaultDashboard.messages.unread} unread message
              {defaultDashboard.messages.unread !== 1 ? "s" : ""}
            </button>
          )}
        </section>
      )}

      {/* 6 · action required — numbered, priority is a word, never a fill */}
      {defaultDashboard.actions.length > 0 && (
        <section>
          <SectionHead
            title="Action required"
            linkLabel="All processes"
            href="/portal/process"
          />
          <ol className="flex flex-col gap-2">
            {defaultDashboard.actions.map((action, i) => {
              const priority =
                action.priority === "high"
                  ? { tone: "you" as PillTone, label: "Needs you" }
                  : action.priority === "medium"
                    ? { tone: "ours" as PillTone, label: "Soon" }
                    : { tone: "wait" as PillTone, label: "Pending" };
              return (
                <li key={action.id}>
                  <button
                    type="button"
                    onClick={() => {
                      window.location.href = action.href;
                    }}
                    className={cn(
                      CARD,
                      "grid w-full grid-cols-[30px_1fr] items-center gap-3 px-4 py-3.5 text-left transition-colors hover:border-[var(--bz-border-hover)] md:grid-cols-[36px_1fr_auto] md:gap-4 md:px-5 md:py-4",
                      FOCUS,
                    )}
                  >
                    <span
                      className="text-[22px] leading-none tabular-nums text-[var(--bz-copper-text)]"
                      style={SERIF}
                    >
                      {pad2(i + 1)}
                    </span>
                    <span className="min-w-0">
                      <span className="block font-semibold text-[var(--tx-pure)]">
                        {action.title}
                      </span>
                      <span className="block text-[13px] text-[var(--tx-secondary)]">
                        {action.description}
                      </span>
                    </span>
                    <span className="col-start-2 flex items-center justify-between gap-3.5 md:col-start-3 md:justify-end">
                      <StatePill tone={priority.tone} label={priority.label} />
                      <ChevronRight className="h-4 w-4 text-[var(--tx-secondary)]" />
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </section>
      )}

      {/* 7 · recent activity — hairline spine, one dot per event */}
      <section>
        <SectionHead
          title="Recent activity"
          linkLabel="Vault"
          href="/portal/vault"
        />

        <div className="relative pl-[22px]">
          <div
            aria-hidden="true"
            className="absolute left-[5px] top-[6px] bottom-[6px] w-px bg-[var(--bz-border-hover)]"
          />
          {visibleTimeline.map((entry: TimelineEntry, index: number) => (
            <TimelineItem
              key={entry.id}
              entry={entry}
              isLast={index === visibleTimeline.length - 1}
            />
          ))}

          {timeline.length === 0 && (
            <div className="py-2 text-[var(--tx-secondary)]">
              No activity yet. Your journey starts here.
            </div>
          )}
        </div>

        {!showAllTimeline && timeline.length > TIMELINE_PREVIEW_COUNT && (
          <button
            type="button"
            onClick={() => setShowAllTimeline(true)}
            className={cn(
              "mt-2 text-xs font-semibold text-[var(--bz-copper-text)] transition-colors hover:text-[var(--tx-pure)]",
              FOCUS,
            )}
          >
            Show {timeline.length - TIMELINE_PREVIEW_COUNT} more events
          </button>
        )}
      </section>
    </div>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function StatusCard({
  title,
  status,
  label,
  subLabel,
  expiry,
  daysRemaining,
  onClick,
  "aria-label": ariaLabel,
}: {
  title: string;
  status:
    | "active"
    | "warning"
    | "expired"
    | "pending"
    | "none"
    | "upcoming"
    | "attention"
    | "overdue";
  label: string;
  subLabel?: string;
  expiry?: string | null;
  daysRemaining?: number | null;
  onClick?: () => void;
  // Callers already passed aria-label but it was silently dropped (WS3 a11y
  // fix): forward it to the button so the card has an accessible name.
  "aria-label"?: string;
}) {
  const { formatDate } = usePortalDateFormat();

  // One vocabulary for the whole portal: four words, four meanings, no fill.
  const getState = (s: string): { tone: PillTone; label: string } => {
    switch (s) {
      case "active":
        return { tone: "ok", label: "Active" };
      case "warning":
      case "attention":
        return { tone: "you", label: "Needs you" };
      case "expired":
        return { tone: "you", label: "Expired" };
      case "overdue":
        return { tone: "you", label: "Overdue" };
      case "pending":
      case "upcoming":
        return { tone: "ours", label: "In progress" };
      default:
        return { tone: "wait", label: "Nothing tracked" };
    }
  };
  const state = getState(status);

  // Expiry tiers consolidated 4→3 for AA on the day theme (WS3); the copper
  // step carries every "needs you" case — no red on this surface.
  const getExpiryInfo = () => {
    if (!expiry) return { text: subLabel || "", color: "" };
    const formatted = formatDate(expiry, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
    if (daysRemaining !== null && daysRemaining !== undefined) {
      if (daysRemaining < 0)
        return {
          text: `Expired ${Math.abs(daysRemaining)}d ago`,
          color: "text-[var(--bz-copper-text)]",
        };
      if (daysRemaining === 0)
        return {
          text: "Expires today",
          color: "text-[var(--bz-copper-text)]",
        };
      if (daysRemaining <= 90)
        return {
          text: `${daysRemaining}d left`,
          color: "text-[var(--bz-copper-text)]",
        };
    }
    return { text: `Expires ${formatted}`, color: "" };
  };
  const expiryInfo = getExpiryInfo();

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      className={cn(
        "flex min-h-[150px] cursor-pointer flex-col items-start gap-1.5 px-5 py-5 text-left transition-colors hover:bg-[var(--bz-base)] md:px-6",
        FOCUS,
      )}
    >
      <span className={EYEBROW}>{title}</span>
      <span
        className="mt-1 max-w-full truncate text-[24px] leading-[1.14] tracking-[-0.02em] text-[var(--tx-pure)]"
        style={SERIF}
      >
        {label}
      </span>
      <span
        className={cn(
          "text-[13px] tabular-nums text-[var(--tx-secondary)]",
          expiryInfo.color,
        )}
        title={
          expiry
            ? formatDate(expiry, {
                month: "long",
                day: "numeric",
                year: "numeric",
              })
            : undefined
        }
      >
        {expiryInfo.text}
      </span>
      <span className="mt-auto pt-3">
        <StatePill tone={state.tone} label={state.label} />
      </span>
    </button>
  );
}

// ============================================================================
// V2 Matter-First Hero Cards — next move + numbered index
// ============================================================================

function HeroCards({
  summary,
  onOpenMatter,
}: {
  summary: DashboardSummary | undefined;
  onOpenMatter: (id: number | string) => void;
}) {
  if (!summary) return null;

  const empty =
    summary.open_actions.length === 0 &&
    summary.upcoming_deadlines.length === 0 &&
    (summary.unread_messages ?? 0) === 0;

  if (empty) {
    return (
      <section
        className={cn(CARD, "px-6 py-8 text-center")}
        aria-label="Your matters"
      >
        <h2
          className={cn(SECTION_H2, "text-[var(--state-success)]")}
          style={SERIF}
        >
          All caught up
        </h2>
        <p className="mt-1.5 text-sm text-[var(--tx-secondary)]">
          No open actions, no deadlines in the next 30 days.
        </p>
      </section>
    );
  }

  const total = summary.open_actions.length;
  const [lead, ...rest] = summary.open_actions;

  return (
    <section className="space-y-5" aria-label="Your matters">
      {lead && (
        <article
          className={cn(
            CARD,
            "grid gap-6 p-6 shadow-[0_10px_30px_rgba(29,44,59,0.045)] md:grid-cols-[1fr_auto] md:items-end md:p-7",
          )}
        >
          <div>
            <p className={EYEBROW}>
              Your next move · matter{" "}
              <span className="tabular-nums">{pad2(1)}</span> of{" "}
              <span className="tabular-nums">{pad2(total)}</span>
            </p>
            <h2
              className="mt-2.5 max-w-[26ch] text-[26px] leading-[1.12] tracking-[-0.02em] text-[var(--tx-pure)] md:text-[30px]"
              style={SERIF}
            >
              {lead.title}
            </h2>
            <p className="mt-2.5 max-w-[56ch] text-[var(--tx-secondary)]">
              {matterState(lead.status, lead.pending_from_client).sentence}
              {lead.pending_from_client ? (
                <>
                  {" "}
                  Still needed from you:{" "}
                  <b className="font-semibold text-[var(--bz-copper-text)]">
                    {lead.pending_from_client}
                  </b>
                  .
                </>
              ) : null}
            </p>
            <p className="mt-3.5 flex flex-wrap gap-x-[18px] gap-y-2 text-xs text-[var(--tx-secondary)]">
              <span>
                Ref{" "}
                <b className="font-semibold tabular-nums text-[var(--tx-pure)]">
                  {lead.id}
                </b>
              </span>
              {lead.type && (
                <span>
                  Type{" "}
                  <b className="font-semibold text-[var(--tx-pure)]">
                    {lead.type.replace(/[_-]+/g, " ")}
                  </b>
                </span>
              )}
            </p>
          </div>
          <Button
            onClick={() => onOpenMatter(lead.id)}
            className="h-12 rounded px-[22px] text-[13px] font-semibold tracking-[0.02em] bg-[var(--state-success)] text-white hover:bg-[var(--state-success)]/90 md:min-w-[180px]"
          >
            Open matter
          </Button>
        </article>
      )}

      {rest.length > 0 && (
        <ol className="border-t border-[var(--bz-border)]">
          {rest.map((a, i) => {
            const state = matterState(a.status, a.pending_from_client);
            return (
              <li key={a.id}>
                <button
                  type="button"
                  onClick={() => onOpenMatter(a.id)}
                  className={cn(
                    "grid w-full grid-cols-[36px_1fr] items-center gap-3 border-b border-[var(--bz-border)] py-4 text-left md:grid-cols-[44px_1fr_auto] md:gap-4",
                    FOCUS,
                  )}
                >
                  <span
                    className="text-[26px] leading-none tabular-nums text-[var(--bz-copper-text)]"
                    style={SERIF}
                  >
                    {pad2(i + 2)}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate font-semibold text-[var(--tx-pure)]">
                      {a.title}
                    </span>
                    <span className="block truncate text-[13px] text-[var(--tx-secondary)]">
                      {a.pending_from_client || state.sentence}
                    </span>
                  </span>
                  <span className="col-start-2 flex items-center justify-between gap-3.5 md:col-start-3 md:justify-end">
                    <StatePill tone={state.tone} label={state.label} />
                    <ChevronRight className="h-4 w-4 text-[var(--tx-secondary)]" />
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      )}

      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <span className={EYEBROW}>Deadlines · next 30 days</span>
        <a
          href="/api/portal/deadlines/ical"
          download
          className="text-xs font-semibold text-[var(--bz-copper-text)] hover:text-[var(--tx-pure)] transition-colors"
        >
          Export iCal
        </a>
      </div>
      {summary.upcoming_deadlines.length === 0 ? (
        <p className="text-[13px] text-[var(--tx-secondary)]">
          No upcoming deadlines.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {summary.upcoming_deadlines.slice(0, 5).map((d) => (
            <li key={d.id} className="flex items-center gap-2.5 text-[13px]">
              {d.due_date && <DeadlineBadge date={new Date(d.due_date)} />}
              <span className="truncate text-[var(--tx-primary)]">
                {d.label}
              </span>
            </li>
          ))}
        </ul>
      )}

      {(summary.unread_messages ?? 0) > 0 && (
        <button
          type="button"
          onClick={() => {
            window.location.href = "/portal/messages";
          }}
          className={cn(
            "flex w-full items-center justify-between gap-4 border-t border-[var(--bz-border)] pt-4 text-left text-[13px] text-[var(--tx-secondary)]",
            FOCUS,
          )}
        >
          <span>
            <b className="font-semibold tabular-nums text-[var(--tx-pure)]">
              {summary.unread_messages}
            </b>{" "}
            unread from your team
          </span>
          <ChevronRight className="h-4 w-4" />
        </button>
      )}
    </section>
  );
}
