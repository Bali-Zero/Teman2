"use client";

// Payment proof for one invoice in portal Billing (spec
// docs/specs/payment-proof-upload.md, step 2). Renders nothing until the
// backend serves `payment_proofs`; file checks reuse the Vault limits.

import React, { useRef, useState } from "react";
import { CheckCircle2, Clock, Upload, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import type { PortalInvoice } from "@/lib/api/portal/portal.types";
import {
  paymentProofUploadError,
  paymentProofView,
} from "@/lib/portal/paymentProof";
import {
  MAX_SIZE_BYTES,
  UPLOAD_ACCEPT,
  UPLOAD_FORMAT_LABEL,
  isAllowedUploadMime,
} from "@/lib/vault/uploadLimits";

const WARN = { color: "var(--state-warning)" };
const OK = { color: "var(--state-success)" };
const BAD = { color: "var(--state-danger)" };
const LIMITS_NOTE = `${UPLOAD_FORMAT_LABEL}. Up to 10 uploads every 15 minutes; the same file name can be sent once per hour.`;

export function PaymentProofPanel({
  invoice,
  onUploaded,
}: {
  invoice: PortalInvoice;
  onUploaded: () => void;
}) {
  const view = paymentProofView(invoice);
  const inputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (view.kind === "hidden") return null;

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    setError(null);
    if (!isAllowedUploadMime(file.type)) {
      setError(`This file type is not accepted. ${UPLOAD_FORMAT_LABEL}.`);
      return;
    }
    if (file.size > MAX_SIZE_BYTES) {
      setError(`This file is too large. ${UPLOAD_FORMAT_LABEL}.`);
      return;
    }
    setIsUploading(true);
    try {
      await api.portal.uploadPaymentProof(invoice.id, file);
      onUploaded();
    } catch (err) {
      setError(paymentProofUploadError(err));
      logger.error(
        "Payment proof upload failed",
        { component: "PaymentProofPanel", itemId: String(invoice.id) },
        err instanceof Error ? err : new Error(String(err)),
      );
    } finally {
      setIsUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const canUpload = view.kind === "none" || view.kind === "rejected";

  return (
    <div
      className="mt-3 rounded-md border p-3 text-sm"
      style={{ borderColor: "var(--bz-border)" }}
    >
      {(view.kind === "received" || view.kind === "verified") && (
        <p className="flex items-center gap-2" role="status">
          {view.kind === "received" ? (
            <Clock className="w-4 h-4" aria-hidden="true" style={WARN} />
          ) : (
            <CheckCircle2 className="w-4 h-4" aria-hidden="true" style={OK} />
          )}
          {view.kind === "received"
            ? "Payment proof received — our team is checking it."
            : "Payment confirmed."}
        </p>
      )}
      {view.kind === "rejected" && (
        <div role="alert">
          <p className="flex items-center gap-2 font-medium">
            <XCircle className="w-4 h-4" aria-hidden="true" style={BAD} />
            We could not accept your payment proof.
          </p>
          {view.proof.note && (
            <p className="mt-1 text-xs" style={{ color: "var(--bz-text-2)" }}>
              Reason: {view.proof.note}
            </p>
          )}
          <p className="mt-1 text-xs" style={{ color: "var(--bz-text-2)" }}>
            Please upload a new proof below.
          </p>
        </div>
      )}

      {canUpload && (
        <div className={view.kind === "rejected" ? "mt-3" : undefined}>
          <input
            ref={inputRef}
            type="file"
            accept={UPLOAD_ACCEPT}
            className="sr-only"
            aria-label={`Upload payment proof for ${invoice.invoice_number}`}
            onChange={(e) => void handleFile(e.target.files?.[0])}
            disabled={isUploading}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="gap-2"
            disabled={isUploading}
            onClick={() => inputRef.current?.click()}
          >
            <Upload className="w-4 h-4" aria-hidden="true" />
            {isUploading ? "Uploading…" : "Upload payment proof"}
          </Button>
          <p className="mt-1 text-xs" style={{ color: "var(--bz-text-2)" }}>
            {LIMITS_NOTE}
          </p>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-2 text-xs" style={BAD}>
          {error}
        </p>
      )}
    </div>
  );
}
