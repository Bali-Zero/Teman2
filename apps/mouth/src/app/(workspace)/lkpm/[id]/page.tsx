"use client";

import React, { useEffect, useState } from "react";
import { Loader2, ArrowLeft, Printer, CheckCircle, Upload } from "lucide-react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import { lkpmApi } from "@/lib/api/workspace/lkpm.api";
import type { LKPMReadyPack } from "@/lib/api/portal/portal.types";
import { safeHtml } from "@/lib/utils/safe-html";

export default function LKPMReadyPackPage() {
  const params = useParams();
  const draftId = Number(params.id);

  const { error, success } = useToast();
  const [pack, setPack] = useState<LKPMReadyPack | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showReceiptForm, setShowReceiptForm] = useState(false);
  const [receiptNumber, setReceiptNumber] = useState("");

  useEffect(() => {
    loadReadyPack();
  }, [draftId]);

  const loadReadyPack = async () => {
    try {
      setIsLoading(true);
      const data = await lkpmApi.getReadyPack(draftId);
      setPack(data);
    } catch (err) {
      error("Failed to load ready pack", "Please try again");
      logger.error(
        `Failed to load LKPM ready pack ${draftId}`,
        {},
        err as Error,
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleMarkSubmitted = async () => {
    setIsSubmitting(true);
    try {
      await lkpmApi.markSubmitted(draftId);
      success("Marked as submitted", "LKPM report marked as submitted to OSS");
      await loadReadyPack();
    } catch (err) {
      error("Failed to mark submitted", "Please try again");
      logger.error(`LKPM mark submitted failed ${draftId}`, {}, err as Error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUploadReceipt = async () => {
    if (!receiptNumber.trim()) {
      error("Receipt number required", "Please enter the OSS receipt number");
      return;
    }
    try {
      await lkpmApi.uploadReceipt(draftId, receiptNumber.trim());
      success("Receipt uploaded", `Receipt ${receiptNumber} saved`);
      setShowReceiptForm(false);
      setReceiptNumber("");
      await loadReadyPack();
    } catch (err) {
      error("Failed to upload receipt", "Please try again");
      logger.error(`LKPM receipt upload failed ${draftId}`, {}, err as Error);
    }
  };

  const handlePrint = () => {
    const printWindow = window.open("", "_blank");
    if (printWindow && pack?.html_content) {
      // Sanitize before writing to the print window to prevent XSS
      const sanitized = safeHtml(pack.html_content).__html;
      printWindow.document.write(sanitized);
      printWindow.document.close();
      printWindow.print();
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

  if (!pack) {
    return (
      <div className="space-y-4 animate-in fade-in duration-500">
        <Link
          href="/lkpm"
          className="flex items-center gap-2 text-sm"
          style={{ color: "var(--bz-text-2)" }}
        >
          <ArrowLeft className="w-4 h-4" /> Back to LKPM
        </Link>
        <p style={{ color: "var(--bz-text-2)" }}>Ready pack not found.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/lkpm">
            <ArrowLeft
              className="w-5 h-5"
              style={{ color: "var(--bz-text-2)" }}
            />
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              {pack.company_name} — {pack.quarter} {pack.year}
            </h1>
            <p style={{ color: "var(--bz-text-2)" }}>
              Ready Pack for OSS submission
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handlePrint}
            className="px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2"
            style={{
              background: "var(--bz-surface)",
              color: "var(--bz-text-2)",
              border: "1px solid var(--bz-border)",
            }}
          >
            <Printer className="w-4 h-4" />
            Print
          </button>
          <button
            onClick={handleMarkSubmitted}
            disabled={isSubmitting}
            className="px-3 py-2 rounded-lg text-sm font-medium text-white flex items-center gap-2 disabled:opacity-50"
            style={{ background: "var(--bz-accent-warm)" }}
          >
            {isSubmitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <CheckCircle className="w-4 h-4" />
            )}
            Mark Submitted
          </button>
          <button
            onClick={() => setShowReceiptForm(!showReceiptForm)}
            className="px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2"
            style={{ background: "rgba(59,130,246,0.12)", color: "#60a5fa" }}
          >
            <Upload className="w-4 h-4" />
            Upload Receipt
          </button>
        </div>
      </section>

      {/* Receipt Form */}
      {showReceiptForm && (
        <section
          className="rounded-xl border p-4 flex items-end gap-3"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
          }}
        >
          <div className="flex-1">
            <label
              className="block text-xs mb-1"
              style={{ color: "var(--bz-text-2)" }}
            >
              OSS Receipt Number
            </label>
            <input
              type="text"
              value={receiptNumber}
              onChange={(e) => setReceiptNumber(e.target.value)}
              placeholder="e.g., LKPM-2026-Q1-001"
              className="w-full rounded-lg border px-3 py-2 text-sm"
              style={{
                background: "var(--bz-surface)",
                borderColor: "var(--bz-border)",
              }}
            />
          </div>
          <button
            onClick={handleUploadReceipt}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white"
            style={{ background: "var(--bz-accent-warm)" }}
          >
            Save
          </button>
        </section>
      )}

      {/* Validation Summary Sidebar + HTML Content */}
      <div className="grid grid-cols-[1fr_280px] gap-6">
        {/* Ready Pack HTML */}
        <section
          className="rounded-xl border overflow-hidden"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
          }}
        >
          <div
            className="p-6 prose prose-sm max-w-none"
            dangerouslySetInnerHTML={safeHtml(pack.html_content)}
          />
        </section>

        {/* Validation Summary */}
        <aside className="space-y-4">
          <div
            className="rounded-xl border p-4 space-y-3"
            style={{
              background: "var(--bz-card)",
              borderColor: "var(--bz-border)",
            }}
          >
            <h3 className="text-sm font-semibold">Validation</h3>

            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: "var(--bz-text-2)" }}>
                Status
              </span>
              <span
                className="px-2 py-0.5 rounded-full text-xs font-medium"
                style={
                  pack.validation_summary.is_valid
                    ? { background: "rgba(16,185,129,0.12)", color: "#34d399" }
                    : { background: "rgba(239,68,68,0.12)", color: "#f87171" }
                }
              >
                {pack.validation_summary.is_valid ? "Valid" : "Issues Found"}
              </span>
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ background: "#f87171" }}
                  />
                  Red
                </div>
                <span className="font-medium">
                  {pack.validation_summary.red_count}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ background: "#fbbf24" }}
                  />
                  Yellow
                </div>
                <span className="font-medium">
                  {pack.validation_summary.yellow_count}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ background: "#34d399" }}
                  />
                  Green
                </div>
                <span className="font-medium">
                  {pack.validation_summary.green_count}
                </span>
              </div>
            </div>
          </div>

          <div
            className="rounded-xl border p-4 space-y-2"
            style={{
              background: "var(--bz-card)",
              borderColor: "var(--bz-border)",
            }}
          >
            <h3 className="text-sm font-semibold">Quick Info</h3>
            <div
              className="text-xs space-y-1"
              style={{ color: "var(--bz-text-2)" }}
            >
              <p>
                <span className="font-medium">Grand Total:</span>{" "}
                {new Intl.NumberFormat("id-ID", {
                  style: "currency",
                  currency: "IDR",
                  minimumFractionDigits: 0,
                }).format(pack.realized.grand_total)}
              </p>
              <p>
                <span className="font-medium">Employees:</span>{" "}
                {pack.employment.tki} TKI + {pack.employment.tka} TKA
              </p>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
