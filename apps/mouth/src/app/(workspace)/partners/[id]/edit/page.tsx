"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Loader2, AlertCircle } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import * as partnersApi from "@/lib/api/partners/partners";
import type { Partner, UpdatePartnerBody, CommissionTier, TaxWithholdingCategory } from "@/lib/api/partners/partners";

type FormSection = "profile" | "fiscal" | "payment" | "commission";

const SECTION_LABELS: Record<FormSection, string> = {
  profile: "Profile",
  fiscal: "Fiscal",
  payment: "Payment",
  commission: "Commission",
};

interface EditFormState {
  full_name: string;
  phone: string;
  whatsapp: string;
  nationality: string;
  company_name: string;
  work_role: string;
  tax_id: string;
  payment_method: string;
  bank_name: string;
  bank_account_number: string;
  bank_account_name: string;
  tax_withholding_category: TaxWithholdingCategory;
  commission_tier: CommissionTier;
  commission_rate_override: string;
  notes: string;
}

function FieldGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-zinc-300">{label}</label>
      {children}
    </div>
  );
}

function Input({
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-amber-500"
    />
  );
}

function partnerToFormState(partner: Partner): EditFormState {
  return {
    full_name: partner.full_name,
    phone: partner.phone || "",
    whatsapp: partner.whatsapp || "",
    nationality: partner.nationality || "",
    company_name: partner.company_name || "",
    work_role: partner.work_role || "",
    tax_id: partner.tax_id || "",
    payment_method: partner.payment_method || "bank_transfer",
    bank_name: partner.bank_name || "",
    bank_account_number: partner.bank_account_number || "",
    bank_account_name: partner.bank_account_name || "",
    tax_withholding_category: partner.tax_withholding_category,
    commission_tier: partner.commission_tier,
    commission_rate_override: partner.commission_rate_override != null ? String(partner.commission_rate_override) : "",
    notes: partner.notes || "",
  };
}

