"use client";

import React from "react";
import Link from "next/link";
import {
  ExternalLink,
  ArrowUpRight,
  Clock,
  AlertTriangle,
  CheckCircle2,
  FileText,
  TrendingUp,
} from "lucide-react";
import {
  LiveActivityFeed,
  RoleWidget,
  ZantaraPortalCard,
} from "@/components/dashboard";
import { HeroLiveWindow } from "@/components/workspace/HeroLiveWindow";
import type { PraticaPreview } from "@/components/dashboard/PratichePreview";
import { DashboardErrorBoundary } from "@/components/ErrorBoundary";
import { TeamActivityPanel } from "@/components/dashboard/TeamActivityPanel";
import type {
  TeamMemberStats,
  TeamOverview,
} from "@/components/dashboard/TeamActivityPanel";
import { useDashboardData } from "@/hooks/useDashboardData";
import { useRealtime } from "@/lib/realtime";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { normalizeDashboardRole } from "@/lib/dashboard-role";
import type { LiveActivityEvent } from "@/types/dashboard-role.types";
import { logger } from "@/lib/logger";
import { RefreshCw } from "lucide-react";

// ── Category colors ────────────────────────────────────────
const CATEGORY_COLOR: Record<string, string> = {
  visas: "#4a8ec4",
  business: "#5cb88a",
  taxes: "#b89a40",
  property: "#9880d8",
  living: "#d4845a",
  emerging_trends: "#4ab8c4",
};
function getCategoryColor(cat: string): string {
  return CATEGORY_COLOR[cat] ?? "#9880d8";
}

interface IntelArticle {
  slug: string;
  title: string;
  category: string;
  publishedAt: string;
  excerpt?: string;
}

function useIntelFeed() {
  return useQuery<IntelArticle[]>({
    queryKey: ["intel-feed"],
    queryFn: async () => {
      const res = await fetch("/api/blog/articles?limit=8&offset=0");
      if (!res.ok) throw new Error("Failed to fetch intel");
      const data = await res.json();
      return (data.articles ?? []).slice(0, 8) as IntelArticle[];
    },
    staleTime: 5 * 60_000,
    refetchInterval: 10 * 60_000,
  });
}

// ── Team stats hook ────────────────────────────────────────
interface TeamStatsResult {
  members: TeamMemberStats[];
  overview: TeamOverview | null;
}

