"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  Calendar,
  ChevronLeft,
  ChevronRight,
  CheckCircle,
  XCircle,
  Clock,
  Plus,
  Users,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import * as hrApi from "@/lib/api/hr/hr";
import type { LeaveRequest, LeaveBalance } from "@/types/hr";

// ── Constants ─────────────────────────────────────────────────────────────────

const ADMIN_EMAILS = [
  "zero@balizero.com",
  "asya@balizero.com",
  "ruslana@balizero.com",
  "antonellosiano@gmail.com",
];

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const statusIcons: Record<string, LucideIcon> = {
  pending: Clock,
  approved: CheckCircle,
  rejected: XCircle,
  cancelled: XCircle,
};

const statusColors: Record<string, string> = {
  pending: "text-amber-400",
  approved: "text-emerald-400",
  rejected: "text-red-400",
  cancelled: "text-zinc-500",
};

const statusBg: Record<string, string> = {
  pending: "bg-amber-500/10",
  approved: "bg-emerald-500/10",
  rejected: "bg-zinc-900",
  cancelled: "bg-zinc-900",
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

  function dayClass(day: number): string {
    const key = cellKey(day);
    const statuses = dayMap[key] ?? [];
    const isToday = key === todayStr;
    if (statuses.includes("approved"))
      return "bg-emerald-500/25 text-emerald-300 rounded-md font-semibold";
    if (statuses.includes("pending"))
      return "bg-amber-500/20 text-amber-300 rounded-md font-semibold";
    if (isToday)
      return "bg-[var(--bz-accent)]/20 text-[var(--bz-accent)] rounded-md font-bold ring-1 ring-[var(--bz-accent)]/40";
    return "text-zinc-400 hover:bg-zinc-800 rounded-md";
  }

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => setCurrent(new Date(year, month - 1, 1))}
          className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <ChevronLeft size={16} />
        </button>
        <span className="text-sm font-semibold text-zinc-200">
          {MONTH_NAMES[month]} {year}
        </span>
        <button
          onClick={() => setCurrent(new Date(year, month + 1, 1))}
          className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <ChevronRight size={16} />
        </button>
      </div>

      <div className="grid grid-cols-7 mb-1">
        {["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"].map((d) => (
          <div key={d} className="text-center text-xs text-zinc-600 font-medium py-1">
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
              className={`text-center text-xs py-1.5 cursor-default transition-colors ${dayClass(day)}`}
            >
              {day}
            </div>
          ),
        )}
      </div>

      <div className="flex items-center gap-4 mt-3 pt-3 border-t border-zinc-800">
        <div className="flex items-center gap-1.5 text-xs text-zinc-500">
          <div className="w-2.5 h-2.5 rounded-sm bg-emerald-500/25" />
          Approved
        </div>
        <div className="flex items-center gap-1.5 text-xs text-zinc-500">
          <div className="w-2.5 h-2.5 rounded-sm bg-amber-500/20" />
          Pending
        </div>
        <div className="flex items-center gap-1.5 text-xs text-zinc-500">
          <div className="w-2.5 h-2.5 rounded-sm bg-[var(--bz-accent)]/20 ring-1 ring-[var(--bz-accent)]/40" />
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
    annual.allocated_days + (annual.carried_over ?? 0) - annual.used_days - annual.pending_days;
  const pct =
    annual.allocated_days > 0
      ? Math.max(0, Math.round((remaining / annual.allocated_days) * 100))
      : 0;

  return (
    <div className="grid grid-cols-3 gap-3">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
        <div className="text-xs text-zinc-500 mb-1">Allocated</div>
        <div className="text-2xl font-bold text-zinc-100">{annual.allocated_days}</div>
        <div className="text-xs text-zinc-600 mt-0.5">days / year</div>
      </div>
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
        <div className="text-xs text-zinc-500 mb-1">Used</div>
        <div className="flex items-baseline gap-1">
          <span className="text-2xl font-bold text-zinc-300">{annual.used_days}</span>
          {annual.pending_days > 0 && (
            <span className="text-xs text-amber-400">+{annual.pending_days} pending</span>
          )}
        </div>
        <div className="text-xs text-zinc-600 mt-0.5">days taken</div>
      </div>
      <div className="bg-zinc-900 border border-[var(--bz-accent)]/20 rounded-xl p-4">
        <div className="text-xs text-zinc-500 mb-1">Remaining</div>
        <div className="text-2xl font-bold text-[var(--bz-accent)]">{remaining}</div>
        <div className="w-full bg-zinc-800 rounded-full h-1 mt-2">
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
  const dateLabel = req.start_date === req.end_date ? start : `${start} → ${end}`;

  return (
    <div>
      <div
        className={`border border-zinc-800 rounded-lg p-4 flex items-center justify-between ${statusBg[req.status]}`}
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <StatusIcon size={17} className={`shrink-0 ${statusColors[req.status]}`} />
          <div className="min-w-0">
            <div className="font-medium text-zinc-200 text-sm">
              {req.leave_type_name} — {req.total_days} day{req.total_days > 1 ? "s" : ""}
            </div>
            <div className="text-xs text-zinc-500 mt-0.5">
              {isAdmin && req.employee_name && (
                <span className="font-medium text-zinc-400 mr-1">{req.employee_name} ·</span>
              )}
              {dateLabel}
              {req.reason ? ` · "${req.reason}"` : ""}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0 ml-3">
          <span
            className={`text-xs font-medium capitalize px-2 py-0.5 rounded-full bg-zinc-900/60 ${statusColors[req.status]}`}
          >
            {req.status}
          </span>
          {isAdmin && req.status === "pending" && (
            <>
              <button
                onClick={() => onApprove(req.id)}
                className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
                title="Approve"
              >
                <CheckCircle size={15} />
              </button>
              <button
                onClick={() => onRejectOpen(req.id)}
                className="p-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors"
                title="Reject"
              >
                <XCircle size={15} />
              </button>
            </>
          )}
        </div>
      </div>

      {rejectingId === req.id && (
        <div className="bg-zinc-950 border border-zinc-800 border-t-0 rounded-b-lg px-4 py-3 flex items-center gap-2">
          <input
            type="text"
            value={rejectReason}
            onChange={(e) => onRejectReasonChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onRejectConfirm(req.id);
              if (e.key === "Escape") onRejectCancel();
            }}
            placeholder="Rejection reason..."
            className="flex-1 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
            autoFocus
          />
          <button
            onClick={() => onRejectConfirm(req.id)}
            className="px-3 py-1.5 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30 text-xs font-medium"
          >
            Confirm
          </button>
          <button
            onClick={onRejectCancel}
            className="px-3 py-1.5 rounded bg-zinc-800 text-zinc-400 hover:bg-zinc-700 text-xs"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function LeavePage() {
  const [requests, setRequests] = useState<LeaveRequest[]>([]);
  const [balances, setBalances] = useState<LeaveBalance[]>([]);
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminTab, setAdminTab] = useState<"mine" | "team">("mine");
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  useEffect(() => {
    Promise.all([
      (api.getProfile() as Promise<{ email: string }>).catch(() => null),
      hrApi.listLeaveRequests().catch(() => ({ requests: [] })),
      hrApi.getLeaveBalance().catch(() => ({ balances: [] })),
    ]).then(([profile, reqData, balData]) => {
      if (profile) setIsAdmin(ADMIN_EMAILS.includes(profile.email));
      setRequests((reqData.requests as LeaveRequest[]) ?? []);
      setBalances((balData.balances as LeaveBalance[]) ?? []);
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
        <h1 className="text-2xl font-bold text-zinc-100">Leave</h1>
        <div className="animate-pulse space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-16 bg-zinc-900 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-zinc-100">Leave</h1>
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
        <div className="flex gap-1 bg-zinc-900 border border-zinc-800 rounded-lg p-1 w-fit">
          <button
            onClick={() => setAdminTab("mine")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              adminTab === "mine"
                ? "bg-zinc-800 text-zinc-100"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <Calendar size={14} />
            My Leave
          </button>
          <button
            onClick={() => setAdminTab("team")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              adminTab === "team"
                ? "bg-zinc-800 text-zinc-100"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            <Users size={14} />
            Team
            {pendingTeam.length > 0 && (
              <span className="ml-1 px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400 text-xs font-semibold leading-none">
                {pendingTeam.length}
              </span>
            )}
          </button>
        </div>
      )}

      {/* TEAM VIEW */}
      {isAdmin && adminTab === "team" ? (
        <div className="space-y-6">
          <div>
            <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
              Team Calendar
            </p>
            <MiniCalendar requests={requests} />
          </div>

          <div>
            <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
              Pending Approval
            </p>
            {pendingTeam.length === 0 ? (
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 text-center text-zinc-500 text-sm">
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
              <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                All Requests
              </p>
              <div className="space-y-2">
                {requests
                  .filter((r) => r.status !== "pending")
                  .map((req) => (
                    <RequestRow key={req.id} req={req} isAdmin {...rejectProps} />
                  ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        /* MY LEAVE VIEW */
        <div className="space-y-6">
          {balances.length > 0 && <BalanceCards balances={balances} />}

          <div>
            <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
              Calendar
            </p>
            <MiniCalendar requests={requests} />
          </div>

          <div>
            <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
              My Requests
            </p>
            {requests.length === 0 ? (
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 text-center text-zinc-500 text-sm">
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
                  <RequestRow key={req.id} req={req} isAdmin={false} {...rejectProps} />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
