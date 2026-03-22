"use client";

import React, { useEffect, useState } from "react";
import {
  Loader2,
  CheckCircle,
  AlertTriangle,
  ArrowLeft,
  ThumbsUp,
  AlertCircle,
} from "lucide-react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import type {
  LKPMDraft,
  LKPMValidationAlert,
} from "@/lib/api/portal/portal.types";

export default function LKPMReviewPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const quarter = params.quarter as string;
  const year = Number(searchParams.get("year") || new Date().getFullYear());

  const { error, success } = useToast();
  const [draft, setDraft] = useState<LKPMDraft | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isApproving, setIsApproving] = useState(false);

  useEffect(() => {
    loadDraft();
  }, [quarter, year]);

  const loadDraft = async () => {
    try {
      setIsLoading(true);
      const data = await api.portal.getLKPMDraft(0, quarter, year); // 0 = resolve from authenticated session
      setDraft(data);
    } catch (err) {
      error("Failed to load draft", "Please try again later");
      logger.error(
        `Failed to load LKPM draft ${quarter} ${year}`,
        {},
        err as Error,
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!draft) return;
    setIsApproving(true);
    try {
      await api.portal.approveLKPMDraft(draft.id);
      success(
        "Draft approved",
        "Your LKPM report has been approved for submission",
      );
      setDraft((prev) => (prev ? { ...prev, status: "approved" } : null));
    } catch (err) {
      error("Approval failed", "Please try again");
      logger.error(`LKPM approval failed ${draft.id}`, {}, err as Error);
    } finally {
      setIsApproving(false);
    }
  };

  const formatIDR = (amount: number) =>
    new Intl.NumberFormat("id-ID", {
      style: "currency",
      currency: "IDR",
      minimumFractionDigits: 0,
    }).format(amount);

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

  if (!draft) {
    return (
      <div className="space-y-4 animate-in fade-in duration-500">
        <Link
          href="/portal/lkpm"
          className="flex items-center gap-2 text-sm"
          style={{ color: "var(--bz-text-2)" }}
        >
          <ArrowLeft className="w-4 h-4" /> Back to LKPM
        </Link>
        <p style={{ color: "var(--bz-text-2)" }}>
          No draft found for {quarter} {year}.
        </p>
      </div>
    );
  }

  const redAlerts =
    draft.validation_alerts?.filter((a) => a.severity === "red") ?? [];
  const yellowAlerts =
    draft.validation_alerts?.filter((a) => a.severity === "yellow") ?? [];
  const greenAlerts =
    draft.validation_alerts?.filter((a) => a.severity === "green") ?? [];

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section className="flex items-center gap-3">
        <Link href="/portal/lkpm">
          <ArrowLeft
            className="w-5 h-5"
            style={{ color: "var(--bz-text-2)" }}
          />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">
            {quarter} {year} — LKPM Draft
          </h1>
          <p style={{ color: "var(--bz-text-2)" }}>
            Review your data before approval
          </p>
        </div>
        <StatusBadge status={draft.status} />
      </section>

      {/* Validation Alerts */}
      {(redAlerts.length > 0 || yellowAlerts.length > 0) && (
        <section className="space-y-2">
          {redAlerts.map((alert, i) => (
            <AlertCard key={`red-${i}`} alert={alert} />
          ))}
          {yellowAlerts.map((alert, i) => (
            <AlertCard key={`yellow-${i}`} alert={alert} />
          ))}
        </section>
      )}

      {/* Investment Realization Table */}
      <section
        className="rounded-xl border p-6 space-y-4"
        style={{
          background: "rgba(30,30,35,0.7)",
          borderColor: "rgba(255,255,255,0.05)",
          backdropFilter: "blur(24px)",
        }}
      >
        <h2 className="text-lg font-semibold">Investment Realization</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ color: "var(--bz-text-2)" }}>
                <th className="text-left py-2">Category</th>
                <th className="text-right py-2">Domestic</th>
                <th className="text-right py-2">Import</th>
              </tr>
            </thead>
            <tbody
              className="divide-y"
              style={{ borderColor: "var(--bz-border)" }}
            >
              <InvestmentRow
                label="Land & Building"
                domestic={draft.realized.land_building_domestic}
                importVal={draft.realized.land_building_import}
                format={formatIDR}
              />
              <InvestmentRow
                label="Machinery"
                domestic={draft.realized.machinery_domestic}
                importVal={draft.realized.machinery_import}
                format={formatIDR}
              />
              <InvestmentRow
                label="Equipment"
                domestic={draft.realized.equipment_domestic}
                importVal={draft.realized.equipment_import}
                format={formatIDR}
              />
              <InvestmentRow
                label="Vehicles"
                domestic={draft.realized.vehicles_domestic}
                importVal={draft.realized.vehicles_import}
                format={formatIDR}
              />
              <InvestmentRow
                label="Other Fixed"
                domestic={draft.realized.other_fixed_domestic}
                importVal={draft.realized.other_fixed_import}
                format={formatIDR}
              />
              <InvestmentRow
                label="Working Capital"
                domestic={draft.realized.working_capital_domestic}
                importVal={draft.realized.working_capital_import}
                format={formatIDR}
              />
              <tr className="font-bold">
                <td className="py-2">Grand Total</td>
                <td className="py-2 text-right" colSpan={2}>
                  {formatIDR(draft.realized.grand_total)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Employment */}
      <section
        className="rounded-xl border p-6"
        style={{
          background: "rgba(30,30,35,0.7)",
          borderColor: "rgba(255,255,255,0.05)",
          backdropFilter: "blur(24px)",
        }}
      >
        <h2 className="text-lg font-semibold mb-4">Employment</h2>
        <div className="grid grid-cols-3 gap-4">
          <div
            className="p-4 rounded-lg"
            style={{ background: "rgba(255,255,255,0.03)" }}
          >
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              TKI (Indonesian)
            </p>
            <p className="text-lg font-bold">{draft.employment.tki}</p>
          </div>
          <div
            className="p-4 rounded-lg"
            style={{ background: "rgba(255,255,255,0.03)" }}
          >
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              TKA (Foreign)
            </p>
            <p className="text-lg font-bold">{draft.employment.tka}</p>
          </div>
          <div
            className="p-4 rounded-lg"
            style={{ background: "rgba(255,255,255,0.03)" }}
          >
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              Total
            </p>
            <p className="text-lg font-bold">{draft.employment.total}</p>
          </div>
        </div>
      </section>

      {/* Validation Summary */}
      {greenAlerts.length > 0 && (
        <section
          className="rounded-xl border p-6 space-y-2"
          style={{
            background: "rgba(30,30,35,0.7)",
            borderColor: "rgba(255,255,255,0.05)",
            backdropFilter: "blur(24px)",
          }}
        >
          <h2 className="text-lg font-semibold mb-2">Validation Passed</h2>
          {greenAlerts.map((alert, i) => (
            <div key={i} className="flex items-center gap-2 text-sm">
              <CheckCircle className="w-4 h-4" style={{ color: "#34d399" }} />
              <span>{alert.message}</span>
            </div>
          ))}
        </section>
      )}

      {/* Approve Button */}
      {draft.status === "validated" && (
        <div className="flex justify-end">
          <button
            onClick={handleApprove}
            disabled={isApproving || redAlerts.length > 0}
            className="px-6 py-2.5 rounded-lg text-sm font-medium text-white flex items-center gap-2 disabled:opacity-50"
            style={{ background: "var(--bz-accent-warm)" }}
          >
            {isApproving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <ThumbsUp className="w-4 h-4" />
            )}
            {isApproving ? "Approving..." : "Approve Draft"}
          </button>
        </div>
      )}

      {draft.status === "approved" && (
        <section
          className="rounded-lg border p-4"
          style={{
            background: "rgba(16,185,129,0.06)",
            borderColor: "rgba(16,185,129,0.25)",
          }}
        >
          <div className="flex items-center gap-2">
            <CheckCircle className="w-5 h-5" style={{ color: "#34d399" }} />
            <p className="text-sm font-medium" style={{ color: "#34d399" }}>
              This report has been approved. Your team will submit it to OSS.
            </p>
          </div>
        </section>
      )}

      {draft.status === "submitted" && (
        <section
          className="rounded-lg border p-4"
          style={{
            background: "rgba(16,185,129,0.06)",
            borderColor: "rgba(16,185,129,0.25)",
          }}
        >
          <div className="flex items-center gap-2">
            <CheckCircle className="w-5 h-5" style={{ color: "#34d399" }} />
            <p className="text-sm font-medium" style={{ color: "#34d399" }}>
              This report has been submitted to OSS.
            </p>
          </div>
        </section>
      )}
    </div>
  );
}

