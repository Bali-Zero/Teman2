"use client";

import React from "react";
import { formatIDRCompact } from "@balizero/core/utils";
import {
  Users,
  Briefcase,
  Clock,
  Star,
  TrendingUp,
  CheckCircle2,
  DollarSign,
} from "lucide-react";

// Only metrics with a live data source are rendered. Chat convos/messages,
// emails in/out and KB views/downloads were zero for every member (their
// source tables are dead or stale — P0.2 audit 2026-06-11) and were removed.
export interface TeamMemberStats {
  email: string;
  name: string;
  role: string;
  days_worked: number;
  crm_actions: number;
  // Practice stats (joined via client.assigned_to)
  practices_completed?: number;
  practices_active?: number;
  practices_revenue?: number;
}

export interface TeamOverview {
  active_today: number;
}

interface Props {
  members: TeamMemberStats[];
  overview: TeamOverview | null;
  isLoading: boolean;
}

const EXCLUDED_NAMES = [
  "amanda",
  "zainal",
  "ruslana",
  "zero",
  "nina",
  "anna",
  "marta",
];
function isExcluded(name: string): boolean {
  const n = name.toLowerCase();
  return EXCLUDED_NAMES.some((ex) => n.includes(ex));
}

const ROW_ACCENTS = [
  "var(--state-info)",
  "var(--state-success)",
  "var(--state-warning)",
  "var(--bz-copper-text)",
];

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

function isTopPerformer(m: TeamMemberStats): boolean {
  return m.crm_actions > 50 || m.days_worked >= 18;
}

// Mini bar — no label
function MiniBar({
  value,
  max,
  accent,
}: {
  value: number;
  max: number;
  accent: string;
}) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div
      className="h-[3px] w-full rounded-full mt-1"
      style={{ background: "var(--surface-sunken)" }}
    >
      <div
        className="h-full rounded-full transition-all duration-700"
        style={{
          width: `${pct}%`,
          background: pct > 0 ? accent : "transparent",
          boxShadow:
            pct > 0
              ? `0 0 5px color-mix(in srgb, ${accent} 45%, transparent)`
              : "none",
        }}
      />
    </div>
  );
}

function RevenueCell({
  value,
  max,
  accent,
}: {
  value: number;
  max: number;
  accent: string;
}) {
  const dim = value === 0;
  return (
    <div className="px-2 min-w-0">
      <span
        className="text-[11px] font-black tabular-nums leading-none"
        style={{ color: dim ? "var(--bz-text-3)" : accent }}
      >
        {dim ? "—" : formatIDRCompact(value)}
      </span>
      <MiniBar
        value={value}
        max={max}
        accent={dim ? "var(--surface-sunken)" : accent}
      />
    </div>
  );
}

// Metric cell — just value + bar, no label
function Cell({
  value,
  max,
  accent,
}: {
  value: number;
  max: number;
  accent: string;
}) {
  const dim = value === 0;
  return (
    <div className="px-2 min-w-0">
      <span
        className="text-[13px] font-black tabular-nums leading-none"
        style={{ color: dim ? "var(--bz-text-3)" : accent }}
      >
        {value}
      </span>
      <MiniBar
        value={value}
        max={max}
        accent={dim ? "var(--surface-sunken)" : accent}
      />
    </div>
  );
}

const COLS = "190px 1fr 1fr 1fr 1fr";

