"use client";

/**
 * The kita dashboard — concept-K v2 "TEPAT FORTE"
 * (R19-KITA-20260914/fusion/concept.md §2 "02 Dashboard").
 *
 * A live operations ledger, not a set of cards: the page opens on a 40px
 * Fraunces masthead, then numbered hairline sections in the order the fusion
 * freezes and §7 forbids reordering — Portal Champion (where PR #6483 shipped
 * it), Zantara, the action margin, the KPI band, team activity, ops, and the
 * pipeline / intelligence / role triple.
 *
 * Copper appears ONLY where the signed-in viewer is the next actor, derived in
 * `_lib/actionMargin.ts` from the viewer and the record together. Expiries and
 * countdowns take `--state-warning`; terminal states take muted plus their
 * word. There is no red on this page.
 */

import React from "react";
import Link from "next/link";
import { Sparkles } from "lucide-react";
import { RoleWidget } from "@/components/dashboard";
import { DashboardErrorBoundary } from "@/components/ErrorBoundary";
import { TeamActivityPanel } from "@/components/dashboard/TeamActivityPanel";
import type {
  TeamMemberStats,
  TeamOverview,
} from "@/components/dashboard/TeamActivityPanel";
import { dashboardQueryKey, useDashboardData } from "@/hooks/useDashboardData";
import { useRealtime } from "@/lib/realtime";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { normalizeDashboardRole } from "@/lib/dashboard-role";
import { logger } from "@/lib/logger";
import { STRINGS } from "@/lib/strings";
import { api } from "@/lib/api";
import { formatIDRCompact } from "@balizero/core/utils";
import {
  ComplianceRadar,
  SystemPulse,
  type ComplianceAlert,
  type SystemPulseService,
} from "@balizero/core";
import {
  EmptyState,
  Eyebrow,
  Masthead,
  StatePill,
} from "@/components/workspace/r19";
import { getComplianceAlerts, getSystemPulse } from "./_lib/opsAdapters";
import {
  buildActionMargin,
  mastheadSentence,
  type ActionMarginItem,
} from "./_lib/actionMargin";
import {
  DeskLink,
  Kpi,
  KpiBand,
  LedgerRow,
  LedgerSection,
  type KpiTone,
} from "./desk";
import { PortalChallengeWidget } from "./PortalChallengeWidget";
import { RefreshCw } from "lucide-react";

// ── Intel categories ───────────────────────────────────────
// There is no category COLOUR here any more. The old map read the
// --bz-chart-* ramp, which the kita theme block deliberately does not
// redeclare (globals.css says so in as many words), so on this page it paints
// the pre-R19 palette — and `--bz-chart-5` is literally `var(--bz-copper)`.
// An article's subject would then have painted the one colour that means "you
// are the next actor", keyed off a raw `article.category` string. The fusion's
// own intelligence feed carries the category as a WORD in the eyebrow and no
// colour at all, which is what the rows below do.

interface IntelArticle {
  slug: string;
  title: string;
  category: string;
  publishedAt: string;
  excerpt?: string;
}

function useIntelFeed(identity: string) {
  return useQuery<IntelArticle[]>({
    queryKey: ["intel-feed", identity],
    queryFn: async () => {
      const data = await api.blog.listArticles(8, 0);
      return ((data.articles ?? []) as IntelArticle[]).slice(0, 8);
    },
    staleTime: 5 * 60_000,
    refetchInterval: 10 * 60_000,
    enabled: Boolean(identity),
  });
}

// ── Intake review queue hook ───────────────────────────────
// Backend RBAC scopes the queue: team members get docs they received
// (own-chat), admins get everything. Failure = silently hide the family (the
// reader runs on the Pro; if the tunnel is down the dashboard must not
// degrade).
//
// Same URL, same request, same query key as before — it returns the ITEMS
// rather than discarding them on `.length`, which is the one code change
// concept-K DISPOSITION C3 sanctions so the action margin can be built from
// data the page already fetches.
function useIntakeReviewQueue(identity: string) {
  return useQuery<unknown[]>({
    queryKey: ["intake-review-count", identity],
    queryFn: async () => {
      const res = await api.get<{ items: unknown[] }>(
        "/api/intake/review/queue?status=review_pending&limit=50",
      );
      return res.items ?? [];
    },
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
    retry: false,
    enabled: Boolean(identity),
  });
}

