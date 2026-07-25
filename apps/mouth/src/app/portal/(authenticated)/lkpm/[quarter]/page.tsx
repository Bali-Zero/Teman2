"use client";

/**
 * Portal LKPM Draft Detail — review + approve a quarterly draft.
 *
 * WS3 slice 8 (GARUDA Day Edition, 2026-07-27): day-theme token alignment,
 * mirroring slice 5 (lkpm list, PR #3066). Masthead = copper rule + Cormorant
 * serif (--font-serif) in --tx-pure; surfaces read --bz-card / --bz-border +
 * the concept .panel shadow; status chips and validation alerts read the
 * semantic --state-* tokens (WS2 operative-light AA overrides: success 4.80 /
 * warning 4.78 / danger 5.74 / info 5.94 :1 on paper) via color-mix tints —
 * the old raw hexes (#34d399, #fbbf24, #f87171, …) were dark-only and fail
 * AA on paper. client_review keeps a distinct copper chip: 12% copper tint
 * fails AA in both themes, so it gets a hairline copper border +
 * --bz-copper-text fg (the established small-copper-chip pattern). The warm
 * approve button carries --bz-on-warm text (slice 6). No hardcoded hexes.
 */

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
import { formatIDR } from "@balizero/core/utils";

// Day card surface (GARUDA Day concept .panel): white card on warm paper,
// hairline warm border, soft navy shadow (near-invisible on dark).
const DETAIL_CARD_STYLE = {
  background: "var(--bz-card)",
  borderColor: "var(--bz-border)",
  boxShadow: "0 14px 34px rgba(22, 33, 58, 0.07)",
  backdropFilter: "blur(24px)",
} as const;

/** State-tinted panel: 8% tint bg + 30% tint border of the state token. */
function statePanelStyle(token: string): React.CSSProperties {
  return {
    background: `color-mix(in srgb, var(${token}) 8%, transparent)`,
    borderColor: `color-mix(in srgb, var(${token}) 30%, transparent)`,
  };
}

/** Status chip: 12% tint bg of the state token + state-token fg (AA-verified
 *  state fg on near-paper tints); copper chip gets a hairline border instead
 *  (12% copper tint fails AA both themes). */
