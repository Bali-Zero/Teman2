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
import { Money } from "@balizero/core";

/** Dashboard panel recipe — mirrors the operative-dark kita surfaces. */
const PANEL: React.CSSProperties = {
  background: "rgba(35,35,40,0.65)",
  borderColor: "var(--bz-border)",
};

/** State-tinted chip (status pills on the dark panel surface). */
function stateChip(state: string): React.CSSProperties {
  return {
    background: `color-mix(in srgb, ${state} 12%, transparent)`,
    color: state,
    borderColor: `color-mix(in srgb, ${state} 30%, transparent)`,
  };
}

/** Neutral chip for closed/inert statuses. */
const NEUTRAL_CHIP: React.CSSProperties = {
  background: "color-mix(in srgb, var(--bz-text-pure) 6%, transparent)",
  color: "var(--bz-text-2)",
  borderColor: "var(--bz-border)",
};

// Commission pipeline statuses, same mapping as partners/[id]: pending steps
// -> warning, approved -> info, ready_to_pay -> neon purple (identity hue),
// paid -> success, clawback steps -> warning/danger, waived -> neutral.
const STATUS_STYLES: Record<string, React.CSSProperties> = {
  pending_approval: stateChip("var(--state-warning)"),
  approved: stateChip("var(--state-info)"),
  ready_to_pay: stateChip("var(--bz-neon-purple)"),
  paid: stateChip("var(--state-success)"),
  clawback_pending: stateChip("var(--state-warning)"),
  clawed_back: stateChip("var(--state-danger)"),
  waived: NEUTRAL_CHIP,
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
  const cs = STATUS_STYLES[c.status] || NEUTRAL_CHIP;
  const isActioning = actioningId === c.id;

  return (
    <tr className="hover:bg-[var(--bz-glass-rim)] transition-colors">
      <td className="px-4 py-3">
        {/* CRIT-8: partner_id is a UUID string */}
        <div className="text-sm font-medium text-[var(--bz-text-1)]">
          {c.partner_name || `Partner ${c.partner_id.substring(0, 8)}…`}
        </div>
        <div className="text-xs text-[var(--bz-text-3)]">
          {c.client_name || ""}
        </div>
      </td>
      <td className="px-4 py-3 text-sm text-[var(--bz-text-2)] hidden md:table-cell">
        {c.practice_type_name ||
          (c.practice_id ? `Practice ${c.practice_id.substring(0, 8)}…` : "—")}
      </td>
      <td className="px-4 py-3 text-sm text-[var(--bz-text-1)]">
        <Money value={c.gross_amount} />
      </td>
      <td className="px-4 py-3 text-sm text-[var(--bz-text-1)]">
        <Money value={c.net_amount} />
      </td>
      <td className="px-4 py-3">
        <span
          className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border"
          style={cs}
        >
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
              className="bg-[var(--state-success)]/15 text-[var(--state-success)] hover:bg-[var(--state-success)]/25 h-7 text-xs px-2"
            >
              {isActioning ? (
                <Loader2 size={10} className="animate-spin" />
              ) : (
                <>
                  <CheckCircle size={10} className="mr-1" />
                  Approve
                </>
              )}
            </Button>
          )}
          {c.status === "approved" && onMarkPaid && (
            <Button
              size="sm"
              disabled={isActioning}
              onClick={() => onMarkPaid(c.id)}
              className="bg-[var(--bz-neon-purple)]/15 text-[var(--bz-neon-purple)] hover:bg-[var(--bz-neon-purple)]/25 h-7 text-xs px-2"
            >
              {isActioning ? (
                <Loader2 size={10} className="animate-spin" />
              ) : (
                <>
                  <DollarSign size={10} className="mr-1" />
                  Mark Paid
                </>
              )}
            </Button>
          )}
          {["pending_approval", "approved", "ready_to_pay"].includes(
            c.status,
          ) &&
            onClawback && (
              <Button
                size="sm"
                variant="outline"
                disabled={isActioning}
                onClick={() => onClawback(c.id)}
                className="border-[var(--state-danger)]/50 text-[var(--state-danger)] hover:bg-[var(--state-danger)]/10 h-7 text-xs px-2"
              >
                {isActioning ? (
                  <Loader2 size={10} className="animate-spin" />
                ) : (
                  <>
                    <XCircle size={10} className="mr-1" />
                    Clawback
                  </>
                )}
              </Button>
            )}
          {["pending_approval", "approved"].includes(c.status) && onWaive && (
            <Button
              size="sm"
              variant="outline"
              disabled={isActioning}
              onClick={() => onWaive(c.id)}
              className="border-[var(--bz-border)] text-[var(--bz-text-2)] hover:bg-[var(--bz-glass-rim)] h-7 text-xs px-2"
            >
              {isActioning ? (
                <Loader2 size={10} className="animate-spin" />
              ) : (
                <>
                  <MinusCircle size={10} className="mr-1" />
                  Waive
                </>
              )}
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
        <h2 className="text-sm font-semibold text-[var(--bz-text-2)] uppercase tracking-wide mb-3">
          {title}
        </h2>
        <div
          className="border rounded-xl p-6 text-center text-sm text-[var(--bz-text-3)]"
          style={PANEL}
        >
          {emptyMessage}
        </div>
      </div>
    );
  }

  const sectionTotal = commissions.reduce((sum, c) => sum + c.net_amount, 0);

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-[var(--bz-text-2)] uppercase tracking-wide">
          {title}
          <span className="ml-2 text-[var(--bz-text-3)] font-normal normal-case">
            ({commissions.length} · <Money value={sectionTotal} />)
          </span>
        </h2>
      </div>
      <div className="border rounded-xl overflow-hidden" style={PANEL}>
        <table className="w-full">
          <thead>
            <tr className="border-b border-[var(--bz-border)]">
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
                Partner / Client
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase hidden md:table-cell">
                Practice
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
                Gross
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
                Net
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
                Status
              </th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--bz-border)]">
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
      router.replace("/partners");
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
      logger.error(
        "Failed to load finance queue",
        { component: "FinanceQueuePage" },
        err as Error,
      );
      setError("Failed to load commissions. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCommissions();
  }, [loadCommissions]);

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
    // CRIT-8 residual: backend requires paid_via + payment_reference. Prompt must succeed.
    const via = prompt("Paid via (required, e.g. BCA, Cash):");
    if (!via?.trim()) {
      toastError("Paid via is required");
      return;
    }
    const ref = prompt("Payment reference (required, e.g. TX-20260520-001):");
    if (!ref?.trim()) {
      toastError("Payment reference is required");
      return;
    }
    setActioningId(id);
    try {
      await partnersApi.markPaid(id, {
        paid_via: via.trim(),
        payment_reference: ref.trim(),
      });
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
    if (!reason?.trim()) {
      setActioningId(null);
      return;
    }
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
    if (!reason?.trim()) {
      setActioningId(null);
      return;
    }
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

  const pendingApproval = commissions.filter(
    (c) => c.status === "pending_approval",
  );
  const approved = commissions.filter((c) => c.status === "approved");
  const clawbackPending = commissions.filter(
    (c) => c.status === "clawback_pending",
  );

  const csvUrl = partnersApi.exportFinanceCsv();

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/partners">
            <Button
              variant="ghost"
              size="sm"
              className="text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)]"
            >
              <ArrowLeft size={16} className="mr-1" />
              Partners
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold text-[var(--bz-text-1)]">
              Finance Queue
            </h1>
            <p className="text-sm text-[var(--bz-text-3)]">
              Partner commission approval and payment tracking
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadCommissions}
            className="border-[var(--bz-border)] text-[var(--bz-text-1)] hover:bg-[var(--bz-glass-rim)]"
          >
            <RefreshCw size={14} className="mr-1" />
            Refresh
          </Button>
          <a href={csvUrl} download className="inline-flex">
            <Button
              variant="outline"
              size="sm"
              className="border-[var(--bz-border)] text-[var(--bz-text-1)] hover:bg-[var(--bz-glass-rim)]"
            >
              <Download size={14} className="mr-1" />
              Export CSV
            </Button>
          </a>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 size={32} className="animate-spin text-[var(--bz-accent)]" />
        </div>
      ) : error ? (
        <div className="flex items-center gap-3 p-4 bg-[var(--state-danger)]/10 border border-[var(--state-danger)]/30 rounded-xl text-[var(--state-danger)]">
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
