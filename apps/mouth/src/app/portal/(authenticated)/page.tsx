"use client";

/**
 * Portal Dashboard Page
 *
 * Usa React Query per caching e ottimizzazione
 *
 * WS3 (GARUDA Day Edition, 2026-07-24): day-theme token alignment.
 * State colors read the semantic --state-* tokens (WS2 AA light overrides),
 * copper accents read --bz-copper / --bz-copper-text (daylight steps armed
 * in globals.css [data-theme="operative-light"]). No hardcoded hexes.
 */

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import {
  CheckCircle2,
  AlertTriangle,
  Clock,
  ChevronRight,
  FileText,
  MessageCircle,
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
  PortalPageLoader,
  PortalListSkeleton,
} from "@/components/portal";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { TimelineEntry } from "@/lib/api/types/timeline.types";
import type { DashboardSummary } from "@/lib/api/portal/portal.types";
import { DeadlineBadge } from "@balizero/core";

export default function PortalHomePage() {
  const router = useRouter();
  const {
    data: dashboard,
    isLoading: isLoadingDashboard,
    isError,
    error,
  } = usePortalDashboard();
  const { data: summary } = usePortalDashboardSummary();
  const { data: timelineData, isLoading: isLoadingTimeline } =
    usePortalTimeline(20);

  const timeline = timelineData?.entries || [];
  const [showAllTimeline, setShowAllTimeline] = useState(false);
  const TIMELINE_PREVIEW_COUNT = 5;
  const visibleTimeline = showAllTimeline
    ? timeline
    : timeline.slice(0, TIMELINE_PREVIEW_COUNT);

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
  if (isError) {
    return (
      <div className="space-y-6">
        <section>
          <div
            aria-hidden="true"
            className="w-14 h-[3px] rounded-sm mb-4 bg-[var(--bz-copper)]"
          />
          <h1
            className="text-2xl font-semibold tracking-tight text-[var(--foreground)]"
            style={{ fontFamily: "var(--font-serif)" }}
          >
            Welcome Back
          </h1>
          <p className="text-[var(--foreground-muted)]">
            Here is your Bali life overview.
          </p>
        </section>

        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Unable to load dashboard</AlertTitle>
          <AlertDescription>
            {error instanceof Error
              ? error.message
              : "An unexpected error occurred. Please try again."}
          </AlertDescription>
        </Alert>

        <Button onClick={() => window.location.reload()}>Retry</Button>
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
      status: "compliant" as const,
      nextDeadline: null,
      daysToDeadline: null,
    },
    documents: { total: 0, pending: 0 },
    messages: { unread: 0 },
    actions: [],
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Welcome Section — Day masthead (GARUDA Day Edition): copper rule +
          Cormorant serif headline per concept (--font-serif, wired on <html>);
          Inter everywhere else. */}
      <section>
        <div
          aria-hidden="true"
          className="w-14 h-[3px] rounded-sm mb-4 bg-[var(--bz-copper)]"
        />
        <h1
          className="text-3xl font-semibold tracking-tight text-[var(--tx-pure)]"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Welcome Back
        </h1>
        <p className="text-[var(--tx-secondary)] mt-1">
          Here is your Bali life overview.
        </p>
      </section>

      {/* V2 Matter-First Hero Cards */}
      <HeroCards
        summary={summary}
        onOpenMatter={(id) => router.push(`/portal/matters/${id}`)}
      />

      {/* Status Cards (Traffic Lights) */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
              ? new Date(
                  defaultDashboard.taxes.nextDeadline,
                ).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                })
              : "All Good"
          }
          subLabel={
            defaultDashboard.taxes.daysToDeadline
              ? `${defaultDashboard.taxes.daysToDeadline} days`
              : "Up to date"
          }
          onClick={() => router.push("/portal/taxes")}
        />
      </section>

      {/* Quick Stats Bar */}
      {(defaultDashboard.documents.pending > 0 ||
        defaultDashboard.messages.unread > 0) && (
        <section className="flex flex-wrap gap-3">
          {defaultDashboard.documents.pending > 0 && (
            <button
              type="button"
              onClick={() => {
                window.location.href = "/portal/process";
              }}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg border cursor-pointer transition-all hover:scale-[1.01]"
              style={{
                background:
                  "color-mix(in srgb, var(--state-warning) 7%, transparent)",
                borderColor:
                  "color-mix(in srgb, var(--state-warning) 25%, transparent)",
              }}
            >
              <FileText className="w-4 h-4 text-[var(--state-warning)]" />
              <span className="text-sm font-medium text-[var(--state-warning)]">
                {defaultDashboard.documents.pending} document
                {defaultDashboard.documents.pending !== 1 ? "s" : ""} pending
              </span>
            </button>
          )}
          {defaultDashboard.messages.unread > 0 && (
            <button
              type="button"
              onClick={() => {
                window.location.href = "/portal/messages";
              }}
              className="flex items-center gap-2 px-4 py-2.5 rounded-lg border cursor-pointer transition-all hover:scale-[1.01]"
              style={{
                background:
                  "color-mix(in srgb, var(--state-info) 7%, transparent)",
                borderColor:
                  "color-mix(in srgb, var(--state-info) 25%, transparent)",
              }}
            >
              <MessageCircle className="w-4 h-4 text-[var(--state-info)]" />
              <span className="text-sm font-medium text-[var(--state-info)]">
                {defaultDashboard.messages.unread} unread message
                {defaultDashboard.messages.unread !== 1 ? "s" : ""}
              </span>
            </button>
          )}
        </section>
      )}

      {/* Action Items */}
      {defaultDashboard.actions.length > 0 && (
        <section className="space-y-3">
          <h2
            className="text-lg font-semibold"
            style={{ color: "var(--bz-text-1)" }}
          >
            Action Required
          </h2>
          <div className="space-y-2">
            {defaultDashboard.actions.map((action) => (
              <button
                key={action.id}
                type="button"
                onClick={() => {
                  window.location.href = action.href;
                }}
                className={cn(
                  "flex items-center justify-between p-4 rounded-lg border cursor-pointer transition-all hover:scale-[1.01] w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-accent-warm)]",
                  action.priority === "high"
                    ? "bg-[color-mix(in_srgb,var(--state-danger)_8%,transparent)] border-[color-mix(in_srgb,var(--state-danger)_25%,transparent)] text-[var(--state-danger)]"
                    : action.priority === "medium"
                      ? "bg-[color-mix(in_srgb,var(--state-warning)_8%,transparent)] border-[color-mix(in_srgb,var(--state-warning)_25%,transparent)] text-[var(--state-warning)]"
                      : "bg-[color-mix(in_srgb,var(--state-info)_8%,transparent)] border-[color-mix(in_srgb,var(--state-info)_25%,transparent)] text-[var(--state-info)]",
                )}
              >
                <div>
                  <h3 className="font-medium">{action.title}</h3>
                  <p className="text-sm opacity-80">{action.description}</p>
                </div>
                <ChevronRight className="w-5 h-5" />
              </button>
            ))}
          </div>
        </section>
      )}

      {/* The Timeline */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold flex items-center gap-2 text-[var(--tx-primary)] mb-6">
          <Clock className="w-5 h-5 text-[var(--bz-copper)]" />
          Timeline
        </h2>

        <div className="relative border-l-2 ml-3 space-y-8 pb-10 border-[var(--glass-rim)]">
          {visibleTimeline.map((entry: TimelineEntry, index: number) => (
            <TimelineItem
              key={entry.id}
              entry={entry}
              isLast={index === visibleTimeline.length - 1}
            />
          ))}

          {timeline.length === 0 && (
            <div
              className="pl-6 py-4 italic"
              style={{ color: "var(--bz-text-2)" }}
            >
              No activity yet. Your journey starts here.
            </div>
          )}
        </div>

        {!showAllTimeline && timeline.length > TIMELINE_PREVIEW_COUNT && (
          <button
            onClick={() => setShowAllTimeline(true)}
            className="w-full text-center text-xs py-2 rounded-lg transition-opacity hover:opacity-80"
            style={{
              color: "var(--bz-copper-text)",
              background:
                "color-mix(in srgb, var(--bz-copper) 8%, transparent)",
            }}
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
    | "compliant"
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
  // Semantic state tokens: WS2 light overrides keep these ≥4.5:1 on paper
  // (success 4.80, warning 4.78, danger 5.74, info 5.94 — see semantic.css).
  const getStatusStyle = (s: string) => {
    switch (s) {
      case "active":
      case "compliant":
        return "bg-[color-mix(in_srgb,var(--state-success)_6%,transparent)] text-[var(--state-success)] border-[color-mix(in_srgb,var(--state-success)_25%,transparent)]";
      case "warning":
      case "attention":
        return "bg-[color-mix(in_srgb,var(--state-warning)_6%,transparent)] text-[var(--state-warning)] border-[color-mix(in_srgb,var(--state-warning)_25%,transparent)]";
      case "expired":
      case "overdue":
        return "bg-[color-mix(in_srgb,var(--state-danger)_6%,transparent)] text-[var(--state-danger)] border-[color-mix(in_srgb,var(--state-danger)_25%,transparent)]";
      default:
        return "bg-[var(--glass-rim)] text-[var(--tx-secondary)] border-[var(--glass-rim)]";
    }
  };

  const getIcon = (s: string) => {
    switch (s) {
      case "active":
      case "compliant":
        return <CheckCircle2 className="w-5 h-5" />;
      case "warning":
      case "attention":
      case "expired":
      case "overdue":
        return <AlertTriangle className="w-5 h-5" />;
      default:
        return <Clock className="w-5 h-5" />;
    }
  };

  // Expiry tiers consolidated 4→3 for AA on the day theme (WS3): the old
  // 31–90d tier used yellow-300 (1.17:1 on paper — unreadable); it now
  // shares the warning step with the ≤30d tier.
  const getExpiryInfo = () => {
    if (!expiry) return { text: subLabel || "", color: "" };
    const date = new Date(expiry);
    const formatted = date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
    if (daysRemaining !== null && daysRemaining !== undefined) {
      if (daysRemaining < 0)
        return {
          text: `Expired ${Math.abs(daysRemaining)}d ago`,
          color: "text-[var(--state-danger)]",
        };
      if (daysRemaining === 0)
        return { text: "Expires today", color: "text-[var(--state-danger)]" };
      if (daysRemaining <= 90)
        return {
          text: `⏰ ${daysRemaining}d left`,
          color: "text-[var(--state-warning)]",
        };
    }
    return {
      text: `Expires: ${formatted}`,
      color: "text-[var(--state-success)]",
    };
  };
  const expiryInfo = getExpiryInfo();

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={ariaLabel}
      className={cn(
        "crystal-stat-card cursor-pointer !flex !flex-col border transition-all duration-200 hover:scale-[1.02] hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-accent-warm)]",
        getStatusStyle(status),
      )}
    >
      <div className="flex justify-between items-start mb-2">
        <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--tx-secondary)]">
          {title}
        </span>
        {getIcon(status)}
      </div>
      <div className="font-bold text-2xl font-mono text-[var(--tx-pure)] leading-tight truncate">
        {label}
      </div>
      <div
        className={cn(
          "text-[10px] uppercase font-bold tracking-widest mt-2",
          expiryInfo.color,
        )}
        title={
          expiry
            ? new Date(expiry).toLocaleDateString("en-US", {
                month: "long",
                day: "numeric",
                year: "numeric",
              })
            : undefined
        }
      >
        {expiryInfo.text}
      </div>
    </button>
  );
}

