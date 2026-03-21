"use client";

import React, { useEffect, useState } from "react";
import {
  Loader2,
  FileText,
  Calendar,
  CheckCircle,
  AlertTriangle,
  Clock,
  ArrowRight,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import type {
  LKPMDraftSummary,
  LKPMDeadline,
} from "@/lib/api/portal/portal.types";

export default function LKPMPage() {
  const { error } = useToast();
  const [history, setHistory] = useState<LKPMDraftSummary[]>([]);
  const [deadlines, setDeadlines] = useState<LKPMDeadline[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setIsLoading(true);
      // Portal context — clientId comes from the authenticated session
      const [historyData, deadlineData] = await Promise.all([
        api.get<{ success: boolean; items: LKPMDraftSummary[] }>(
          "/api/v1/lkpm/history/me",
        ),
        api.get<{ success: boolean; deadlines: LKPMDeadline[] }>(
          "/api/v1/lkpm/deadlines",
        ),
      ]);
      setHistory(historyData.items ?? []);
      setDeadlines(deadlineData.deadlines ?? []);
    } catch (err) {
      error("Failed to load LKPM data", "Please try again later");
      logger.error("Failed to load portal LKPM data", {}, err as Error);
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

  const formatIDR = (amount: number) =>
    new Intl.NumberFormat("id-ID", {
      style: "currency",
      currency: "IDR",
      minimumFractionDigits: 0,
    }).format(amount);

  const nextDeadline = deadlines.find((d) => !d.is_overdue);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">LKPM Reports</h1>
          <p style={{ color: "var(--bz-text-2)" }}>
            Quarterly investment activity reports
          </p>
        </div>
        <Link
          href="/portal/lkpm/submit"
          className="px-4 py-2 rounded-lg text-sm font-medium text-white flex items-center gap-2"
          style={{ background: "var(--bz-accent-warm)" }}
        >
          <FileText className="w-4 h-4" />
          Submit Data
        </Link>
      </section>

      {/* Deadline Card */}
      {nextDeadline && (
        <section
          className="rounded-xl border p-6"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
          }}
        >
          <div className="flex items-center gap-2 mb-4">
            <Calendar
              className="w-5 h-5"
              style={{ color: "var(--bz-accent-warm)" }}
            />
            <h2 className="text-lg font-semibold">Next Deadline</h2>
          </div>

          <div
            className="p-4 rounded-lg flex items-center gap-3 border"
            style={
              nextDeadline.days_remaining <= 7
                ? {
                    background: "rgba(239,68,68,0.08)",
                    borderColor: "rgba(239,68,68,0.3)",
                  }
                : nextDeadline.days_remaining <= 30
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
                  nextDeadline.days_remaining <= 7
                    ? "#f87171"
                    : nextDeadline.days_remaining <= 30
                      ? "#fbbf24"
                      : "#34d399",
              }}
            />
            <div className="flex-1">
              <p className="text-sm font-semibold">
                {nextDeadline.quarter} {nextDeadline.year} —{" "}
                {nextDeadline.days_remaining} days remaining
              </p>
              <p className="text-xs" style={{ color: "var(--bz-text-2)" }}>
                Deadline:{" "}
                {new Date(nextDeadline.deadline).toLocaleDateString("en-US", {
                  month: "long",
                  day: "numeric",
                  year: "numeric",
                })}
              </p>
            </div>
          </div>
        </section>
      )}

      {/* Report History */}
      <section
        className="rounded-xl border p-6 space-y-4"
        style={{
          background: "var(--bz-card)",
          borderColor: "var(--bz-border)",
        }}
      >
        <div className="flex items-center gap-2">
          <Clock
            className="w-5 h-5"
            style={{ color: "var(--bz-accent-warm)" }}
          />
          <h2 className="text-lg font-semibold">Report History</h2>
        </div>

        {history.length === 0 ? (
          <p className="text-sm py-4" style={{ color: "var(--bz-text-2)" }}>
            No LKPM reports yet. Submit your first quarterly data to get
            started.
          </p>
        ) : (
          <div className="space-y-3">
            {history.map((report) => (
              <ReportCard
                key={report.id}
                report={report}
                formatIDR={formatIDR}
              />
            ))}
          </div>
        )}
      </section>

      {/* Help Notice */}
      <section
        className="rounded-lg border p-4"
        style={{
          background: "rgba(201,169,110,0.06)",
          borderColor: "rgba(201,169,110,0.3)",
        }}
      >
        <p className="text-sm" style={{ color: "var(--bz-accent-warm)" }}>
          LKPM reports must be submitted quarterly to OSS. Contact your account
          manager for assistance.
        </p>
      </section>
    </div>
  );
}

function ReportCard({
  report,
  formatIDR,
}: {
  report: LKPMDraftSummary;
  formatIDR: (amount: number) => string;
}) {
  const statusConfig: Record<
    string,
    { icon: React.ElementType; label: string; style: React.CSSProperties }
  > = {
    draft: {
      icon: FileText,
      label: "Draft",
      style: { background: "rgba(245,158,11,0.12)", color: "#fbbf24" },
    },
    validated: {
      icon: CheckCircle,
      label: "Validated",
      style: { background: "rgba(59,130,246,0.12)", color: "#60a5fa" },
    },
    approved: {
      icon: CheckCircle,
      label: "Approved",
      style: { background: "rgba(16,185,129,0.12)", color: "#34d399" },
    },
    submitted: {
      icon: CheckCircle,
      label: "Submitted",
      style: { background: "rgba(16,185,129,0.12)", color: "#34d399" },
    },
  };

  const {
    icon: Icon,
    label,
    style,
  } = statusConfig[report.status] ?? statusConfig.draft;

  return (
    <Link href={`/portal/lkpm/${report.quarter}?year=${report.year}`}>
      <div
        className="rounded-lg border p-4 transition-colors hover:border-[var(--bz-accent-warm)]"
        style={{
          background: "var(--bz-surface)",
          borderColor: "var(--bz-border)",
        }}
      >
        <div className="flex items-center justify-between">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold">
              {report.quarter} {report.year}
            </p>
            <p className="text-xs mt-0.5" style={{ color: "var(--bz-text-2)" }}>
              Total Realized: {formatIDR(report.realized_total)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span
              className="text-xs px-2 py-1 rounded-full font-medium flex items-center gap-1"
              style={style}
            >
              <Icon className="w-3 h-3" />
              {label}
            </span>
            <ArrowRight
              className="w-4 h-4"
              style={{ color: "var(--bz-text-2)" }}
            />
          </div>
        </div>
      </div>
    </Link>
  );
}
