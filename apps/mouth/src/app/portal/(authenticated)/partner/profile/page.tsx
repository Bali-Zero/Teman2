"use client";

/**
 * Partner Profile — the partner's personal, account and payout details.
 *
 * WS3 final slice (GARUDA Day Edition, 2026-07-26): day-theme token
 * alignment. Masthead = copper rule + serif (--font-serif) in --tx-pure;
 * sections read --bz-card / --bz-border with the concept .panel shadow;
 * field labels --tx-secondary, values --tx-primary (was text-gray-400 /
 * text-gray-100 on white/5 dark cards); the onboarding Status row renders
 * the shared StatusBadge on --state-* AA tokens (active → success,
 * pending_approval → warning, inactive → danger); the support mailto reads
 * --bz-copper-text (5.05:1 on paper, 5.70:1 on card — was text-amber-400,
 * ~1.9:1 on paper). No hardcoded hexes.
 */

import { useCallback, useEffect, useState } from "react";
import { StatusBadge } from "@/components/portal/StatusBadge";
import { getMe, type Partner } from "@/lib/api/partners/partners";
import { PartnerLoadError } from "../PartnerLoadError";

// Day surface: token card + concept .panel shadow (soft navy on paper,
// near-invisible on dark). Was border-white/10 + bg-white/5 dark glass.
const CARD_STYLE = {
  background: "var(--bz-card)",
  borderColor: "var(--bz-border)",
  boxShadow: "0 14px 34px rgba(22, 33, 58, 0.07)",
} as const;

function Field({
  label,
  value,
}: {
  label: string;
  value: string | undefined | null;
}) {
  return (
    <div className="py-3 border-b border-[var(--bz-border)] last:border-0">
      <dt className="text-xs text-[var(--tx-secondary)] uppercase tracking-wide mb-1">
        {label}
      </dt>
      <dd className="text-sm text-[var(--tx-primary)]">{value ?? "—"}</dd>
    </div>
  );
}

function StatusField({ status }: { status: string | undefined | null }) {
  return (
    <div className="py-3 border-b border-[var(--bz-border)] last:border-0">
      <dt className="text-xs text-[var(--tx-secondary)] uppercase tracking-wide mb-1">
        Status
      </dt>
      <dd className="text-sm text-[var(--tx-primary)]">
        {status ? <StatusBadge status={status} /> : "—"}
      </dd>
    </div>
  );
}

export default function PartnerProfilePage() {
  const [partner, setPartner] = useState<Partner | null>(null);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setUnavailable(false);
    try {
      const data = await getMe();
      if (!data) throw new Error("Invalid partner profile response");
      setPartner(data);
    } catch {
      setPartner(null);
      setUnavailable(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading)
    return <div className="p-6 text-[var(--tx-secondary)]">Loading...</div>;
  if (unavailable)
    return (
      <PartnerLoadError
        title="Profile is temporarily unavailable"
        onRetry={load}
      />
    );
  if (!partner)
    return (
      <div className="p-6 text-[var(--tx-secondary)]">No profile data.</div>
    );

  return (
    <div className="p-6 space-y-8 max-w-2xl">
      {/* Day masthead: copper rule + Cormorant serif headline per concept */}
      <section>
        <div
          aria-hidden="true"
          className="w-14 h-[3px] rounded-sm mb-4 bg-[var(--bz-copper)]"
        />
        <h1
          className="text-2xl font-semibold tracking-tight text-[var(--tx-pure)]"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          My Profile
        </h1>
      </section>

      <div className="rounded-xl border p-6" style={CARD_STYLE}>
        <h2 className="text-sm font-medium text-[var(--tx-primary)] mb-4">
          Personal Information
        </h2>
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

      <div className="rounded-xl border p-6" style={CARD_STYLE}>
        <h2 className="text-sm font-medium text-[var(--tx-primary)] mb-4">
          Account Status
        </h2>
        <dl>
          <StatusField status={partner.onboarding_status} />
          {/* CRIT-8: commission_tier is optional; backend uses default_commission_type + value */}
          <Field
            label="Commission Policy"
            value={
              partner.commission_tier ??
              (partner.default_commission_value
                ? `${partner.default_commission_value}${partner.default_commission_type === "percentage" ? "%" : " IDR flat"}`
                : undefined)
            }
          />
          <Field
            label="Tax Withholding Category"
            value={partner.tax_withholding_category}
          />
          {/* CRIT-8: backend field is 'npwp', not 'tax_id' */}
          <Field label="Tax ID (NPWP)" value={partner.npwp} />
          {/* CRIT-8: pdp_consent boolean removed; use pdp_consent_at presence */}
          <Field
            label="PDP Consent"
            value={partner.pdp_consent_at ? "Yes" : "No"}
          />
          {partner.pdp_consent_at && (
            <Field
              label="PDP Consent Date"
              value={new Date(partner.pdp_consent_at).toLocaleDateString(
                "id-ID",
              )}
            />
          )}
        </dl>
      </div>

      <div className="rounded-xl border p-6" style={CARD_STYLE}>
        <h2 className="text-sm font-medium text-[var(--tx-primary)] mb-4">
          Bank / Payment
        </h2>
        <dl>
          <Field label="Payment Method" value={partner.payment_method} />
          <Field label="Bank Name" value={partner.bank_name} />
          {/* CRIT-8: backend field is 'bank_account_holder', not 'bank_account_name' */}
          <Field label="Account Holder" value={partner.bank_account_holder} />
          <Field label="Account Number" value={partner.bank_account_number} />
        </dl>
      </div>

      <p
        className="text-xs text-[var(--tx-secondary)] border rounded-xl p-4"
        style={CARD_STYLE}
      >
        To update your profile, reply to{" "}
        <a
          href="mailto:zantara@balizero.com"
          className="text-[var(--bz-copper-text)] hover:underline"
        >
          zantara@balizero.com
        </a>
        . Direct editing will be available in a future release.
      </p>
    </div>
  );
}