// ============================================================================
// V2 Matter-First Hero Cards
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
      <section className="crystal-stat-card !flex !flex-col items-center justify-center p-8 text-center">
        <CheckCircle2 className="w-10 h-10 text-[var(--state-success)] mb-3" />
        <h2 className="text-xl font-bold text-[var(--tx-pure)]">
          All caught up
        </h2>
        <p className="text-sm text-[var(--tx-secondary)] mt-1">
          No open actions, no deadlines in the next 30 days.
        </p>
      </section>
    );
  }

  return (
    <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <article className="crystal-stat-card !flex !flex-col p-5 min-h-[180px]">
        <h2 className="text-[10px] font-bold uppercase tracking-widest text-[var(--tx-secondary)] mb-3">
          Open Actions
        </h2>
        {summary.open_actions.length === 0 ? (
          <p className="text-sm text-[var(--tx-secondary)] italic">
            None pending
          </p>
        ) : (
          <ul className="space-y-2">
            {summary.open_actions.slice(0, 5).map((a) => (
              <li key={a.id}>
                <button
                  type="button"
                  onClick={() => onOpenMatter(a.id)}
                  className="text-left text-sm text-[var(--tx-primary)] hover:text-[var(--bz-copper-text)] transition-colors w-full truncate"
                >
                  {a.title}
                </button>
              </li>
            ))}
          </ul>
        )}
      </article>

      <article className="crystal-stat-card !flex !flex-col p-5 min-h-[180px]">
        <h2 className="text-[10px] font-bold uppercase tracking-widest text-[var(--tx-secondary)] mb-3">
          Deadlines · Next 30 days
        </h2>
        {summary.upcoming_deadlines.length === 0 ? (
          <p className="text-sm text-[var(--tx-secondary)] italic">
            No upcoming deadlines
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {summary.upcoming_deadlines.slice(0, 5).map((d) => (
              <li key={d.id} className="flex items-center gap-2 text-sm">
                {d.due_date && <DeadlineBadge date={new Date(d.due_date)} />}
                <span className="text-[var(--tx-primary)] truncate">
                  {d.label}
                </span>
              </li>
            ))}
          </ul>
        )}
        <a
          href="/api/portal/deadlines/ical"
          download
          className="mt-auto text-[10px] uppercase tracking-widest font-bold text-[var(--bz-copper-text)] hover:text-[var(--tx-pure)] transition-colors"
        >
          Export iCal →
        </a>
      </article>

      <article className="crystal-stat-card !flex !flex-col p-5 min-h-[180px]">
        <h2 className="text-[10px] font-bold uppercase tracking-widest text-[var(--tx-secondary)] mb-3">
          Team Messages
        </h2>
        <div className="flex-1 flex flex-col items-center justify-center">
          <span className="text-4xl font-bold text-[var(--tx-pure)]">
            {summary.unread_messages}
          </span>
          <span className="text-xs text-[var(--tx-secondary)] mt-1">
            unread
          </span>
        </div>
        <button
          type="button"
          onClick={() => {
            window.location.href = "/portal/messages";
          }}
          className="mt-auto text-[10px] uppercase tracking-widest font-bold text-[var(--bz-copper-text)] hover:text-[var(--tx-pure)] transition-colors self-start"
        >
          Open →
        </button>
      </article>
    </section>
  );
}
