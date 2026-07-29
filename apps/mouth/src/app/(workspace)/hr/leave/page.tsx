"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  ChevronLeft,
  ChevronRight,
  CheckCircle,
  XCircle,
  Clock,
  Plus,
  Users,
  Calendar,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import * as hrApi from "@/lib/api/hr/hr";
import { isHRAdmin } from "@/lib/hr/admin";
import type {
  LeaveRequest,
  LeaveBalance,
  TeamLeaveSummaryRow,
} from "@/types/hr";

// ── Constants ─────────────────────────────────────────────────────────────────

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

/** Dashboard panel recipe — mirrors the operative-dark kita surfaces. */
const PANEL: React.CSSProperties = {
  background: "rgba(35,35,40,0.65)",
  borderColor: "var(--bz-border)",
};

const statusIcons: Record<string, LucideIcon> = {
  pending: Clock,
  approved: CheckCircle,
  rejected: XCircle,
  cancelled: XCircle,
};

/** Icon / label ink per leave status, honestly mapped to --state-*. */
const statusColors: Record<string, string> = {
  pending: "var(--state-warning)",
  approved: "var(--state-success)",
  rejected: "var(--state-danger)",
  cancelled: "var(--bz-text-3)",
};

/** Row surface per status: tinted for actionable states, neutral panel for closed ones. */
const statusRowBg: Record<string, string> = {
  pending: "color-mix(in srgb, var(--state-warning) 10%, transparent)",
  approved: "color-mix(in srgb, var(--state-success) 10%, transparent)",
  rejected: PANEL.background as string,
  cancelled: PANEL.background as string,
};

// ── Mini Calendar ─────────────────────────────────────────────────────────────

