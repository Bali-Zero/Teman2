"use client";

import React, { useState, useRef, useCallback, memo, useEffect } from "react";
import {
  User,
  Building2,
  Calendar,
  FileText,
  Upload,
  X,
  CheckCircle,
  AlertCircle,
  UserCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { fileToBase64 } from "@/lib/utils";
import type { Client, ClientCompanyLink } from "@/lib/api/crm/crm.types";
import { lkpmApi } from "@/lib/api/workspace/lkpm.api";
import type { LKPMBatchItem, LKPMReceipt } from "@/lib/api/portal/portal.types";

// ============================================
// TAX CONSULTANT DROPDOWN (Bali Zero tax team)
// ============================================
// 5 allowed values, kept in sync with backend migration 093 CHECK constraint.
const TAX_CONSULTANTS: { value: string; label: string }[] = [
  { value: "veronika.tax@balizero.com", label: "Veronika" },
  { value: "kadek.tax@balizero.com", label: "Kadek" },
  { value: "dewaayu.tax@balizero.com", label: "Dewa Ayu" },
  { value: "angel.tax@balizero.com", label: "Angel" },
  { value: "faisha.tax@balizero.com", label: "Faisha" },
];

// ============================================
// TAX TYPES AND INTERFACES
// ============================================
type TaxYear = number;
type TaxSection = "personal" | "annual" | "monthly" | "lkpm";

interface TaxDocument {
  id?: string;
  file?: File;
  fileName?: string;
  uploadedAt?: string;
  status: "pending" | "uploaded" | "verified";
}

interface PersonalTaxData {
  npwp: string;
  annualIncome: string;
  documents: {
    form1770?: TaxDocument;
    buktiPotong?: TaxDocument;
    sptTahunan?: TaxDocument;
  };
}

interface AnnualCompanyTaxData {
  companyId: string;
  companyName: string;
  npwp: string;
  documents: {
    sptTahunan?: TaxDocument;
    laporanKeuangan?: TaxDocument;
    buktiPembayaran?: TaxDocument;
    formTaxAmnesty?: TaxDocument;
  };
}

interface MonthlyReportData {
  month: string;
  year: number;
  pph21: TaxDocument;
  pph23: TaxDocument;
  ppn: TaxDocument;
  pph25: TaxDocument;
}

interface LKPMQuarterData {
  quarter: 1 | 2 | 3 | 4;
  year: number;
  realization: string;
  documents: {
    lkpmReport?: TaxDocument;
    investmentRealization?: TaxDocument;
    employeeReport?: TaxDocument;
    productionReport?: TaxDocument;
  };
}

// ============================================
// FILE UPLOAD COMPONENT
// ============================================
interface FileUploadFieldProps {
  id: string;
  label: string;
  subLabel?: string;
  file?: File;
  error?: string;
  accept?: string;
  onChange: (file: File | undefined) => void;
  onClear: () => void;
  extraButton?: React.ReactNode;
  className?: string;
}

const FileUploadField = memo(function FileUploadField({
  id,
  label,
  subLabel,
  file,
  error,
  accept = ".pdf,.jpg,.jpeg,.png",
  onChange,
  onClear,
  extraButton,
  className = "",
}: FileUploadFieldProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      if (selectedFile) {
        // Validate file size (10MB max)
        if (selectedFile.size > 10 * 1024 * 1024) {
          toast.error("File too large", {
            description: "Maximum size is 10MB",
          });
          return;
        }
        // Validate file type
        const allowedTypes = [
          "application/pdf",
          "image/jpeg",
          "image/jpg",
          "image/png",
        ];
        if (!allowedTypes.includes(selectedFile.type)) {
          toast.error("Invalid file type", {
            description: "Please upload PDF, JPG, or PNG",
          });
          return;
        }
        onChange(selectedFile);
      }
    },
    [onChange],
  );

  const handleClear = useCallback(() => {
    onClear();
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }, [onClear]);

  return (
    <div className={className}>
      <label className="block text-xs font-medium mb-1.5">
        {label}
        {subLabel && (
          <span className="text-[var(--bz-text-2)]"> {subLabel}</span>
        )}
      </label>
      <div className="flex items-center gap-2">
        <input
          ref={inputRef}
          type="file"
          id={id}
          accept={accept}
          onChange={handleChange}
          className="hidden"
        />
        <label
          htmlFor={id}
          className={`
            flex-1 px-3 py-2 rounded-lg border border-dashed cursor-pointer transition-colors text-sm truncate
            ${
              error
                ? "border-red-500 bg-red-500/10 text-red-500"
                : "border-[var(--bz-border)] bg-[var(--bz-surface)] hover:border-[var(--accent)]"
            }
          `}
        >
          {file ? file.name : `Upload ${label}`}
        </label>
        {file && (
          <>
            {extraButton}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0 text-red-500 hover:text-red-600"
              onClick={handleClear}
            >
              <X className="w-4 h-4" />
            </Button>
          </>
        )}
      </div>
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
    </div>
  );
});

