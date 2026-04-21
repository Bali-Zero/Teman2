"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2, AlertTriangle, User, Mail, Phone, Briefcase, CreditCard, Building2 } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import * as partnersApi from "@/lib/api/partners/partners";
import type { CreatePartnerBody, CommissionTier, TaxWithholdingCategory, EntityType } from "@/lib/api/partners/partners";
import { useTeamMemberOptions } from "@/hooks/useTeamMembers";

// NB-2 guardrail: warn if work_role matches sponsor/guarantor patterns
const SPONSOR_ROLE_RE = /sponsor|garante|penjamin/i;

type FormSection = "profile" | "fiscal" | "payment" | "commission";

const SECTION_LABELS: Record<FormSection, string> = {
  profile: "Profile",
  fiscal: "Fiscal",
  payment: "Payment",
  commission: "Commission",
};

interface FormState {
  full_name: string;
  email: string;
  entity_type: EntityType;
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
  assigned_to: string;
  notes: string;
  pdp_consent: boolean;
}

const INITIAL_FORM: FormState = {
  full_name: "",
  email: "",
  entity_type: "individual",
  phone: "",
  whatsapp: "",
  nationality: "",
  company_name: "",
  work_role: "",
  tax_id: "",
  payment_method: "bank_transfer",
  bank_name: "",
  bank_account_number: "",
  bank_account_name: "",
  tax_withholding_category: "tbd",
  commission_tier: "bronze",
  commission_rate_override: "",
  assigned_to: "",
  notes: "",
  pdp_consent: false,
};