function statusChipStyle(token: string): React.CSSProperties {
  return {
    background: `color-mix(in srgb, var(${token}) 12%, transparent)`,
    color: `var(${token})`,
  };
}

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

  if (isLoading) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        {/* Back + header */}
        <div
          className="h-5 w-24 rounded animate-pulse"
          style={{ background: "var(--bz-border)" }}
        />
        <section className="flex items-center gap-3">
          <div
            className="h-8 w-8 rounded-full animate-pulse"
            style={{ background: "var(--bz-border)" }}
          />
          <div className="space-y-1.5">
            <div
              className="h-6 w-48 rounded animate-pulse"
              style={{ background: "var(--bz-border)" }}
            />
            <div
              className="h-4 w-32 rounded animate-pulse"
              style={{ background: "var(--bz-border)", opacity: 0.5 }}
            />
          </div>
        </section>
        {/* Validation alerts skeleton */}
        <div
          className="rounded-xl border p-6 space-y-3 animate-pulse"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
          }}
        >
          <div
            className="h-5 w-40 rounded"
            style={{ background: "var(--bz-border)" }}
          />
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-10 rounded-lg"
              style={{ background: "var(--bz-border)", opacity: 0.4 }}
            />
          ))}
        </div>
        {/* Investment table skeleton */}
        <div
          className="rounded-xl border p-6 space-y-4 animate-pulse"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
          }}
        >
          <div
            className="h-5 w-36 rounded"
            style={{ background: "var(--bz-border)" }}
          />
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex justify-between">
                <div
                  className="h-4 w-32 rounded"
                  style={{ background: "var(--bz-border)", opacity: 0.5 }}
                />
                <div
                  className="h-4 w-24 rounded"
                  style={{ background: "var(--bz-border)", opacity: 0.5 }}
                />
              </div>
            ))}
          </div>
        </div>
        {/* Approve button skeleton */}
        <div
          className="h-12 w-full rounded-lg animate-pulse"
          style={{ background: "var(--bz-border)" }}
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
      {/* Header — day masthead: copper rule + Cormorant serif in --tx-pure */}
      <section className="flex items-center gap-3">
        <Link href="/portal/lkpm">
          <ArrowLeft
            className="w-5 h-5"
            style={{ color: "var(--bz-text-2)" }}
          />
        </Link>
        <div className="flex-1">
          <div
            aria-hidden="true"
            className="w-14 h-[3px] rounded-sm mb-3 bg-[var(--bz-copper)]"
          />
          <h1
            className="text-2xl font-semibold tracking-tight text-[var(--tx-pure)]"
            style={{ fontFamily: "var(--font-serif)" }}
          >
            {quarter} {year} — LKPM Draft
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--bz-text-2)" }}>
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
        style={DETAIL_CARD_STYLE}
      >
        <h2 className="text-lg font-semibold">Investment Realization</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ color: "var(--bz-text-2)" }}>
                <th scope="col" className="text-left py-2">
                  Category
                </th>
                <th scope="col" className="text-right py-2">
                  Domestic
                </th>
                <th scope="col" className="text-right py-2">
                  Import
                </th>
              </tr>
            </thead>
            <tbody
              className="divide-y"
              style={{ borderColor: "var(--bz-border)" }}
            >
              {/* Categories with import split per OSS schema */}
              <InvestmentRow
                label="Equipment"
                domestic={draft.realized.equipment_domestic}
                importVal={draft.realized.equipment_import}
                format={formatIDR}
              />
              <InvestmentRow
                label="Building"
                domestic={draft.realized.building_domestic}
                importVal={draft.realized.building_import}
                format={formatIDR}
              />
              <InvestmentRow
                label="Vehicle"
                domestic={draft.realized.vehicle_domestic}
                importVal={draft.realized.vehicle_import}
                format={formatIDR}
              />
              {/* Single-column categories (no import breakdown) */}
              <InvestmentRow
                label="Land"
                domestic={draft.realized.land}
                importVal={0}
                format={formatIDR}
              />
              <InvestmentRow
                label="Working Capital"
                domestic={draft.realized.working_capital}
                importVal={0}
                format={formatIDR}
              />
              <InvestmentRow
                label="Other"
                domestic={draft.realized.other}
                importVal={0}
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
      <section className="rounded-xl border p-6" style={DETAIL_CARD_STYLE}>
        <h2 className="text-lg font-semibold mb-4">Employment</h2>
        <div className="grid grid-cols-3 gap-4">
          <div
            className="p-4 rounded-lg"
            style={{ background: "var(--glass-rim)" }}
          >
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              TKI (Indonesian)
            </p>
            <p className="text-lg font-bold">{draft.employment.tki}</p>
          </div>
          <div
            className="p-4 rounded-lg"
            style={{ background: "var(--glass-rim)" }}
          >
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              TKA (Foreign)
            </p>
            <p className="text-lg font-bold">{draft.employment.tka}</p>
          </div>
          <div
            className="p-4 rounded-lg"
            style={{ background: "var(--glass-rim)" }}
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
          style={DETAIL_CARD_STYLE}
        >
          <h2 className="text-lg font-semibold mb-2">Validation Passed</h2>
          {greenAlerts.map((alert, i) => (
            <div key={i} className="flex items-center gap-2 text-sm">
              <CheckCircle
                className="w-4 h-4"
                style={{ color: "var(--state-success)" }}
              />
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
            className="px-6 py-2.5 rounded-lg text-sm font-medium flex items-center gap-2 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-copper)]"
            style={{
              background: "var(--bz-accent-warm)",
              // --bz-on-warm: white on daylight gold (4.86:1), near-black on
              // dark sand (8.43:1) — AA in both themes (slice 6 token).
              color: "var(--bz-on-warm)",
            }}
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
          style={statePanelStyle("--state-success")}
        >
          <div className="flex items-center gap-2">
            <CheckCircle
              className="w-5 h-5"
              style={{ color: "var(--state-success)" }}
            />
            <p
              className="text-sm font-medium"
              style={{ color: "var(--state-success)" }}
            >
              This report has been approved. Your team will submit it to OSS.
            </p>
          </div>
        </section>
      )}

      {draft.status === "submitted" && (
        <section
          className="rounded-lg border p-4"
          style={statePanelStyle("--state-success")}
        >
          <div className="flex items-center gap-2">
            <CheckCircle
              className="w-5 h-5"
              style={{ color: "var(--state-success)" }}
            />
            <p
              className="text-sm font-medium"
              style={{ color: "var(--state-success)" }}
            >
              This report has been submitted to OSS.
            </p>
          </div>
        </section>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  // Semantic state mapping (WS3 slice 8): statuses read the AA-verified
  // --state-* tokens as 12% self-tint chips; client_review keeps a distinct
  // copper chip — 12% copper tint fails AA in both themes, so it reads
  // --bz-copper-text on a hairline copper border (small-copper-chip pattern).
  const config: Record<string, { label: string; style: React.CSSProperties }> =
    {
      draft: { label: "Draft", style: statusChipStyle("--state-warning") },
      validated: {
        label: "Validated",
        style: statusChipStyle("--state-info"),
      },
      client_review: {
        label: "Client Review",
        style: {
          background: "transparent",
          border:
            "1px solid color-mix(in srgb, var(--bz-copper) 45%, transparent)",
          color: "var(--bz-copper-text, var(--tx-secondary))",
        },
      },
      approved: {
        label: "Approved",
        style: statusChipStyle("--state-success"),
      },
      submitted: {
        label: "Submitted",
        style: statusChipStyle("--state-success"),
      },
      archived: {
        label: "Archived",
        style: {
          background: "var(--glass-rim)",
          color: "var(--bz-text-2)",
        },
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
              background:
                "color-mix(in srgb, var(--state-danger) 8%, transparent)",
              borderColor:
                "color-mix(in srgb, var(--state-danger) 30%, transparent)",
            }
          : {
              background:
                "color-mix(in srgb, var(--state-warning) 8%, transparent)",
              borderColor:
                "color-mix(in srgb, var(--state-warning) 30%, transparent)",
            }
      }
    >
      {isRed ? (
        <AlertCircle
          className="w-4 h-4 mt-0.5"
          style={{ color: "var(--state-danger)" }}
        />
      ) : (
        <AlertTriangle
          className="w-4 h-4 mt-0.5"
          style={{ color: "var(--state-warning)" }}
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