// ── Ops panels (WS2 slice 2) ───────────────────────────────
// System Pulse probes /api/admin/system-health for admins only; Compliance
// Radar reads /api/compliance/alerts with backend RBAC. Both query keys include
// the authenticated identity so a browser-session account switch cannot reuse
// the previous user's cached rows.
function useSystemPulse(identity: string, enabled: boolean) {
  return useQuery<SystemPulseService[]>({
    queryKey: ["system-pulse", identity],
    queryFn: getSystemPulse,
    staleTime: 60_000,
    refetchInterval: 2 * 60_000,
    retry: false,
    enabled: enabled && Boolean(identity),
  });
}

function useComplianceAlerts(identity: string) {
  return useQuery<ComplianceAlert[]>({
    queryKey: ["compliance-radar", identity],
    queryFn: () => getComplianceAlerts(6),
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
    retry: false,
    enabled: Boolean(identity),
  });
}

// ── Team stats hook ────────────────────────────────────────
interface TeamStatsResult {
  members: TeamMemberStats[];
  overview: TeamOverview | null;
}

function useTeamStats(identity: string, enabled: boolean) {
  return useQuery<TeamStatsResult>({
    queryKey: ["team-stats", identity],
    enabled: enabled && Boolean(identity),
    queryFn: async () => {
      const [membersData, overviewData, practiceData] = await Promise.all([
        api.adminApi
          .getTeamStats()
          .catch(
            () =>
              ({ team_stats: [] as TeamMemberStats[] }) as Record<
                string,
                unknown
              >,
          ),
        api.adminApi.getTeamActivityOverview().catch(() => null),
        api.adminApi.getPracticeStats().catch(() => ({ practice_stats: [] })),
      ]);
      const rawMembers: TeamMemberStats[] = Array.isArray(membersData)
        ? membersData
        : Array.isArray((membersData as Record<string, unknown>)?.team_stats)
          ? ((membersData as Record<string, unknown>)
              .team_stats as TeamMemberStats[])
          : [];

      // Merge practice stats by email
      const practiceMap = new Map<
        string,
        { completed: number; active: number; revenue: number }
      >();
      if (practiceData && Array.isArray(practiceData.practice_stats)) {
        for (const p of practiceData.practice_stats) {
          practiceMap.set(p.email, {
            completed: p.completed ?? 0,
            active: p.active ?? 0,
            revenue: p.revenue ?? 0,
          });
        }
      }

      const members: TeamMemberStats[] = rawMembers.map((m) => {
        const ps = practiceMap.get(m.email);
        return {
          ...m,
          practices_completed: ps?.completed ?? 0,
          practices_active: ps?.active ?? 0,
          practices_revenue: ps?.revenue ?? 0,
        };
      });

      const overview: TeamOverview | null =
        ((overviewData as unknown as Record<string, unknown>)
          ?.stats as TeamOverview) ??
        (overviewData as unknown as TeamOverview) ??
        null;
      return { members, overview };
    },
    staleTime: 3 * 60_000,
    refetchInterval: 5 * 60_000,
  });
}

// ── Practice status → the four meanings ────────────────────
// A status says what PHASE a record is in. It never says who moves next, so
// nothing here returns the `you` tone — ownership is decided in
// `_lib/actionMargin.ts` from the viewer and the record together.
const STATUS_CONFIG = {
  inquiry: { label: "Inquiry", tone: "wait" },
  quotation: { label: "Quotation", tone: "wait" },
  in_progress: { label: "On process", tone: "ours" },
  documents: { label: "Documents", tone: "wait" },
  completed: { label: "Completed", tone: "ok" },
} as const;