// ============================================
// YEAR SELECTOR — module-scope to prevent remount
// ============================================
interface YearSelectorProps {
  selectedYear: TaxYear;
  onYearChange: (year: TaxYear) => void;
}

const YearSelector = memo(function YearSelector({
  selectedYear,
  onYearChange,
}: YearSelectorProps) {
  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: 5 }, (_, i) => currentYear - i);

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-[var(--bz-text-2)]">Year:</span>
      <div className="flex gap-1">
        {years.map((year) => (
          <Button
            key={year}
            variant={selectedYear === year ? "default" : "outline"}
            size="sm"
            className="h-8 px-3 text-xs"
            onClick={() => onYearChange(year)}
          >
            {year}
          </Button>
        ))}
      </div>
    </div>
  );
});

// ============================================
// TAX CARD — module-scope to prevent remount
// ============================================
interface TaxCardProps {
  title: string;
  subtitle: string;
  deadline: Date;
  icon: React.ElementType;
  color: string;
  section: TaxSection;
  activeSection: TaxSection;
  onClick: () => void;
}

const TaxCard = memo(function TaxCard({
  title,
  subtitle,
  deadline,
  icon: Icon,
  color,
  section,
  activeSection,
  onClick,
}: TaxCardProps) {
  const isActive = activeSection === section;
  const now = new Date();
  const daysUntilDeadline = Math.ceil(
    (deadline.getTime() - now.getTime()) / (1000 * 60 * 60 * 24),
  );
  const isOverdue = daysUntilDeadline < 0;
  const isUrgent = daysUntilDeadline >= 0 && daysUntilDeadline <= 30;

  return (
    <div
      className={`rounded-xl border bg-[var(--bz-surface)] p-5 cursor-pointer transition-all ${
        isActive
          ? "border-[var(--accent)] ring-1 ring-[var(--accent)]/30"
          : "border-[var(--bz-border)] hover:border-[var(--bz-border)]/80"
      }`}
      onClick={onClick}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className={`w-12 h-12 rounded-xl ${color} flex items-center justify-center`}
          >
            <Icon className="w-6 h-6 text-white" />
          </div>
          <div>
            <h4 className="font-semibold text-[var(--bz-text-1)]">{title}</h4>
            <p className="text-xs text-[var(--bz-text-2)]">{subtitle}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs text-[var(--bz-text-2)]">Deadline</p>
          <p
            className={`text-sm font-medium ${
              isOverdue
                ? "text-red-500"
                : isUrgent
                  ? "text-yellow-500"
                  : "text-[var(--bz-text-1)]"
            }`}
          >
            {deadline.toLocaleDateString("en-GB", {
              day: "numeric",
              month: "short",
              year: "numeric",
            })}
          </p>
          <div className="flex justify-end mt-1">
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${
                isOverdue
                  ? "bg-red-500/15 text-red-400"
                  : isUrgent
                    ? "bg-yellow-500/15 text-yellow-400"
                    : "bg-[rgba(255,255,255,0.04)] text-[var(--bz-text-2)]"
              }`}
            >
              {isOverdue
                ? `${Math.abs(daysUntilDeadline)}d overdue`
                : daysUntilDeadline === 0
                  ? "today"
                  : daysUntilDeadline <= 365
                    ? `⏰ ${daysUntilDeadline}d left`
                    : `${Math.floor(daysUntilDeadline / 30)}mo left`}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
});

// ============================================
// SIDE WORKSPACE — module-scope to prevent remount
// ============================================
interface SideWorkspaceProps {
  activeSection: TaxSection;
  selectedYear: TaxYear;
  isUploading: boolean;
  uploadError: string | null;
  onFileUpload: (section: TaxSection, docType: string, file: File) => void;
}

const DOC_TYPES: Record<TaxSection, { key: string; label: string }[]> = {
  personal: [
    { key: "form1770", label: "Form 1770" },
    { key: "buktiPotong", label: "Bukti Potong" },
    { key: "sptTahunan", label: "SPT Tahunan" },
  ],
  annual: [
    { key: "sptTahunan", label: "SPT Tahunan Badan" },
    { key: "laporanKeuangan", label: "Laporan Keuangan" },
    { key: "buktiPembayaran", label: "Bukti Pembayaran" },
    { key: "formTaxAmnesty", label: "Form Tax Amnesty" },
  ],
  monthly: [
    { key: "pph21", label: "PPH 21" },
    { key: "pph23", label: "PPH 23" },
    { key: "ppn", label: "PPN" },
    { key: "pph25", label: "PPH 25" },
  ],
  lkpm: [
    { key: "lkpmReport", label: "LKPM Report" },
    { key: "investmentRealization", label: "Investment Realization" },
    { key: "employeeReport", label: "Employee Report" },
    { key: "productionReport", label: "Production Report" },
  ],
};

const SECTION_TITLES: Record<TaxSection, string> = {
  personal: "Personal Tax Documents",
  annual: "Annual Company Documents",
  monthly: "Monthly Report Documents",
  lkpm: "LKPM Documents",
};

const SideWorkspace = memo(function SideWorkspace({
  activeSection,
  selectedYear,
  isUploading,
  uploadError,
  onFileUpload,
}: SideWorkspaceProps) {
  const [files, setFiles] = useState<Record<string, File | undefined>>({});

  const docTypes = DOC_TYPES[activeSection];
  const title = SECTION_TITLES[activeSection];

  const handleFileChange = useCallback(
    (docKey: string, file: File | undefined) => {
      setFiles((prev) => ({ ...prev, [docKey]: file }));
    },
    [],
  );

  const handleFileClear = useCallback((docKey: string) => {
    setFiles((prev) => ({ ...prev, [docKey]: undefined }));
  }, []);

  const handleUpload = useCallback(
    (docKey: string) => {
      const file = files[docKey];
      if (!file) return;
      onFileUpload(activeSection, docKey, file);
      setFiles((prev) => ({ ...prev, [docKey]: undefined }));
    },
    [files, activeSection, onFileUpload],
  );

  return (
    <div className="rounded-xl border border-[var(--bz-border)] bg-[var(--bz-surface)] p-5 sticky top-4">
      <h4 className="font-semibold text-[var(--bz-text-1)] mb-1">{title}</h4>
      <p className="text-xs text-[var(--bz-text-2)] mb-4">
        Tax year {selectedYear}
      </p>

      {uploadError && (
        <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-xs text-red-400">
          {uploadError}
        </div>
      )}

      <div className="space-y-3">
        {docTypes.map(({ key, label }) => (
          <FileUploadField
            key={key}
            id={`tax-doc-${activeSection}-${key}`}
            label={label}
            file={files[key]}
            onChange={(file) => handleFileChange(key, file)}
            onClear={() => handleFileClear(key)}
            extraButton={
              files[key] ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 px-2 text-xs gap-1"
                  onClick={() => handleUpload(key)}
                  disabled={isUploading}
                >
                  <Upload className="w-3 h-3" />
                  {isUploading ? "..." : "Upload"}
                </Button>
              ) : undefined
            }
          />
        ))}
      </div>
    </div>
  );
});

// ============================================
// TAX CONSULTANT SELECTOR
// ============================================
interface TaxConsultantSelectorProps {
  clientId: number;
  initialValue: string | null | undefined;
  onSaved?: () => Promise<void> | void;
}

const TaxConsultantSelector = memo(function TaxConsultantSelector({
  clientId,
  initialValue,
  onSaved,
}: TaxConsultantSelectorProps) {
  const [value, setValue] = useState<string>(initialValue ?? "");
  const [isSaving, setIsSaving] = useState(false);

  // Keep local state in sync if the parent's initialValue changes
  // (e.g. after an external refresh).
  useEffect(() => {
    setValue(initialValue ?? "");
  }, [initialValue]);

  const handleChange = useCallback(
    async (e: React.ChangeEvent<HTMLSelectElement>) => {
      const newValue = e.target.value;
      const previous = value;
      setValue(newValue);
      setIsSaving(true);
      try {
        const user = await api.getProfile();
        // null clears the assignment; backend accepts explicit null for this field.
        await api.crm.updateClient(
          clientId,
          { tax_consultant: newValue || null },
          user.email,
        );
        toast.success(
          newValue
            ? `Tax consultant: ${TAX_CONSULTANTS.find((c) => c.value === newValue)?.label ?? newValue}`
            : "Tax consultant cleared",
        );
        await onSaved?.();
      } catch (err) {
        setValue(previous); // revert on error
        toast.error("Failed to update tax consultant", {
          description: (err as Error).message,
        });
      } finally {
        setIsSaving(false);
      }
    },
    [clientId, value, onSaved],
  );

  return (
    <div className="flex items-center gap-3 px-4 py-3 rounded-xl border border-[var(--bz-border)] bg-[var(--bz-surface)]">
      <UserCheck className="w-4 h-4 text-[var(--bz-accent)] shrink-0" />
      <label
        htmlFor={`tax-consultant-${clientId}`}
        className="text-sm font-medium text-[var(--bz-text-1)]"
      >
        Tax Consultant
      </label>
      <select
        id={`tax-consultant-${clientId}`}
        value={value}
        onChange={handleChange}
        disabled={isSaving}
        className="flex-1 max-w-[220px] px-3 py-1.5 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-base)] text-sm text-[var(--bz-text-1)] focus:outline-none focus:border-[var(--bz-accent)] transition-colors disabled:opacity-60"
      >
        <option value="">— not assigned —</option>
        {TAX_CONSULTANTS.map((c) => (
          <option key={c.value} value={c.value}>
            {c.label}
          </option>
        ))}
      </select>
      {isSaving && (
        <span className="text-xs text-[var(--bz-text-2)]">Saving…</span>
      )}
    </div>
  );
});

// ============================================
// TAX ID BADGE
// ============================================
function TaxIdBadge({
  label,
  value,
  fallbackValue,
  fallbackLabel,
}: {
  label: string;
  value?: string;
  fallbackValue?: string;
  fallbackLabel?: string;
}) {
  if (!value && fallbackValue) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-amber-500/30 bg-amber-500/10">
        <Building2 className="w-3.5 h-3.5 text-amber-400 shrink-0" />
        <div className="min-w-0">
          <p className="text-[10px] text-amber-400/70 font-medium uppercase tracking-wide">
            {label} <span className="normal-case font-normal">via company</span>
          </p>
          <p className="text-xs font-mono text-amber-300 truncate">
            {fallbackValue}
          </p>
          {fallbackLabel && (
            <p className="text-[10px] text-amber-400/50 truncate">
              {fallbackLabel}
            </p>
          )}
        </div>
      </div>
    );
  }
  if (!value) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-dashed border-[var(--bz-border)] bg-[var(--bz-surface)]">
        <AlertCircle className="w-3.5 h-3.5 text-[var(--bz-text-2)]" />
        <span className="text-xs text-[var(--bz-text-2)]">
          {label}: not registered
        </span>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10">
      <CheckCircle className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
      <div className="min-w-0">
        <p className="text-[10px] text-emerald-400/70 font-medium uppercase tracking-wide">
          {label}
        </p>
        <p className="text-xs font-mono text-emerald-300 truncate">{value}</p>
      </div>
    </div>
  );
}

// ============================================
// LKPM QUARTER CARD — 5 tokens per card
// ============================================
function LkpmQuarterCard({
  quarter,
  report,
}: {
  quarter: string;
  report: LKPMBatchItem | null;
}) {
  const qLabels: Record<string, string> = {
    Q1: "Jan-Mar",
    Q2: "Apr-Jun",
    Q3: "Jul-Sep",
    Q4: "Oct-Dec",
  };

  if (!report) {
    return (
      <div className="text-center p-3 rounded-lg border border-[var(--bz-border)]">
        <p className="text-lg font-bold text-[var(--bz-text-1)]">{quarter}</p>
        <p className="text-[10px] text-[var(--bz-text-2)]">
          {qLabels[quarter]}
        </p>
        <p className="text-[10px] text-[var(--bz-text-2)] mt-1 italic">
          No report
        </p>
      </div>
    );
  }

  // 1. Status+OSS badge
  const statusLabel = report.oss_submitted
    ? "Submitted"
    : report.status === "approved"
      ? "Approved"
      : report.status === "validated"
        ? "Validated"
        : "Draft";
  const statusColor = report.oss_submitted
    ? "text-emerald-400"
    : report.status === "approved"
      ? "text-blue-400"
      : report.status === "validated"
        ? "text-blue-300"
        : "text-amber-400";
  const statusIcon = report.oss_submitted ? " \u2705" : "";

  // 2. Days to deadline — hide if submitted
  const daysColor =
    report.days_to_deadline != null && report.days_to_deadline <= 3
      ? "text-red-400"
      : report.days_to_deadline != null && report.days_to_deadline <= 7
        ? "text-amber-400"
        : "text-emerald-400";

  // 3. Assigned consultant — extract first name from email
  const assignedName = report.lkpm_assigned_to
    ? report.lkpm_assigned_to
        .split(".")[0]
        .replace(/^\w/, (c) => c.toUpperCase())
    : null;

  // 5. Alert health dot
  const healthDot =
    report.red_alerts > 0
      ? "\uD83D\uDD34"
      : report.yellow_alerts > 0
        ? "\uD83D\uDFE1"
        : "\uD83D\uDFE2";

  return (
    <div className="p-3 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] space-y-1">
      {/* Quarter header */}
      <div className="flex items-center justify-between">
        <p className="text-sm font-bold text-[var(--bz-text-1)]">{quarter}</p>
        <span className="text-[10px]">{healthDot}</span>
      </div>

      {/* 1. Status badge */}
      <p className={`text-[10px] font-semibold ${statusColor}`}>
        {statusLabel}
        {statusIcon}
      </p>

      {/* 2. Days to deadline */}
      {!report.oss_submitted && report.days_to_deadline != null && (
        <p className={`text-[10px] ${daysColor}`}>
          {report.days_to_deadline} days
        </p>
      )}

      {/* 3. Assigned consultant */}
      {assignedName ? (
        <p className="text-[10px] text-[var(--bz-text-2)]">{assignedName}</p>
      ) : (
        <p className="text-[10px] text-red-400">Unassigned</p>
      )}

      {/* 4. Client approved */}
      <p className="text-[10px]">
        {report.client_approved ? (
          <span className="text-emerald-400">{"\u2713"} Approved</span>
        ) : (
          <span className="text-red-400">{"\u2717"} Not approved</span>
        )}
      </p>

      {/* Open link */}
      <a
        href={`/lkpm/${report.id}`}
        className="text-[10px] text-[var(--bz-accent)] hover:underline block mt-1"
      >
        Open
      </a>
    </div>
  );
}

// ============================================
// LKPM RECEIPTS PANEL — OSS tanda terima per kegiatan usaha
// ============================================
function LkpmReceiptsPanel({
  loading,
  receiptsByCompany,
  selectedYear,
}: {
  loading: boolean;
  receiptsByCompany: Record<string, LKPMReceipt[]>;
  selectedYear: number;
}) {
  const companies = Object.entries(receiptsByCompany);
  if (loading) {
    return (
      <div className="mt-4 border-t border-[var(--bz-border)] pt-4 text-xs text-[var(--bz-text-2)]">
        Loading OSS tanda terima…
      </div>
    );
  }
  if (companies.length === 0) {
    return null; // hide section if no receipts — quarter cards already show "No report"
  }

  const totalReceipts = companies.reduce((n, [, list]) => n + list.length, 0);
  const approvedCount = companies.reduce(
    (n, [, list]) =>
      n + list.filter((r) => r.oss_status === "Disetujui").length,
    0,
  );

  return (
    <div className="mt-5 border-t border-[var(--bz-border)] pt-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold text-[var(--bz-text-1)]">
          OSS Tanda Terima — {selectedYear}
        </p>
        <p className="text-[10px] text-[var(--bz-text-2)]">
          {totalReceipts} receipt{totalReceipts === 1 ? "" : "s"}
          {approvedCount > 0 && (
            <>
              {" · "}
              <span className="text-emerald-400">{approvedCount} approved</span>
            </>
          )}
        </p>
      </div>

      {companies.map(([companyName, list]) => (
        <div key={companyName} className="space-y-1.5">
          <p className="text-[11px] font-medium text-[var(--bz-text-2)]">
            {companyName}
          </p>
          <div className="rounded-lg border border-[var(--bz-border)] overflow-hidden">
            <table className="w-full text-[11px]">
              <thead className="bg-[var(--bz-surface-2)] text-[var(--bz-text-2)]">
                <tr>
                  <th className="text-left px-2 py-1.5 font-normal">Qtr</th>
                  <th className="text-left px-2 py-1.5 font-normal">KBLI</th>
                  <th className="text-left px-2 py-1.5 font-normal">
                    Nomor Laporan
                  </th>
                  <th className="text-left px-2 py-1.5 font-normal">Stage</th>
                  <th className="text-left px-2 py-1.5 font-normal">Status</th>
                  <th className="text-left px-2 py-1.5 font-normal">Date</th>
                  <th className="text-left px-2 py-1.5 font-normal">PDF</th>
                </tr>
              </thead>
              <tbody>
                {list.map((r) => {
                  const approved = r.oss_status === "Disetujui";
                  return (
                    <tr
                      key={r.id}
                      className="border-t border-[var(--bz-border)] hover:bg-[var(--bz-surface-2)]"
                    >
                      <td className="px-2 py-1.5 text-[var(--bz-text-1)]">
                        {r.quarter ?? "—"}
                      </td>
                      <td className="px-2 py-1.5 font-mono text-[var(--bz-text-1)]">
                        {r.kbli_code ?? "—"}
                      </td>
                      <td
                        className="px-2 py-1.5 font-mono text-[var(--bz-text-2)]"
                        title={r.nomor_kegiatan_usaha}
                      >
                        {r.nomor_laporan}
                      </td>
                      <td className="px-2 py-1.5 text-[var(--bz-text-2)]">
                        {r.stage ?? "—"}
                      </td>
                      <td className="px-2 py-1.5">
                        <span
                          className={
                            approved ? "text-emerald-400" : "text-amber-400"
                          }
                        >
                          {r.oss_status ?? "—"}
                          {approved ? " \u2705" : ""}
                        </span>
                      </td>
                      <td className="px-2 py-1.5 text-[var(--bz-text-2)]">
                        {r.tanggal_diterima ?? "—"}
                      </td>
                      <td className="px-2 py-1.5">
                        {r.file_drive_url ? (
                          <a
                            href={r.file_drive_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[var(--bz-accent)] hover:underline"
                          >
                            Open
                          </a>
                        ) : (
                          <span className="text-[var(--bz-text-2)]">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}

// ============================================
// TAX TAB COMPONENT
// ============================================
export function TaxTab({
  clientId,
  formatDate,
  client,
  companyLinks,
  onRefresh,
}: {
  clientId: number;
  formatDate: (d: string) => string;
  client: Client | null;
  companyLinks?: ClientCompanyLink[];
  onRefresh?: () => Promise<void> | void;
}) {
  const [selectedYear, setSelectedYear] = useState<TaxYear>(
    new Date().getFullYear(),
  );
  const [activeSection, setActiveSection] = useState<TaxSection>("personal");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [lkpmItems, setLkpmItems] = useState<LKPMBatchItem[]>([]);
  const [lkpmLoading, setLkpmLoading] = useState(false);
  const [lkpmReceipts, setLkpmReceipts] = useState<LKPMReceipt[]>([]);
  const [lkpmReceiptsLoading, setLkpmReceiptsLoading] = useState(false);

  // Fetch LKPM reports + OSS tanda terima for this client (shareholder cascade)
  useEffect(() => {
    if (!clientId) return;
    let cancelled = false;
    setLkpmLoading(true);
    setLkpmReceiptsLoading(true);
    Promise.allSettled([
      lkpmApi.getClientHistory(clientId),
      lkpmApi.getClientReceipts(clientId),
    ])
      .then(([histRes, recRes]) => {
        if (cancelled) return;
        setLkpmItems(histRes.status === "fulfilled" ? histRes.value.items : []);
        setLkpmReceipts(
          recRes.status === "fulfilled" ? recRes.value.items : [],
        );
      })
      .finally(() => {
        if (!cancelled) {
          setLkpmLoading(false);
          setLkpmReceiptsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  // Group receipts by company for the selected year
  const receiptsByCompany = lkpmReceipts
    .filter((r) => r.year === selectedYear)
    .reduce<Record<string, LKPMReceipt[]>>((acc, r) => {
      const key = r.company_name ?? r.nama_perusahaan_oss ?? "Unknown PT";
      if (!acc[key]) acc[key] = [];
      acc[key].push(r);
      return acc;
    }, {});

  // Group LKPM items by company for the selected year
  const lkpmByCompany = lkpmItems
    .filter((item) => item.year === selectedYear)
    .reduce<Record<string, LKPMBatchItem[]>>((acc, item) => {
      const key = item.company_name;
      if (!acc[key]) acc[key] = [];
      acc[key].push(item);
      return acc;
    }, {});

  // Calculate deadlines based on selected year
  const deadlines = {
    personalTax: new Date(selectedYear, 2, 31), // March 31
    annualCompany: new Date(selectedYear, 3, 30), // April 30
  };

  const handleFileUpload = useCallback(
    async (section: TaxSection, docType: string, file: File) => {
      setIsUploading(true);
      setUploadError(null);
      try {
        const base64 = await fileToBase64(file);
        await api.post(`/api/crm/clients/${clientId}/tax-documents`, {
          file: base64,
          file_name: file.name,
          document_type: docType,
          section: section,
          year: selectedYear,
        });
        toast.success(`${docType} uploaded successfully`);
        await onRefresh?.();
      } catch (err) {
        setUploadError(
          `Failed to upload ${docType}: ${(err as Error).message}`,
        );
        toast.error("Upload failed", { description: (err as Error).message });
      } finally {
        setIsUploading(false);
      }
    },
    [clientId, selectedYear, onRefresh],
  );

  return (
    <div className="space-y-6">
      {/* Header with year selector */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-[var(--bz-text-1)]">
            Tax Overview
          </h3>
          <p className="text-sm text-[var(--bz-text-2)]">
            Manage tax obligations and filings
          </p>
        </div>
        <YearSelector
          selectedYear={selectedYear}
          onYearChange={setSelectedYear}
        />
      </div>

      {/* Tax Consultant selector (Bali Zero team assignment) */}
      <TaxConsultantSelector
        clientId={clientId}
        initialValue={client?.tax_consultant}
        onSaved={onRefresh}
      />

      {/* Tax identifiers from CRM */}
      {(() => {
        const primaryCompany =
          companyLinks?.find((l) => l.is_primary) ?? companyLinks?.[0];
        const npwpValue = client?.npwp ?? client?.tax_id ?? undefined;
        const nibValue = client?.nib ?? undefined;
        const companyNpwp = !npwpValue
          ? primaryCompany?.npwp_company
          : undefined;
        const companyNib = !nibValue ? primaryCompany?.nib : undefined;
        return (
          <div className="flex flex-wrap gap-2">
            <TaxIdBadge
              label="NPWP"
              value={npwpValue}
              fallbackValue={companyNpwp}
              fallbackLabel={primaryCompany?.company_name}
            />
            <TaxIdBadge
              label="NIB"
              value={nibValue}
              fallbackValue={companyNib}
              fallbackLabel={primaryCompany?.company_name}
            />
          </div>
        );
      })()}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main content - Tax cards */}
        <div className="lg:col-span-2 space-y-4">
          <TaxCard
            title="Personal Tax"
            aria-label="Personal Tax"
            subtitle="Individual SPT Tahunan"
            deadline={deadlines.personalTax}
            icon={User}
            color="bg-gradient-to-br from-emerald-500 to-teal-600"
            section="personal"
            activeSection={activeSection}
            onClick={() => setActiveSection("personal")}
          />

          <TaxCard
            title="Annual Company Tax"
            aria-label="Annual Company Tax"
            subtitle="Corporate SPT Tahunan Badan"
            deadline={deadlines.annualCompany}
            icon={Building2}
            color="bg-gradient-to-br from-blue-500 to-cyan-600"
            section="annual"
            activeSection={activeSection}
            onClick={() => setActiveSection("annual")}
          />

          <TaxCard
            title="Monthly Reports"
            aria-label="Monthly Reports"
            subtitle="PPH 21, 23, PPN, PPH 25"
            deadline={new Date(selectedYear, 11, 20)} // Dec 20 as example
            icon={Calendar}
            color="bg-gradient-to-br from-purple-500 to-pink-600"
            section="monthly"
            activeSection={activeSection}
            onClick={() => setActiveSection("monthly")}
          />

          {/* LKPM with live quarter cards */}
          <div className="rounded-xl border border-[var(--bz-border)] bg-[var(--bz-surface)] p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center">
                  <FileText className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h4 className="font-semibold text-[var(--bz-text-1)]">
                    LKPM
                  </h4>
                  <p className="text-xs text-[var(--bz-text-2)]">
                    Laporan Kegiatan Penanaman Modal
                  </p>
                </div>
              </div>
              <Button
                variant={activeSection === "lkpm" ? "default" : "outline"}
                size="sm"
                onClick={() => setActiveSection("lkpm")}
              >
                Manage
              </Button>
            </div>

            {lkpmLoading ? (
              <div className="text-center py-4 text-xs text-[var(--bz-text-2)]">
                Loading LKPM data...
              </div>
            ) : Object.keys(lkpmByCompany).length === 0 ? (
              /* No LKPM data — show static Q1-Q4 placeholders */
              <div className="grid grid-cols-4 gap-2">
                {[1, 2, 3, 4].map((q) => (
                  <div
                    key={q}
                    className="text-center p-3 rounded-lg border border-[var(--bz-border)]"
                  >
                    <p className="text-lg font-bold text-[var(--bz-text-1)]">
                      Q{q}
                    </p>
                    <p className="text-xs text-[var(--bz-text-2)]">No report</p>
                  </div>
                ))}
              </div>
            ) : (
              /* Live LKPM data grouped by company */
              <div className="space-y-4">
                {Object.entries(lkpmByCompany).map(([companyName, items]) => (
                  <div key={companyName}>
                    <p className="text-xs font-medium text-[var(--bz-text-2)] mb-2">
                      {companyName}
                    </p>
                    <div className="grid grid-cols-4 gap-2">
                      {(["Q1", "Q2", "Q3", "Q4"] as const).map((q) => {
                        const report = items.find((r) => r.quarter === q);
                        return (
                          <LkpmQuarterCard
                            key={q}
                            quarter={q}
                            report={report ?? null}
                          />
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* OSS Tanda Terima (receipts per kegiatan usaha) — shareholder cascade */}
            <LkpmReceiptsPanel
              loading={lkpmReceiptsLoading}
              receiptsByCompany={receiptsByCompany}
              selectedYear={selectedYear}
            />
          </div>
        </div>

        {/* Side workspace for uploads */}
        <div className="lg:col-span-1">
          <SideWorkspace
            activeSection={activeSection}
            selectedYear={selectedYear}
            isUploading={isUploading}
            uploadError={uploadError}
            onFileUpload={handleFileUpload}
          />
        </div>
      </div>
    </div>
  );
}
