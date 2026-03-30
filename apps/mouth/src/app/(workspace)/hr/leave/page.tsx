"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { Calendar, Plus, CheckCircle, XCircle, Clock } from "lucide-react";
import { toast } from "sonner";
import * as hrApi from "@/lib/api/hr/hr";
import type { LeaveRequest, LeaveBalance } from "@/types/hr";

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

export default function LeavePage() {
  const [requests, setRequests] = useState<LeaveRequest[]>([]);
  const [balances, setBalances] = useState<LeaveBalance[]>([]);
  const [loading, setLoading] = useState(true);
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  useEffect(() => {
    Promise.all([
      hrApi.listLeaveRequests().catch(() => ({ requests: [] })),
      hrApi.getLeaveBalance().catch(() => ({ balances: [] })),
    ]).then(([reqData, balData]) => {
      setRequests((reqData.requests as LeaveRequest[]) || []);
      setBalances((balData.balances as LeaveBalance[]) || []);
      setLoading(false);
    });
  }, []);

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

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-zinc-100">Leave Management</h1>
        <div className="animate-pulse space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 bg-zinc-900 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-zinc-100">Leave Management</h1>
        <Link
          href="/hr/leave/request"
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--bz-accent)]/10 text-[var(--bz-accent)] hover:bg-[var(--bz-accent)]/20 text-sm transition-colors"
        >
          <Plus size={16} />
          Request Leave
        </Link>
      </div>

      {balances.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-zinc-300 mb-3">
            Leave Balances
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {balances.map((bal) => {
              const remaining =
                bal.allocated_days +
                (bal.carried_over || 0) -
                bal.used_days -
                bal.pending_days;
              return (
                <div
                  key={bal.id}
                  className="bg-zinc-900 border border-zinc-800 rounded-lg p-4"
                >
                  <div className="text-sm text-zinc-400">
                    {bal.leave_type_name || bal.name}
                  </div>
                  <div className="text-2xl font-bold text-zinc-100 mt-1">
                    {remaining} days
                  </div>
                  <div className="text-xs text-zinc-500 mt-1">
                    {bal.allocated_days} allocated · {bal.used_days} used ·{" "}
                    {bal.pending_days} pending
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div>
        <h2 className="text-lg font-semibold text-zinc-300 mb-3">Requests</h2>
        {requests.length === 0 ? (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center text-zinc-500">
            No leave requests yet.
          </div>
        ) : (
          <div className="space-y-2">
            {requests.map((req) => {
              const StatusIcon = statusIcons[req.status] || Clock;
              return (
                <div key={req.id} className="space-y-0">
                  <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3 flex-1">
                      <StatusIcon
                        size={18}
                        className={statusColors[req.status]}
                      />
                      <div>
                        <div className="font-medium text-zinc-200">
                          {req.leave_type_name} — {req.total_days} day
                          {req.total_days > 1 ? "s" : ""}
                        </div>
                        <div className="text-sm text-zinc-500">
                          {req.employee_name && `${req.employee_name} · `}
                          {new Date(req.start_date).toLocaleDateString(
                            "id-ID",
                          )}{" "}
                          → {new Date(req.end_date).toLocaleDateString("id-ID")}
                          {req.reason && ` · ${req.reason}`}
                        </div>
                      </div>
                    </div>
                    {req.status === "pending" && (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleApprove(req.id)}
                          className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20"
                          title="Approve"
                        >
                          <CheckCircle size={16} />
                        </button>
                        <button
                          onClick={() => {
                            setRejectingId(
                              rejectingId === req.id ? null : req.id,
                            );
                            setRejectReason("");
                          }}
                          className="p-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20"
                          title="Reject"
                        >
                          <XCircle size={16} />
                        </button>
                      </div>
                    )}
                  </div>
                  {rejectingId === req.id && (
                    <div className="bg-zinc-950 border border-zinc-800 border-t-0 rounded-b-lg px-4 py-3 flex items-center gap-2">
                      <input
                        type="text"
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleReject(req.id);
                          if (e.key === "Escape") {
                            setRejectingId(null);
                            setRejectReason("");
                          }
                        }}
                        placeholder="Rejection reason..."
                        className="flex-1 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm text-zinc-200 placeholder:text-zinc-600"
                        autoFocus
                      />
                      <button
                        onClick={() => handleReject(req.id)}
                        className="px-3 py-1.5 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30 text-xs font-medium"
                      >
                        Confirm
                      </button>
                      <button
                        onClick={() => {
                          setRejectingId(null);
                          setRejectReason("");
                        }}
                        className="px-3 py-1.5 rounded bg-zinc-800 text-zinc-400 hover:bg-zinc-700 text-xs"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