function useTeamStats(enabled: boolean) {
  return useQuery<TeamStatsResult>({
    queryKey: ["team-stats"],
    enabled,
    queryFn: async () => {
      const [membersRes, overviewRes, practiceRes] = await Promise.all([
        fetch("/api/admin/team-activity/team-stats"),
        fetch("/api/admin/team-activity/overview"),
        fetch("/api/admin/team-activity/practice-stats"),
      ]);
      const membersJson = membersRes.ok ? await membersRes.json() : {};
      const rawMembers: TeamMemberStats[] = Array.isArray(membersJson)
        ? membersJson
        : Array.isArray(membersJson.team_stats)
          ? membersJson.team_stats
          : [];

      // Merge practice stats by email
      const practiceJson = practiceRes.ok ? await practiceRes.json() : {};
      const practiceMap = new Map<
        string,
        { completed: number; active: number; revenue: number }
      >();
      if (Array.isArray(practiceJson?.practice_stats)) {
        for (const p of practiceJson.practice_stats) {
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

      const overviewJson = overviewRes.ok ? await overviewRes.json() : null;
      const overview: TeamOverview | null =
        overviewJson?.stats ?? overviewJson ?? null;
      return { members, overview };
    },
    staleTime: 3 * 60_000,
    refetchInterval: 5 * 60_000,
  });
}

// ── Status config for practices ───────────────────────────
const STATUS_CONFIG = {
  inquiry: { label: "Inquiry", dot: "#9ca3af" },
  quotation: { label: "Quotation", dot: "#b89a40" },
  in_progress: { label: "In Progress", dot: "#4a8ec4" },
  documents: { label: "Documents", dot: "#b89a40" },
  completed: { label: "Completed", dot: "#5cb88a" },
} as const;

// ── Formatters ─────────────────────────────────────────────
function formatRevenue(rp: number): string {
  if (rp >= 1_000_000_000) return `Rp ${(rp / 1_000_000_000).toFixed(2)}B`;
  if (rp >= 1_000_000) return `Rp ${(rp / 1_000_000).toFixed(1)}M`;
  if (rp >= 1_000) return `Rp ${(rp / 1_000).toFixed(0)}K`;
  return `Rp ${rp.toFixed(0)}`;
}

// ── Metric Bar item ────────────────────────────────────────
function MetricItem({
  label,
  value,
  sub,
  accent,
  href,
}: {
  label: string;
  value: string | number;
  sub?: string;
  accent: string;
  href?: string;
}) {
  const inner = (
    <div className="flex flex-col gap-0.5 min-w-0">
      <span className="text-[9px] font-semibold text-white/30 tracking-[.10em] uppercase">
        {label}
      </span>
      <span
        className="text-[22px] font-black leading-none tracking-tight"
        style={{ color: accent }}
      >
        {value}
      </span>
      {sub && (
        <span className="text-[9px] text-white/35 font-medium">{sub}</span>
      )}
    </div>
  );
  if (href)
    return (
      <Link href={href} className="hover:opacity-80 transition-opacity">
        {inner}
      </Link>
    );
  return inner;
}

// ── Pipeline row ───────────────────────────────────────────
function PipelineRow({ p }: { p: PraticaPreview }) {
  const cfg = STATUS_CONFIG[p.status];
  const isUrgent =
    p.daysRemaining !== undefined &&
    p.daysRemaining <= 3 &&
    p.status !== "completed";
  const isExpired =
    p.daysRemaining !== undefined &&
    p.daysRemaining <= 0 &&
    p.status !== "completed";

  return (
    <Link
      href={`/process/${p.id}`}
      className="group grid items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/[0.04] transition-colors"
      style={{ gridTemplateColumns: "1fr auto auto" }}
    >
      {/* Left: client + title */}
      <div className="min-w-0">
        <p className="text-[11px] font-semibold text-white/80 truncate group-hover:text-white transition-colors">
          {p.client}
        </p>
        <p className="text-[10px] text-white/35 truncate">{p.title}</p>
      </div>

      {/* Status badge */}
      <span
        className="flex items-center gap-1.5 text-[9px] font-semibold tracking-wide whitespace-nowrap"
        style={{ color: cfg.dot }}
      >
        <span
          className="w-1.5 h-1.5 rounded-full flex-shrink-0"
          style={{ backgroundColor: cfg.dot }}
        />
        {cfg.label}
      </span>

      {/* Deadline */}
      <span
        className="text-[9px] font-semibold tabular-nums whitespace-nowrap flex items-center gap-1"
        style={{
          color: isExpired
            ? "#c45c78"
            : isUrgent
              ? "#b89a40"
              : "rgba(255,255,255,0.25)",
        }}
      >
        {p.status === "completed" ? (
          <CheckCircle2 size={10} className="opacity-60" />
        ) : isExpired ? (
          <>
            <AlertTriangle size={9} />
            Expired
          </>
        ) : p.daysRemaining !== undefined ? (
          <>
            <Clock size={9} />
            {p.daysRemaining}d
          </>
        ) : null}
      </span>
    </Link>
  );
}

// ── Intel article row ──────────────────────────────────────
function IntelRow({ article }: { article: IntelArticle }) {
  const color = getCategoryColor(article.category);
  const catLabel = article.category.replace(/[-_]/g, " ").toUpperCase();
  const href = `https://balizero.com/${article.category}/${article.slug}`;
  const date = new Date(article.publishedAt).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
  });

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex items-start gap-2.5 px-3 py-2 rounded-lg hover:bg-white/[0.04] transition-colors"
    >
      {/* Color stripe */}
      <span
        className="flex-shrink-0 w-0.5 self-stretch rounded-full mt-0.5"
        style={{ backgroundColor: color, opacity: 0.6 }}
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span
            className="text-[8px] font-bold tracking-[.08em]"
            style={{ color, opacity: 0.9 }}
          >
            {catLabel}
          </span>
          <span className="ml-auto text-[8px] text-white/25 flex-shrink-0">
            {date}
          </span>
        </div>
        <p className="text-[10px] text-white/60 leading-snug line-clamp-2 group-hover:text-white/80 transition-colors">
          {article.title}
        </p>
      </div>
    </a>
  );
}

