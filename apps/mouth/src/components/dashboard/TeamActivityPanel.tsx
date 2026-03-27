'use client';

import React from 'react';
import {
  Users,
  Briefcase,
  Clock,
  MessageCircle,
  Mail,
  BookOpen,
  Star,
  Zap,
  TrendingUp,
  CheckCircle2,
  DollarSign,
} from 'lucide-react';

export interface TeamMemberStats {
  email: string;
  name: string;
  role: string;
  department: string;
  conversations: number;
  messages: number;
  days_worked: number;
  crm_actions: number;
  emails_sent: number;
  emails_received: number;
  kb_views: number;
  kb_downloads: number;
  last_activity: string | null;
  // Practice stats (joined via client.assigned_to)
  practices_completed?: number;
  practices_active?: number;
  practices_revenue?: number;
}

export interface TeamOverview {
  total_conversations: number;
  total_messages: number;
  total_team_members: number;
  active_today: number;
  messages_today: number;
}

interface Props {
  members: TeamMemberStats[];
  overview: TeamOverview | null;
  isLoading: boolean;
}

const EXCLUDED_NAMES = ['amanda', 'zainal', 'ruslana', 'zero', 'nina', 'anna', 'marta'];
function isExcluded(name: string): boolean {
  const n = name.toLowerCase();
  return EXCLUDED_NAMES.some((ex) => n.includes(ex));
}

// One unique color per index — vivid, distinct
const ROW_PALETTE = [
  {
    bg: 'rgba(74,142,196,0.13)',
    border: 'rgba(74,142,196,0.28)',
    accent: '#4a8ec4',
  }, // blue
  {
    bg: 'rgba(92,184,138,0.13)',
    border: 'rgba(92,184,138,0.28)',
    accent: '#5cb88a',
  }, // green
  {
    bg: 'rgba(184,154,64,0.13)',
    border: 'rgba(184,154,64,0.28)',
    accent: '#b89a40',
  }, // gold
  {
    bg: 'rgba(152,128,216,0.13)',
    border: 'rgba(152,128,216,0.28)',
    accent: '#9880d8',
  }, // violet
  {
    bg: 'rgba(212,132,90,0.13)',
    border: 'rgba(212,132,90,0.28)',
    accent: '#d4845a',
  }, // orange
  {
    bg: 'rgba(196,92,120,0.13)',
    border: 'rgba(196,92,120,0.28)',
    accent: '#c45c78',
  }, // rose
  {
    bg: 'rgba(74,184,196,0.13)',
    border: 'rgba(74,184,196,0.28)',
    accent: '#4ab8c4',
  }, // cyan
  {
    bg: 'rgba(180,100,220,0.13)',
    border: 'rgba(180,100,220,0.28)',
    accent: '#b464dc',
  }, // purple
  {
    bg: 'rgba(220,160,60,0.13)',
    border: 'rgba(220,160,60,0.28)',
    accent: '#dca03c',
  }, // amber
  {
    bg: 'rgba(80,200,160,0.13)',
    border: 'rgba(80,200,160,0.28)',
    accent: '#50c8a0',
  }, // teal
  {
    bg: 'rgba(240,100,80,0.13)',
    border: 'rgba(240,100,80,0.28)',
    accent: '#f06450',
  }, // coral
  {
    bg: 'rgba(100,160,240,0.13)',
    border: 'rgba(100,160,240,0.28)',
    accent: '#64a0f0',
  }, // sky
  {
    bg: 'rgba(200,120,200,0.13)',
    border: 'rgba(200,120,200,0.28)',
    accent: '#c878c8',
  }, // pink
  {
    bg: 'rgba(120,200,80,0.13)',
    border: 'rgba(120,200,80,0.28)',
    accent: '#78c850',
  }, // lime
  {
    bg: 'rgba(160,140,100,0.13)',
    border: 'rgba(160,140,100,0.28)',
    accent: '#a08c64',
  }, // sand
  {
    bg: 'rgba(60,140,220,0.13)',
    border: 'rgba(60,140,220,0.28)',
    accent: '#3c8cdc',
  }, // indigo
  {
    bg: 'rgba(240,180,60,0.13)',
    border: 'rgba(240,180,60,0.28)',
    accent: '#f0b43c',
  }, // yellow
];

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