export default function EditPartnerPage() {
  const params = useParams();
  const router = useRouter();
  const { success: toastSuccess, error: toastError } = useToast();

  const partnerId = params?.id ? Number(params.id) : 0;
  const [partner, setPartner] = useState<Partner | null>(null);
  const [form, setForm] = useState<EditFormState | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<FormSection>("profile");

  useEffect(() => {
    const load = async () => {
      try {
        const data = await partnersApi.getPartner(partnerId);
        setPartner(data);
        setForm(partnerToFormState(data));
      } catch (err) {
        logger.error("Failed to load partner for edit", { component: "EditPartnerPage" }, err as Error);
        setError("Failed to load partner data.");
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [partnerId]);

  const setField = <K extends keyof EditFormState>(key: K, value: EditFormState[K]) => {
    setForm((prev) => prev ? { ...prev, [key]: value } : prev);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form) return;

    setIsSubmitting(true);
    try {
      const body: UpdatePartnerBody = {
        full_name: form.full_name.trim(),
        phone: form.phone.trim() || undefined,
        whatsapp: form.whatsapp.trim() || undefined,
        nationality: form.nationality.trim() || undefined,
        company_name: form.company_name.trim() || undefined,
        work_role: form.work_role.trim() || undefined,
        tax_id: form.tax_id.trim() || undefined,
        payment_method: form.payment_method || undefined,
        bank_name: form.bank_name.trim() || undefined,
        bank_account_number: form.bank_account_number.trim() || undefined,
        bank_account_name: form.bank_account_name.trim() || undefined,
        tax_withholding_category: form.tax_withholding_category,
        commission_tier: form.commission_tier,
        commission_rate_override: form.commission_rate_override
          ? parseFloat(form.commission_rate_override)
          : undefined,
        notes: form.notes.trim() || undefined,
      };

      await partnersApi.updatePartner(partnerId, body);
      toastSuccess("Partner updated");
      router.push(`/partners/${partnerId}`);
    } catch (err) {
      logger.error("Failed to update partner", { component: "EditPartnerPage" }, err as Error);
      toastError("Failed to update partner. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 size={32} className="animate-spin text-amber-400" />
      </div>
    );
  }

  if (error || !form) {
    return (
      <div className="flex flex-col items-center gap-4 py-16">
        <AlertCircle size={32} className="text-red-400" />
        <p className="text-zinc-400">{error || "Partner not found"}</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href={`/partners/${partnerId}`}>
          <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-zinc-200">
            <ArrowLeft size={16} className="mr-1" />
            Back
          </Button>
        </Link>
        <div>
          <h1 className="text-xl font-bold text-zinc-100">Edit Partner</h1>
          {partner && <p className="text-sm text-zinc-500">{partner.full_name}</p>}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Section Tabs */}
        <div className="flex gap-1 bg-zinc-900 border border-zinc-800 rounded-xl p-1">
          {(["profile", "fiscal", "payment", "commission"] as FormSection[]).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setActiveSection(s)}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                activeSection === s
                  ? "bg-amber-600 text-white"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
              }`}
            >
              {SECTION_LABELS[s]}
            </button>
          ))}
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
          {/* Profile */}
          {activeSection === "profile" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FieldGroup label="Full Name">
                <Input value={form.full_name} onChange={(v) => setField("full_name", v)} placeholder="Full legal name" />
              </FieldGroup>
              <FieldGroup label="Phone">
                <Input value={form.phone} onChange={(v) => setField("phone", v)} placeholder="+62 8xx xxxx xxxx" />
              </FieldGroup>
              <FieldGroup label="WhatsApp">
                <Input value={form.whatsapp} onChange={(v) => setField("whatsapp", v)} placeholder="+62 8xx xxxx xxxx" />
              </FieldGroup>
              <FieldGroup label="Nationality">
                <Input value={form.nationality} onChange={(v) => setField("nationality", v)} placeholder="e.g. Indonesian" />
              </FieldGroup>
              <FieldGroup label="Company Name">
                <Input value={form.company_name} onChange={(v) => setField("company_name", v)} placeholder="Company or agency" />
              </FieldGroup>
              <FieldGroup label="Work Role">
                <Input value={form.work_role} onChange={(v) => setField("work_role", v)} placeholder="e.g. Real Estate Agent" />
              </FieldGroup>
              <div className="sm:col-span-2">
                <FieldGroup label="Notes">
                  <textarea
                    value={form.notes}
                    onChange={(e) => setField("notes", e.target.value)}
                    rows={3}
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-amber-500 resize-none"
                  />
                </FieldGroup>
              </div>
            </div>
          )}

          {/* Fiscal */}
          {activeSection === "fiscal" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FieldGroup label="NPWP (Tax ID)">
                <Input value={form.tax_id} onChange={(v) => setField("tax_id", v)} placeholder="XX.XXX.XXX.X-XXX.XXX" />
              </FieldGroup>
              <FieldGroup label="Tax Withholding Category">
                <select
                  value={form.tax_withholding_category}
                  onChange={(e) => setField("tax_withholding_category", e.target.value as TaxWithholdingCategory)}
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 focus:outline-none focus:border-amber-500"
                >
                  <option value="tbd">TBD (not yet determined)</option>
                  <option value="withheld_tarif_umum">Withheld — Tarif Umum</option>
                  <option value="withheld_tarif_final">Withheld — Tarif Final</option>
                  <option value="exempt">Exempt</option>
                </select>
              </FieldGroup>
            </div>
          )}

          {/* Payment */}
          {activeSection === "payment" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FieldGroup label="Payment Method">
                <select
                  value={form.payment_method}
                  onChange={(e) => setField("payment_method", e.target.value)}
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 focus:outline-none focus:border-amber-500"
                >
                  <option value="bank_transfer">Bank Transfer</option>
                  <option value="cash">Cash</option>
                  <option value="e-wallet">E-Wallet</option>
                </select>
              </FieldGroup>
              <FieldGroup label="Bank Name">
                <Input value={form.bank_name} onChange={(v) => setField("bank_name", v)} placeholder="e.g. BCA, Mandiri" />
              </FieldGroup>
              <FieldGroup label="Account Number">
                <Input value={form.bank_account_number} onChange={(v) => setField("bank_account_number", v)} placeholder="Account number" />
              </FieldGroup>
              <FieldGroup label="Account Holder Name">
                <Input value={form.bank_account_name} onChange={(v) => setField("bank_account_name", v)} placeholder="Name on account" />
              </FieldGroup>
            </div>
          )}

          {/* Commission */}
          {activeSection === "commission" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FieldGroup label="Commission Tier">
                <select
                  value={form.commission_tier}
                  onChange={(e) => setField("commission_tier", e.target.value as CommissionTier)}
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 focus:outline-none focus:border-amber-500"
                >
                  <option value="bronze">Bronze</option>
                  <option value="silver">Silver</option>
                  <option value="gold">Gold</option>
                  <option value="platinum">Platinum</option>
                </select>
              </FieldGroup>
              <FieldGroup label="Rate Override (%)">
                <Input
                  value={form.commission_rate_override}
                  onChange={(v) => setField("commission_rate_override", v)}
                  type="number"
                  placeholder="Leave empty for tier default"
                />
              </FieldGroup>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between">
          <Link href={`/partners/${partnerId}`}>
            <Button type="button" variant="outline" className="border-zinc-700 text-zinc-300">
              Cancel
            </Button>
          </Link>
          <Button
            type="submit"
            disabled={isSubmitting}
            className="bg-amber-600 hover:bg-amber-700 text-white"
          >
            {isSubmitting ? (
              <>
                <Loader2 size={14} className="mr-2 animate-spin" />
                Saving…
              </>
            ) : (
              "Save Changes"
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