export function TeamActivityPanel({ members, overview, isLoading }: Props) {
  const safeMembers = Array.isArray(members) ? members : [];

  const filteredMembers = React.useMemo(
    () => safeMembers.filter((m) => !isExcluded(m.name)),
    [safeMembers],
  );

  const maxima = React.useMemo(
    () => ({
      days_worked: Math.max(...filteredMembers.map((m) => m.days_worked), 1),
      crm_actions: Math.max(...filteredMembers.map((m) => m.crm_actions), 1),
      practices_completed: Math.max(
        ...filteredMembers.map((m) => m.practices_completed ?? 0),
        1,
      ),
      practices_revenue: Math.max(
        ...filteredMembers.map((m) => m.practices_revenue ?? 0),
        1,
      ),
    }),
    [filteredMembers],
  );

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        background: "var(--bz-card)",
        border: "1px solid var(--bz-border)",
      }}
    >
      {/* ── Panel header ───────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--bz-border)]">
        <div className="flex items-center gap-2">
          <Users size={12} className="text-[var(--bz-text-3)]" />
          <span className="text-[11px] font-semibold text-[var(--bz-text-1)]">
            Team Performance
          </span>
          <span className="text-[9px] text-[var(--bz-text-3)]">
            · Current Period
          </span>
        </div>
        {overview && (
          <div className="flex items-center gap-4 text-[9px] text-[var(--bz-text-3)]">
            <span className="flex items-center gap-1">
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{
                  backgroundColor:
                    overview.active_today > 0
                      ? "var(--state-success)"
                      : "var(--bz-text-3)",
                }}
              />
              {overview.active_today} online
            </span>
            <span>{filteredMembers.length} members</span>
          </div>
        )}
      </div>

      {/* ── Column headers — sticky, shown once ────────────── */}
      <div
        className="grid items-center px-4 py-3 border-b border-[var(--bz-border)]"
        style={{
          gridTemplateColumns: COLS,
          background: "var(--surface-raised)",
        }}
      >
        <div className="flex items-center gap-1.5">
          <TrendingUp size={10} className="text-[var(--bz-text-3)]" />
          <span className="text-[11px] font-black text-[var(--bz-text-2)] uppercase tracking-widest">
            Member
          </span>
        </div>
        {[
          { icon: Clock, label: "Days" },
          { icon: Briefcase, label: "CRM" },
          { icon: CheckCircle2, label: "Done" },
          { icon: DollarSign, label: "Revenue" },
        ].map(({ icon: Icon, label }) => (
          <div key={label} className="flex items-center gap-1.5 px-2">
            <Icon size={10} className="text-[var(--bz-text-3)] flex-shrink-0" />
            <span className="text-[11px] font-black text-[var(--bz-text-2)] uppercase tracking-wide">
              {label}
            </span>
          </div>
        ))}
      </div>

      {/* ── Rows ───────────────────────────────────────────── */}
      <div className="flex flex-col">
        {isLoading && (
          <>
            {[1, 2, 3, 4, 5].map((i) => (
              <div
                key={i}
                className="h-14 mx-3 my-1 rounded-xl bg-[var(--surface-raised)] animate-pulse"
              />
            ))}
          </>
        )}

        {!isLoading && filteredMembers.length === 0 && (
          <div className="flex items-center justify-center py-10 text-[11px] text-[var(--bz-text-3)]">
            No team data
          </div>
        )}

        {!isLoading &&
          filteredMembers.map((m, idx) => {
            const accent = ROW_ACCENTS[idx % ROW_ACCENTS.length];
            const top = isTopPerformer(m);

            return (
              <div
                key={m.email}
                className="relative mx-3 my-1 rounded-xl overflow-hidden"
                style={{
                  background: `color-mix(in srgb, ${accent} 8%, var(--bz-card))`,
                  border: `1px solid color-mix(in srgb, ${accent} 24%, var(--bz-border))`,
                }}
              >
                {/* subtle glow at left edge */}
                <div
                  className="absolute left-0 top-0 bottom-0 w-1 rounded-l-xl"
                  style={{ background: accent, opacity: 0.5 }}
                />

                <div
                  className="grid items-center pl-4 pr-3 py-3"
                  style={{ gridTemplateColumns: COLS }}
                >
                  {/* Identity */}
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div
                      className="relative w-8 h-8 rounded-lg flex items-center justify-center text-[11px] font-black flex-shrink-0"
                      style={{
                        background: `color-mix(in srgb, ${accent} 14%, transparent)`,
                        border: `1.5px solid color-mix(in srgb, ${accent} 34%, transparent)`,
                        color: accent,
                        boxShadow: `0 0 12px color-mix(in srgb, ${accent} 20%, transparent)`,
                      }}
                    >
                      {getInitials(m.name)}
                      {top && (
                        <Star
                          size={7}
                          className="absolute -top-1 -right-1"
                          style={{
                            color: "var(--state-warning)",
                            fill: "var(--state-warning)",
                          }}
                        />
                      )}
                    </div>
                    <div className="min-w-0">
                      <p
                        className="text-[13px] font-black leading-tight truncate"
                        style={{ color: accent }}
                      >
                        {m.name}
                      </p>
                      <p className="text-[8px] font-semibold text-[var(--bz-text-3)] truncate leading-tight capitalize">
                        {m.role}
                      </p>
                    </div>
                  </div>

                  {/* 4 metric cells */}
                  <Cell
                    value={m.days_worked}
                    max={maxima.days_worked}
                    accent={accent}
                  />
                  <Cell
                    value={m.crm_actions}
                    max={maxima.crm_actions}
                    accent={accent}
                  />
                  <Cell
                    value={m.practices_completed ?? 0}
                    max={maxima.practices_completed}
                    accent={accent}
                  />
                  <RevenueCell
                    value={m.practices_revenue ?? 0}
                    max={maxima.practices_revenue}
                    accent={accent}
                  />
                </div>
              </div>
            );
          })}
        <div className="h-2" />
      </div>
    </div>
  );
}