// ── Pipeline row ───────────────────────────────────────────
interface CasePreview {
  id: number;
  title: string;
  client: string;
  status: "inquiry" | "quotation" | "in_progress" | "documents" | "completed";
  daysRemaining?: number;
}

/**
 * A due date is URGENCY, never ownership: it takes the warning word and never
 * copper (fusion DISPOSITION F3, F10). A terminal record carries muted plus
 * its own word, which the state pill already supplies.
 */
function dueWord(p: CasePreview): { text: string; tone: KpiTone } | null {
  if (p.status === "completed" || p.daysRemaining === undefined) return null;
  if (p.daysRemaining <= 0) return { text: "Overdue", tone: "warn" };
  if (p.daysRemaining <= 3)
    return { text: `${p.daysRemaining}d left`, tone: "warn" };
  return { text: `${p.daysRemaining}d`, tone: "ink" };
}

function PipelineRow({ p, mark }: { p: CasePreview; mark: string }) {
  const cfg = STATUS_CONFIG[p.status];
  const due = dueWord(p);
  return (
    <LedgerRow
      mark={mark}
      primary={p.client}
      secondary={p.title}
      state={<StatePill tone={cfg.tone} label={cfg.label} />}
      trailing={
        due ? (
          <span
            className={due.tone === "warn" ? "text-[var(--state-warning)]" : ""}
          >
            {due.text}
          </span>
        ) : null
      }
      action={
        <DeskLink
          href={`/process/${p.id}`}
          label={`Open ${p.client} · ${p.title}`}
        >
          Open
        </DeskLink>
      }
    />
  );
}

// ── Intel article row ──────────────────────────────────────
function IntelRow({ article, mark }: { article: IntelArticle; mark: string }) {
  const catLabel = article.category.replace(/[-_]/g, " ").toUpperCase();
  const href = `https://balizero.com/${article.category}/${article.slug}`;
  const date = new Date(article.publishedAt).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
  });

  return (
    <LedgerRow
      mark={mark}
      primary={<Eyebrow className="truncate">{catLabel}</Eyebrow>}
      secondary={article.title}
      trailing={date}
      action={
        <DeskLink href={href} external label={`Read: ${article.title}`}>
          Read
        </DeskLink>
      }
    />
  );
}

// ── The action margin ──────────────────────────────────────
function MarginRow({ item, mark }: { item: ActionMarginItem; mark: string }) {
  return (
    <LedgerRow
      mark={mark}
      markTone="you"
      primary={item.title}
      secondary={item.detail}
      state={<StatePill tone="you" label={item.state} />}
      trailing={
        item.when ? (
          <span className={item.urgent ? "text-[var(--state-warning)]" : ""}>
            {item.when}
          </span>
        ) : null
      }
      action={
        <DeskLink href={item.href} tone="you" label={`Open ${item.title}`}>
          Open
        </DeskLink>
      }
    />
  );
}