function MiniCalendar({ requests }: { requests: LeaveRequest[] }) {
  const today = new Date();
  const [current, setCurrent] = useState(
    new Date(today.getFullYear(), today.getMonth(), 1),
  );

  const year = current.getFullYear();
  const month = current.getMonth();
  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const startOffset = (firstDay + 6) % 7; // normalize to Monday start

  const dayMap = useMemo(() => {
    const map: Record<string, string[]> = {};
    for (const req of requests) {
      if (req.status === "rejected" || req.status === "cancelled") continue;
      const start = new Date(req.start_date);
      const end = new Date(req.end_date);
      const cursor = new Date(start);
      while (cursor <= end) {
        const key = cursor.toISOString().slice(0, 10);
        if (!map[key]) map[key] = [];
        map[key].push(req.status);
        cursor.setDate(cursor.getDate() + 1);
      }
    }
    return map;
  }, [requests]);

  const todayStr = today.toISOString().slice(0, 10);

  const cells: (number | null)[] = [
    ...Array(startOffset).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  function cellKey(day: number) {
    return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  }

  function dayStyle(day: number): React.CSSProperties {
    const key = cellKey(day);
    const statuses = dayMap[key] ?? [];
    const isToday = key === todayStr;
    if (statuses.includes("approved"))
      return {
        background: "color-mix(in srgb, var(--state-success) 25%, transparent)",
        color:
          "color-mix(in srgb, var(--state-success) 55%, var(--bz-text-pure))",
      };
    if (statuses.includes("pending"))
      return {
        background: "color-mix(in srgb, var(--state-warning) 20%, transparent)",
        color:
          "color-mix(in srgb, var(--state-warning) 55%, var(--bz-text-pure))",
      };
    if (isToday)
      return {
        background: "color-mix(in srgb, var(--bz-accent) 20%, transparent)",
        color: "var(--bz-accent)",
        boxShadow:
          "0 0 0 1px color-mix(in srgb, var(--bz-accent) 40%, transparent)",
      };
    return { color: "var(--bz-text-2)" };
  }

  function dayWeight(day: number): string {
    const key = cellKey(day);
    const statuses = dayMap[key] ?? [];
    if (statuses.includes("approved") || statuses.includes("pending"))
      return "font-semibold";
    if (key === todayStr) return "font-bold";
    return "hover:bg-[var(--surface-raised)]";
  }

  return (
    <div className="border rounded-xl p-4" style={PANEL}>
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => setCurrent(new Date(year, month - 1, 1))}
          className="p-1 rounded text-[var(--bz-text-2)] hover:bg-[var(--surface-raised)] hover:text-[var(--bz-text-1)] transition-colors"
        >
          <ChevronLeft size={16} />
        </button>
        <span
          className="text-sm font-semibold"
          style={{ color: "var(--bz-text-1)" }}
        >
          {MONTH_NAMES[month]} {year}
        </span>
        <button
          onClick={() => setCurrent(new Date(year, month + 1, 1))}
          className="p-1 rounded text-[var(--bz-text-2)] hover:bg-[var(--surface-raised)] hover:text-[var(--bz-text-1)] transition-colors"
        >
          <ChevronRight size={16} />
        </button>
      </div>

      <div className="grid grid-cols-7 mb-1">
        {["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"].map((d) => (
          <div
            key={d}
            className="text-center text-xs font-medium py-1"
            style={{ color: "var(--bz-text-3)" }}
          >
            {d}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-0.5">
        {cells.map((day, i) =>
          day === null ? (
            <div key={`p-${i}`} />
          ) : (
            <div
              key={day}
              className={`text-center text-xs py-1.5 cursor-default transition-colors rounded-md ${dayWeight(day)}`}
              style={dayStyle(day)}
            >
              {day}
            </div>
          ),
        )}
      </div>

      <div
        className="flex items-center gap-4 mt-3 pt-3 border-t"
        style={{ borderColor: "var(--bz-border)" }}
      >
        <div
          className="flex items-center gap-1.5 text-xs"
          style={{ color: "var(--bz-text-2)" }}
        >
          <div
            className="w-2.5 h-2.5 rounded-sm"
            style={{
              background:
                "color-mix(in srgb, var(--state-success) 25%, transparent)",
            }}
          />
          Approved
        </div>
        <div
          className="flex items-center gap-1.5 text-xs"
          style={{ color: "var(--bz-text-2)" }}
        >
          <div
            className="w-2.5 h-2.5 rounded-sm"
            style={{
              background:
                "color-mix(in srgb, var(--state-warning) 20%, transparent)",
            }}
          />
          Pending
        </div>
        <div
          className="flex items-center gap-1.5 text-xs"
          style={{ color: "var(--bz-text-2)" }}
        >
          <div
            className="w-2.5 h-2.5 rounded-sm"
            style={{
              background:
                "color-mix(in srgb, var(--bz-accent) 20%, transparent)",
              boxShadow:
                "0 0 0 1px color-mix(in srgb, var(--bz-accent) 40%, transparent)",
            }}
          />
          Today
        </div>
      </div>
    </div>
  );
}

// ── Balance Cards ─────────────────────────────────────────────────────────────

function BalanceCards({ balances }: { balances: LeaveBalance[] }) {
  const annual = balances.find(
    (b) => b.code === "annual" || b.leave_type_name === "Annual Leave",
  );
  if (!annual) return null;

  const remaining =
    annual.allocated_days +
    (annual.carried_over ?? 0) -
    annual.used_days -
    annual.pending_days;
  const pct =
    annual.allocated_days > 0
      ? Math.max(0, Math.round((remaining / annual.allocated_days) * 100))
      : 0;

  return (
    <div className="grid grid-cols-3 gap-3">
      <div className="border rounded-xl p-4" style={PANEL}>
        <div className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
          Allocated
        </div>
        <div
          className="text-2xl font-bold"
          style={{ color: "var(--bz-text-1)" }}
        >
          {annual.allocated_days}
        </div>
        <div className="text-xs mt-0.5" style={{ color: "var(--bz-text-3)" }}>
          days / year
        </div>
      </div>
      <div className="border rounded-xl p-4" style={PANEL}>
        <div className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
          Used
        </div>
        <div className="flex items-baseline gap-1">
          <span
            className="text-2xl font-bold"
            style={{ color: "var(--bz-text-1)" }}
          >
            {annual.used_days}
          </span>
          {annual.pending_days > 0 && (
            <span className="text-xs" style={{ color: "var(--state-warning)" }}>
              +{annual.pending_days} pending
            </span>
          )}
        </div>
        <div className="text-xs mt-0.5" style={{ color: "var(--bz-text-3)" }}>
          days taken
        </div>
      </div>
      <div
        className="border rounded-xl p-4"
        style={{ ...PANEL, borderColor: "var(--bz-border-accent)" }}
      >
        <div className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
          Remaining
        </div>
        <div className="text-2xl font-bold text-[var(--bz-accent)]">
          {remaining}
        </div>
        <div
          className="w-full rounded-full h-1 mt-2"
          style={{
            background:
              "color-mix(in srgb, var(--bz-text-pure) 6%, transparent)",
          }}
        >
          <div
            className="bg-[var(--bz-accent)] h-1 rounded-full transition-all duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
}

// ── Request Row ───────────────────────────────────────────────────────────────

function RequestRow({
  req,
  isAdmin,
  rejectingId,
  rejectReason,
  onApprove,
  onRejectOpen,
  onRejectConfirm,
  onRejectCancel,
  onRejectReasonChange,
}: {
  req: LeaveRequest;
  isAdmin: boolean;
  rejectingId: number | null;
  rejectReason: string;
  onApprove: (id: number) => void;
  onRejectOpen: (id: number) => void;
  onRejectConfirm: (id: number) => void;
  onRejectCancel: () => void;
  onRejectReasonChange: (v: string) => void;
}) {
  const StatusIcon = statusIcons[req.status] ?? Clock;

  const start = new Date(req.start_date).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
  });
  const end = new Date(req.end_date).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  const dateLabel =
    req.start_date === req.end_date ? start : `${start} → ${end}`;

  return (
    <div>
      <div
        className="border rounded-lg p-4 flex items-center justify-between"
        style={{
          borderColor: "var(--bz-border)",
          background: statusRowBg[req.status] ?? (PANEL.background as string),
        }}
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <StatusIcon
            size={17}
            className="shrink-0"
            style={{ color: statusColors[req.status] ?? "var(--bz-text-2)" }}
          />
          <div className="min-w-0">
            <div
              className="font-medium text-sm"
              style={{ color: "var(--bz-text-1)" }}
            >
              {req.leave_type_name} — {req.total_days} day
              {req.total_days > 1 ? "s" : ""}
            </div>
            <div
              className="text-xs mt-0.5"
              style={{ color: "var(--bz-text-2)" }}
            >
              {isAdmin && req.employee_name && (
                <span
                  className="font-medium mr-1"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  {req.employee_name} ·
                </span>
              )}
              {dateLabel}
              {req.reason ? ` · "${req.reason}"` : ""}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0 ml-3">
          <span
            className="text-xs font-medium capitalize px-2 py-0.5 rounded-full"
            style={{
              background:
                "color-mix(in srgb, var(--surface-deep) 60%, transparent)",
              color: statusColors[req.status] ?? "var(--bz-text-2)",
            }}
          >
            {req.status}
          </span>
          {isAdmin && req.status === "pending" && (
            <>
              <button
                onClick={() => onApprove(req.id)}
                className="p-1.5 rounded-lg bg-[color-mix(in_srgb,var(--state-success)_12%,transparent)] text-[var(--state-success)] hover:bg-[color-mix(in_srgb,var(--state-success)_20%,transparent)] transition-colors"
                title="Approve"
              >
                <CheckCircle size={15} />
              </button>
              <button
                onClick={() => onRejectOpen(req.id)}
                className="p-1.5 rounded-lg bg-[color-mix(in_srgb,var(--state-danger)_12%,transparent)] text-[var(--state-danger)] hover:bg-[color-mix(in_srgb,var(--state-danger)_20%,transparent)] transition-colors"
                title="Reject"
              >
                <XCircle size={15} />
              </button>
            </>
          )}
        </div>
      </div>

      {rejectingId === req.id && (
        <div
          className="border border-t-0 rounded-b-lg px-4 py-3 flex items-center gap-2"
          style={{
            background: "var(--surface-deep)",
            borderColor: "var(--bz-border)",
          }}
        >
          <input
            type="text"
            value={rejectReason}
            onChange={(e) => onRejectReasonChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onRejectConfirm(req.id);
              if (e.key === "Escape") onRejectCancel();
            }}
            placeholder="Rejection reason..."
            className="flex-1 border rounded px-2 py-1.5 text-sm placeholder:text-[var(--bz-text-3)] focus:outline-none focus:border-[var(--bz-border-hover)]"
            style={{
              background: "var(--bz-surface)",
              borderColor: "var(--bz-border)",
              color: "var(--bz-text-1)",
            }}
            autoFocus
          />
          <button
            onClick={() => onRejectConfirm(req.id)}
            className="px-3 py-1.5 rounded bg-[color-mix(in_srgb,var(--state-danger)_20%,transparent)] text-[var(--state-danger)] hover:bg-[color-mix(in_srgb,var(--state-danger)_30%,transparent)] text-xs font-medium"
          >
            Confirm
          </button>
          <button
            onClick={onRejectCancel}
            className="px-3 py-1.5 rounded bg-[var(--surface-raised)] text-[var(--bz-text-2)] hover:bg-[color-mix(in_srgb,var(--bz-text-pure)_6%,transparent)] text-xs"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

// ── Team Summary Table ────────────────────────────────────────────────────────

function TeamSummaryTable({ summary }: { summary: TeamLeaveSummaryRow[] }) {
  // Group by employee, show annual leave only (main metric)
  const annual = summary.filter((s) => s.leave_type === "annual");

  if (annual.length === 0) {
    return (
      <div
        className="border rounded-xl p-6 text-center text-sm"
        style={{ ...PANEL, color: "var(--bz-text-2)" }}
      >
        No team leave data.
      </div>
    );
  }

  // Sort by used_days descending (most leave taken first)
  const sorted = [...annual].sort(
    (a, b) => b.used_days + b.pending_days - (a.used_days + a.pending_days),
  );

  return (
    <div className="border rounded-xl overflow-hidden" style={PANEL}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b" style={{ borderColor: "var(--bz-border)" }}>
            <th
              className="text-left text-xs font-semibold uppercase tracking-wider px-4 py-3"
              style={{ color: "var(--bz-text-2)" }}
            >
              Team Member
            </th>
            <th
              className="text-center text-xs font-semibold uppercase tracking-wider px-3 py-3"
              style={{ color: "var(--bz-text-2)" }}
            >
              Allocated
            </th>
            <th
              className="text-center text-xs font-semibold uppercase tracking-wider px-3 py-3"
              style={{ color: "var(--bz-text-2)" }}
            >
              Used
            </th>
            <th
              className="text-center text-xs font-semibold uppercase tracking-wider px-3 py-3"
              style={{ color: "var(--bz-text-2)" }}
            >
              Pending
            </th>
            <th
              className="text-center text-xs font-semibold uppercase tracking-wider px-3 py-3"
              style={{ color: "var(--bz-text-2)" }}
            >
              Remaining
            </th>
            <th
              className="text-right text-xs font-semibold uppercase tracking-wider px-4 py-3 w-32"
              style={{ color: "var(--bz-text-2)" }}
            >
              Usage
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const total = row.allocated_days + (row.carried_over ?? 0);
            const usedPct =
              total > 0
                ? Math.round(((row.used_days + row.pending_days) / total) * 100)
                : 0;
            const barColor =
              usedPct > 75
                ? "var(--state-danger)"
                : usedPct > 50
                  ? "var(--state-warning)"
                  : "var(--state-success)";

            return (
              <tr
                key={row.employee_id}
                className="border-b last:border-0 hover:bg-[var(--surface-raised)] transition-colors"
                style={{
                  borderColor:
                    "color-mix(in srgb, var(--bz-border) 50%, transparent)",
                }}
              >
                <td className="px-4 py-3">
                  <div
                    className="font-medium"
                    style={{ color: "var(--bz-text-1)" }}
                  >
                    {row.employee_name}
                  </div>
                </td>
                <td
                  className="text-center px-3 py-3"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  {row.allocated_days}
                </td>
                <td className="text-center px-3 py-3">
                  <span
                    className={row.used_days > 0 ? "font-medium" : ""}
                    style={{
                      color:
                        row.used_days > 0
                          ? "var(--bz-text-1)"
                          : "var(--bz-text-2)",
                    }}
                  >
                    {row.used_days}
                  </span>
                </td>
                <td className="text-center px-3 py-3">
                  {row.pending_days > 0 ? (
                    <span
                      className="font-medium"
                      style={{ color: "var(--state-warning)" }}
                    >
                      {row.pending_days}
                    </span>
                  ) : (
                    <span style={{ color: "var(--bz-text-3)" }}>0</span>
                  )}
                </td>
                <td className="text-center px-3 py-3">
                  <span
                    className="font-semibold"
                    style={{
                      color:
                        row.remaining_days <= 3
                          ? "var(--state-danger)"
                          : "var(--bz-accent)",
                    }}
                  >
                    {row.remaining_days}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div
                      className="flex-1 rounded-full h-1.5"
                      style={{
                        background:
                          "color-mix(in srgb, var(--bz-text-pure) 6%, transparent)",
                      }}
                    >
                      <div
                        className="h-1.5 rounded-full transition-all duration-300"
                        style={{
                          width: `${Math.min(usedPct, 100)}%`,
                          background: barColor,
                        }}
                      />
                    </div>
                    <span
                      className="text-xs w-8 text-right"
                      style={{ color: "var(--bz-text-2)" }}
                    >
                      {usedPct}%
                    </span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Team Requests Grouped ─────────────────────────────────────────────────────

function TeamRequestsGrouped({ requests }: { requests: LeaveRequest[] }) {
  // Group by employee name
  const grouped = useMemo(() => {
    const map = new Map<string, LeaveRequest[]>();
    for (const req of requests) {
      const name = req.employee_name ?? "Unknown";
      if (!map.has(name)) map.set(name, []);
      map.get(name)!.push(req);
    }
    // Sort groups by total days used (desc)
    return Array.from(map.entries()).sort(
      (a, b) =>
        b[1].reduce((s, r) => s + r.total_days, 0) -
        a[1].reduce((s, r) => s + r.total_days, 0),
    );
  }, [requests]);

  function formatDate(d: string) {
    return new Date(d).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
    });
  }

  return (
    <div
      className="border rounded-xl divide-y divide-[color-mix(in_srgb,var(--bz-text-pure)_4%,transparent)]"
      style={PANEL}
    >
      {grouped.map(([name, reqs]) => {
        const sickReqs = reqs.filter((r) =>
          r.leave_type_name?.includes("Sick"),
        );
        const leaveReqs = reqs.filter(
          (r) => !r.leave_type_name?.includes("Sick"),
        );
        const totalDays = reqs.reduce((s, r) => s + r.total_days, 0);

        return (
          <div key={name} className="px-4 py-3">
            <div className="flex items-center justify-between mb-1.5">
              <span
                className="font-medium text-sm"
                style={{ color: "var(--bz-text-1)" }}
              >
                {name}
              </span>
              <span className="text-xs" style={{ color: "var(--bz-text-2)" }}>
                {totalDays} day{totalDays !== 1 ? "s" : ""} total
              </span>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              {leaveReqs.length > 0 && (
                <div className="text-xs" style={{ color: "var(--bz-text-2)" }}>
                  <span
                    className="font-medium"
                    style={{
                      color:
                        "color-mix(in srgb, var(--state-success) 70%, transparent)",
                    }}
                  >
                    Leave:
                  </span>{" "}
                  {leaveReqs.map((r) => formatDate(r.start_date)).join(", ")}
                </div>
              )}
              {sickReqs.length > 0 && (
                <div className="text-xs" style={{ color: "var(--bz-text-2)" }}>
                  <span
                    className="font-medium"
                    style={{
                      color:
                        "color-mix(in srgb, var(--state-warning) 70%, transparent)",
                    }}
                  >
                    Sick:
                  </span>{" "}
                  {sickReqs.map((r) => formatDate(r.start_date)).join(", ")}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LeavePage() {
  const [requests, setRequests] = useState<LeaveRequest[]>([]);
  const [balances, setBalances] = useState<LeaveBalance[]>([]);
  const [teamSummary, setTeamSummary] = useState<TeamLeaveSummaryRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminTab, setAdminTab] = useState<"team" | "mine">("team");
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  useEffect(() => {
    Promise.all([
      api.getProfile().catch(() => null),
      hrApi.listLeaveRequests().catch(() => ({ requests: [] })),
      hrApi.getLeaveBalance().catch(() => ({ balances: [] })),
      hrApi.getTeamLeaveSummary().catch(() => ({ summary: [] })),
    ]).then(([profile, reqData, balData, teamData]) => {
      const admin = isHRAdmin(profile);
      setIsAdmin(admin);
      setRequests((reqData.requests as LeaveRequest[]) ?? []);
      setBalances((balData.balances as LeaveBalance[]) ?? []);
      setTeamSummary((teamData.summary as TeamLeaveSummaryRow[]) ?? []);
      setLoading(false);
    });
  }, []);

  const pendingTeam = requests.filter((r) => r.status === "pending");

  const handleApprove = async (id: number) => {
    try {
      await hrApi.approveLeave(id);
      setRequests((prev) =>
        prev.map((r) => (r.id === id ? { ...r, status: "approved" } : r)),
      );
      toast.success("Leave request approved");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to approve");
    }
  };

  const handleReject = async (id: number) => {
    if (!rejectReason.trim()) {
      toast.error("Please enter a rejection reason");
      return;
    }
    try {
      await hrApi.rejectLeave(id, rejectReason);
      setRequests((prev) =>
        prev.map((r) => (r.id === id ? { ...r, status: "rejected" } : r)),
      );
      setRejectingId(null);
      setRejectReason("");
      toast.success("Leave request rejected");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to reject");
    }
  };

  const rejectProps = {
    rejectingId,
    rejectReason,
    onApprove: handleApprove,
    onRejectOpen: (id: number) => {
      setRejectingId(rejectingId === id ? null : id);
      setRejectReason("");
    },
    onRejectConfirm: handleReject,
    onRejectCancel: () => {
      setRejectingId(null);
      setRejectReason("");
    },
    onRejectReasonChange: setRejectReason,
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <h1
          className="text-2xl font-bold"
          style={{ color: "var(--bz-text-1)" }}
        >
          Leave
        </h1>
        <div className="animate-pulse space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-16 rounded-lg" style={PANEL} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1
          className="text-2xl font-bold"
          style={{ color: "var(--bz-text-1)" }}
        >
          Leave
        </h1>
        <Link
          href="/hr/leave/request"
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--bz-accent)]/10 text-[var(--bz-accent)] hover:bg-[var(--bz-accent)]/20 text-sm transition-colors"
        >
          <Plus size={15} />
          Request Leave
        </Link>
      </div>

      {/* Admin tab switcher */}
      {isAdmin && (
        <div className="flex gap-1 border rounded-lg p-1 w-fit" style={PANEL}>
          <button
            onClick={() => setAdminTab("team")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              adminTab === "team"
                ? "bg-[var(--surface-selected)] text-[var(--bz-text-1)]"
                : "text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)] hover:bg-[var(--surface-raised)]"
            }`}
          >
            <Users size={14} />
            Team
            {pendingTeam.length > 0 && (
              <span className="ml-1 px-1.5 py-0.5 rounded-full bg-[color-mix(in_srgb,var(--state-warning)_20%,transparent)] text-[var(--state-warning)] text-xs font-semibold leading-none">
                {pendingTeam.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setAdminTab("mine")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              adminTab === "mine"
                ? "bg-[var(--surface-selected)] text-[var(--bz-text-1)]"
                : "text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)] hover:bg-[var(--surface-raised)]"
            }`}
          >
            <Calendar size={14} />
            My Leave
          </button>
        </div>
      )}

      {/* TEAM VIEW */}
      {isAdmin && adminTab === "team" ? (
        <div className="space-y-6">
          <div>
            <p
              className="text-xs font-semibold uppercase tracking-wider mb-3"
              style={{ color: "var(--bz-text-2)" }}
            >
              Team Leave Balances
            </p>
            <TeamSummaryTable summary={teamSummary} />
          </div>

          <div>
            <p
              className="text-xs font-semibold uppercase tracking-wider mb-3"
              style={{ color: "var(--bz-text-2)" }}
            >
              Team Calendar
            </p>
            <MiniCalendar requests={requests} />
          </div>

          <div>
            <p
              className="text-xs font-semibold uppercase tracking-wider mb-3"
              style={{ color: "var(--bz-text-2)" }}
            >
              Pending Approval
            </p>
            {pendingTeam.length === 0 ? (
              <div
                className="border rounded-xl p-6 text-center text-sm"
                style={{ ...PANEL, color: "var(--bz-text-2)" }}
              >
                No pending leave requests.
              </div>
            ) : (
              <div className="space-y-2">
                {pendingTeam.map((req) => (
                  <RequestRow key={req.id} req={req} isAdmin {...rejectProps} />
                ))}
              </div>
            )}
          </div>

          {requests.filter((r) => r.status !== "pending").length > 0 && (
            <div>
              <p
                className="text-xs font-semibold uppercase tracking-wider mb-3"
                style={{ color: "var(--bz-text-2)" }}
              >
                Recent History
              </p>
              <TeamRequestsGrouped
                requests={requests.filter((r) => r.status !== "pending")}
              />
            </div>
          )}
        </div>
      ) : (
        /* MY LEAVE VIEW */
        <div className="space-y-6">
          {balances.length > 0 && <BalanceCards balances={balances} />}

          <div>
            <p
              className="text-xs font-semibold uppercase tracking-wider mb-3"
              style={{ color: "var(--bz-text-2)" }}
            >
              Calendar
            </p>
            <MiniCalendar requests={requests} />
          </div>

          <div>
            <p
              className="text-xs font-semibold uppercase tracking-wider mb-3"
              style={{ color: "var(--bz-text-2)" }}
            >
              My Requests
            </p>
            {requests.length === 0 ? (
              <div
                className="border rounded-xl p-6 text-center text-sm"
                style={{ ...PANEL, color: "var(--bz-text-2)" }}
              >
                No leave requests yet.{" "}
                <Link
                  href="/hr/leave/request"
                  className="text-[var(--bz-accent)] hover:underline"
                >
                  Submit your first request →
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                {requests.map((req) => (
                  <RequestRow
                    key={req.id}
                    req={req}
                    isAdmin={false}
                    {...rejectProps}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
