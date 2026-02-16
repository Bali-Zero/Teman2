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
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
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
        <p className="text-muted-foreground">
          Your tax obligations and history
        </p>
      </section>

      {/* Summary Card */}
      <section className="rounded-xl border bg-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-primary" />
            <h2 className="text-lg font-semibold">Tax Status</h2>
          </div>
          <StatusBadge status={taxData.summary.status} />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 rounded-lg bg-neutral-50 dark:bg-neutral-900">
            <p className="text-xs text-muted-foreground mb-1">Total Due</p>
            <p className="text-lg font-bold">
              {taxData.summary.totalDue > 0
                ? formatCurrency(taxData.summary.totalDue)
                : "Rp 0"}
            </p>
          </div>

          <div className="p-4 rounded-lg bg-neutral-50 dark:bg-neutral-900">
            <p className="text-xs text-muted-foreground mb-1">Next Deadline</p>
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
            className={cn(
              "mt-4 p-4 rounded-lg flex items-center gap-3",
              taxData.summary.daysToDeadline <= 7
                ? "bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800"
                : taxData.summary.daysToDeadline <= 30
                  ? "bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800"
                  : "bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800",
            )}
          >
            <Calendar
              className={cn(
                "w-5 h-5",
                taxData.summary.daysToDeadline <= 7
                  ? "text-red-600 dark:text-red-400"
                  : taxData.summary.daysToDeadline <= 30
                    ? "text-amber-600 dark:text-amber-400"
                    : "text-emerald-600 dark:text-emerald-400",
              )}
            />
            <div className="flex-1">
              <p className="text-sm font-semibold">
                {taxData.summary.daysToDeadline} days to deadline
              </p>
              <p className="text-xs text-muted-foreground">
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
        <section className="rounded-xl border bg-card p-6 space-y-4">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-primary" />
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
        <section className="rounded-xl border bg-card p-6 space-y-4">
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-primary" />
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
      <section className="rounded-lg border border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/20 p-4">
        <p className="text-sm text-emerald-800 dark:text-emerald-400">
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
  const config = {
    compliant: {
      icon: CheckCircle,
      label: "Compliant",
      className:
        "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
    },
    attention: {
      icon: AlertTriangle,
      label: "Attention",
      className:
        "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    },
    overdue: {
      icon: AlertTriangle,
      label: "Overdue",
      className: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    },
  };

  const { icon: Icon, label, className } = config[status];

  return (
    <div
      className={cn(
        "px-3 py-1.5 rounded-full flex items-center gap-1.5 text-xs font-medium",
        className,
      )}
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
  const getStatusColor = (status: string) => {
    switch (status) {
      case "filed":
        return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400";
      case "pending":
        return "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400";
      case "overdue":
        return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400";
      default:
        return "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-400";
    }
  };

  return (
    <div className="rounded-lg border p-4 hover:bg-muted/50 transition-colors">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-sm">{obligation.name}</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            {obligation.type} • {obligation.period}
          </p>
        </div>
        <span
          className={cn(
            "text-xs px-2 py-1 rounded-full font-medium whitespace-nowrap",
            getStatusColor(obligation.status),
          )}
        >
          {obligation.status}
        </span>
      </div>

      <div className="flex items-center justify-between pt-2 border-t">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
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
    <div className="rounded-lg border p-3 bg-neutral-50 dark:bg-neutral-900">
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{item.name}</p>
          <p className="text-xs text-muted-foreground mt-0.5">
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
            <CheckCircle className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
            <span className="text-xs text-emerald-600 dark:text-emerald-400">
              Paid
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
