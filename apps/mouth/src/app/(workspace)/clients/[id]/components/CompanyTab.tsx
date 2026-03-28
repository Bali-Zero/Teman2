"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Building2,
  FileText,
  Loader2,
  Upload,
  Download,
  Eye,
  CheckCircle2,
  Edit2,
  X,
  Shield,
  Network,
  Database,
  Sparkles,
  Copy,
  AlertCircle,
  FolderOpen,
  ExternalLink,
  Clock,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { fileToBase64 } from "@/lib/utils";
import type {
  ClientProfile,
  ClientDocument,
  CompanyDocument,
} from "@/lib/api/crm/crm.types";

// ============================================
// COMPANY DOC UPLOAD (internal)
// ============================================
function CompanyDocUpload({
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
          ? "bg-gradient-to-br from-[var(--bz-base)] to-[var(--bz-surface)] border border-[var(--bz-border)] shadow-sm"
          : "border border-dashed border-[var(--bz-border)] hover:border-[var(--bz-accent)]/40 bg-[var(--bz-base)]/50"
      }`}
    >
      {/* Top accent bar */}
      {hasDoc && (
        <div className="h-1 bg-gradient-to-r from-green-500/60 to-emerald-500/30" />
      )}

      <div className="p-3.5">
        <div className="flex items-start gap-3">
          <div
            className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg flex-shrink-0 ${
              hasDoc ? "bg-green-500/10" : "bg-[var(--bz-text-2)]/5"
            }`}
          >
            {docIcon[docType] || "\u{1F4C4}"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-[var(--bz-text-1)]">
                {label}
              </span>
              {hasDoc ? (
                <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0" />
              ) : (
                <span className="text-[10px] text-[var(--bz-text-2)]">
                  {hint}
                </span>
              )}
            </div>

            {/* Existing doc filename */}
            {existingDoc?.file_name && !uploadedFile && (
              <p className="text-[11px] text-[var(--bz-text-2)] truncate mt-0.5">
                {existingDoc.file_name}
              </p>
            )}
            {uploadedFile && (
              <p className="text-[11px] text-green-400 mt-0.5 truncate">
                {uploadedFile}
              </p>
            )}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex gap-1.5 mt-3">
          {existingDoc?.google_drive_file_id && !uploadedFile && (
            <>
              <Button
                variant="ghost"
                size="sm"
                className="gap-1.5 text-xs h-7 px-2.5 flex-1 hover:bg-[var(--bz-accent)]/10 hover:text-[var(--bz-accent)]"
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

// ============================================
// EDIT COMPANY MODAL (internal to CompanyTab)
// ============================================
function EditCompanyModal({
  companyId,
  initialData,
  onClose,
  onSave,
  formatDate,
}: {
  companyId: number;
  initialData: {
    company_name?: string;
    company_type?: string;
    kbli_code?: string;
    nib?: string;
    npwp_company?: string;
    registered_address?: string;
    office_address?: string;
    city?: string;
    province?: string;
    akta_pendirian_no?: string;
    akta_pendirian_date?: string;
    akta_perubahan_no?: string;
    akta_perubahan_date?: string;
    sk_menhumkam_no?: string;
    sk_menhumkam_date?: string;
    company_status?: string;
  };
  onClose: () => void;
  onSave: () => void;
  formatDate: (d: string) => string;
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [form, setForm] = useState({
    company_name: initialData.company_name || "",
    company_type: initialData.company_type || "PT PMA",
    kbli_code: initialData.kbli_code || "",
    nib: initialData.nib || "",
    npwp_company: initialData.npwp_company || "",
    registered_address:
      initialData.registered_address || initialData.office_address || "",
    city: initialData.city || "",
    province: initialData.province || "",
    akta_pendirian_no: initialData.akta_pendirian_no || "",
    akta_pendirian_date: initialData.akta_pendirian_date?.split("T")[0] || "",
    akta_perubahan_no: initialData.akta_perubahan_no || "",
    akta_perubahan_date: initialData.akta_perubahan_date?.split("T")[0] || "",
    sk_menhumkam_no: initialData.sk_menhumkam_no || "",
    sk_menhumkam_date: initialData.sk_menhumkam_date?.split("T")[0] || "",
    status: initialData.company_status || "active",
  });

  const inputClass =
    "w-full px-3 py-2 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] text-[var(--bz-text-1)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]/50";

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Only send non-empty fields
      const updates: Record<string, string> = {};
      Object.entries(form).forEach(([k, v]) => {
        if (v !== "") updates[k] = v;
      });
      await api.crm.updateCompany(companyId, updates);
      toast.success("Company updated");
      onSave();
    } catch (err) {
      toast.error("Failed to update company", {
        description: (err as Error).message,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div
        className="w-full max-w-2xl rounded-2xl overflow-hidden shadow-2xl max-h-[90vh] flex flex-col"
        style={{
          background: "var(--bz-card)",
          border: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-6 py-4 border-b"
          style={{ borderColor: "rgba(255,255,255,0.06)" }}
        >
          <h2 className="text-lg font-semibold text-[var(--bz-text-1)]">
            Edit Company
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-white/10 text-[var(--bz-text-2)] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-6 py-5 space-y-4">
          {/* Company Name + Type */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                Company Name
              </label>
              <input
                className={inputClass}
                value={form.company_name}
                onChange={(e) =>
                  setForm((f) => ({ ...f, company_name: e.target.value }))
                }
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                Type
              </label>
              <select
                className={inputClass}
                value={form.company_type}
                onChange={(e) =>
                  setForm((f) => ({ ...f, company_type: e.target.value }))
                }
              >
                <option value="PT PMA">PT PMA</option>
                <option value="PT Perorangan">PT Perorangan</option>
                <option value="CV">CV</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>

          {/* KBLI + NIB + NPWP */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                KBLI Code
              </label>
              <input
                className={inputClass}
                value={form.kbli_code}
                placeholder="e.g. 56101"
                onChange={(e) =>
                  setForm((f) => ({ ...f, kbli_code: e.target.value }))
                }
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                NIB
              </label>
              <input
                className={inputClass}
                value={form.nib}
                placeholder="Nomor Induk Berusaha"
                onChange={(e) =>
                  setForm((f) => ({ ...f, nib: e.target.value }))
                }
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                NPWP
              </label>
              <input
                className={inputClass}
                value={form.npwp_company}
                placeholder="NPWP Perusahaan"
                onChange={(e) =>
                  setForm((f) => ({ ...f, npwp_company: e.target.value }))
                }
              />
            </div>
          </div>

          {/* Address */}
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-3 sm:col-span-1">
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                Address
              </label>
              <input
                className={inputClass}
                value={form.registered_address}
                onChange={(e) =>
                  setForm((f) => ({ ...f, registered_address: e.target.value }))
                }
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                City
              </label>
              <input
                className={inputClass}
                value={form.city}
                onChange={(e) =>
                  setForm((f) => ({ ...f, city: e.target.value }))
                }
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                Province
              </label>
              <input
                className={inputClass}
                value={form.province}
                onChange={(e) =>
                  setForm((f) => ({ ...f, province: e.target.value }))
                }
              />
            </div>
          </div>

          {/* Akta Pendirian */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                Akta Pendirian No.
              </label>
              <input
                className={inputClass}
                value={form.akta_pendirian_no}
                onChange={(e) =>
                  setForm((f) => ({ ...f, akta_pendirian_no: e.target.value }))
                }
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                Akta Pendirian Date
              </label>
              <input
                type="date"
                className={inputClass}
                value={form.akta_pendirian_date}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    akta_pendirian_date: e.target.value,
                  }))
                }
              />
            </div>
          </div>

          {/* Akta Perubahan */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                Akta Perubahan No.
              </label>
              <input
                className={inputClass}
                value={form.akta_perubahan_no}
                onChange={(e) =>
                  setForm((f) => ({ ...f, akta_perubahan_no: e.target.value }))
                }
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                Akta Perubahan Date
              </label>
              <input
                type="date"
                className={inputClass}
                value={form.akta_perubahan_date}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    akta_perubahan_date: e.target.value,
                  }))
                }
              />
            </div>
          </div>

          {/* SK Kemenkumham */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                SK Kemenkumham No.
              </label>
              <input
                className={inputClass}
                value={form.sk_menhumkam_no}
                onChange={(e) =>
                  setForm((f) => ({ ...f, sk_menhumkam_no: e.target.value }))
                }
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                SK Date
              </label>
              <input
                type="date"
                className={inputClass}
                value={form.sk_menhumkam_date}
                onChange={(e) =>
                  setForm((f) => ({ ...f, sk_menhumkam_date: e.target.value }))
                }
              />
            </div>
          </div>

          {/* Status */}
          <div>
            <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
              Status
            </label>
            <select
              className={inputClass}
              value={form.status}
              onChange={(e) =>
                setForm((f) => ({ ...f, status: e.target.value }))
              }
            >
              <option value="active">Active</option>
              <option value="in_setup">In Setup</option>
              <option value="dormant">Dormant</option>
              <option value="dissolved">Dissolved</option>
            </select>
          </div>
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-end gap-3 px-6 py-4 border-t"
          style={{ borderColor: "rgba(255,255,255,0.06)" }}
        >
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg border border-[var(--bz-border)] text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)] hover:border-[var(--bz-text-2)] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-4 py-2 text-sm rounded-lg bg-[var(--bz-accent)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-2 transition-opacity"
          >
            {isSaving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================
// COMPANY TAB (main export)
// ============================================
export function CompanyTab({
  clientId,
  client,
  documents,
  formatDate,
  onRefresh,
}: {
  clientId: number;
  client: ClientProfile["client"];
  documents: ClientDocument[];
  formatDate: (d: string) => string;
  onRefresh: () => Promise<void>;
}) {
  // Company docs from client's documents (category = pma)
  const pmaDocs = documents.filter((d) => d.document_category === "pma");

  // Company data: try linked companies first, then fallback to search by name
  const [companyData, setCompanyData] = useState<{
    company_name: string;
    company_type: string;
    kbli_code?: string;
    kbli_description?: string;
    nib?: string;
    npwp_company?: string;
    akta_pendirian_no?: string;
    akta_pendirian_date?: string;
    akta_perubahan_no?: string;
    akta_perubahan_date?: string;
    sk_menhumkam_no?: string;
    sk_menhumkam_date?: string;
    registered_address?: string;
    office_address?: string;
    city?: string;
    province?: string;
    company_status?: string;
    shares_count?: number;
    share_nominal_value?: number;
    setup_progress?: number;
    company_id?: number;
  } | null>(null);

  const [associates, setAssociates] = useState<
    Array<{
      client_name?: string;
      role: string;
      ownership_percentage?: number;
      shares_count?: number;
    }>
  >([]);

  const [companyDocs, setCompanyDocs] = useState<CompanyDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isEditingCompany, setIsEditingCompany] = useState(false);
  const [reloadTrigger, setReloadTrigger] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function loadCompanyData() {
      try {
        // Step 1: Try linked companies
        const linked = await api.crm.getClientCompanies(clientId);
        if (!cancelled && linked.length > 0) {
          const co = linked[0];
          setCompanyData({
            company_name: co.company_name,
            company_type: co.company_type,
            kbli_code: co.kbli_code,
            kbli_description: co.kbli_description,
            nib: co.nib,
            npwp_company: co.npwp_company,
            akta_pendirian_no: co.akta_pendirian_no,
            akta_pendirian_date: co.akta_pendirian_date,
            akta_perubahan_no: co.akta_perubahan_no,
            akta_perubahan_date: co.akta_perubahan_date,
            sk_menhumkam_no: co.sk_menhumkam_no,
            sk_menhumkam_date: co.sk_menhumkam_date,
            registered_address: co.registered_address,
            office_address: co.office_address,
            city: co.city,
            province: co.province,
            company_status: co.company_status,
            shares_count: co.shares_count,
            share_nominal_value: co.share_nominal_value,
            setup_progress: co.setup_progress,
            company_id: co.company_id,
          });
          // Load full company data (all shareholders + docs) via company_id
          if (co.company_id) {
            api.crm
              .getCompany(co.company_id)
              .then((full) => {
                if (cancelled) return;
                if (full.associates?.length) {
                  // Group by client_name — each person may have multiple role links
                  const grouped = new Map<
                    string,
                    {
                      client_name?: string;
                      roles: string[];
                      ownership_percentage?: number;
                      shares_count?: number;
                    }
                  >();
                  for (const a of full.associates) {
                    const key = a.client_name || "unknown";
                    if (!grouped.has(key)) {
                      grouped.set(key, {
                        client_name: a.client_name,
                        roles: [],
                        ownership_percentage: a.ownership_percentage,
                        shares_count: a.shares_count,
                      });
                    }
                    const entry = grouped.get(key)!;
                    if (a.role && !entry.roles.includes(a.role)) {
                      entry.roles.push(a.role);
                    }
                    // Take the highest shares_count / ownership across links
                    if (
                      a.shares_count &&
                      (!entry.shares_count ||
                        a.shares_count > entry.shares_count)
                    ) {
                      entry.shares_count = a.shares_count;
                    }
                    if (
                      a.ownership_percentage &&
                      (!entry.ownership_percentage ||
                        a.ownership_percentage > entry.ownership_percentage)
                    ) {
                      entry.ownership_percentage = a.ownership_percentage;
                    }
                  }
                  setAssociates(
                    Array.from(grouped.values()).map((g) => ({
                      client_name: g.client_name,
                      role: g.roles.join(" / "),
                      ownership_percentage: g.ownership_percentage,
                      shares_count: g.shares_count,
                    })),
                  );
                } else {
                  // Fallback: at least show the current client
                  setAssociates([
                    {
                      client_name: client.full_name,
                      role: co.role,
                      ownership_percentage: co.ownership_percentage,
                      shares_count: co.shares_count,
                    },
                  ]);
                }
                if (full.documents?.length) setCompanyDocs(full.documents);
              })
              .catch(() => {
                // Fallback to current client only
                setAssociates([
                  {
                    client_name: client.full_name,
                    role: co.role,
                    ownership_percentage: co.ownership_percentage,
                    shares_count: co.shares_count,
                  },
                ]);
              });
          } else {
            setAssociates([
              {
                client_name: client.full_name,
                role: co.role,
                ownership_percentage: co.ownership_percentage,
                shares_count: co.shares_count,
              },
            ]);
          }
          return;
        }

        // Step 2: Fallback — search by client.company_name
        if (client.company_name) {
          const found = await api.crm.searchCompanyByName(client.company_name);
          if (!cancelled && found) {
            setCompanyData({
              company_name: found.company_name,
              company_type: found.company_type,
              kbli_code: found.kbli_code,
              kbli_description: found.kbli_description,
              nib: found.nib,
              npwp_company: found.npwp_company,
              akta_pendirian_no: found.akta_pendirian_no,
              akta_pendirian_date: found.akta_pendirian_date,
              akta_perubahan_no: found.akta_perubahan_no,
              akta_perubahan_date: found.akta_perubahan_date,
              sk_menhumkam_no: found.sk_menhumkam_no,
              sk_menhumkam_date: found.sk_menhumkam_date,
              registered_address: found.registered_address,
              office_address: found.office_address,
              city: found.city,
              province: found.province,
              company_status: found.status,
              company_id: found.id,
            });
            if (found.associates?.length) {
              const grouped2 = new Map<
                string,
                {
                  client_name?: string;
                  roles: string[];
                  ownership_percentage?: number;
                  shares_count?: number;
                }
              >();
              for (const a of found.associates) {
                const key = a.client_name || "unknown";
                if (!grouped2.has(key)) {
                  grouped2.set(key, {
                    client_name: a.client_name,
                    roles: [],
                    ownership_percentage: a.ownership_percentage,
                    shares_count: a.shares_count,
                  });
                }
                const entry = grouped2.get(key)!;
                if (a.role && !entry.roles.includes(a.role)) {
                  entry.roles.push(a.role);
                }
                if (
                  a.shares_count &&
                  (!entry.shares_count || a.shares_count > entry.shares_count)
                ) {
                  entry.shares_count = a.shares_count;
                }
                if (
                  a.ownership_percentage &&
                  (!entry.ownership_percentage ||
                    a.ownership_percentage > entry.ownership_percentage)
                ) {
                  entry.ownership_percentage = a.ownership_percentage;
                }
              }
              setAssociates(
                Array.from(grouped2.values()).map((g) => ({
                  client_name: g.client_name,
                  role: g.roles.join(" / "),
                  ownership_percentage: g.ownership_percentage,
                  shares_count: g.shares_count,
                })),
              );
            }
            // Load company documents
            api.crm
              .getCompanyDocuments(found.id)
              .then((docs) => !cancelled && setCompanyDocs(docs))
              .catch((err) => {
                toast.error("Failed to load company documents", {
                  description: (err as Error).message,
                });
              });
            return;
          }
        }

        // Step 3: No company data found — companyData stays null
      } catch (err) {
        if (!cancelled) {
          toast.error("Failed to load company data", {
            description: (err as Error).message,
          });
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    loadCompanyData();
    return () => {
      cancelled = true;
    };
  }, [clientId, client.company_name, client.full_name, reloadTrigger]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-[var(--bz-text-2)]" />
      </div>
    );
  }

  const hasCompanyName = !!client.company_name;
  const hasAnyDoc = pmaDocs.length > 0;

  if (!companyData && !hasCompanyName && !hasAnyDoc) {
    return (
      <div className="rounded-xl border border-dashed border-[rgba(255,255,255,0.1)] bg-[rgba(26,26,30,0.5)] p-12 text-center">
        <Building2 className="w-12 h-12 mx-auto text-[var(--bz-text-2)] mb-3 opacity-50" />
        <p className="text-[var(--bz-text-2)]">No company information</p>
      </div>
    );
  }

  const co = companyData;

  // Format capital
  const formatCapital = (shares?: number, nominal?: number) => {
    if (!shares) return null;
    const nom = nominal || 1000000;
    const total = shares * nom;
    if (total >= 1e12)
      return `Rp ${(total / 1e12).toFixed(total % 1e12 === 0 ? 0 : 1)}T`;
    if (total >= 1e9)
      return `Rp ${(total / 1e9).toFixed(total % 1e9 === 0 ? 0 : 1)}B`;
    if (total >= 1e6) return `Rp ${(total / 1e6).toFixed(0)}M`;
    return `Rp ${total.toLocaleString()}`;
  };

  const companyName = co?.company_name || client.company_name || "Company";
  const companyType = co?.company_type || "";
  const capital = formatCapital(co?.shares_count, co?.share_nominal_value);

  // Merge client pma docs + company docs for the strip
  const allDocs = [
    ...pmaDocs.map((d) => ({
      key: `client-${d.id}`,
      name: d.file_name || d.document_type,
      url: d.google_drive_file_url,
      type: d.document_type,
    })),
    ...companyDocs
      .filter((cd) => cd.google_drive_file_url || cd.google_drive_file_id)
      .map((cd) => ({
        key: `company-${cd.id}`,
        name: cd.file_name || cd.document_type,
        url:
          cd.google_drive_file_url ||
          (cd.google_drive_file_id
            ? `https://drive.google.com/file/d/${cd.google_drive_file_id}/view`
            : undefined),
        type: cd.document_type,
      })),
  ];

  // Determine founding year
  const foundingYear = co?.akta_pendirian_date
    ? new Date(co.akta_pendirian_date).getFullYear()
    : co?.sk_menhumkam_date
      ? new Date(co.sk_menhumkam_date).getFullYear()
      : null;

  // Address string
  const addressStr = [
    co?.registered_address || co?.office_address,
    co?.city,
    co?.province,
  ]
    .filter(Boolean)
    .join(", ");

  // Age chip helper (from Guardian loop 114)
  const getAgeChip = (dateStr?: string) => {
    if (!dateStr) return null;
    const ageDays = Math.floor(
      (Date.now() - new Date(dateStr).getTime()) / 86400000,
    );
    if (ageDays < 30) return null;
    const label =
      ageDays >= 365
        ? `${Math.floor(ageDays / 365)}y old`
        : `${Math.floor(ageDays / 30)}mo ago`;
    return (
      <span
        style={{
          background: "rgba(255,255,255,0.04)",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: "999px",
          fontSize: "0.6rem",
          fontWeight: 600,
          padding: "0.1rem 0.45rem",
          color: "rgba(148,163,184,0.9)",
          letterSpacing: "0.03em",
          display: "inline-flex",
          alignItems: "center",
          gap: "0.2rem",
        }}
      >
        <Clock className="w-2.5 h-2.5" />
        {label}
      </span>
    );
  };

  // Design tokens
  const crystalCard: React.CSSProperties = {
    background:
      "linear-gradient(160deg, rgba(235,240,255,0.03) 0%, rgba(235,240,255,0.005) 100%)",
    backdropFilter: "blur(48px)",
    WebkitBackdropFilter: "blur(48px)",
    borderRadius: "1.25rem",
    boxShadow:
      "inset 0 1px 0 0 rgba(255,255,255,0.15), inset 0 0 0 1px rgba(255,255,255,0.04), 0 20px 40px -10px rgba(0,0,0,0.5)",
  };
  const pillData: React.CSSProperties = {
    background: "rgba(255,255,255,0.02)",
    borderRadius: "0.5rem",
    padding: "0.75rem 1rem",
    boxShadow:
      "inset 0 1px 0 0 rgba(255,255,255,0.06), inset 0 0 0 1px rgba(255,255,255,0.03)",
  };

  return (
    <div className="space-y-4">
      {/* ── HEADER CARD ─────────────────────────────────────────────────── */}
      <div style={crystalCard} className="p-6">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-5">
          <div className="flex items-center gap-5">
            {/* Icon container */}
            <div
              className="w-14 h-14 rounded-[14px] flex items-center justify-center relative overflow-hidden group shrink-0"
              style={{
                background: "rgba(255,255,255,0.02)",
                boxShadow:
                  "inset 0 1px 0 0 rgba(255,255,255,0.15), inset 0 0 0 1px rgba(255,255,255,0.05)",
              }}
            >
              <Building2
                className="w-7 h-7"
                style={{
                  color: "#d4845a",
                  filter: "drop-shadow(0 0 10px rgba(212,132,90,0.5))",
                }}
              />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1
                  className="text-2xl font-bold tracking-tight"
                  style={{
                    background:
                      "linear-gradient(180deg, #ffffff 0%, #cbd5e1 100%)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                  }}
                >
                  {companyName}
                </h1>
                {co?.company_id && (
                  <button
                    onClick={() => setIsEditingCompany(true)}
                    className="shrink-0 p-1 rounded hover:bg-white/10 transition-colors"
                    style={{ color: "rgba(148,163,184,0.7)" }}
                    title="Edit company"
                  >
                    <Edit2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2 mt-1.5">
                {companyType && (
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "0.375rem",
                      padding: "0.25rem 0.6rem",
                      borderRadius: "999px",
                      fontSize: "0.65rem",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      background: "rgba(52, 211, 153, 0.08)",
                      border: "1px solid rgba(52, 211, 153, 0.2)",
                      color: "#34d399",
                    }}
                  >
                    <CheckCircle2 className="w-3 h-3" />
                    {companyType}
                  </span>
                )}
                {(co?.company_status || "active") === "active" && (
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "0.375rem",
                      padding: "0.25rem 0.6rem",
                      borderRadius: "999px",
                      fontSize: "0.65rem",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      background: "rgba(52, 211, 153, 0.08)",
                      border: "1px solid rgba(52, 211, 153, 0.2)",
                      color: "#34d399",
                    }}
                  >
                    Active
                  </span>
                )}
                {co?.company_status === "in_setup" && (
                  <span
                    style={{
                      padding: "0.25rem 0.6rem",
                      borderRadius: "999px",
                      fontSize: "0.65rem",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      background: "rgba(251,191,36,0.08)",
                      border: "1px solid rgba(251,191,36,0.2)",
                      color: "#fbbf24",
                    }}
                  >
                    In Setup
                  </span>
                )}
                {co?.nib && (
                  <span
                    className="font-mono"
                    style={{
                      fontSize: "0.65rem",
                      color: "rgba(148,163,184,0.8)",
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                    }}
                  >
                    NIB {co.nib}
                  </span>
                )}
                {co?.kbli_code && (
                  <span
                    className="font-mono"
                    style={{
                      fontSize: "0.65rem",
                      color: "#60a5fa",
                      borderBottom: "1px dashed rgba(96,165,250,0.3)",
                      paddingBottom: "1px",
                    }}
                  >
                    KBLI {co.kbli_code}
                  </span>
                )}
                {foundingYear && (
                  <span
                    style={{
                      fontSize: "0.7rem",
                      color: "rgba(100,116,139,0.9)",
                    }}
                  >
                    Est. {foundingYear}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── ZANTARA STARLIGHT AI ─────────────────────────────────────────── */}
      <div
        style={{
          ...crystalCard,
          background:
            "linear-gradient(160deg, rgba(241,245,249,0.06) 0%, rgba(138,122,103,0.04) 100%)",
          boxShadow:
            "inset 0 1px 0 0 rgba(241,245,249,0.12), inset 0 0 0 1px rgba(241,245,249,0.04), 0 20px 40px -10px rgba(0,0,0,0.4)",
          position: "relative",
          overflow: "hidden",
        }}
        className="p-5 flex gap-4 items-start"
      >
        {/* Pearl glow orb */}
        <div
          style={{
            position: "absolute",
            width: "300px",
            height: "300px",
            background:
              "radial-gradient(circle, rgba(241,245,249,0.12), transparent 65%)",
            borderRadius: "50%",
            top: "-100px",
            right: "-100px",
            filter: "blur(40px)",
            mixBlendMode: "screen",
            pointerEvents: "none",
          }}
        />
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 relative z-10"
          style={{
            background: "rgba(255,255,255,0.05)",
            boxShadow:
              "inset 0 1px 0 0 rgba(255,255,255,0.25), inset 0 0 0 1px rgba(255,255,255,0.06)",
          }}
        >
          <Sparkles
            className="w-4 h-4"
            style={{
              color: "#f4f4f5",
              filter: "drop-shadow(0 0 10px rgba(244,244,245,0.8))",
            }}
          />
        </div>
        <div className="flex-1 relative z-10">
          <h3
            className="text-[10px] font-bold uppercase tracking-[0.1em] mb-1.5"
            style={{
              background: "linear-gradient(90deg, #f4f4f5, #c9a96e)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Zantara Intelligence
          </h3>
          <p
            className="text-sm font-light leading-relaxed tracking-wide"
            style={{ color: "#f1f5f9" }}
          >
            {co?.kbli_description ? (
              <>
                Operates under{" "}
                <span className="font-medium" style={{ color: "white" }}>
                  {co.kbli_description}
                </span>
                .{" "}
              </>
            ) : null}
            {addressStr ? (
              <>
                Registered in{" "}
                <span className="font-medium" style={{ color: "white" }}>
                  {co?.city || co?.province || addressStr}
                </span>
                .{" "}
              </>
            ) : null}
            {capital ? (
              <>
                Authorized capital{" "}
                <span
                  className="font-mono text-xs"
                  style={{ color: "#c9a96e", fontWeight: 600 }}
                >
                  {capital}
                </span>
                .{" "}
              </>
            ) : null}
            {associates.length > 0 ? (
              <>
                <span style={{ color: "#d4845a", fontWeight: 500 }}>
                  {associates.length} shareholder
                  {associates.length > 1 ? "s" : ""}
                </span>{" "}
                on record.
              </>
            ) : null}
          </p>
        </div>
      </div>

      {/* ── COMPANY IDENTITY BLOCK ──────────────────────────────────────── */}
      <div
        style={{
          ...crystalCard,
          padding: "1.5rem 1.75rem",
          borderLeft: "3px solid rgba(212,132,90,0.35)",
        }}
      >
        {/* Row 1: status strip */}
        <div className="flex flex-wrap items-center gap-2 mb-4">
          {/* Status badge */}
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.3rem",
              padding: "0.2rem 0.65rem",
              borderRadius: "999px",
              fontSize: "0.65rem",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              background:
                co?.company_status === "in_setup"
                  ? "rgba(251,191,36,0.1)"
                  : "rgba(52,211,153,0.1)",
              border:
                co?.company_status === "in_setup"
                  ? "1px solid rgba(251,191,36,0.25)"
                  : "1px solid rgba(52,211,153,0.25)",
              color: co?.company_status === "in_setup" ? "#fbbf24" : "#34d399",
            }}
          >
            <CheckCircle2 className="w-2.5 h-2.5" />
            {co?.company_status
              ? co.company_status.replace(/_/g, " ")
              : "Active"}
          </span>
          {/* OSS verified */}
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.3rem",
              padding: "0.2rem 0.65rem",
              borderRadius: "999px",
              fontSize: "0.65rem",
              fontWeight: 600,
              background: "rgba(96,165,250,0.07)",
              border: "1px solid rgba(96,165,250,0.2)",
              color: "#60a5fa",
            }}
          >
            <Shield className="w-2.5 h-2.5" />
            OSS Verified
          </span>
          {/* Type */}
          {companyType && (
            <span
              style={{
                padding: "0.2rem 0.65rem",
                borderRadius: "999px",
                fontSize: "0.65rem",
                fontWeight: 600,
                background: "rgba(212,132,90,0.08)",
                border: "1px solid rgba(212,132,90,0.2)",
                color: "#d4845a",
              }}
            >
              {companyType}
            </span>
          )}
          {/* Vault count */}
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.3rem",
              marginLeft: "auto",
              padding: "0.2rem 0.65rem",
              borderRadius: "999px",
              fontSize: "0.65rem",
              fontWeight: 600,
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.07)",
              color: "rgba(148,163,184,0.7)",
            }}
          >
            <FolderOpen className="w-2.5 h-2.5" />
            {allDocs.length} docs in vault
          </span>
        </div>

        {/* Row 2: data grid — 6 cols on desktop, 3 on tablet, 2 on mobile */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-x-6 gap-y-4">
          {/* Authorized Capital */}
          {capital && (
            <div>
              <p
                className="text-[9px] uppercase tracking-widest font-bold mb-1"
                style={{ color: "rgba(100,116,139,0.9)" }}
              >
                Authorized Capital
              </p>
              <p
                className="text-base font-mono font-semibold"
                style={{ color: "#c9a96e" }}
              >
                {capital}
              </p>
              {co?.shares_count && (
                <p
                  className="text-[10px] font-mono mt-0.5"
                  style={{ color: "rgba(100,116,139,0.8)" }}
                >
                  {co.shares_count.toLocaleString()} sh ·{" "}
                  {co?.share_nominal_value
                    ? `Rp ${(co.share_nominal_value / 1e6).toFixed(0)}M/sh`
                    : ""}
                </p>
              )}
            </div>
          )}

          {/* KBLI */}
          {co?.kbli_code && (
            <div className="lg:col-span-2">
              <p
                className="text-[9px] uppercase tracking-widest font-bold mb-1"
                style={{ color: "#60a5fa" }}
              >
                Business Activity (KBLI)
              </p>
              <p
                className="font-mono text-sm font-semibold"
                style={{ color: "#60a5fa" }}
              >
                {co.kbli_code}
              </p>
              {co.kbli_description && (
                <p
                  className="text-[10px] mt-0.5 leading-tight"
                  style={{ color: "rgba(148,163,184,0.7)" }}
                >
                  {co.kbli_description.length > 55
                    ? co.kbli_description.slice(0, 55) + "…"
                    : co.kbli_description}
                </p>
              )}
            </div>
          )}

          {/* Registered city */}
          {(co?.city || co?.province) && (
            <div>
              <p
                className="text-[9px] uppercase tracking-widest font-bold mb-1"
                style={{ color: "rgba(100,116,139,0.9)" }}
              >
                Registered In
              </p>
              <p className="text-sm font-medium" style={{ color: "#f1f5f9" }}>
                {co.city || co.province}
              </p>
              {co.province && co.city && co.city !== co.province && (
                <p
                  className="text-[10px] mt-0.5"
                  style={{ color: "rgba(100,116,139,0.8)" }}
                >
                  {co.province}
                </p>
              )}
            </div>
          )}

          {/* NIB */}
          {co?.nib && (
            <div>
              <p
                className="text-[9px] uppercase tracking-widest font-bold mb-1"
                style={{ color: "rgba(100,116,139,0.9)" }}
              >
                NIB
              </p>
              <p
                className="font-mono text-xs font-medium"
                style={{ color: "#f1f5f9" }}
              >
                {co.nib}
              </p>
            </div>
          )}

          {/* Founded */}
          {foundingYear && (
            <div>
              <p
                className="text-[9px] uppercase tracking-widest font-bold mb-1"
                style={{ color: "rgba(100,116,139,0.9)" }}
              >
                Founded
              </p>
              <p className="text-sm font-medium" style={{ color: "#f1f5f9" }}>
                {foundingYear}
              </p>
              {co?.akta_pendirian_no && (
                <p
                  className="text-[10px] mt-0.5"
                  style={{ color: "rgba(100,116,139,0.8)" }}
                >
                  Akta #{co.akta_pendirian_no}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Row 3: full address if present */}
        {addressStr && (
          <div
            className="mt-4 pt-4 flex items-start gap-2"
            style={{
              borderTop: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            <p
              className="text-[9px] uppercase tracking-widest font-bold shrink-0 mt-0.5"
              style={{ color: "rgba(100,116,139,0.9)" }}
            >
              Address
            </p>
            <p
              className="text-xs ml-4 leading-relaxed"
              style={{ color: "rgba(148,163,184,0.8)" }}
            >
              {addressStr}
            </p>
          </div>
        )}
      </div>

      {/* ── MAIN GRID: Ledger + Vault (LEFT) / Registry (RIGHT) ─────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        {/* LEFT: Capital Ledger + Vault */}
        <div className="lg:col-span-8 flex flex-col gap-4">
          {/* Capital & Shareholders Ledger */}
          <div
            style={{ ...crystalCard, padding: 0 }}
            className="overflow-hidden"
          >
            <div className="px-6 pt-5 pb-4 flex items-center justify-between">
              <h2
                className="text-sm font-semibold uppercase tracking-widest"
                style={{ color: "rgba(148,163,184,0.8)" }}
              >
                Capital &amp; Shareholders Ledger
              </h2>
              <Network
                className="w-4 h-4"
                style={{ color: "rgba(100,116,139,0.7)" }}
              />
            </div>

            {/* Divider */}
            <div
              style={{
                height: "1px",
                margin: "0 1.5rem 1rem",
                background:
                  "linear-gradient(90deg, transparent, rgba(255,255,255,0.08) 50%, transparent)",
              }}
            />

            <div className="px-6 pb-6">
              {/* Capital aggregate */}
              {capital && (
                <div
                  className="flex flex-col sm:flex-row rounded-xl overflow-hidden"
                  style={{
                    background: "rgba(0,0,0,0.3)",
                    border: "1px solid rgba(255,255,255,0.06)",
                    boxShadow: "inset 0 4px 10px rgba(0,0,0,0.4)",
                  }}
                >
                  <div
                    className="flex-1 p-5 relative"
                    style={{
                      borderRight: "1px solid rgba(255,255,255,0.04)",
                    }}
                  >
                    <div
                      style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        right: 0,
                        height: "1px",
                        background:
                          "linear-gradient(90deg, transparent, rgba(212,132,90,0.3), transparent)",
                      }}
                    />
                    <p
                      className="text-[9px] uppercase tracking-widest font-bold mb-1"
                      style={{ color: "rgba(100,116,139,0.9)" }}
                    >
                      Total Paid-in Capital
                    </p>
                    <p
                      className="text-2xl font-bold font-mono tracking-tight"
                      style={{ color: "white" }}
                    >
                      {capital}
                    </p>
                  </div>
                  <div className="flex-1 p-5 grid grid-cols-2 gap-4 items-center">
                    <div>
                      <p
                        className="text-[9px] uppercase tracking-widest mb-1"
                        style={{ color: "rgba(100,116,139,0.9)" }}
                      >
                        Total Shares
                      </p>
                      <p
                        className="text-base font-mono"
                        style={{ color: "rgba(148,163,184,0.9)" }}
                      >
                        {co?.shares_count?.toLocaleString() || "—"}
                      </p>
                    </div>
                    <div>
                      <p
                        className="text-[9px] uppercase tracking-widest mb-1"
                        style={{ color: "rgba(100,116,139,0.9)" }}
                      >
                        Nominal / Sh
                      </p>
                      <p
                        className="text-base font-mono"
                        style={{ color: "rgba(148,163,184,0.9)" }}
                      >
                        {co?.share_nominal_value
                          ? `Rp ${(co.share_nominal_value / 1e6).toFixed(0)}M`
                          : "—"}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Shareholders ledger table */}
              {associates.length > 0 && (
                <div className="mt-5 w-full">
                  <div
                    className="grid grid-cols-12 text-[9px] uppercase tracking-widest font-bold pb-3 px-2"
                    style={{
                      color: "rgba(100,116,139,0.9)",
                      borderBottom: "1px solid rgba(255,255,255,0.08)",
                    }}
                  >
                    <div className="col-span-5">Shareholder Name</div>
                    <div className="col-span-3">Role</div>
                    <div className="col-span-2 text-right">Shares</div>
                    <div className="col-span-2 text-right">Equity</div>
                  </div>
                  {associates.map((a, i) => {
                    const initials = (a.client_name || client.full_name || "?")
                      .split(" ")
                      .slice(0, 2)
                      .map((w) => w[0])
                      .join("")
                      .toUpperCase();
                    return (
                      <div
                        key={i}
                        className="grid grid-cols-12 py-3 px-2 items-center text-sm"
                        style={{
                          borderBottom:
                            i < associates.length - 1
                              ? "1px solid rgba(255,255,255,0.05)"
                              : "none",
                          transition: "background 0.2s",
                        }}
                        onMouseEnter={(e) =>
                          (e.currentTarget.style.background =
                            "rgba(255,255,255,0.03)")
                        }
                        onMouseLeave={(e) =>
                          (e.currentTarget.style.background = "transparent")
                        }
                      >
                        <div className="col-span-5 flex items-center gap-2.5">
                          <div
                            className="w-6 h-6 rounded flex items-center justify-center text-[10px] font-bold shrink-0"
                            style={{
                              background: "rgba(255,255,255,0.04)",
                              border: "1px solid rgba(255,255,255,0.08)",
                              color: "rgba(148,163,184,0.9)",
                            }}
                          >
                            {initials}
                          </div>
                          <p
                            className="font-medium truncate"
                            style={{ color: "#f1f5f9" }}
                          >
                            {a.client_name || client.full_name}
                          </p>
                        </div>
                        <div className="col-span-3">
                          <span
                            className="text-[10px] uppercase tracking-wider font-bold"
                            style={{ color: "#d4845a" }}
                          >
                            {a.role || "Shareholder"}
                          </span>
                        </div>
                        <div
                          className="col-span-2 text-right font-mono text-xs"
                          style={{ color: "rgba(148,163,184,0.8)" }}
                        >
                          {a.shares_count
                            ? a.shares_count.toLocaleString()
                            : "—"}
                        </div>
                        <div className="col-span-2 flex flex-col items-end gap-1">
                          <span
                            className="font-mono text-xs font-bold"
                            style={{ color: "white" }}
                          >
                            {a.ownership_percentage
                              ? `${a.ownership_percentage}%`
                              : "—"}
                          </span>
                          {a.ownership_percentage && (
                            <div
                              className="w-12 h-0.5 rounded-full overflow-hidden"
                              style={{ background: "rgba(255,255,255,0.08)" }}
                            >
                              <div
                                className="h-full"
                                style={{
                                  width: `${a.ownership_percentage}%`,
                                  background:
                                    a.ownership_percentage >= 50
                                      ? "white"
                                      : "rgba(148,163,184,0.7)",
                                }}
                              />
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {!capital && associates.length === 0 && (
                <p
                  className="text-sm py-4"
                  style={{ color: "rgba(100,116,139,0.7)" }}
                >
                  No capital or shareholder data on record.
                </p>
              )}
            </div>
          </div>

          {/* Company Vault Directory */}
          <div style={crystalCard} className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h2
                className="text-sm font-semibold uppercase tracking-widest"
                style={{ color: "rgba(148,163,184,0.8)" }}
              >
                Company Vault Directory
              </h2>
              <Shield
                className="w-4 h-4"
                style={{ color: "rgba(100,116,139,0.7)" }}
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {allDocs.length > 0 ? (
                allDocs.slice(0, 6).map((doc) => (
                  <a
                    key={doc.key}
                    href={doc.url || "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-3 group"
                    style={pillData}
                  >
                    <FileText
                      className="w-4 h-4 shrink-0 transition-colors"
                      style={{ color: "rgba(100,116,139,0.7)" }}
                    />
                    <div className="flex-1 min-w-0 flex items-center justify-between">
                      <p
                        className="text-xs font-mono truncate transition-colors"
                        style={{ color: "rgba(148,163,184,0.8)" }}
                      >
                        {doc.name}
                      </p>
                      <div
                        className="w-1.5 h-1.5 rounded-full shrink-0 ml-2"
                        style={{ background: "#34d399" }}
                      />
                    </div>
                  </a>
                ))
              ) : (
                <div
                  className="col-span-2 flex items-center gap-3"
                  style={{ ...pillData, opacity: 0.5 }}
                >
                  <AlertCircle
                    className="w-4 h-4"
                    style={{ color: "#f87171" }}
                  />
                  <p className="text-xs font-mono" style={{ color: "#f87171" }}>
                    No documents uploaded yet
                  </p>
                </div>
              )}
              {allDocs.length > 6 && (
                <div
                  className="col-span-2 flex items-center justify-center cursor-pointer"
                  style={{
                    ...pillData,
                    border: "1px dashed rgba(255,255,255,0.15)",
                    background: "transparent",
                  }}
                >
                  <FolderOpen
                    className="w-3 h-3 mr-2"
                    style={{ color: "rgba(148,163,184,0.6)" }}
                  />
                  <p
                    className="text-[10px] font-mono uppercase tracking-widest"
                    style={{ color: "rgba(148,163,184,0.6)" }}
                  >
                    Access {allDocs.length - 6} more files
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT: Corporate Registry */}
        <div className="lg:col-span-4">
          <div style={crystalCard} className="p-5 flex flex-col gap-2.5">
            <div className="flex items-center justify-between pb-2">
              <h2
                className="text-sm font-semibold uppercase tracking-widest"
                style={{ color: "rgba(148,163,184,0.8)" }}
              >
                Registry Data
              </h2>
              <Database
                className="w-4 h-4"
                style={{ color: "rgba(100,116,139,0.7)" }}
              />
            </div>

            {/* Classification */}
            <div style={pillData}>
              <p
                className="text-[9px] uppercase tracking-widest font-bold mb-1.5"
                style={{ color: "rgba(100,116,139,0.9)" }}
              >
                Classification
              </p>
              <p className="text-sm font-medium" style={{ color: "#f1f5f9" }}>
                {companyType || "PT PMA"}{" "}
                <span
                  className="text-[10px] font-normal ml-1"
                  style={{ color: "rgba(148,163,184,0.6)" }}
                >
                  (Foreign Direct)
                </span>
              </p>
            </div>

            {/* NPWP */}
            {co?.npwp_company && (
              <div style={pillData}>
                <p
                  className="text-[9px] uppercase tracking-widest font-bold mb-1.5"
                  style={{ color: "rgba(100,116,139,0.9)" }}
                >
                  NPWP / Tax Number
                </p>
                <div className="flex justify-between items-center group">
                  <p className="font-mono text-sm" style={{ color: "#f1f5f9" }}>
                    {co.npwp_company}
                  </p>
                  <button
                    onClick={() => {
                      void navigator.clipboard.writeText(co.npwp_company!);
                      toast.success("Copied");
                    }}
                    className="opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <Copy
                      className="w-3 h-3"
                      style={{ color: "rgba(100,116,139,0.9)" }}
                    />
                  </button>
                </div>
              </div>
            )}

            {/* NIB */}
            {co?.nib && (
              <div style={pillData}>
                <p
                  className="text-[9px] uppercase tracking-widest font-bold mb-1.5"
                  style={{ color: "rgba(100,116,139,0.9)" }}
                >
                  NIB / Business Reg.
                </p>
                <div className="flex justify-between items-center group">
                  <p className="font-mono text-sm" style={{ color: "#f1f5f9" }}>
                    {co.nib}
                  </p>
                  <button
                    onClick={() => {
                      void navigator.clipboard.writeText(co.nib!);
                      toast.success("Copied");
                    }}
                    className="opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <Copy
                      className="w-3 h-3"
                      style={{ color: "rgba(100,116,139,0.9)" }}
                    />
                  </button>
                </div>
              </div>
            )}

            {/* Akta Pendirian */}
            {co?.akta_pendirian_no && (
              <div style={pillData}>
                <p
                  className="text-[9px] uppercase tracking-widest font-bold mb-1.5"
                  style={{ color: "rgba(100,116,139,0.9)" }}
                >
                  Deed of Est. (Akta)
                </p>
                <div className="flex items-center justify-between">
                  <p
                    className="text-sm font-medium font-mono"
                    style={{ color: "#f1f5f9" }}
                  >
                    #{co.akta_pendirian_no}
                    {co.akta_pendirian_date && (
                      <span
                        className="text-[10px] mx-1"
                        style={{ color: "rgba(148,163,184,0.5)" }}
                      >
                        |
                      </span>
                    )}
                    {co.akta_pendirian_date &&
                      formatDate(co.akta_pendirian_date)}
                  </p>
                  {getAgeChip(co.akta_pendirian_date)}
                </div>
              </div>
            )}

            {/* Akta Perubahan */}
            {co?.akta_perubahan_no && (
              <div style={pillData}>
                <p
                  className="text-[9px] uppercase tracking-widest font-bold mb-1.5"
                  style={{ color: "rgba(100,116,139,0.9)" }}
                >
                  Amendment (Akta Perubahan)
                </p>
                <div className="flex items-center justify-between">
                  <p
                    className="text-sm font-medium font-mono"
                    style={{ color: "#f1f5f9" }}
                  >
                    #{co.akta_perubahan_no}
                    {co.akta_perubahan_date && (
                      <span
                        className="text-[10px] mx-1"
                        style={{ color: "rgba(148,163,184,0.5)" }}
                      >
                        |
                      </span>
                    )}
                    {co.akta_perubahan_date &&
                      formatDate(co.akta_perubahan_date)}
                  </p>
                  {getAgeChip(co.akta_perubahan_date)}
                </div>
              </div>
            )}

            {/* SK Kemenkumham */}
            {co?.sk_menhumkam_no && (
              <div style={pillData}>
                <p
                  className="text-[9px] uppercase tracking-widest font-bold mb-1.5 flex justify-between items-center"
                  style={{ color: "rgba(100,116,139,0.9)" }}
                >
                  SK Kemenkumham
                  <ExternalLink
                    className="w-3 h-3 cursor-pointer hover:text-white transition-colors"
                    style={{ color: "rgba(100,116,139,0.7)" }}
                  />
                </p>
                <div className="flex items-center justify-between">
                  <p
                    className="text-[11px] font-medium font-mono break-all leading-tight"
                    style={{ color: "rgba(148,163,184,0.9)" }}
                  >
                    {co.sk_menhumkam_no}
                  </p>
                  {getAgeChip(co.sk_menhumkam_date)}
                </div>
                {co.sk_menhumkam_date && (
                  <p
                    className="text-[10px] mt-0.5"
                    style={{ color: "rgba(100,116,139,0.7)" }}
                  >
                    {formatDate(co.sk_menhumkam_date)}
                  </p>
                )}
              </div>
            )}

            {/* KBLI pill */}
            {co?.kbli_code && (
              <div
                style={{
                  ...pillData,
                  background: "rgba(96,165,250,0.03)",
                  boxShadow:
                    "inset 0 1px 0 0 rgba(96,165,250,0.08), inset 0 0 0 1px rgba(96,165,250,0.06)",
                  cursor: "pointer",
                  transition: "all 0.2s",
                }}
              >
                <p
                  className="text-[9px] uppercase tracking-widest font-bold mb-1.5"
                  style={{ color: "#60a5fa" }}
                >
                  Sector Focus
                </p>
                <p
                  className="text-sm font-medium flex items-center gap-1.5"
                  style={{ color: "#f1f5f9" }}
                >
                  <span
                    className="font-mono text-xs font-bold px-1.5 py-0.5 rounded"
                    style={{
                      background: "rgba(96,165,250,0.2)",
                      color: "#60a5fa",
                    }}
                  >
                    {co.kbli_code}
                  </span>
                  {co.kbli_description && (
                    <span className="text-xs truncate">
                      {co.kbli_description}
                    </span>
                  )}
                </p>
              </div>
            )}

            {/* Address */}
            {addressStr && (
              <div style={pillData}>
                <p
                  className="text-[9px] uppercase tracking-widest font-bold mb-1.5"
                  style={{ color: "rgba(100,116,139,0.9)" }}
                >
                  Registered Address
                </p>
                <p className="text-xs" style={{ color: "#f1f5f9" }}>
                  {addressStr}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── UPLOAD SECTION ──────────────────────────────────────────────── */}
      {co?.company_id && (
        <div style={crystalCard} className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2
              className="text-sm font-semibold uppercase tracking-widest"
              style={{ color: "rgba(148,163,184,0.8)" }}
            >
              Document Upload
            </h2>
            <Upload
              className="w-4 h-4"
              style={{ color: "rgba(100,116,139,0.7)" }}
            />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {[
              {
                docType: "akta_pendirian",
                label: "Akta Pendirian",
                hint: "PDF/JPG",
              },
              {
                docType: "sk_decree",
                label: "SK Kemenkumham",
                hint: "PDF/JPG",
              },
              {
                docType: "npwp",
                label: "NPWP Perusahaan",
                hint: "PDF/JPG",
              },
              { docType: "nib", label: "NIB", hint: "PDF/JPG" },
              {
                docType: "company_profile",
                label: "Company Profile",
                hint: "PDF",
              },
            ].map((item) => {
              const existing =
                companyDocs.find((d) => d.document_type === item.docType) ||
                null;
              return (
                <CompanyDocUpload
                  key={item.docType}
                  clientId={clientId}
                  companyId={co.company_id!}
                  companyName={companyName}
                  docType={item.docType}
                  label={item.label}
                  hint={item.hint}
                  existingDoc={existing}
                  onUploaded={() => {
                    setReloadTrigger((t) => t + 1);
                    void onRefresh();
                  }}
                />
              );
            })}
          </div>
        </div>
      )}

      {/* Edit Company Modal */}
      {isEditingCompany && co?.company_id && (
        <EditCompanyModal
          companyId={co.company_id}
          initialData={co}
          onClose={() => setIsEditingCompany(false)}
          onSave={() => {
            setIsEditingCompany(false);
            setReloadTrigger((t) => t + 1);
          }}
          formatDate={formatDate}
        />
      )}
    </div>
  );
}
