"use client";

/**
 * Portal Taxes — tax status, obligations and deadlines.
 *
 * WS3 slice 5 (GARUDA Day Edition, 2026-07-24): day-theme token alignment,
 * mirroring slice 3 (billing, PR #3055) and slice 4 (process, PR #3056).
 * Masthead = copper rule + Cormorant serif (--font-serif) in --tx-pure;
 * surfaces read --bz-elevated / --bz-card / --bz-border; deadline/status
 * state colors read the semantic --state-* tokens (WS2 operative-light AA
 * overrides: success 4.80 / warning 4.78 / danger 5.74 :1 on paper) via
 * color-mix tints; countdown chips reuse the shared <CountdownChip>;
 * copper small text reads --bz-copper-text (--tx-secondary fallback).
 * No hardcoded hexes.
 */

import React, { useEffect, useState } from "react";
import { DollarSign, Calendar, FileText } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import type { TaxOverview, TaxObligation } from "@/lib/api/portal/portal.types";
import {
  StatusBadge,
  CountdownChip,
  PortalEmptyState,
  PortalCardSkeleton,
  PortalListSkeleton,
} from "@/components/portal";
import { trackTaxDashboardViewed } from "@/lib/analytics";
import { formatIDR } from "@balizero/core/utils";

// Day card surface (GARUDA Day concept .panel): white card on warm paper,
// hairline warm border, soft navy shadow (near-invisible on dark).
const PORTAL_CARD_STYLE = {
  background: "var(--bz-elevated)",
  borderColor: "var(--bz-border)",
  boxShadow: "0 14px 34px rgba(22, 33, 58, 0.07)",
} as const;

// Inner tile well — visible on both themes (white 3% on dark, ink 6% on day).
const TILE_STYLE = { background: "var(--glass-rim)" } as const;

/** Deadline panel: 8% tint bg + 30% tint border of the state token. */
function tonePanelStyle(token: string): React.CSSProperties {
  return {
    background: `color-mix(in srgb, var(${token}) 8%, transparent)`,
    borderColor: `color-mix(in srgb, var(${token}) 30%, transparent)`,
  };
}

/** Urgency → semantic state token (honest day mapping, slice-5 brief). */
function deadlineToken(days: number): string {
  return days <= 7
    ? "--state-danger"
    : days <= 30
      ? "--state-warning"
      : "--state-success";
}

