"use client";

import React, { useEffect, useState } from "react";
import {
  Loader2,
  DollarSign,
  Calendar,
  AlertTriangle,
  CheckCircle,
  Clock,
  FileText,
} from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { logger } from "@/lib/logger";
import type {
  TaxOverview,
  TaxObligation,
  TaxHistoryItem,
} from "@/lib/api/portal/portal.types";

export default function TaxesPage() {
  const { error } = useToast();
  const [taxData, setTaxData] = useState<TaxOverview | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadTaxData();
  }, []);

  const loadTaxData = async () => {
    try {
      setIsLoading(true);
      const data = await api.portal.getTaxOverview();
      setTaxData(data);
    } catch (err) {
      error("Failed to load tax information", "Please try again later");
      logger.error("Failed to load portal tax data", {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2
          className="w-8 h-8 animate-spin"
          style={{ color: "var(--bz-accent-warm)" }}
        />
      </div>
    );
  }

  if (!taxData) return null;

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("id-ID", {
      style: "currency",
      currency: "IDR",
      minimumFractionDigits: 0,
    }).format(amount);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Tax Overview</h1>
        <p style={{ color: "var(--bz-text-2)" }}>
          Your tax obligations and history
        </p>
      </section>

      {/* Summary Card */}
      <section
        className="rounded-xl border p-6 space-y-4"
        style={{
          background: "rgba(30,30,35,0.7)",
          borderColor: "rgba(255,255,255,0.05)",
          backdropFilter: "blur(24px)",
        }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <DollarSign
              className="w-5 h-5"
              style={{ color: "var(--bz-accent-warm)" }}
            />
            <h2 className="text-lg font-semibold">Tax Status</h2>
          </div>
          <StatusBadge status={taxData.summary.status} />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div
            className="p-4 rounded-lg"
            style={{ background: "rgba(255,255,255,0.03)" }}
          >
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              Total Due
            </p>
            <p className="text-lg font-bold">
              {taxData.summary.totalDue > 0
                ? formatCurrency(taxData.summary.totalDue)
                : "Rp 0"}
            </p>
          </div>

          <div
            className="p-4 rounded-lg"
            style={{ background: "rgba(255,255,255,0.03)" }}
          >
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              Next Deadline
            </p>
            <p className="text-lg font-bold">
              {taxData.summary.nextDeadline
                ? new Date(taxData.summary.nextDeadline).toLocaleDateString(
                    "en-US",
                    {
                      month: "short",
                      day: "numeric",
                    },
                  )
                : "None"}
            </p>
          </div>
        </div>

        {/* Days to Deadline */}
        {taxData.summary.daysToDeadline !== null && (
          <div
            className="mt-4 p-4 rounded-lg flex items-center gap-3 border"
            style={
              taxData.summary.daysToDeadline <= 7
                ? {
                    background: "rgba(239,68,68,0.08)",
                    borderColor: "rgba(239,68,68,0.3)",
                  }
                : taxData.summary.daysToDeadline <= 30
                  ? {
                      background: "rgba(245,158,11,0.08)",
                      borderColor: "rgba(245,158,11,0.3)",
                    }
                  : {
                      background: "rgba(16,185,129,0.06)",
                      borderColor: "rgba(16,185,129,0.25)",
                    }
            }
          >
            <Calendar
              className="w-5 h-5"
              style={{
                color:
                  taxData.summary.daysToDeadline <= 7
                    ? "#f87171"
                    : taxData.summary.daysToDeadline <= 30
                      ? "#fbbf24"
                      : "#34d399",
              }}
            />
            <div className="flex-1">
              <p className="text-sm font-semibold">
                {taxData.summary.daysToDeadline} days to deadline
              </p>
              <p className="text-xs" style={{ color: "var(--bz-text-2)" }}>
                {taxData.summary.daysToDeadline <= 7
                  ? "Urgent: Please file immediately"
                  : taxData.summary.daysToDeadline <= 30
                    ? "Action required soon"
                    : "No immediate action required"}
              </p>
            </div>
          </div>
        )}
      </section>

      {/* Current Obligations */}
      {taxData.obligations && taxData.obligations.length > 0 && (
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{
            background: "rgba(30,30,35,0.7)",
            borderColor: "rgba(255,255,255,0.05)",
            backdropFilter: "blur(24px)",
          }}
        >
          <div className="flex items-center gap-2">
            <FileText
              className="w-5 h-5"
              style={{ color: "var(--bz-accent-warm)" }}
            />
            <h2 className="text-lg font-semibold">Current Obligations</h2>
          </div>

          <div className="space-y-3">
            {taxData.obligations.map((obligation) => (
              <ObligationCard
                key={obligation.id}
                obligation={obligation}
                formatCurrency={formatCurrency}
              />
            ))}
          </div>
        </section>
      )}

      {/* Tax History */}
      {taxData.history && taxData.history.length > 0 && (
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{
            background: "rgba(30,30,35,0.7)",
            borderColor: "rgba(255,255,255,0.05)",
            backdropFilter: "blur(24px)",
          }}
        >
          <div className="flex items-center gap-2">
            <Clock
              className="w-5 h-5"
              style={{ color: "var(--bz-accent-warm)" }}
            />
            <h2 className="text-lg font-semibold">Filing History</h2>
          </div>

          <div className="space-y-2">
            {taxData.history.map((item) => (
              <HistoryCard
                key={item.id}
                item={item}
                formatCurrency={formatCurrency}
              />
            ))}
          </div>
        </section>
      )}

      {/* Help Notice */}
      <section
        className="rounded-lg border p-4"
        style={{
          background: "rgba(201,169,110,0.06)",
          borderColor: "rgba(201,169,110,0.3)",
        }}
      >
        <p className="text-sm" style={{ color: "var(--bz-accent-warm)" }}>
          Need help with your taxes? Contact your account manager or reach out
          via Chat for assistance.
        </p>
      </section>
    </div>
  );
}