// ── Section header ─────────────────────────────────────────
function SectionHeader({
  label,
  href,
  count,
}: {
  label: string;
  href?: string;
  count?: number;
}) {
  return (
    <div className="flex items-center justify-between px-3 pb-1">
      <span className="text-[9px] font-bold text-white/25 tracking-[.12em] uppercase">
        {label}
      </span>
      <div className="flex items-center gap-2">
        {count !== undefined && (
          <span className="text-[9px] text-white/20">{count}</span>
        )}
        {href && (
          <Link
            href={href}
            className="flex items-center gap-0.5 text-[9px] text-white/20 hover:text-white/50 transition-colors"
          >
            All <ArrowUpRight size={9} />
          </Link>
        )}
      </div>
    </div>
  );
}

// ── Divider ────────────────────────────────────────────────
function Divider() {
  return <div className="h-px mx-3 bg-white/[0.05]" />;
}

// ── Main page ──────────────────────────────────────────────
export default function DashboardPage() {
  const { data: intelArticles, isLoading: intelLoading } = useIntelFeed();

  // Team stats — loaded lazily after main data resolves
  const [teamEnabled, setTeamEnabled] = React.useState(false);
  React.useEffect(() => {
    const t = setTimeout(() => setTeamEnabled(true), 800);
    return () => clearTimeout(t);
  }, []);
  const { data: teamData, isLoading: teamLoading } = useTeamStats(teamEnabled);

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
  } = useDashboardData();

  const realtime = useRealtime();
  const queryClient = useQueryClient();
  const role = normalizeDashboardRole(user?.role, user?.is_admin ?? false);

  React.useEffect(() => {
    const unsubscribe = realtime.subscribe("dashboard_update", () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    });
    return unsubscribe;
  }, [realtime, queryClient]);

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

  // Live events from practices
  const liveEvents: LiveActivityEvent[] = React.useMemo(() => {
    return practices.slice(0, 8).map(
      (p): LiveActivityEvent => ({
        id: String(p.id),
        type:
          p.status === "completed"
            ? "ok"
            : p.daysRemaining !== undefined && p.daysRemaining < 7
              ? "critical"
              : p.status === "documents"
                ? "warning"
                : "info",
        icon:
          p.status === "completed"
            ? "✅"
            : p.daysRemaining !== undefined && p.daysRemaining < 7
              ? "🚨"
              : p.status === "documents"
                ? "📄"
                : "📁",
        text: `${p.client} · ${p.title || p.status}`,
        tag:
          p.status === "completed"
            ? "COMPLETED"
            : p.daysRemaining !== undefined && p.daysRemaining < 7
              ? "URGENT"
              : p.status === "documents"
                ? "DOCUMENTS"
                : undefined,
        timestamp: new Date().toLocaleTimeString("en-US", {
          hour: "2-digit",
          minute: "2-digit",
        }),
        userId: user?.email,
      }),
    );
  }, [practices, user?.email]);

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="p-2.5 space-y-2">
        <div className="h-[240px] rounded-xl bg-white/[0.025] animate-pulse" />
        <div className="h-12 rounded-xl bg-white/[0.025] animate-pulse" />
        <div className="grid grid-cols-4 gap-2">
          <div className="col-span-3 h-[220px] rounded-xl bg-white/[0.025] animate-pulse" />
          <div className="h-[220px] rounded-xl bg-white/[0.025] animate-pulse" />
        </div>
        <div className="h-[320px] rounded-xl bg-white/[0.025] animate-pulse" />
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="p-4 rounded-xl border border-[#c45c78]/25 bg-[rgba(196,92,120,0.06)]">
        <h3 className="font-semibold text-[#c45c78]">Dashboard Error</h3>
        <p className="text-sm text-[#c45c78]/70 mt-1">
          Failed to load dashboard data.
        </p>
        <button
          onClick={() => refetch()}
          className="mt-3 px-4 py-2 bg-[#c45c78] text-white rounded-lg hover:opacity-90 transition-opacity inline-flex items-center gap-2 text-sm"
        >
          <RefreshCw className="w-4 h-4" />
          Retry
        </button>
      </div>
    );
  }

  // Stat values
  const statItems = isZero
    ? [
        {
          label: "Revenue · MTD",
          value: revenue?.total_revenue
            ? formatRevenue(revenue.total_revenue)
            : "—",
          sub: revenue?.paid_revenue
            ? `${formatRevenue(revenue.paid_revenue)} incassato`
            : "—",
          accent: "#9880d8",
        },
        {
          label: "Outstanding",
          value: revenue?.outstanding_revenue
            ? formatRevenue(revenue.outstanding_revenue)
            : "—",
          sub: "da incassare",
          accent: "#d4845a",
        },
        {
          label: "Clienti",
          value: totalClients != null ? totalClients.toLocaleString() : "—",
          sub: "registrati",
          accent: "#4a8ec4",
          href: "/clients",
        },
        {
          label: "Processi",
          value: totalPractices != null ? totalPractices : "—",
          sub: `${stats.activeCases} attivi · ${stats.criticalDeadlines} critici`,
          accent: "#5cb88a",
          href: "/process",
        },
        {
          label: "Fatture",
          value: stats.pendingInvoices > 0 ? stats.pendingInvoices : "✓",
          sub: stats.pendingInvoices > 0 ? "in attesa" : "tutte pagate",
          accent: "#b89a40",
        },
      ]
    : [
        {
          label: "My Cases",
          value: stats.activeCases,
          sub: "assigned",
          accent: "#5cb88a",
          href: "/process",
        },
        {
          label: "Stalled",
          value: stats.criticalDeadlines,
          sub: ">14 days",
          accent: "#c45c78",
        },
        {
          label: "Invoices",
          value: stats.pendingInvoices > 0 ? stats.pendingInvoices : "—",
          sub: "pending",
          accent: "#b89a40",
        },
        {
          label: "Unread",
          value: stats.whatsappUnread + stats.emailUnread,
          sub: "messages",
          accent: "#4a8ec4",
        },
      ];

  return (
    <DashboardErrorBoundary>
      <div className="relative dash-liquid-bg">
        <div className="p-2.5 space-y-2">
          {/* ROW 0: Hero */}
          <HeroLiveWindow />

          {/* ROW 1: Zantara AI portal */}
          <ZantaraPortalCard />

          {/* ROW 2: Metric bar */}
          <div
            className="rounded-xl px-6 py-4 flex items-stretch shadow-2xl backdrop-blur-xl transition-all duration-300 hover:bg-[rgba(35,35,40,0.8)]"
            style={{
              background: "rgba(35, 35, 40, 0.65)",
              border: "1px solid rgba(255,255,255,0.08)",
            }}
          >
            {statItems.map((s, i) => (
              <React.Fragment key={s.label}>
                <div className="flex-1 min-w-0">
                  <MetricItem {...s} />
                </div>
                {i < statItems.length - 1 && (
                  <div
                    className="w-px flex-shrink-0 mx-6 self-stretch"
                    style={{ background: "rgba(255,255,255,0.10)" }}
                  />
                )}
              </React.Fragment>
            ))}
          </div>

          {/* ROW 3: Team Activity — admin sees all, team member sees own row only */}
          {teamEnabled && (
            <TeamActivityPanel
              members={
                isZero
                  ? (teamData?.members ?? [])
                  : (teamData?.members ?? []).filter(
                      (m) => m.email === user?.email,
                    )
              }
              overview={isZero ? (teamData?.overview ?? null) : null}
              isLoading={teamLoading || !teamEnabled}
            />
          )}

          {/* ROW 4: Pipeline + Intel + LiveActivity/RoleWidget */}
          <div
            className="grid gap-2"
            style={{ gridTemplateColumns: "1.5fr 1fr 1fr" }}
          >
            {/* Pipeline panel */}
            <div
              className="rounded-xl overflow-hidden flex flex-col shadow-xl backdrop-blur-xl transition-all duration-300 hover:bg-[rgba(35,35,40,0.8)]"
              style={{
                background: "rgba(35, 35, 40, 0.65)",
                border: "1px solid rgba(255,255,255,0.08)",
                minHeight: 320,
              }}
            >
              {/* Panel header */}
              <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.05]">
                <div className="flex items-center gap-2">
                  <FileText size={12} className="text-white/30" />
                  <span className="text-[11px] font-semibold text-white/60">
                    Process Pipeline
                  </span>
                </div>
                <Link
                  href="/process"
                  className="flex items-center gap-1 text-[9px] text-white/25 hover:text-white/55 transition-colors"
                >
                  View all <ArrowUpRight size={9} />
                </Link>
              </div>

              {/* Column headers */}
              <div
                className="grid px-3 py-1.5 border-b border-white/[0.04]"
                style={{ gridTemplateColumns: "1fr auto auto" }}
              >
                <span className="text-[8px] font-semibold text-white/20 uppercase tracking-widest">
                  Client
                </span>
                <span className="text-[8px] font-semibold text-white/20 uppercase tracking-widest">
                  Status
                </span>
                <span className="text-[8px] font-semibold text-white/20 uppercase tracking-widest ml-3">
                  Due
                </span>
              </div>

              {/* Rows */}
              <div className="flex flex-col py-1 flex-1">
                {practices.length === 0 ? (
                  <div className="flex items-center justify-center py-10 text-[11px] text-white/20">
                    No processes assigned
                  </div>
                ) : (
                  practices.map((p) => (
                    <PipelineRow
                      key={p.id}
                      p={{
                        id: p.id,
                        title: p.title || "Unknown",
                        client: p.client || "Unknown Client",
                        status: p.status,
                        daysRemaining: p.daysRemaining,
                        completedAt:
                          p.status === "completed"
                            ? new Date().toLocaleDateString()
                            : undefined,
                      }}
                    />
                  ))
                )}
              </div>
            </div>

            {/* Intel panel */}
            <div
              className="rounded-xl overflow-hidden flex flex-col shadow-xl backdrop-blur-xl transition-all duration-300 hover:bg-[rgba(35,35,40,0.8)]"
              style={{
                background: "rgba(35, 35, 40, 0.65)",
                border: "1px solid rgba(255,255,255,0.08)",
                minHeight: 320,
              }}
            >
              {/* Panel header */}
              <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.05]">
                <div className="flex items-center gap-2">
                  <TrendingUp size={12} className="text-white/30" />
                  <span className="text-[11px] font-semibold text-white/60">
                    Intelligence Feed
                  </span>
                </div>
                <Link
                  href="/intelligence"
                  className="flex items-center gap-1 text-[9px] text-white/25 hover:text-white/55 transition-colors"
                >
                  All <ExternalLink size={9} />
                </Link>
              </div>

              {/* Articles */}
              <div className="flex flex-col py-1 flex-1">
                {intelLoading && (
                  <div className="flex flex-col gap-1 p-3">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <div
                        key={i}
                        className="h-10 rounded-lg bg-white/[0.03] animate-pulse"
                      />
                    ))}
                  </div>
                )}
                {!intelLoading &&
                  (!intelArticles || intelArticles.length === 0) && (
                    <div className="flex items-center justify-center py-10 text-[11px] text-white/20">
                      No recent articles
                    </div>
                  )}
                {!intelLoading &&
                  intelArticles &&
                  intelArticles.length > 0 &&
                  intelArticles.map((article, i) => (
                    <React.Fragment key={article.slug}>
                      <IntelRow article={article} />
                      {i < intelArticles.length - 1 && <Divider />}
                    </React.Fragment>
                  ))}
              </div>
            </div>

            {/* Right column: LiveActivityFeed + RoleWidget stacked */}
            <div className="flex flex-col gap-2">
              <LiveActivityFeed events={liveEvents} isLoading={isLoading} />
              <RoleWidget role={role} userId={user?.email ?? ""} />
            </div>
          </div>
        </div>
      </div>
    </DashboardErrorBoundary>
  );
}
