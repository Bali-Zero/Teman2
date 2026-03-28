"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Loader2,
  Upload,
  Download,
  Eye,
  CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { fileToBase64 } from "@/lib/utils";
import type { CompanyDocument } from "@/lib/api/crm/crm.types";

export function CompanyDocUpload({
  clientId,
  companyId,
  companyName,
  docType,
  label,
  hint,
  existingDoc,
  onUploaded,
}: {
  clientId: number;
  companyId: number;
  companyName: string;
  docType: string;
  label: string;
  hint: string;
  existingDoc?: CompanyDocument | null;
  onUploaded?: () => void;
}) {
  const [isUploading, setIsUploading] = useState(false);
  const [ocrPolling, setOcrPolling] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const ocrTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ocrAbortedRef = useRef(false);
  const onUploadedRef = useRef(onUploaded);
  onUploadedRef.current = onUploaded;

  useEffect(() => {
    ocrAbortedRef.current = false;
    return () => {
      ocrAbortedRef.current = true;
      if (ocrTimerRef.current) clearTimeout(ocrTimerRef.current);
    };
  }, []);

  const pollOcrStatus = useCallback(async () => {
    setOcrPolling(true);
    let attempts = 0;
    const poll = async () => {
      if (ocrAbortedRef.current) return;
      try {
        const status = (await api.request(
          `/api/crm/clients/${clientId}/ocr-status`,
        )) as {
          pending_ocr: number;
        };
        if (status.pending_ocr === 0 || attempts >= 10) {
          if (!ocrAbortedRef.current) {
            setOcrPolling(false);
            onUploadedRef.current?.();
          }
          return;
        }
        attempts++;
        ocrTimerRef.current = setTimeout(poll, 3000);
      } catch {
        if (!ocrAbortedRef.current) setOcrPolling(false);
      }
    };
    ocrTimerRef.current = setTimeout(poll, 2000);
  }, [clientId]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const allowedTypes = [
      "image/jpeg",
      "image/jpg",
      "image/png",
      "application/pdf",
    ];
    if (!allowedTypes.includes(file.type)) {
      toast.error("Invalid file type", {
        description: "Please upload JPG, PNG, or PDF",
      });
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      toast.error("File too large", { description: "Maximum 10MB" });
      return;
    }
    setIsUploading(true);
    try {
      const base64 = await fileToBase64(file);
      const response = (await api.post(
        `/api/crm/clients/${clientId}/documents/upload`,
        {
          file: base64,
          file_name: file.name,
          document_type: docType,
          document_category: "pma",
          mime_type: file.type,
          company_id: companyId,
        },
      )) as { success: boolean; message?: string };
      if (response.success) {
        setUploadedFile(file.name);
        toast.success(`${label} uploaded for ${companyName} — OCR in corso...`);
        pollOcrStatus();
      } else {
        toast.error("Upload failed", { description: response.message });
      }
    } catch (err) {
      toast.error("Upload failed", { description: (err as Error).message });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const hasDoc = existingDoc?.google_drive_file_id || uploadedFile;

  const docIcon: Record<string, string> = {
    akta_pendirian: "\u{1F4DC}",
    npwp: "\u{1F3DB}\uFE0F",
    nib: "\u{1F4CB}",
    company_profile: "\u{1F3E2}",
    sk_decree: "\u2696\uFE0F",
  };

  return (
    <div
      className={`rounded-xl overflow-hidden transition-all ${
        hasDoc
          ? "bg-gradient-to-br from-[var(--kbli-bg-base)] to-[var(--kbli-bg-surface)] border border-[var(--kbli-border)] shadow-sm"
          : "border border-dashed border-[var(--kbli-border)] hover:border-[var(--kbli-accent)]/40 bg-[var(--kbli-bg-base)]/50"
      }`}
    >
      {hasDoc && (
        <div className="h-1 bg-gradient-to-r from-[var(--kbli-pma-open)]/60 to-emerald-500/30" />
      )}

      <div className="p-3.5">
        <div className="flex items-start gap-3">
          <div
            className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg flex-shrink-0 ${
              hasDoc
                ? "bg-[var(--kbli-pma-open)]/10"
                : "bg-[var(--kbli-text-secondary)]/5"
            }`}
          >
            {docIcon[docType] || "\u{1F4C4}"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-[var(--kbli-text-primary)]">
                {label}
              </span>
              {hasDoc ? (
                <CheckCircle2 className="w-4 h-4 text-[var(--kbli-pma-open)] flex-shrink-0" />
              ) : (
                <span className="text-[10px] text-[var(--kbli-text-secondary)]">
                  {hint}
                </span>
              )}
            </div>

            {existingDoc?.file_name && !uploadedFile && (
              <p className="text-[11px] text-[var(--kbli-text-secondary)] truncate mt-0.5">
                {existingDoc.file_name}
              </p>
            )}
            {uploadedFile && (
              <p className="text-[11px] text-[var(--kbli-pma-open)] mt-0.5 truncate">
                {uploadedFile}
              </p>
            )}
          </div>
        </div>

        <div className="flex gap-1.5 mt-3">
          {existingDoc?.google_drive_file_id && !uploadedFile && (
            <>
              <Button
                variant="ghost"
                size="sm"
                className="gap-1.5 text-xs h-7 px-2.5 flex-1 hover:bg-[var(--kbli-accent)]/10 hover:text-[var(--kbli-accent)]"
                onClick={() => {
                  window.open(
                    `/api/documents/proxy/${existingDoc.google_drive_file_id}`,
                    "_blank",
                  );
                }}
              >
                <Eye className="w-3 h-3" />
                View
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="gap-1.5 text-xs h-7 px-2.5 flex-1 hover:bg-blue-500/10 hover:text-blue-400"
                onClick={() => {
                  window.open(
                    `/api/documents/proxy/${existingDoc.google_drive_file_id}`,
                    "_blank",
                  );
                }}
              >
                <Download className="w-3 h-3" />
                Download
              </Button>
            </>
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept=".jpg,.jpeg,.png,.pdf"
            className="hidden"
            onChange={handleUpload}
            disabled={isUploading}
          />
          <Button
            variant="outline"
            size="sm"
            className={`gap-1.5 text-xs h-7 ${hasDoc ? "px-2.5" : "w-full px-3"}`}
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading || ocrPolling}
          >
            {isUploading || ocrPolling ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <Upload className="w-3 h-3" />
            )}
            {isUploading
              ? "..."
              : ocrPolling
                ? "OCR..."
                : hasDoc
                  ? ""
                  : `Upload`}
          </Button>
        </div>
      </div>
    </div>
  );
}