// Day masthead (GARUDA Day Edition): copper rule + Cormorant serif headline
// per concept (--font-serif, wired on <html>); Inter everywhere else.
function TaxesMasthead() {
  return (
    <section>
      <div
        aria-hidden="true"
        className="w-14 h-[3px] rounded-sm mb-4 bg-[var(--bz-copper)]"
      />
      <h1
        className="text-2xl font-semibold tracking-tight text-[var(--tx-pure)]"
        style={{ fontFamily: "var(--font-serif)" }}
      >
        Tax Overview
      </h1>
      <p className="text-sm text-[var(--tx-secondary)] mt-1">
        Your tax obligations and history
      </p>
    </section>
  );
}

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
      trackTaxDashboardViewed(data.summary.status, data.obligations.length);
    } catch (err) {
      error("Failed to load tax information", "Please try again later");
      logger.error("Failed to load portal tax data", {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <section>
          <div
            className="h-7 w-40 rounded animate-pulse"
            style={{ background: "var(--bz-border)" }}
          />
          <div
            className="h-4 w-60 rounded mt-2 animate-pulse"
            style={{ background: "var(--bz-border)", opacity: 0.5 }}
          />
        </section>
        <PortalCardSkeleton />
        <PortalListSkeleton count={3} />
      </div>
    );
  }

  if (!taxData) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <TaxesMasthead />
        <PortalEmptyState
          icon={DollarSign}
          title="No tax data available"
          description="Tax information will appear here once your company is set up."
          cta={{ label: "Message our team", href: "/portal/chat" }}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <TaxesMasthead />

      {/* Summary Card */}
      <section
        className="rounded-xl border p-6 space-y-4"
        style={PORTAL_CARD_STYLE}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <DollarSign
              className="w-5 h-5"
              style={{ color: "var(--bz-copper)" }}
            />
            <h2 className="text-lg font-semibold">Tax Status</h2>
          </div>
          <StatusBadge status={taxData.summary.status} />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 rounded-lg" style={TILE_STYLE}>
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              Total Due
            </p>
            <p className="text-lg font-bold">
              {taxData.summary.totalDue > 0
                ? formatIDR(taxData.summary.totalDue)
                : "Rp 0"}
            </p>
          </div>

          <div className="p-4 rounded-lg" style={TILE_STYLE}>
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              Next Deadline
            </p>
            {taxData.summary.nextDeadline ? (
              <div className="flex items-baseline gap-2 flex-wrap">
                <p className="text-lg font-bold">
                  {new Date(taxData.summary.nextDeadline).toLocaleDateString(
                    "en-US",
                    {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    },
                  )}
                </p>
                <CountdownChip date={taxData.summary.nextDeadline} />
              </div>
            ) : (
              <p className="text-lg font-bold">None</p>
            )}
          </div>
        </div>

        {/* Days to Deadline */}
        {taxData.summary.daysToDeadline !== null && (
          <div
            className="mt-4 p-4 rounded-lg flex items-center gap-3 border"
            style={tonePanelStyle(
              deadlineToken(taxData.summary.daysToDeadline),
            )}
          >
            <Calendar
              className="w-5 h-5"
              style={{
                color: `var(${deadlineToken(taxData.summary.daysToDeadline)})`,
              }}
            />
            <div className="flex-1">
              <div className="flex items-baseline gap-2">
                <span
                  className="text-2xl font-bold font-mono"
                  style={{
                    color: `var(${deadlineToken(taxData.summary.daysToDeadline)})`,
                  }}
                >
                  {taxData.summary.daysToDeadline}
                </span>
                <span
                  className="text-sm font-semibold"
                  style={{ color: "var(--bz-text-1)" }}
                >
                  days to deadline
                </span>
              </div>
              <p
                className="text-xs mt-0.5"
                style={{ color: "var(--bz-text-2)" }}
              >
                {taxData.summary.daysToDeadline <= 7
                  ? "Please file immediately to avoid penalties."
                  : taxData.summary.daysToDeadline <= 30
                    ? "Action required soon — we will remind you."
                    : "No immediate action required."}
              </p>
            </div>
          </div>
        )}
      </section>

      {/* Current Obligations */}
      {taxData.obligations && taxData.obligations.length > 0 && (
        <section
          className="rounded-xl border p-6 space-y-4"
          style={PORTAL_CARD_STYLE}
        >
          <div className="flex items-center gap-2">
            <FileText
              className="w-5 h-5"
              style={{ color: "var(--bz-copper)" }}
            />
            <h2 className="text-lg font-semibold">Current Obligations</h2>
          </div>

          <div className="space-y-3">
            {taxData.obligations.map((obligation) => (
              <ObligationCard
                key={obligation.id}
                obligation={obligation}
                formatCurrency={formatIDR}
              />
            ))}
          </div>
        </section>
      )}

      {/* Help Notice */}
      <section
        className="rounded-lg border p-4"
        style={{
          background: "color-mix(in srgb, var(--bz-copper) 8%, transparent)",
          borderColor: "color-mix(in srgb, var(--bz-copper) 30%, transparent)",
        }}
      >
        <p
          className="text-sm"
          style={{ color: "var(--bz-copper-text, var(--tx-secondary))" }}
        >
          Need help with your taxes? Contact your account manager or reach out
          via Chat for assistance.
        </p>
      </section>
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
  return (
    <div
      className="rounded-lg border p-4 transition-colors"
      style={{
        background: "var(--glass-rim)",
        borderColor: "var(--bz-border)",
      }}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-sm">{obligation.name}</h3>
          <p className="text-xs mt-0.5" style={{ color: "var(--bz-text-2)" }}>
            {obligation.type} • {obligation.period}
          </p>
        </div>
        <StatusBadge status={obligation.status} />
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
          {/* Chip only inside the 30-day window (previous behavior); the
              shared CountdownChip owns the state-token styling. */}
          {Math.ceil(
            (new Date(obligation.dueDate).getTime() - Date.now()) / 86400000,
          ) <= 30 && <CountdownChip date={obligation.dueDate} />}
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
