"use client";

/**
 * Portal Billing — invoices and payments.
 *
 * WS3 slice 3 (GARUDA Day Edition, 2026-07-24): day-theme token alignment,
 * mirroring slice 1 (portal home, PR #3050) and slice 2 (matters, PR #3051).
 * Masthead = copper rule + Cormorant serif (--font-serif) in --tx-pure;
 * surfaces read --bz-card / --bz-border; invoice state colors read the
 * semantic --state-* tokens (WS2 operative-light AA overrides); copper small
 * text reads --bz-copper-text (armed in globals.css by slice 1;
 * --tx-secondary fallback keeps AA until that merges). Amounts render via
 * the shared <Money> component (tabular-nums). No hardcoded hexes.
 */

import React from "react";
import { Download, FileText, Receipt, AlertTriangle } from "lucide-react";
import { usePortalBilling } from "@/hooks/usePortalBilling";
import {
  StatusBadge,
  CountdownChip,
  PortalCardSkeleton,
  PortalEmptyState,
} from "@/components/portal";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import type { PortalInvoice } from "@/lib/api/portal/portal.types";
import { Money } from "@balizero/core";

// Day masthead (GARUDA Day Edition): copper rule + Cormorant serif headline
// per concept (--font-serif, wired on <html>); Inter everywhere else.
function BillingMasthead() {
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
        Billing
      </h1>
      <p className="text-sm text-[var(--tx-secondary)] mt-1">
        Your invoices and payments
      </p>
    </section>
  );
}

export default function BillingPage() {
  const { data, isLoading, isError, error } = usePortalBilling();
  const { error: toastError } = useToast();

  const handleDownloadPdf = async (invoice: PortalInvoice) => {
    try {
      const result = await api.portal.getInvoicePdfUrl(invoice.id);
      if (result.download_url) {
        window.open(result.download_url, "_blank", "noopener,noreferrer");
      }
    } catch (err) {
      toastError("Download failed", "Could not get invoice PDF");
      logger.error("Failed to get invoice PDF URL", {}, err as Error);
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
            className="h-4 w-64 rounded mt-2 animate-pulse"
            style={{ background: "var(--bz-border)", opacity: 0.5 }}
          />
        </section>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <PortalCardSkeleton key={i} className="h-24" />
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <BillingMasthead />
        <section
          className="rounded-xl border p-8 text-center"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
          }}
        >
          <AlertTriangle
            className="w-12 h-12 mx-auto mb-3"
            style={{ color: "var(--state-warning)" }}
          />
          <p>
            {error instanceof Error
              ? error.message
              : "Failed to load billing data"}
          </p>
          <Button
            onClick={() => window.location.reload()}
            variant="outline"
            className="mt-3"
          >
            Retry
          </Button>
        </section>
      </div>
    );
  }

  const summary = data?.summary;
  const invoices = data?.invoices ?? [];

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <BillingMasthead />

      {/* Summary Cards */}
      {summary && summary.count > 0 && (
        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div
            className="rounded-xl border p-5"
            style={{
              background: "var(--bz-card)",
              borderColor: "var(--bz-border)",
            }}
          >
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              Total Invoiced
            </p>
            <Money
              value={summary.total_invoiced}
              className="block text-xl font-bold font-mono"
            />
            {/* --bz-text-2 (7.64:1 on card): --bz-text-3 (#7a8aa6) computes
                3.49:1 on white cards — below the 4.5:1 small-text floor. */}
            <p className="text-xs mt-1" style={{ color: "var(--bz-text-2)" }}>
              {summary.count} invoice{summary.count !== 1 ? "s" : ""}
            </p>
          </div>
          <div
            className="rounded-xl border p-5"
            style={{
              background: "var(--bz-card)",
              borderColor: "var(--bz-border)",
            }}
          >
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              Paid
            </p>
            <Money
              value={summary.total_paid}
              className="block text-xl font-bold font-mono"
              style={{ color: "var(--state-success)" }}
            />
          </div>
          <div
            className="rounded-xl border p-5"
            style={{
              background: "var(--bz-card)",
              borderColor: "var(--bz-border)",
            }}
          >
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              Outstanding
            </p>
            <Money
              value={summary.total_pending}
              className="block text-xl font-bold font-mono"
              style={{
                color:
                  summary.total_pending > 0
                    ? "var(--state-warning)"
                    : "var(--state-success)",
              }}
            />
          </div>
        </section>
      )}

      {/* Invoice List */}
      <section className="space-y-3">
        {invoices.length === 0 ? (
          <PortalEmptyState
            icon={Receipt}
            title="No invoices yet"
            description="Invoices will appear here when your services are billed."
          />
        ) : (
          invoices.map((invoice) => (
            <div
              key={invoice.id}
              className="rounded-lg border p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
              style={{
                background: "var(--bz-card)",
                borderColor: "var(--bz-border)",
              }}
            >
              <div className="flex items-start gap-3">
                <div
                  className="p-2 rounded-md"
                  style={{
                    background:
                      "color-mix(in srgb, var(--bz-copper) 12%, transparent)",
                  }}
                >
                  <FileText
                    className="w-5 h-5"
                    style={{ color: "var(--bz-copper)" }}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-sm font-mono">
                      {invoice.invoice_number}
                    </span>
                    <StatusBadge status={invoice.payment_status} />
                  </div>
                  <p
                    className="text-xs mt-1"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    {invoice.practice_name} ({invoice.practice_category})
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <Money
                      value={invoice.amount_idr}
                      className="text-lg font-bold font-mono"
                    />
                    {invoice.generated_at && (
                      <CountdownChip date={invoice.generated_at} mode="age" />
                    )}
                  </div>
                  {invoice.generated_at && (
                    <p
                      className="text-xs mt-0.5"
                      style={{ color: "var(--bz-text-2)" }}
                    >
                      Issued:{" "}
                      {new Date(invoice.generated_at).toLocaleDateString(
                        "en-US",
                        {
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        },
                      )}
                    </p>
                  )}
                </div>
                {invoice.has_pdf && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDownloadPdf(invoice)}
                    aria-label={`Download invoice ${invoice.invoice_number}`}
                  >
                    <Download className="w-4 h-4" />
                  </Button>
                )}
              </div>
            </div>
          ))
        )}
      </section>

      {/* Help Notice — small copper text reads --bz-copper-text (slice-1
          daylight step, 5.05:1 on paper); --tx-secondary fallback keeps AA
          until that merge lands. */}
      <section
        className="rounded-lg border p-4"
        style={{
          background: "color-mix(in srgb, var(--bz-copper) 6%, transparent)",
          borderColor: "var(--bz-border-accent)",
        }}
      >
        <p
          className="text-sm"
          style={{ color: "var(--bz-copper-text, var(--tx-secondary))" }}
        >
          For payment inquiries or to request a receipt, please contact your
          account manager or send us a message through Chat.
        </p>
      </section>
    </div>
  );
}