function SectionTab({
  id,
  active,
  onClick,
}: {
  id: FormSection;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
        active
          ? "bg-amber-600 text-white"
          : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
      }`}
    >
      {SECTION_LABELS[id]}
    </button>
  );
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
  error,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  error?: string;
}) {
  return (
    <div>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`w-full px-3 py-2 bg-zinc-800 border rounded-lg text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-amber-500 ${
          error ? "border-red-500" : "border-zinc-700"
        }`}
      />
      {error && <p className="text-xs text-red-400 mt-1">{error}</p>}
    </div>
  );
}

export default function NewPartnerPage() {
  const router = useRouter();
  const { success: toastSuccess, error: toastError } = useToast();
  const { options: teamMemberOptions } = useTeamMemberOptions();

  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [activeSection, setActiveSection] = useState<FormSection>("profile");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [showSponsorWarning, setShowSponsorWarning] = useState(false);

  const setField = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (fieldErrors[key]) {
      setFieldErrors((prev) => ({ ...prev, [key]: "" }));
    }
    // NB-2 guardrail check
    if (key === "work_role" && typeof value === "string") {
      setShowSponsorWarning(SPONSOR_ROLE_RE.test(value));
    }
  };

  const validate = (): boolean => {
    const errors: Record<string, string> = {};
    if (!form.full_name.trim()) errors.full_name = "Full name is required";
    if (!form.email.trim()) errors.email = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errors.email = "Invalid email address";
    if (!form.pdp_consent) errors.pdp_consent = "PDP consent is required";
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) {
      toastError("Please fix the form errors before submitting");
      return;
    }

    setIsSubmitting(true);
    try {
      const body: CreatePartnerBody = {
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        entity_type: form.entity_type,
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
        assigned_to: form.assigned_to || undefined,
        notes: form.notes.trim() || undefined,
        pdp_consent: form.pdp_consent,
      };

      const partner = await partnersApi.createPartner(body);
      toastSuccess(`Partner ${partner.full_name} created`);
      router.push(`/partners/${partner.id}`);
    } catch (err) {
      logger.error("Failed to create partner", { component: "NewPartnerPage" }, err as Error);
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("409") || msg.toLowerCase().includes("conflict") || msg.toLowerCase().includes("already exists")) {
        toastError("A partner with this email already exists");
        setFieldErrors({ email: "Email already registered" });
        setActiveSection("profile");
      } else {
        toastError("Failed to create partner. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/partners">
          <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-zinc-200">
            <ArrowLeft size={16} className="mr-1" />
            Back
          </Button>
        </Link>
        <h1 className="text-xl font-bold text-zinc-100">New Partner</h1>
      </div>

      {/* NB-2 Sponsor Guardrail */}
      {showSponsorWarning && (
        <div className="flex items-start gap-3 p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-300 text-sm">
          <AlertTriangle size={18} className="flex-shrink-0 mt-0.5" />
          <div>
            <strong>Warning:</strong> The work role appears to indicate a sponsor/guarantor position.
            Please verify the partner{"'"}s role does not conflict with Indonesian immigration regulations
            before proceeding.
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Section Tabs */}
        <div className="flex gap-1 bg-zinc-900 border border-zinc-800 rounded-xl p-1">
          {(["profile", "fiscal", "payment", "commission"] as FormSection[]).map((s) => (
            <SectionTab key={s} id={s} active={activeSection === s} onClick={() => setActiveSection(s)} />
          ))}
        </div>

        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
          {/* Profile Section */}
          {activeSection === "profile" && (
            <>
              <div className="flex items-center gap-2 mb-2">
                <User size={16} className="text-amber-400" />
                <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wide">Profile</h2>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FieldGroup label="Full Name *">
                  <Input
                    value={form.full_name}
                    onChange={(v) => setField("full_name", v)}
                    placeholder="Full legal name"
                    error={fieldErrors.full_name}
                  />
                </FieldGroup>
                <FieldGroup label="Email *">
                  <Input
                    value={form.email}
                    onChange={(v) => setField("email", v)}
                    type="email"
                    placeholder="partner@email.com"
                    error={fieldErrors.email}
                  />
                </FieldGroup>
                <FieldGroup label="Entity Type *">
                  <select
                    value={form.entity_type}
                    onChange={(e) => setField("entity_type", e.target.value as EntityType)}
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 focus:outline-none focus:border-amber-500"
                  >
                    <option value="individual">Individual</option>
                    <option value="corporate_pt">Corporate PT</option>
                    <option value="corporate_cv">Corporate CV</option>
                    <option value="foreign">Foreign</option>
                  </select>
                </FieldGroup>
                <FieldGroup label="Phone">
                  <Input
                    value={form.phone}
                    onChange={(v) => setField("phone", v)}
                    placeholder="+62 8xx xxxx xxxx"
                  />
                </FieldGroup>
                <FieldGroup label="WhatsApp">
                  <Input
                    value={form.whatsapp}
                    onChange={(v) => setField("whatsapp", v)}
                    placeholder="+62 8xx xxxx xxxx"
                  />
                </FieldGroup>
                <FieldGroup label="Nationality">
                  <Input
                    value={form.nationality}
                    onChange={(v) => setField("nationality", v)}
                    placeholder="e.g. Indonesian"
                  />
                </FieldGroup>
                <FieldGroup label="Company Name">
                  <Input
                    value={form.company_name}
                    onChange={(v) => setField("company_name", v)}
                    placeholder="Company or agency name"
                  />
                </FieldGroup>
                <FieldGroup label="Work Role">
                  <Input
                    value={form.work_role}
                    onChange={(v) => setField("work_role", v)}
                    placeholder="e.g. Real Estate Agent, Consultant"
                  />
                </FieldGroup>
                <FieldGroup label="Assigned To">
                  <select
                    value={form.assigned_to}
                    onChange={(e) => setField("assigned_to", e.target.value)}
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 focus:outline-none focus:border-amber-500"
                  >
                    <option value="">Unassigned</option>
                    {teamMemberOptions.map((m) => (
                      <option key={m.value} value={m.value}>{m.label}</option>
                    ))}
                  </select>
                </FieldGroup>
              </div>
              <FieldGroup label="Notes">
                <textarea
                  value={form.notes}
                  onChange={(e) => setField("notes", e.target.value)}
                  rows={3}
                  placeholder="Internal notes about this partner..."
                  className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-amber-500 resize-none"
                />
              </FieldGroup>
            </>
          )}

          {/* Fiscal Section */}
          {activeSection === "fiscal" && (
            <>
              <div className="flex items-center gap-2 mb-2">
                <CreditCard size={16} className="text-amber-400" />
                <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wide">Fiscal</h2>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FieldGroup label="NPWP (Tax ID)">
                  <Input
                    value={form.tax_id}
                    onChange={(v) => setField("tax_id", v)}
                    placeholder="XX.XXX.XXX.X-XXX.XXX"
                  />
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
              <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg text-blue-300 text-sm">
                <strong>Note:</strong> Payouts are blocked when tax_withholding_category is &apos;tbd&apos;. Confirm
                the partner{"'"}s tax status before approving commissions.
              </div>
            </>
          )}

          {/* Payment Section */}
          {activeSection === "payment" && (
            <>
              <div className="flex items-center gap-2 mb-2">
                <Building2 size={16} className="text-amber-400" />
                <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wide">Payment</h2>
              </div>
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
                  <Input
                    value={form.bank_name}
                    onChange={(v) => setField("bank_name", v)}
                    placeholder="e.g. BCA, Mandiri, BNI"
                  />
                </FieldGroup>
                <FieldGroup label="Account Number">
                  <Input
                    value={form.bank_account_number}
                    onChange={(v) => setField("bank_account_number", v)}
                    placeholder="Bank account number"
                  />
                </FieldGroup>
                <FieldGroup label="Account Holder Name">
                  <Input
                    value={form.bank_account_name}
                    onChange={(v) => setField("bank_account_name", v)}
                    placeholder="Name as on bank account"
                  />
                </FieldGroup>
              </div>
            </>
          )}

          {/* Commission Section */}
          {activeSection === "commission" && (
            <>
              <div className="flex items-center gap-2 mb-2">
                <Briefcase size={16} className="text-amber-400" />
                <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wide">Commission Policy</h2>
              </div>
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
                    placeholder="Leave empty to use tier default"
                  />
                </FieldGroup>
              </div>
            </>
          )}
        </div>

        {/* PDP Consent — always visible */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={form.pdp_consent}
              onChange={(e) => setField("pdp_consent", e.target.checked)}
              className="mt-0.5 rounded border-zinc-600 text-amber-500"
            />
            <div>
              <span className="text-sm text-zinc-200 font-medium">PDP Consent (UU No. 27/2022) *</span>
              <p className="text-xs text-zinc-500 mt-0.5">
                The partner has given explicit consent for their personal data to be processed for commission
                tracking, payment processing, and related business purposes.
              </p>
              {fieldErrors.pdp_consent && (
                <p className="text-xs text-red-400 mt-1">{fieldErrors.pdp_consent}</p>
              )}
            </div>
          </label>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between">
          <Link href="/partners">
            <Button type="button" variant="outline" className="border-zinc-700 text-zinc-300">
              Cancel
            </Button>
          </Link>
          <div className="flex items-center gap-2">
            {/* Section nav buttons */}
            {activeSection !== "profile" && (
              <Button
                type="button"
                variant="outline"
                className="border-zinc-700 text-zinc-300"
                onClick={() => {
                  const sections: FormSection[] = ["profile", "fiscal", "payment", "commission"];
                  const idx = sections.indexOf(activeSection);
                  if (idx > 0) setActiveSection(sections[idx - 1]);
                }}
              >
                Previous
              </Button>
            )}
            {activeSection !== "commission" ? (
              <Button
                type="button"
                className="bg-zinc-700 hover:bg-zinc-600 text-zinc-100"
                onClick={() => {
                  const sections: FormSection[] = ["profile", "fiscal", "payment", "commission"];
                  const idx = sections.indexOf(activeSection);
                  if (idx < sections.length - 1) setActiveSection(sections[idx + 1]);
                }}
              >
                Next
              </Button>
            ) : (
              <Button
                type="submit"
                disabled={isSubmitting}
                className="bg-amber-600 hover:bg-amber-700 text-white"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 size={14} className="mr-2 animate-spin" />
                    Creating…
                  </>
                ) : (
                  "Create Partner"
                )}
              </Button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}