// Sub-components
function StatusBadge({
  status,
}: {
  status: "compliant" | "attention" | "overdue";
}) {
  const config: Record<
    string,
    { icon: React.ElementType; label: string; style: React.CSSProperties }
  > = {
    compliant: {
      icon: CheckCircle,
      label: "Compliant",
      style: { background: "rgba(16,185,129,0.12)", color: "#34d399" },
    },
    attention: {
      icon: AlertTriangle,
      label: "Attention",
      style: { background: "rgba(245,158,11,0.12)", color: "#fbbf24" },
    },
    overdue: {
      icon: AlertTriangle,
      label: "Overdue",
      style: { background: "rgba(239,68,68,0.12)", color: "#f87171" },
    },
  };

  const { icon: Icon, label, style } = config[status] ?? config.attention;

  return (
    <div
      className="px-3 py-1.5 rounded-full flex items-center gap-1.5 text-xs font-medium"
      style={style}
    >
      <Icon className="w-3.5 h-3.5" />
      {label}
    </div>
  );
}

function ObligationCard({
  obligation,
  formatCurrency,
}: {
  obligation: TaxObligation;
  formatCurrency: (amount: number) => string;
}) {
  const getStatusStyle = (status: string): React.CSSProperties => {
    switch (status) {
      case "filed":
        return { background: "rgba(16,185,129,0.12)", color: "#34d399" };
      case "pending":
        return { background: "rgba(245,158,11,0.12)", color: "#fbbf24" };
      case "overdue":
        return { background: "rgba(239,68,68,0.12)", color: "#f87171" };
      default:
        return {
          background: "rgba(255,255,255,0.05)",
          color: "var(--bz-text-2)",
        };
    }
  };

  return (
    <div
      className="rounded-lg border p-4 transition-colors"
      style={{
        background: "rgba(255,255,255,0.03)",
        borderColor: "rgba(255,255,255,0.05)",
      }}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-sm">{obligation.name}</h3>
          <p className="text-xs mt-0.5" style={{ color: "var(--bz-text-2)" }}>
            {obligation.type} • {obligation.period}
          </p>
        </div>
        <span
          className="text-xs px-2 py-1 rounded-full font-medium whitespace-nowrap"
          style={getStatusStyle(obligation.status)}
        >
          {obligation.status}
        </span>
      </div>

      <div
        className="flex items-center justify-between pt-2 border-t"
        style={{ borderColor: "var(--bz-border)" }}
      >
        <div
          className="flex items-center gap-1.5 text-xs"
          style={{ color: "var(--bz-text-2)" }}
        >
          <Calendar className="w-3.5 h-3.5" />
          Due:{" "}
          {new Date(obligation.dueDate).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </div>
        {obligation.amount && (
          <span className="text-sm font-bold">
            {formatCurrency(obligation.amount)}
          </span>
        )}
      </div>
    </div>
  );
}

function HistoryCard({
  item,
  formatCurrency,
}: {
  item: TaxHistoryItem;
  formatCurrency: (amount: number) => string;
}) {
  return (
    <div
      className="rounded-lg border p-3"
      style={{
        background: "rgba(255,255,255,0.03)",
        borderColor: "rgba(255,255,255,0.05)",
      }}
    >
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{item.name}</p>
          <p className="text-xs mt-0.5" style={{ color: "var(--bz-text-2)" }}>
            {item.period} • Filed:{" "}
            {new Date(item.filedDate).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}
          </p>
        </div>
        <div className="text-right">
          <p className="text-sm font-bold">{formatCurrency(item.amount)}</p>
          <div className="flex items-center gap-1 justify-end mt-0.5">
            <CheckCircle className="w-3 h-3" style={{ color: "#34d399" }} />
            <span className="text-xs" style={{ color: "#34d399" }}>
              Paid
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