// ── Main page ──────────────────────────────────────────────
export default function DashboardPage() {
  const authIdentity = api.getUserProfile()?.email?.trim().toLowerCase() ?? "";
  const { data: intelArticles, isLoading: intelLoading } =
    useIntelFeed(authIdentity);
  const {
    user,
    stats,
    practices,
    isZero,
    isLoading,
    isError,
    refetch,
    revenue,
    totalClients,
    totalPractices,
  } = useDashboardData(authIdentity);
  const dashboardIdentity = user?.email?.trim().toLowerCase() ?? "";
  const identityIsCurrent =
    Boolean(authIdentity) && dashboardIdentity === authIdentity;
  const opsIdentity = identityIsCurrent ? authIdentity : "";
  const canViewSystemPulse = identityIsCurrent && Boolean(user?.is_admin);
  const { data: pulseServices, isLoading: pulseLoading } = useSystemPulse(
    opsIdentity,
    canViewSystemPulse,
  );
  const { data: complianceAlerts, isLoading: complianceLoading } =
    useComplianceAlerts(opsIdentity);
  const { data: reviewItems } = useIntakeReviewQueue(authIdentity);

  // Team stats
  const { data: teamData, isLoading: teamLoading } = useTeamStats(
    authIdentity,
    Boolean(authIdentity),
  );

  const realtime = useRealtime();
  const queryClient = useQueryClient();
  const role = normalizeDashboardRole(user?.role, user?.is_admin ?? false);

  React.useEffect(() => {
    const unsubscribe = realtime.subscribe("dashboard_update", () => {
      if (authIdentity) {
        queryClient.invalidateQueries({
          queryKey: dashboardQueryKey(authIdentity),
        });
      }
    });
    return unsubscribe;
  }, [authIdentity, realtime, queryClient]);

  React.useEffect(() => {
    if (user?.email && !isLoading) {
      realtime.connect(user.email, user.email);
      logger.info("Dashboard loaded", {
        component: "DashboardPage",
        action: "mount",
        user: user.email,
      });
    }
  }, [user?.email, isLoading]);

  // Loading skeleton — the derived shape of the page below, so the first paint
  // does not move (fusion §10: "derived skeleton").
  if (isLoading) {
    return (
      <div className="space-y-3 p-4 md:p-6">
        <div className="h-[104px] w-full animate-pulse bg-[var(--bz-card)]" />
        <div className="h-24 w-full animate-pulse bg-[var(--bz-card)]" />
        <div className="h-24 w-full animate-pulse bg-[var(--bz-card)]" />
        <div className="h-[280px] w-full animate-pulse bg-[var(--bz-card)]" />
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="p-4 md:p-6">
        <Masthead
          eyebrow="Desk"
          title="Dashboard Error"
          subtitle="We could not load the desk. Nothing was changed."
          right={
            <button
              onClick={() => refetch()}
              className="inline-flex min-h-11 items-center gap-2 border border-[var(--line-control)] bg-[var(--bz-card)] px-3 text-[12px] font-[650] text-[var(--tx-pure)] hover:bg-[var(--bz-card-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-copper)]"
            >
              <RefreshCw className="h-4 w-4" />
              Retry
            </button>
          }
        />
      </div>
    );
  }

  // ── Derived: the margin, the sentence, the section numbering ──
  const margin = buildActionMargin({
    reviewItems,
    practices,
    // Two conditions, both required. The summary scopes its practice list to
    // `assigned_to = user_id` for every non-admin, so for an admin it is the
    // whole book and assignment is not derivable from it. And the array must
    // belong to the CURRENT identity: after an account switch the previous
    // user's dashboard response can still be in cache, and `identityIsCurrent`
    // is the same guard the ops panels already use to refuse it. Without it the
    // margin would say "Assigned to you" over somebody else's work.
    practicesAreMine: identityIsCurrent && !isZero,
  });
  const movingCount = practices.filter((p) => p.status !== "completed").length;
  const sentence = mastheadSentence(movingCount, margin.count);
  // Asia/Makassar, not the runtime's zone: this component still pre-renders on
  // the server, and a UTC server against a WITA browser disagrees about the
  // calendar day for the first eight hours of every Bali day.
  const today = new Date().toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone: "Asia/Makassar",
  });
  const marks = "ABCDEFGHIJ";
  // The ordinals are RENDERED, not stored: they restart at 02 after the margin
  // and skip System pulse when RBAC hides it.
  let n = 1;
  const nextOrdinal = () => String(++n).padStart(2, "0");

  // Stat values
  const statItems: Array<{
    label: string;
    value: string | number;
    sub?: string;
    tone?: KpiTone;
    href?: string;
  }> = isZero
    ? [
        {
          label: "Revenue · MTD",
          value: revenue?.total_revenue
            ? formatIDRCompact(revenue.total_revenue)
            : "—",
          sub: revenue?.paid_revenue
            ? STRINGS.dashboard.collectedSub(
                formatIDRCompact(revenue.paid_revenue),
              )
            : "—",
        },
        {
          label: "Outstanding",
          value: revenue?.outstanding_revenue
            ? formatIDRCompact(revenue.outstanding_revenue)
            : "—",
          sub: STRINGS.dashboard.outstandingSub,
        },
        {
          label: STRINGS.dashboard.clientsLabel,
          value:
            totalClients != null ? totalClients.toLocaleString("en-US") : "—",
          sub: STRINGS.dashboard.clientsSub,
          href: "/clients",
        },
        {
          label: STRINGS.dashboard.casesLabel,
          value: totalPractices != null ? totalPractices : "—",
          sub: STRINGS.dashboard.casesSub(
            stats.activeCases,
            stats.criticalDeadlines,
          ),
          href: "/process",
        },
        {
          label: STRINGS.dashboard.invoicesLabel,
          value: stats.pendingInvoices > 0 ? stats.pendingInvoices : "✓",
          sub:
            stats.pendingInvoices > 0
              ? STRINGS.dashboard.invoicesPendingSub
              : STRINGS.dashboard.invoicesPaidSub,
          tone: stats.pendingInvoices > 0 ? "ink" : "done",
        },
      ]
    : [
        {
          label: "My processes",
          value: stats.activeCases,
          sub: "assigned",
          href: "/process",
        },
        {
          label: "Expiring",
          value: stats.criticalDeadlines,
          sub: "within 7 days",
          // Urgency, never ownership.
          tone: stats.criticalDeadlines > 0 ? "warn" : "ink",
        },
        {
          label: "Invoices",
          value: stats.pendingInvoices > 0 ? stats.pendingInvoices : "—",
          sub: "pending",
        },
        {
          label: "Messages",
          value: stats.whatsappUnread + stats.emailUnread,
          sub: "WhatsApp + email",
        },
      ];

  return (
    <DashboardErrorBoundary>
      <div className="p-4 md:p-6">
        <Masthead
          eyebrow={
            <span className="text-[var(--bz-copper-text)]">Desk · {today}</span>
          }
          title="Today"
          subtitle={sentence}
          headingClassName="text-[32px] md:text-[40px]"
          className="mb-5"
          right={
            <Link
              href="/process/new"
              className="inline-flex min-h-11 items-center bg-[var(--state-success)] px-3.5 text-[12px] font-[650] text-[var(--bz-on-warm)] hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-copper)]"
            >
              New process
            </Link>
          }
        />

        {/* Portal Champion challenge — where PR #6483 shipped it. concept §7
            forbids reordering the dashboard's sections. */}
        <div className="mb-4">
          <PortalChallengeWidget identity={authIdentity} />
        </div>

        {/* 00 · Zantara AI */}
        <LedgerSection
          ordinal="00"
          title="Zantara AI"
          right={
            <DeskLink href="https://zantara.balizero.com/chat" external>
              <span className="flex items-center gap-1.5">
                <Sparkles size={12} aria-hidden="true" />
                Zantara AI
              </span>
            </DeskLink>
          }
        />

        {/* 01 · Your action margin — the owned queue */}
        <LedgerSection
          ordinal="01"
          title="Your action margin"
          titleId="action-margin-title"
          meta="Only work this viewer can move"
          // The copper rule is the claim "something here is yours". It goes
          // when the claim does, rather than framing "Nothing is waiting".
          owned={margin.items.length > 0}
          className="mt-4"
        >
          {margin.items.length === 0 ? (
            <EmptyState className="border-t-0">
              Nothing is waiting on you right now.
            </EmptyState>
          ) : (
            margin.items.map((item, i) => (
              <MarginRow key={item.id} item={item} mark={marks[i] ?? "·"} />
            ))
          )}
        </LedgerSection>

        {/* KPI band — the viewport peak */}
        <KpiBand label="Workspace metrics">
          {statItems.map((s) => (
            <Kpi key={s.label} {...s} />
          ))}
        </KpiBand>

        {/* 02 · Team activity — admin sees all, a team member sees own row */}
        <LedgerSection
          ordinal={nextOrdinal()}
          title="Team activity"
          meta="Recent movement"
          className="mt-4"
        >
          <TeamActivityPanel
            members={
              isZero
                ? (teamData?.members ?? [])
                : (teamData?.members ?? []).filter(
                    (m) => m.email === user?.email,
                  )
            }
            overview={isZero ? (teamData?.overview ?? null) : null}
            isLoading={teamLoading}
          />
        </LedgerSection>

        {/* Ops — System Pulse (admin only) + Compliance Radar */}
        <div
          data-testid="dashboard-ops-panels"
          className={`mt-4 grid grid-cols-1 gap-6 ${
            canViewSystemPulse ? "xl:grid-cols-2" : ""
          }`}
        >
          {canViewSystemPulse && (
            <LedgerSection
              ordinal={nextOrdinal()}
              title="System Pulse"
              meta="live stack"
            >
              {pulseLoading ? (
                <div className="flex flex-col gap-1 py-3">
                  {[1, 2, 3].map((i) => (
                    <div
                      key={i}
                      className="h-8 animate-pulse bg-[var(--bz-card)]"
                    />
                  ))}
                </div>
              ) : (
                <SystemPulse services={pulseServices ?? []} />
              )}
            </LedgerSection>
          )}

          <LedgerSection
            ordinal={nextOrdinal()}
            title="Compliance Radar"
            meta="auto-tracked"
          >
            {complianceLoading ? (
              <div className="flex flex-col gap-1 py-3">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="h-8 animate-pulse bg-[var(--bz-card)]"
                  />
                ))}
              </div>
            ) : (
              <ComplianceRadar alerts={complianceAlerts ?? []} />
            )}
          </LedgerSection>
        </div>

        {/* Process pipeline · Intelligence feed · My role */}
        {/* Equal thirds, as the fusion's `.three-col` has them. An uneven
            template starved the third column and truncated "My role" at
            1440 — measured in the dev-server render. */}
        <div className="mt-4 grid grid-cols-1 gap-6 xl:grid-cols-3">
          <LedgerSection
            ordinal={nextOrdinal()}
            title="Process pipeline"
            right={<DeskLink href="/process">View all</DeskLink>}
          >
            {practices.length === 0 ? (
              <EmptyState className="border-t-0">
                No processes assigned.
              </EmptyState>
            ) : (
              practices.map((p, i) => (
                <PipelineRow
                  key={p.id}
                  mark={marks[i] ?? "·"}
                  p={{
                    id: p.id,
                    title: p.title || "Unknown",
                    client: p.client || "Unknown Client",
                    status: p.status,
                    daysRemaining: p.daysRemaining,
                  }}
                />
              ))
            )}
          </LedgerSection>

          <LedgerSection
            ordinal={nextOrdinal()}
            title="Intelligence feed"
            right={<DeskLink href="/intelligence">All</DeskLink>}
          >
            {intelLoading && (
              <div className="flex flex-col gap-1 py-3">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div
                    key={i}
                    className="h-10 animate-pulse bg-[var(--bz-card)]"
                  />
                ))}
              </div>
            )}
            {!intelLoading &&
              (!intelArticles || intelArticles.length === 0) && (
                <EmptyState className="border-t-0">
                  No recent articles.
                </EmptyState>
              )}
            {!intelLoading &&
              intelArticles &&
              intelArticles.map((article, i) => (
                <IntelRow
                  key={article.slug}
                  article={article}
                  mark={String(i + 1).padStart(2, "0")}
                />
              ))}
          </LedgerSection>

          <LedgerSection ordinal={nextOrdinal()} title="My role">
            <div className="pt-3">
              <RoleWidget role={role} userId={user?.email ?? ""} />
            </div>
          </LedgerSection>
        </div>
      </div>
    </DashboardErrorBoundary>
  );
}
