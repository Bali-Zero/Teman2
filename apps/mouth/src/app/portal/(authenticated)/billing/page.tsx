"use client";

import React from "react";
import { Download, FileText, Receipt, AlertTriangle } from "lucide-react";
import { usePortalBilling } from "@/hooks/usePortalBilling";
import {
  StatusBadge,
  CountdownChip,
  PortalCardSkeleton,
} from "@/components/portal";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import type { PortalInvoice } from "@/lib/api/portal/portal.types";

const formatIDR = (amount: number) =>
  new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    minimumFractionDigits: 0,
  }).format(amount);

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
        <section>
          <h1 className="text-2xl font-bold tracking-tight">Billing</h1>
        </section>
        <section
          className="rounded-xl border p-8 text-center"
          style={{
            background: "rgba(30,30,35,0.7)",
            borderColor: "rgba(255,255,255,0.05)",
          }}
        >
          <AlertTriangle className="w-12 h-12 mx-auto mb-3 text-amber-400" />
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
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Billing</h1>
        <p style={{ color: "var(--bz-text-2)" }}>Your invoices and payments</p>
      </section>

      {/* Summary Cards */}
      {summary && summary.count > 0 && (
        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div
            className="rounded-xl border p-5"
            style={{
              background: "rgba(30,30,35,0.7)",
              borderColor: "rgba(255,255,255,0.05)",
            }}
          >
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              Total Invoiced
            </p>
            <p className="text-xl font-bold font-mono">
              {formatIDR(summary.total_invoiced)}
            </p>
            <p className="text-xs mt-1" style={{ color: "var(--bz-text-3)" }}>
              {summary.count} invoice{summary.count !== 1 ? "s" : ""}
            </p>
          </div>
          <div
            className="rounded-xl border p-5"
            style={{
              background: "rgba(30,30,35,0.7)",
              borderColor: "rgba(255,255,255,0.05)",
            }}
          >
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              Paid
            </p>
            <p
              className="text-xl font-bold font-mono"
              style={{ color: "#34d399" }}
            >
              {formatIDR(summary.total_paid)}
            </p>
          </div>
          <div
            className="rounded-xl border p-5"
            style={{
              background: "rgba(30,30,35,0.7)",
              borderColor: "rgba(255,255,255,0.05)",
            }}
          >
            <p className="text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
              Outstanding
            </p>
            <p
              className="text-xl font-bold font-mono"
              style={{
                color: summary.total_pending > 0 ? "#fbbf24" : "#34d399",
              }}
            >
              {formatIDR(summary.total_pending)}
            </p>
          </div>
        </section>
      )}

      {/* Invoice List */}
      <section className="space-y-3">
        {invoices.length === 0 ? (
          <div
            className="rounded-xl border border-dashed p-12 text-center"
            style={{
              background: "rgba(30,30,35,0.7)",
              borderColor: "rgba(255,255,255,0.05)",
            }}
          >
            <Receipt
              className="w-16 h-16 mx-auto mb-4 opacity-30"
              style={{ color: "var(--bz-text-2)" }}
            />
            <h2
              className="text-lg font-semibold"
              style={{ color: "var(--bz-text-2)" }}
            >
              No invoices yet
            </h2>
            <p
              className="text-sm mt-1"
              style={{ color: "var(--bz-text-3)" }}
            >
              Invoices will appear here when your services are billed.
            </p>
          </div>
        ) : (
          invoices.map((invoice) => (
            <div
              key={invoice.id}
              className="rounded-lg border p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
              style={{
                background: "rgba(30,30,35,0.7)",
                borderColor: "rgba(255,255,255,0.05)",
              }}
            >
              <div className="flex items-start gap-3">
                <div
                  className="p-2 rounded-md"
                  style={{ background: "rgba(201,169,110,0.12)" }}
                >
                  <FileText
                    className="w-5 h-5"
                    style={{ color: "var(--bz-accent-warm)" }}
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
                    <span className="text-lg font-bold font-mono">
                      {formatIDR(invoice.amount_idr)}
                    </span>
                    {invoice.generated_at && (
                      <CountdownChip date={invoice.generated_at} mode="age" />
                    )}
                  </div>
                  {invoice.generated_at && (
                    <p
                      className="text-xs mt-0.5"
                      style={{ color: "var(--bz-text-3)" }}
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

      {/* Help Notice */}
      <section
        className="rounded-lg border p-4"
        style={{
          background: "rgba(201,169,110,0.06)",
          borderColor: "rgba(201,169,110,0.3)",
        }}
      >
        <p className="text-sm" style={{ color: "var(--bz-accent-warm)" }}>
          For payment inquiries or to request a receipt, please contact your
          account manager or send us a message through Chat.
        </p>
      </section>
    </div>
  );
}
