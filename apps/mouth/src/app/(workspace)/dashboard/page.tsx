"use client";

import React from "react";
import { RefreshCw } from "lucide-react";
import {
  PratichePreview,
  LiveActivityFeed,
  RoleWidget,
  DashboardStatCard,
  ZantaraPortalCard,
} from "@/components/dashboard";
import { HeroLiveWindow } from "@/components/workspace/HeroLiveWindow";
import { NusantaraHealthWidget } from "@/components/dashboard/NusantaraHealthWidget";
import type { PraticaPreview } from "@/components/dashboard";
import { DashboardErrorBoundary } from "@/components/ErrorBoundary";
import { useDashboardData } from "@/hooks/useDashboardData";
import { useRealtime } from "@/lib/realtime";
import { useQueryClient } from "@tanstack/react-query";
import { normalizeDashboardRole } from "@/lib/dashboard-role";
import type {
  LiveActivityEvent,
  DashboardStatConfig,
} from "@/types/dashboard-role.types";
import { logger } from "@/lib/logger";

export default function DashboardPage() {
  const {
    user,
    stats,
    practices,
    isZero,
    isLoading,
    isError,
    error: _error,
    refetch,
  } = useDashboardData();

  const realtime = useRealtime();
  const queryClient = useQueryClient();
  const role = normalizeDashboardRole(user?.role, user?.is_admin ?? false);

  // Bridge WebSocket → React Query invalidation
  React.useEffect(() => {
    const unsubscribe = realtime.subscribe("dashboard_update", () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    });
    return unsubscribe;
  }, [realtime, queryClient]);

  // Connect WebSocket on user load
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

  // ── Build live feed events from practices ─────────────────────
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

  // ── Build stat cards per role ─────────────────────────────────
  const statCards: DashboardStatConfig[] = React.useMemo(() => {
    if (isZero) {
      return [
        {
          icon: "📁",
          value: stats.activeCases,
          label: "Active Cases",
          trend: "▲ team",
          colorVariant: "green",
        },
        {
          icon: "⏰",
          value: stats.criticalDeadlines,
          label: "Critical Deadlines",
          trend: "active alerts",
          colorVariant: "red",
        },
        {
          icon: "💰",
          value: "—",
          label: "Pending Invoices",
          trend: "see accounting",
          colorVariant: "yellow",
        },
        {
          icon: "🤖",
          value: "46",
          label: "AI Agents",
          trend: "100% uptime",
          colorVariant: "blue",
        },
      ];
    }
    if (role === "accounting") {
      return [
        {
          icon: "✅",
          value: "—",
          label: "Paid MTD",
          trend: "see metrics",
          colorVariant: "green",
        },
        {
          icon: "🔴",
          value: "—",
          label: "Overdue",
          trend: "urgent",
          colorVariant: "red",
        },
        {
          icon: "⏳",
          value: "—",
          label: "Pending",
          trend: "awaiting",
          colorVariant: "yellow",
        },
        {
          icon: "💶",
          value: "—",
          label: "Revenue MTD",
          trend: "current month",
          colorVariant: "blue",
        },
      ];
    }
    if (role === "tax") {
      return [
        {
          icon: "✅",
          value: "—",
          label: "Compliant Clients",
          trend: "up to date",
          colorVariant: "green",
        },
        {
          icon: "⏰",
          value: "—",
          label: "Due <7 days",
          trend: "urgent",
          colorVariant: "red",
        },
        {
          icon: "📋",
          value: "—",
          label: "Pending Filings",
          trend: "queued",
          colorVariant: "yellow",
        },
        {
          icon: "📌",
          value: "—",
          label: "Tax Alerts",
          trend: "to verify",
          colorVariant: "blue",
        },
      ];
    }
    if (role === "marketing") {
      return [
        {
          icon: "📝",
          value: "—",
          label: "Published Articles",
          trend: "this month",
          colorVariant: "green",
        },
        {
          icon: "✍️",
          value: "—",
          label: "In Review",
          trend: "queued",
          colorVariant: "red",
        },
        {
          icon: "📧",
          value: "—",
          label: "Newsletter Subs",
          trend: "delta",
          colorVariant: "yellow",
        },
        {
          icon: "🎯",
          value: "—",
          label: "New Leads",
          trend: "this week",
          colorVariant: "blue",
        },
      ];
    }
    // Default: team
    return [
      {
        icon: "📁",
        value: stats.activeCases,
        label: "My Cases",
        trend: "assigned",
        colorVariant: "green",
      },
      {
        icon: "⏰",
        value: stats.criticalDeadlines,
        label: "Stalled >14d",
        trend: "to unblock",
        colorVariant: "red",
      },
      {
        icon: "📄",
        value: "—",
        label: "Missing Docs",
        trend: "to upload",
        colorVariant: "yellow",
      },
      {
        icon: "👥",
        value: "—",
        label: "Assigned Clients",
        trend: "active",
        colorVariant: "blue",
      },
    ];
  }, [isZero, role, stats]);

  // ── Loading skeleton ──────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="p-2.5 grid grid-cols-4 gap-2">
        <div className="col-span-4 h-[240px] rounded-xl bg-white/[0.025] animate-pulse mb-2" />
        <div className="col-span-3 h-[240px] rounded-xl bg-white/[0.025] animate-pulse" />
        <div className="col-span-1 h-[240px] rounded-xl bg-white/[0.025] animate-pulse" />
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-20 rounded-xl bg-white/[0.025] animate-pulse"
          />
        ))}
      </div>
    );
  }

  // ── Error state ───────────────────────────────────────────────
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

  return (
    <DashboardErrorBoundary>
      {/* Liquid background */}
      <div className="relative dash-liquid-bg">
        <div className="p-2.5 space-y-3">
          {/* ── ROW 0: Website Live Cover (Full Width) ── */}
          <HeroLiveWindow />

          {/* ── Zantara AI Portal Card ── */}
          <ZantaraPortalCard />

          <div
            className="grid gap-2"
            style={{ gridTemplateColumns: "1fr 1fr 1fr 1fr" }}
          >
            {/* ── ROW 1: Live Activity (3/4) + Role Widget (1/4) ── */}
            <LiveActivityFeed events={liveEvents} isLoading={isLoading} />

            <RoleWidget role={role} userId={user?.email ?? ""} />

            {/* ── ROW 2: 4 Stat Cards ── */}
            {statCards.map((card) => (
              <DashboardStatCard key={card.label} {...card} />
            ))}

            {/* ── ROW 3: Pratiche (1.6fr) + Intel (1fr) ── */}
            <div
              className="col-span-4 grid gap-2"
              style={{ gridTemplateColumns: "1.6fr 1fr" }}
            >
              {/* Pratiche Pipeline */}
              <PratichePreview
                pratiche={practices.map(
                  (p): PraticaPreview => ({
                    id: p.id,
                    title: p.title || "Unknown",
                    client: p.client || "Unknown Client",
                    status: p.status,
                    daysRemaining: p.daysRemaining,
                    completedAt:
                      p.status === "completed"
                        ? new Date().toLocaleDateString()
                        : undefined,
                  }),
                )}
                isLoading={isLoading}
              />

              {/* Right: Intel Normativo */}
              <div className="glass-base glass-blue p-3.5">
                <h4 className="text-[9px] font-bold text-[#4a8ec4]/65 tracking-[.1em] mb-2.5">
                  REGULATORY INTEL
                </h4>
                <div className="flex flex-col gap-2">
                  {[
                    "New immigration circular KITAS B211A",
                    "PPh deadline March 31 — 8 clients",
                    "KBLI 2025 — 3 cases to update",
                  ].map((item) => (
                    <div
                      key={item}
                      className="flex gap-2 text-[10px] text-white/55 leading-snug border-b border-white/[0.04] pb-1.5 last:border-0"
                    >
                      <span className="text-[#4a8ec4] flex-shrink-0">📌</span>
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardErrorBoundary>
  );
}