function StatusBadge({
  status,
}: {
  status: "draft" | "validated" | "approved" | "submitted";
}) {
  const config: Record<string, { label: string; style: React.CSSProperties }> =
    {
      draft: {
        label: "Draft",
        style: { background: "rgba(245,158,11,0.12)", color: "#fbbf24" },
      },
      validated: {
        label: "Validated",
        style: { background: "rgba(59,130,246,0.12)", color: "#60a5fa" },
      },
      approved: {
        label: "Approved",
        style: { background: "rgba(16,185,129,0.12)", color: "#34d399" },
      },
      submitted: {
        label: "Submitted",
        style: { background: "rgba(16,185,129,0.12)", color: "#34d399" },
      },
    };

  const { label, style } = config[status] ?? config.draft;
  return (
    <span
      className="px-3 py-1.5 rounded-full text-xs font-medium"
      style={style}
    >
      {label}
    </span>
  );
}

function AlertCard({ alert }: { alert: LKPMValidationAlert }) {
  const isRed = alert.severity === "red";
  return (
    <div
      className="rounded-lg border p-3 flex items-start gap-2"
      style={
        isRed
          ? {
              background: "rgba(239,68,68,0.08)",
              borderColor: "rgba(239,68,68,0.3)",
            }
          : {
              background: "rgba(245,158,11,0.08)",
              borderColor: "rgba(245,158,11,0.3)",
            }
      }
    >
      {isRed ? (
        <AlertCircle className="w-4 h-4 mt-0.5" style={{ color: "#f87171" }} />
      ) : (
        <AlertTriangle
          className="w-4 h-4 mt-0.5"
          style={{ color: "#fbbf24" }}
        />
      )}
      <div>
        <p className="text-sm font-medium">{alert.message}</p>
        {alert.details && (
          <p className="text-xs mt-0.5" style={{ color: "var(--bz-text-2)" }}>
            {alert.details}
          </p>
        )}
      </div>
    </div>
  );
}

function InvestmentRow({
  label,
  domestic,
  importVal,
  format,
}: {
  label: string;
  domestic: number;
  importVal: number;
  format: (n: number) => string;
}) {
  return (
    <tr>
      <td className="py-2">{label}</td>
      <td className="py-2 text-right">{format(domestic)}</td>
      <td className="py-2 text-right">{format(importVal)}</td>
    </tr>
  );
}
