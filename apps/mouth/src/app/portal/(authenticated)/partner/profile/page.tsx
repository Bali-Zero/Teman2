"use client";

import { useEffect, useState } from "react";
import { getMe, type Partner } from "@/lib/api/partners/partners";

function Field({ label, value }: { label: string; value: string | undefined | null }) {
  return (
    <div className="py-3 border-b border-white/10 last:border-0">
      <dt className="text-xs text-gray-400 uppercase tracking-wide mb-1">{label}</dt>
      <dd className="text-sm text-gray-100">{value ?? "—"}</dd>
    </div>
  );
}

export default function PartnerProfilePage() {
  const [partner, setPartner] = useState<Partner | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMe()
      .then((data) => setPartner(data))
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : String(e))
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6">Loading...</div>;
  if (error) return <div className="p-6 text-red-500">Error: {error}</div>;
  if (!partner) return <div className="p-6 text-gray-400">No profile data.</div>;

  return (
    <div className="p-6 space-y-8 max-w-2xl">
      <h1 className="text-2xl font-semibold text-white">My Profile</h1>

      <div className="rounded-lg border border-white/10 bg-white/5 p-6">
        <h2 className="text-sm font-medium text-gray-300 mb-4">Personal Information</h2>
        <dl>
          <Field label="Full Name" value={partner.full_name} />
          <Field label="Email" value={partner.email} />
          <Field label="Phone" value={partner.phone} />
          <Field label="WhatsApp" value={partner.whatsapp} />
          <Field label="Nationality" value={partner.nationality} />
          <Field label="Entity Type" value={partner.entity_type} />
          <Field label="Company" value={partner.company_name} />
          <Field label="Work Role" value={partner.work_role} />
        </dl>
      </div>

      <div className="rounded-lg border border-white/10 bg-white/5 p-6">
        <h2 className="text-sm font-medium text-gray-300 mb-4">Account Status</h2>
        <dl>
          <Field label="Status" value={partner.onboarding_status} />
          <Field label="Commission Tier" value={partner.commission_tier} />
          <Field label="Tax Withholding Category" value={partner.tax_withholding_category} />
          <Field label="Tax ID (NPWP)" value={partner.tax_id} />
          <Field label="PDP Consent" value={partner.pdp_consent ? "Yes" : "No"} />
          {partner.pdp_consent_at && (
            <Field
              label="PDP Consent Date"
              value={new Date(partner.pdp_consent_at).toLocaleDateString("id-ID")}
            />
          )}
        </dl>
      </div>

      <div className="rounded-lg border border-white/10 bg-white/5 p-6">
        <h2 className="text-sm font-medium text-gray-300 mb-4">Bank / Payment</h2>
        <dl>
          <Field label="Payment Method" value={partner.payment_method} />
          <Field label="Bank Name" value={partner.bank_name} />
          <Field label="Account Holder" value={partner.bank_account_name} />
          <Field label="Account Number" value={partner.bank_account_number} />
        </dl>
      </div>

      <p className="text-xs text-gray-500 border border-white/10 rounded-lg p-4">
        To update your profile, reply to{" "}
        <a
          href="mailto:zantara@balizero.com"
          className="text-amber-400 hover:underline"
        >
          zantara@balizero.com
        </a>
        . Direct editing will be available in a future release.
      </p>
    </div>
  );
}