function isTopPerformer(m: TeamMemberStats): boolean {
  return m.crm_actions > 50 || m.days_worked >= 18;
}

// Mini bar — no label
function MiniBar({ value, max, accent }: { value: number; max: number; accent: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div
      className="h-[3px] w-full rounded-full mt-1"
      style={{ background: 'rgba(255,255,255,0.07)' }}
    >
      <div
        className="h-full rounded-full transition-all duration-700"
        style={{
          width: `${pct}%`,
          background: pct > 0 ? accent : 'transparent',
          boxShadow: pct > 0 ? `0 0 5px ${accent}70` : 'none',
        }}
      />
    </div>
  );
}

function fmtRp(rp: number): string {
  if (rp >= 1_000_000_000) return `${(rp / 1_000_000_000).toFixed(1)}B`;
  if (rp >= 1_000_000) return `${(rp / 1_000_000).toFixed(0)}M`;
  if (rp >= 1_000) return `${(rp / 1_000).toFixed(0)}K`;
  return rp > 0 ? `${rp}` : '—';
}

function RevenueCell({ value, max, accent }: { value: number; max: number; accent: string }) {
  const dim = value === 0;
  return (
    <div className="px-2 min-w-0">
      <span
        className="text-[11px] font-black tabular-nums leading-none"
        style={{ color: dim ? 'rgba(255,255,255,0.18)' : accent }}
      >
        {dim ? '—' : `Rp ${fmtRp(value)}`}
      </span>
      <MiniBar value={value} max={max} accent={dim ? 'rgba(255,255,255,0.06)' : accent} />
    </div>
  );
}

// Metric cell — just value + bar, no label
function Cell({ value, max, accent }: { value: number; max: number; accent: string }) {
  const dim = value === 0;
  return (
    <div className="px-2 min-w-0">
      <span
        className="text-[13px] font-black tabular-nums leading-none"
        style={{ color: dim ? 'rgba(255,255,255,0.18)' : accent }}
      >
        {value}
      </span>
      <MiniBar value={value} max={max} accent={dim ? 'rgba(255,255,255,0.06)' : accent} />
    </div>
  );
}

const COLS = '190px 1fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr 1fr';

