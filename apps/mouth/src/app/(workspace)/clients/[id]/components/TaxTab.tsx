"use client";

import React, { useState, useCallback, memo, useEffect } from "react";
import {
  Building2,
  FileText,
  CheckCircle,
  AlertCircle,
  UserCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { Client, ClientCompanyLink } from "@/lib/api/crm/crm.types";
import { lkpmApi } from "@/lib/api/workspace/lkpm.api";
import type { LKPMBatchItem, LKPMReceipt } from "@/lib/api/portal/portal.types";
import { AiSummaryCard } from "./AiSummaryCard";

// ============================================
// TAX CONSULTANT DROPDOWN (Bali Zero tax team)
// ============================================
// The five allowed values USED to be a literal here. They are not any more: this
// is a "use client" module, so a literal in it is compiled into
// `app/(workspace)/clients/[id]/page-*.js`, and that chunk is served from the
// static CDN path with no session — an anonymous
// `curl https://balizero.com/_next/static/chunks/app/(workspace)/clients/%5Bid%5D/page-*.js`
// returned 200 and a name the owner had excluded from public surfaces. Measured,
// not theorised: 2 marker hits in that chunk on production as of 2026-09-12.
//
// The list now arrives as a prop from the server (`page.tsx` ->
// `taxConsultants()` in `@/lib/workspace/roster-directory`, which is the module
// that stays in sync with backend migration 093's CHECK constraint). Only the
// TYPE crosses this boundary, and `import type` is erased at compile time.
import type { TaxConsultantOption } from "@/lib/workspace/roster-directory";

type TaxYear = number;

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
// TAX CONSULTANT SELECTOR
// ============================================
interface TaxConsultantSelectorProps {
  clientId: number;
  initialValue: string | null | undefined;
  onSaved?: () => Promise<void> | void;
  /** Server-supplied; required, so an empty dropdown cannot pass unnoticed. */
  consultants: readonly TaxConsultantOption[];
}

const TaxConsultantSelector = memo(function TaxConsultantSelector({
  clientId,
  initialValue,
  onSaved,
  consultants,
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
            ? `Tax consultant: ${consultants.find((c) => c.value === newValue)?.label ?? newValue}`
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
    [clientId, value, onSaved, consultants],
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
        {consultants.map((c) => (
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
  taxConsultants,
}: {
  clientId: number;
  formatDate: (d: string) => string;
  client: Client | null;
  companyLinks?: ClientCompanyLink[];
  onRefresh?: () => Promise<void> | void;
  /**
   * The assignable tax team, resolved on the server. REQUIRED and not defaulted:
   * a default here would put the names back into this chunk, which is the whole
   * defect, and an optional prop would let a caller silently ship an empty
   * dropdown instead of failing the type check.
   */
  taxConsultants: readonly TaxConsultantOption[];
}) {
  const [selectedYear, setSelectedYear] = useState<TaxYear>(
    new Date().getFullYear(),
  );
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

  return (
    <div className="space-y-6">
      {/* AI Summary (CRM-Guardian L1 cross-folder, tax slice) */}
      <AiSummaryCard clientId={clientId} section="tax" />
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
        consultants={taxConsultants}
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

      {/* LKPM with live quarter cards */}
      <div className="rounded-xl border border-[var(--bz-border)] bg-[var(--bz-surface)] p-5">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center">
            <FileText className="w-6 h-6 text-white" />
          </div>
          <div>
            <h4 className="font-semibold text-[var(--bz-text-1)]">LKPM</h4>
            <p className="text-xs text-[var(--bz-text-2)]">
              Laporan Kegiatan Penanaman Modal
            </p>
          </div>
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
  );
}
