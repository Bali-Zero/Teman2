"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  CheckCircle,
  DollarSign,
  XCircle,
  MinusCircle,
  Download,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import { api } from "@/lib/api";
import * as partnersApi from "@/lib/api/partners/partners";
import type { PartnerCommission } from "@/lib/api/partners/partners";

function formatIDR(amount: number): string {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(amount);
}

const STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  pending_approval: { bg: "bg-amber-500/20", text: "text-amber-400" },
  approved: { bg: "bg-blue-500/20", text: "text-blue-400" },
  ready_to_pay: { bg: "bg-purple-500/20", text: "text-purple-400" },
  paid: { bg: "bg-green-500/20", text: "text-green-400" },
  clawback_pending: { bg: "bg-orange-500/20", text: "text-orange-400" },
  clawed_back: { bg: "bg-red-500/20", text: "text-red-400" },
  waived: { bg: "bg-gray-500/20", text: "text-gray-400" },
};

interface CommissionRowProps {
  commission: PartnerCommission;
  // CRIT-8: commission IDs are UUID strings
  onApprove?: (id: string) => void;
  onMarkPaid?: (id: string) => void;
  onClawback?: (id: string) => void;
  onWaive?: (id: string) => void;
  actioningId: string | null;
}

function CommissionRow({
  commission: c,
  onApprove,
  onMarkPaid,
  onClawback,
  onWaive,
  actioningId,
}: CommissionRowProps) {
  const cs = STATUS_STYLES[c.status] || { bg: "bg-gray-500/20", text: "text-gray-400" };
  const isActioning = actioningId === c.id;

  return (
    <tr className="hover:bg-zinc-800/30 transition-colors">
      <td className="px-4 py-3">
        {/* CRIT-8: partner_id is a UUID string */}
        <div className="text-sm font-medium text-zinc-100">{c.partner_name || `Partner ${c.partner_id.substring(0, 8)}…`}</div>
        <div className="text-xs text-zinc-500">{c.client_name || ""}</div>
      </td>
      <td className="px-4 py-3 text-sm text-zinc-400 hidden md:table-cell">
        {c.practice_type_name || (c.practice_id ? `Practice ${c.practice_id.substring(0, 8)}…` : "—")}
      </td>
      <td className="px-4 py-3 text-sm text-zinc-300">{formatIDR(c.gross_amount)}</td>
      <td className="px-4 py-3 text-sm text-zinc-300">{formatIDR(c.net_amount)}</td>
      <td className="px-4 py-3">
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cs.bg} ${cs.text}`}>
          {c.status.replace(/_/g, " ")}
        </span>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1 justify-end flex-wrap">
          {c.status === "pending_approval" && onApprove && (
            <Button
              size="sm"
              disabled={isActioning}
              onClick={() => onApprove(c.id)}
              className="bg-green-700 hover:bg-green-600 text-white h-7 text-xs px-2"
            >
              {isActioning ? <Loader2 size={10} className="animate-spin" /> : <><CheckCircle size={10} className="mr-1" />Approve</>}
            </Button>
          )}
          {c.status === "approved" && onMarkPaid && (
            <Button
              size="sm"
              disabled={isActioning}
              onClick={() => onMarkPaid(c.id)}
              className="bg-purple-700 hover:bg-purple-600 text-white h-7 text-xs px-2"
            >
              {isActioning ? <Loader2 size={10} className="animate-spin" /> : <><DollarSign size={10} className="mr-1" />Mark Paid</>}
            </Button>
          )}
          {["pending_approval", "approved", "ready_to_pay"].includes(c.status) && onClawback && (
            <Button
              size="sm"
              variant="outline"
              disabled={isActioning}
              onClick={() => onClawback(c.id)}
              className="border-red-700 text-red-400 hover:bg-red-900/20 h-7 text-xs px-2"
            >
              {isActioning ? <Loader2 size={10} className="animate-spin" /> : <><XCircle size={10} className="mr-1" />Clawback</>}
            </Button>
          )}
          {["pending_approval", "approved"].includes(c.status) && onWaive && (
            <Button
              size="sm"
              variant="outline"
              disabled={isActioning}
              onClick={() => onWaive(c.id)}
              className="border-zinc-700 text-zinc-400 hover:bg-zinc-800 h-7 text-xs px-2"
            >
              {isActioning ? <Loader2 size={10} className="animate-spin" /> : <><MinusCircle size={10} className="mr-1" />Waive</>}
            </Button>
          )}
        </div>
      </td>
    </tr>
  );
}

interface CommissionSectionProps {
  title: string;
  commissions: PartnerCommission[];
  // CRIT-8: commission IDs are UUID strings
  onApprove?: (id: string) => void;
  onMarkPaid?: (id: string) => void;
  onClawback?: (id: string) => void;
  onWaive?: (id: string) => void;
  actioningId: string | null;
  emptyMessage: string;
}

function CommissionSection({
  title,
  commissions,
  onApprove,
  onMarkPaid,
  onClawback,
  onWaive,
  actioningId,
  emptyMessage,
}: CommissionSectionProps) {
  if (commissions.length === 0) {
    return (
      <div>
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wide mb-3">{title}</h2>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 text-center text-sm text-zinc-600">
          {emptyMessage}
        </div>
      </div>
    );
  }

  const sectionTotal = commissions.reduce((sum, c) => sum + c.net_amount, 0);

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wide">
          {title}
          <span className="ml-2 text-zinc-600 font-normal normal-case">
            ({commissions.length} · {formatIDR(sectionTotal)})
          </span>
        </h2>
      </div>
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-zinc-800">
              <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">Partner / Client</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase hidden md:table-cell">Practice</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">Gross</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">Net</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {commissions.map((c) => (
              <CommissionRow
                key={c.id}
                commission={c}
                onApprove={onApprove}
                onMarkPaid={onMarkPaid}
                onClawback={onClawback}
                onWaive={onWaive}
                actioningId={actioningId}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function FinanceQueuePage() {
  const router = useRouter();
  const { success: toastSuccess, error: toastError } = useToast();
  const [commissions, setCommissions] = useState<PartnerCommission[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // CRIT-8: commission IDs are UUID strings
  const [actioningId, setActioningId] = useState<string | null>(null);

  // Admin gate — redirect non-admin users back to partners list
  useEffect(() => {
    if (!api.isAdmin?.()) {
      router.replace('/partners');
    }
  }, [router]);

  const loadCommissions = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await partnersApi.listAllCommissions({
        status: "pending_approval,approved,clawback_pending",
      });
      setCommissions(data.commissions);
    } catch (err) {
      logger.error("Failed to load finance queue", { component: "FinanceQueuePage" }, err as Error);
      setError("Failed to load commissions. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadCommissions(); }, [loadCommissions]);

  // CRIT-8: commission IDs are UUID strings
  const handleApprove = async (id: string) => {
    setActioningId(id);
    try {
      await partnersApi.approveCommission(id);
      toastSuccess("Commission approved");
      await loadCommissions();
    } catch {
      toastError("Failed to approve commission");
    } finally {
      setActioningId(null);
    }
  };

  const handleMarkPaid = async (id: string) => {
    setActioningId(id);
    const ref = prompt("Payment reference (optional):");
    const via = prompt("Paid via (e.g. BCA, Cash):");
    try {
      await partnersApi.markPaid(id, { payment_reference: ref || undefined, paid_via: via || undefined });
      toastSuccess("Commission marked as paid");
      await loadCommissions();
    } catch {
      toastError("Failed to mark commission as paid");
    } finally {
      setActioningId(null);
    }
  };

  const handleClawback = async (id: string) => {
    setActioningId(id);
    const reason = prompt("Clawback reason (required):");
    if (!reason?.trim()) { setActioningId(null); return; }
    try {
      await partnersApi.clawback(id, { reason: reason.trim() });
      toastSuccess("Clawback initiated");
      await loadCommissions();
    } catch {
      toastError("Failed to initiate clawback");
    } finally {
      setActioningId(null);
    }
  };

  const handleWaive = async (id: string) => {
    setActioningId(id);
    const reason = prompt("Waive reason (required):");
    if (!reason?.trim()) { setActioningId(null); return; }
    try {
      await partnersApi.waive(id, { reason: reason.trim() });
      toastSuccess("Commission waived");
      await loadCommissions();
    } catch {
      toastError("Failed to waive commission");
    } finally {
      setActioningId(null);
    }
  };

  const pendingApproval = commissions.filter((c) => c.status === "pending_approval");
  const approved = commissions.filter((c) => c.status === "approved");
  const clawbackPending = commissions.filter((c) => c.status === "clawback_pending");

  const csvUrl = partnersApi.exportFinanceCsv();

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/partners">
            <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-zinc-200">
              <ArrowLeft size={16} className="mr-1" />
              Partners
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold text-zinc-100">Finance Queue</h1>
            <p className="text-sm text-zinc-500">Partner commission approval and payment tracking</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadCommissions}
            className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
          >
            <RefreshCw size={14} className="mr-1" />
            Refresh
          </Button>
          <a href={csvUrl} download className="inline-flex">
            <Button
              variant="outline"
              size="sm"
              className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
            >
              <Download size={14} className="mr-1" />
              Export CSV
            </Button>
          </a>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 size={32} className="animate-spin text-amber-400" />
        </div>
      ) : error ? (
        <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      ) : (
        <>
          <CommissionSection
            title="Pending Approval"
            commissions={pendingApproval}
            onApprove={handleApprove}
            onClawback={handleClawback}
            onWaive={handleWaive}
            actioningId={actioningId}
            emptyMessage="No commissions pending approval"
          />

          <CommissionSection
            title="Ready to Pay (Approved)"
            commissions={approved}
            onMarkPaid={handleMarkPaid}
            onClawback={handleClawback}
            actioningId={actioningId}
            emptyMessage="No commissions ready to pay"
          />

          <CommissionSection
            title="Pending Clawback"
            commissions={clawbackPending}
            actioningId={actioningId}
            emptyMessage="No pending clawbacks"
          />
        </>
      )}
    </div>
  );
}