export function TeamActivityPanel({ members, overview, isLoading }: Props) {
  const safeMembers = Array.isArray(members) ? members : [];

  const filteredMembers = React.useMemo(
    () => safeMembers.filter((m) => !isExcluded(m.name)),
    [safeMembers]
  );

  const maxima = React.useMemo(
    () => ({
      conversations: Math.max(...filteredMembers.map((m) => m.conversations), 1),
      messages: Math.max(...filteredMembers.map((m) => m.messages), 1),
      days_worked: Math.max(...filteredMembers.map((m) => m.days_worked), 1),
      crm_actions: Math.max(...filteredMembers.map((m) => m.crm_actions), 1),
      emails_sent: Math.max(...filteredMembers.map((m) => m.emails_sent), 1),
      emails_received: Math.max(...filteredMembers.map((m) => m.emails_received), 1),
      kb_views: Math.max(...filteredMembers.map((m) => m.kb_views), 1),
      kb_downloads: Math.max(...filteredMembers.map((m) => m.kb_downloads), 1),
      practices_completed: Math.max(...filteredMembers.map((m) => m.practices_completed ?? 0), 1),
      practices_revenue: Math.max(...filteredMembers.map((m) => m.practices_revenue ?? 0), 1),
    }),
    [filteredMembers]
  );

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        background: 'rgba(255,255,255,0.016)',
        border: '1px solid rgba(255,255,255,0.07)',
      }}
    >
      {/* ── Panel header ───────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.05]">
        <div className="flex items-center gap-2">
          <Users size={12} className="text-white/30" />
          <span className="text-[11px] font-semibold text-white/60">Team Performance</span>
          <span className="text-[9px] text-white/20">· Current Period</span>
        </div>
        {overview && (
          <div className="flex items-center gap-4 text-[9px] text-white/25">
            <span className="flex items-center gap-1">
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{
                  backgroundColor: overview.active_today > 0 ? '#5cb88a' : 'rgba(255,255,255,0.15)',
                }}
              />
              {overview.active_today} online
            </span>
            <span>{overview.total_messages.toLocaleString('en-US')} total messages</span>
            <span>{filteredMembers.length} members</span>
          </div>
        )}
      </div>

      {/* ── Column headers — sticky, shown once ────────────── */}
      <div
        className="grid items-center px-4 py-3 border-b border-white/[0.08]"
        style={{
          gridTemplateColumns: COLS,
          background: 'rgba(255,255,255,0.03)',
        }}
      >
        <div className="flex items-center gap-1.5">
          <TrendingUp size={10} className="text-white/40" />
          <span className="text-[11px] font-black text-white/50 uppercase tracking-widest">
            Member
          </span>
        </div>
        {[
          { icon: MessageCircle, label: 'Convos' },
          { icon: Zap, label: 'Messages' },
          { icon: Clock, label: 'Days' },
          { icon: Briefcase, label: 'CRM' },
          { icon: Mail, label: 'Emails Out' },
          { icon: Mail, label: 'Emails In' },
          { icon: BookOpen, label: 'KB Views' },
          { icon: BookOpen, label: 'KB DL' },
          { icon: CheckCircle2, label: 'Done' },
          { icon: DollarSign, label: 'Revenue' },
        ].map(({ icon: Icon, label }) => (
          <div key={label} className="flex items-center gap-1.5 px-2">
            <Icon size={10} className="text-white/40 flex-shrink-0" />
            <span className="text-[11px] font-black text-white/55 uppercase tracking-wide">
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
              <div key={i} className="h-14 mx-3 my-1 rounded-xl bg-white/[0.03] animate-pulse" />
            ))}
          </>
        )}

        {!isLoading && filteredMembers.length === 0 && (
          <div className="flex items-center justify-center py-10 text-[11px] text-white/20">
            No team data
          </div>
        )}

        {!isLoading &&
          filteredMembers.map((m, idx) => {
            const palette = ROW_PALETTE[idx % ROW_PALETTE.length];
            const top = isTopPerformer(m);

            return (
              <div
                key={m.email}
                className="relative mx-3 my-1 rounded-xl overflow-hidden"
                style={{
                  background: palette.bg,
                  border: `1px solid ${palette.border}`,
                }}
              >
                {/* subtle glow at left edge */}
                <div
                  className="absolute left-0 top-0 bottom-0 w-1 rounded-l-xl"
                  style={{ background: palette.accent, opacity: 0.5 }}
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
                        background: `${palette.accent}25`,
                        border: `1.5px solid ${palette.accent}55`,
                        color: palette.accent,
                        boxShadow: `0 0 12px ${palette.accent}30`,
                      }}
                    >
                      {getInitials(m.name)}
                      {top && (
                        <Star
                          size={7}
                          className="absolute -top-1 -right-1"
                          style={{ color: '#b89a40', fill: '#b89a40' }}
                        />
                      )}
                    </div>
                    <div className="min-w-0">
                      <p
                        className="text-[13px] font-black leading-tight truncate"
                        style={{ color: palette.accent }}
                      >
                        {m.name}
                      </p>
                      <p className="text-[8px] font-semibold text-white/35 truncate leading-tight capitalize">
                        {m.role}
                      </p>
                    </div>
                  </div>

                  {/* 9 metric cells */}
                  <Cell
                    value={m.conversations}
                    max={maxima.conversations}
                    accent={palette.accent}
                  />
                  <Cell value={m.messages} max={maxima.messages} accent={palette.accent} />
                  <Cell value={m.days_worked} max={maxima.days_worked} accent={palette.accent} />
                  <Cell value={m.crm_actions} max={maxima.crm_actions} accent={palette.accent} />
                  <Cell value={m.emails_sent} max={maxima.emails_sent} accent={palette.accent} />
                  <Cell
                    value={m.emails_received}
                    max={maxima.emails_received}
                    accent={palette.accent}
                  />
                  <Cell value={m.kb_views} max={maxima.kb_views} accent={palette.accent} />
                  <Cell value={m.kb_downloads} max={maxima.kb_downloads} accent={palette.accent} />
                  <Cell
                    value={m.practices_completed ?? 0}
                    max={maxima.practices_completed}
                    accent={palette.accent}
                  />
                  <RevenueCell
                    value={m.practices_revenue ?? 0}
                    max={maxima.practices_revenue}
                    accent={palette.accent}
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
