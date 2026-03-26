"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, FolderOpen, Calendar, Eye, Trash2, DollarSign, ArrowUpCircle, ArrowDownCircle, MinusCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { ClientProfile } from "@/lib/api/crm/crm.types";
import { STATUS_COLORS, ALERT_COLORS } from "./constants";
import { formatCurrency } from "./utils";

const PRIORITY_STYLES: Record<string, { icon: typeof ArrowUpCircle; color: string }> = {
  high: { icon: ArrowUpCircle, color: "text-red-400" },
  medium: { icon: MinusCircle, color: "text-yellow-400" },
  low: { icon: ArrowDownCircle, color: "text-blue-400" },
};

const PAYMENT_STYLES: Record<string, string> = {
  paid: "bg-green-500/20 text-green-400",
  partial: "bg-yellow-500/20 text-yellow-400",
  unpaid: "bg-red-500/20 text-red-400",
  pending: "bg-orange-500/20 text-orange-400",
};

export function ProcessTab({
  clientId,
  practices,
  formatDate,
  onRefresh,
}: {
  clientId: number;
  practices: ClientProfile["practices"];
  formatDate: (d: string) => string;
  onRefresh: () => void;
}) {
  const router = useRouter();
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set());

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--bz-text-1)]">
          All Process
        </h3>
        <Button
          size="sm"
          className="gap-2"
          onClick={() => router.push(`/process/new?client_id=${clientId}`)}
        >
          <Plus className="w-4 h-4" />
          New Process
        </Button>
      </div>

      {practices.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[rgba(255,255,255,0.1)] bg-[rgba(26,26,30,0.5)] backdrop-blur-sm p-12 text-center shadow-xl">
          <FolderOpen className="w-12 h-12 mx-auto text-[var(--bz-text-2)] mb-3 opacity-50" />
          <p className="text-[var(--bz-text-2)]">No process yet</p>
        </div>
      ) : (
        <div className="space-y-3">
          {practices.map((practice) => (
            <div
              key={practice.id}
              className="rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] p-4 hover:border-[var(--bz-accent)]/50 transition-colors group"
            >
              <div className="flex items-center justify-between mb-2">
                <div
                  className="flex-1 cursor-pointer min-w-0"
                  onClick={() => router.push(`/process/${practice.id}`)}
                >
                  <div className="flex items-center gap-2">
                    {practice.priority && PRIORITY_STYLES[practice.priority] && (() => {
                      const { icon: PIcon, color } = PRIORITY_STYLES[practice.priority!];
                      return <PIcon className={`w-3.5 h-3.5 shrink-0 ${color}`} />;
                    })()}
                    <span className="text-sm font-medium text-[var(--bz-text-1)] truncate">
                      {practice.practice_type_name}
                    </span>
                    <span className="text-xs text-[var(--bz-text-2)] shrink-0">
                      #{practice.id}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span
                    className={`text-xs px-2 py-1 rounded-full ${
                      STATUS_COLORS[practice.status] ||
                      "bg-gray-500/20 text-gray-400"
                    }`}
                  >
                    {practice.status.replace(/_/g, " ")}
                  </span>
                  {/* View/Delete buttons - show on hover */}
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        router.push(`/process/${practice.id}`);
                      }}
                      className="p-1 rounded hover:bg-[var(--bz-card)] text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)]"
                      title="View process"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        if (deletingIds.has(practice.id)) return;
                        if (
                          !window.confirm(
                            `Delete process "${practice.practice_type_name}"?\n\nThis will mark the process as cancelled.`,
                          )
                        )
                          return;
                        setDeletingIds((prev) =>
                          new Set(prev).add(practice.id),
                        );
                        try {
                          const user = await api.getProfile();
                          await api.crm.deletePractice(practice.id, user.email);
                          toast.success("Process deleted");
                          onRefresh();
                        } catch (err) {
                          toast.error("Error", {
                            description: (err as Error).message,
                          });
                          setDeletingIds((prev) => {
                            const next = new Set(prev);
                            next.delete(practice.id);
                            return next;
                          });
                        }
                      }}
                      disabled={deletingIds.has(practice.id)}
                      className="p-1 rounded hover:bg-red-500/20 text-[var(--bz-text-2)] hover:text-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
                      title="Delete process"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-wrap mt-1">
                {practice.expiry_date && (
                  <div
                    className={`text-xs inline-flex items-center gap-1 px-2 py-0.5 rounded ${
                      ALERT_COLORS[practice.alert_color || "green"]
                    }`}
                  >
                    <Calendar className="w-3 h-3" />
                    Expires: {formatDate(practice.expiry_date)}
                  </div>
                )}
                {(practice.quoted_price || practice.actual_price) && (
                  <div className="text-xs inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[var(--bz-base)] text-[var(--bz-text-2)]">
                    <DollarSign className="w-3 h-3" />
                    {practice.actual_price
                      ? formatCurrency(practice.actual_price)
                      : formatCurrency(practice.quoted_price!)}
                  </div>
                )}
                {practice.payment_status && practice.payment_status !== "unpaid" && (
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${
                      PAYMENT_STYLES[practice.payment_status] || "bg-gray-500/20 text-gray-400"
                    }`}
                  >
                    {practice.payment_status}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
