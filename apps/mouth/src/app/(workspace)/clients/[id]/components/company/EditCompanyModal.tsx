"use client";

import React, { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/api/error-handler";
import {
  companyTypeOptionsWithCurrent,
  normalizeCompanyType,
} from "./companyType";

type CompanyForm = {
  company_name: string;
  company_type: string;
  kbli_code: string;
  nib: string;
  npwp_company: string;
  registered_address: string;
  city: string;
  province: string;
  akta_pendirian_no: string;
  akta_pendirian_date: string;
  akta_perubahan_no: string;
  akta_perubahan_date: string;
  sk_menhumkam_no: string;
  sk_menhumkam_date: string;
  status: string;
};

const DATE_FIELDS = new Set<keyof CompanyForm>([
  "akta_pendirian_date",
  "akta_perubahan_date",
  "sk_menhumkam_date",
]);

function buildForm(initialData: {
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
}): CompanyForm {
  return {
    company_name: initialData.company_name || "",
    company_type: normalizeCompanyType(initialData.company_type),
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
  };
}

export function EditCompanyModal({
  companyId,
  initialData,
  onClose,
  onSave,
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
}) {
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<{
    message: string;
    correlationId?: string;
  } | null>(null);
  const [initialForm] = useState<CompanyForm>(() => buildForm(initialData));
  const [form, setForm] = useState<CompanyForm>(initialForm);

  const typeOptions = companyTypeOptionsWithCurrent(form.company_type);

  const inputClass =
    "w-full px-3 py-2 rounded-lg border border-[var(--kbli-border)] bg-[var(--kbli-bg-surface)] text-[var(--kbli-text-primary)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--kbli-accent)]/50";

  const handleSave = async () => {
    setSaveError(null);

    // Dirty-fields only: never resend a field the user didn't touch, and
    // clear a date with `null` (not "") rather than dropping it silently.
    const updates: Record<string, string | null> = {};
    (Object.keys(form) as (keyof CompanyForm)[]).forEach((key) => {
      if (form[key] === initialForm[key]) return;
      if (DATE_FIELDS.has(key)) {
        updates[key] = form[key] === "" ? null : form[key];
      } else {
        updates[key] = form[key];
      }
    });

    if (Object.keys(updates).length === 0) {
      onClose();
      return;
    }

    setIsSaving(true);
    try {
      await api.crm.updateCompany(companyId, updates);
      toast.success("Company updated");
      onSave();
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : null;
      setSaveError({
        message: apiErr?.detail || (err as Error).message,
        correlationId: apiErr?.correlationId,
      });
      toast.error("Failed to update company", {
        description: apiErr?.detail || (err as Error).message,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div
        className="w-full max-w-2xl rounded-2xl overflow-hidden shadow-2xl max-h-[90vh] flex flex-col"
        style={{
          background: "var(--kbli-bg-elevated)",
          border: "1px solid var(--kbli-border)",
        }}
      >
        <div
          className="flex items-center justify-between px-6 py-4 border-b"
          style={{ borderColor: "var(--kbli-border)" }}
        >
          <h2 className="text-lg font-semibold text-[var(--kbli-text-primary)]">
            Edit Company
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-[var(--kbli-bg-card-hover)] text-[var(--kbli-text-secondary)] transition-colors"
            aria-label="Close modal"
            title="Close modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="overflow-y-auto flex-1 px-6 py-5 space-y-4">
          {saveError && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-lg border border-[var(--state-warning)]/30 bg-[var(--state-warning)]/10 px-3 py-2 text-sm text-[var(--state-warning)]"
            >
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <div>
                <p>{saveError.message}</p>
                {saveError.correlationId && (
                  <p className="mt-0.5 text-xs text-[var(--kbli-text-muted)]">
                    Request ID: {saveError.correlationId}
                  </p>
                )}
              </div>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--kbli-text-muted)] mb-1 block">
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
              <label className="text-[10px] uppercase tracking-wider text-[var(--kbli-text-muted)] mb-1 block">
                Type
              </label>
              <select
                className={inputClass}
                value={form.company_type}
                onChange={(e) =>
                  setForm((f) => ({ ...f, company_type: e.target.value }))
                }
              >
                {typeOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--kbli-text-muted)] mb-1 block">
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
              <label className="text-[10px] uppercase tracking-wider text-[var(--kbli-text-muted)] mb-1 block">
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
              <label className="text-[10px] uppercase tracking-wider text-[var(--kbli-text-muted)] mb-1 block">
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

          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-3 sm:col-span-1">
              <label className="text-[10px] uppercase tracking-wider text-[var(--kbli-text-muted)] mb-1 block">
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
              <label className="text-[10px] uppercase tracking-wider text-[var(--kbli-text-muted)] mb-1 block">
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
              <label className="text-[10px] uppercase tracking-wider text-[var(--kbli-text-muted)] mb-1 block">
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

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--kbli-text-muted)] mb-1 block">
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
              <label className="text-[10px] uppercase tracking-wider text-[var(--kbli-text-muted)] mb-1 block">
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

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--kbli-text-muted)] mb-1 block">
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
              <label className="text-[10px] uppercase tracking-wider text-[var(--kbli-text-muted)] mb-1 block">
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

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--kbli-text-muted)] mb-1 block">
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
              <label className="text-[10px] uppercase tracking-wider text-[var(--kbli-text-muted)] mb-1 block">
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

          <div>
            <label className="text-[10px] uppercase tracking-wider text-[var(--kbli-text-muted)] mb-1 block">
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

        <div
          className="flex items-center justify-end gap-3 px-6 py-4 border-t"
          style={{ borderColor: "var(--kbli-border)" }}
        >
          <button
            onClick={onClose}
            disabled={isSaving}
            className="px-4 py-2 text-sm rounded-lg border border-[var(--kbli-border)] text-[var(--kbli-text-secondary)] hover:text-[var(--kbli-text-primary)] hover:border-[var(--kbli-text-secondary)] transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-4 py-2 text-sm rounded-lg bg-[var(--bz-sidebar-active-fill)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-2 transition-opacity"
          >
            {isSaving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            Save Changes
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
