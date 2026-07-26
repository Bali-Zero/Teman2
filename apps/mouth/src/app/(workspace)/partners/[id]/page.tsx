"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  User,
  Mail,
  Phone,
  Building2,
  CreditCard,
  Handshake,
  BarChart3,
  FileText,
  Settings,
  Edit,
  CheckCircle,
  XCircle,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import { api } from "@/lib/api";
import * as partnersApi from "@/lib/api/partners/partners";
import type {
  Partner,
  PartnerReferral,
  PartnerCommission,
  AuditLogEntry,
} from "@/lib/api/partners/partners";
import { Money } from "@balizero/core";

/** Dashboard panel recipe — mirrors the operative-dark kita surfaces. */
const PANEL: React.CSSProperties = {
  background: "rgba(35,35,40,0.65)",
  borderColor: "var(--bz-border)",
};

/** Inline danger strip (load/audit error). */
const DANGER_STRIP: React.CSSProperties = {
  background: "color-mix(in srgb, var(--state-danger) 12%, transparent)",
  borderColor: "color-mix(in srgb, var(--state-danger) 30%, transparent)",
  color: "var(--state-danger)",
};

/** State-tinted chip: 12% tint fill, 30% rim, state ink (portal idiom). */
function stateChip(state: string): React.CSSProperties {
  return {
    background: `color-mix(in srgb, ${state} 12%, transparent)`,
    color: state,
    borderColor: `color-mix(in srgb, ${state} 30%, transparent)`,
  };
}

/** Neutral chip for closed/inert statuses. */
const NEUTRAL_CHIP: React.CSSProperties = {
  background: "color-mix(in srgb, var(--bz-text-pure) 6%, transparent)",
  color: "var(--bz-text-2)",
  borderColor: "var(--bz-border)",
};

type TabId =
  "profile" | "fiscal" | "payment" | "referrals" | "commissions" | "audit";

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: "profile", label: "Profile", icon: <User size={14} /> },
  { id: "fiscal", label: "Fiscal", icon: <CreditCard size={14} /> },
  { id: "payment", label: "Payment", icon: <Building2 size={14} /> },
  { id: "referrals", label: "Referrals", icon: <Handshake size={14} /> },
  { id: "commissions", label: "Commissions", icon: <BarChart3 size={14} /> },
  { id: "audit", label: "Audit", icon: <FileText size={14} /> },
];

// CRIT-8: aligned to backend PartnerStatus enum. Honestly mapped:
// pending_approval -> warning, active -> success, inactive -> neutral.
const STATUS_STYLES: Record<
  string,
  { style: React.CSSProperties; label: string }
> = {
  pending_approval: {
    style: stateChip("var(--state-warning)"),
    label: "Pending Approval",
  },
  active: { style: stateChip("var(--state-success)"), label: "Active" },
  inactive: { style: NEUTRAL_CHIP, label: "Inactive" },
};

// Commission pipeline statuses, honestly mapped: pending steps -> warning,
// approved -> info, ready_to_pay -> neon purple (identity hue, kept from the
// legacy palette), paid -> success, clawback steps -> warning/danger,
// waived -> neutral.
const COMMISSION_STATUS_STYLES: Record<string, React.CSSProperties> = {
  pending_approval: stateChip("var(--state-warning)"),
  approved: stateChip("var(--state-info)"),
  ready_to_pay: stateChip("var(--bz-neon-purple)"),
  paid: stateChip("var(--state-success)"),
  clawback_pending: stateChip("var(--state-warning)"),
  clawed_back: stateChip("var(--state-danger)"),
  waived: NEUTRAL_CHIP,
};

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between py-2 border-b border-[var(--bz-border)] last:border-0">
      <span className="text-sm text-[var(--bz-text-3)] min-w-36">{label}</span>
      <span className="text-sm text-[var(--bz-text-1)] text-right">
        {value || <span className="text-[var(--bz-text-3)] italic">—</span>}
      </span>
    </div>
  );
}

function ProfileTab({ partner }: { partner: Partner }) {
  const statusEntry =
    STATUS_STYLES[partner.onboarding_status] || STATUS_STYLES.inactive;
  return (
    <div className="space-y-4">
      <div className="border rounded-xl p-4 space-y-0" style={PANEL}>
        <InfoRow label="Full Name" value={partner.full_name} />
        <InfoRow
          label="Email"
          value={
            <span className="flex items-center gap-1.5">
              <Mail size={12} className="text-[var(--bz-text-3)]" />
              {partner.email}
            </span>
          }
        />
        <InfoRow
          label="Phone"
          value={
            partner.phone && (
              <span className="flex items-center gap-1.5">
                <Phone size={12} className="text-[var(--bz-text-3)]" />
                {partner.phone}
              </span>
            )
          }
        />
        <InfoRow label="WhatsApp" value={partner.whatsapp} />
        <InfoRow label="Nationality" value={partner.nationality} />
        <InfoRow label="Company" value={partner.company_name} />
        <InfoRow label="Work Role" value={partner.work_role} />
        <InfoRow
          label="Status"
          value={
            <span
              className="inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium"
              style={statusEntry.style}
            >
              {statusEntry.label}
            </span>
          }
        />
        {partner.commission_tier && (
          <InfoRow
            label="Commission Tier"
            value={
              <span className="capitalize">{partner.commission_tier}</span>
            }
          />
        )}
        {partner.default_commission_type && (
          <InfoRow
            label="Commission Policy"
            value={
              partner.default_commission_type === "percentage" ? (
                `${partner.default_commission_value} %`
              ) : (
                <Money value={Number(partner.default_commission_value)} />
              )
            }
          />
        )}
        <InfoRow label="Assigned To" value={partner.assigned_to} />
        <InfoRow
          label="PDP Consent"
          value={
            partner.pdp_consent_at ? (
              <span className="flex items-center gap-1 text-[var(--state-success)]">
                <CheckCircle size={12} /> Yes (
                {new Date(partner.pdp_consent_at).toLocaleDateString()})
              </span>
            ) : (
              <span className="flex items-center gap-1 text-[var(--state-danger)]">
                <XCircle size={12} /> No
              </span>
            )
          }
        />
        <InfoRow
          label="Welcome Email"
          value={
            partner.welcome_email_sent_at
              ? new Date(partner.welcome_email_sent_at).toLocaleDateString()
              : "Not sent"
          }
        />
      </div>
      {partner.notes && (
        <div className="border rounded-xl p-4" style={PANEL}>
          <p className="text-xs text-[var(--bz-text-3)] mb-1 uppercase tracking-wide font-medium">
            Notes
          </p>
          <p className="text-sm text-[var(--bz-text-1)] whitespace-pre-wrap">
            {partner.notes}
          </p>
        </div>
      )}
    </div>
  );
}

function FiscalTab({ partner }: { partner: Partner }) {
  const taxLabels: Record<string, string> = {
    // CRIT-8: aligned to backend TaxWithholdingCategory enum
    tbd: "TBD — not yet determined",
    pph21: "PPh 21 (withheld)",
    pph23: "PPh 23 (withheld)",
    exempt: "Exempt",
  };
  return (
    <div className="border rounded-xl p-4 space-y-0" style={PANEL}>
      <InfoRow label="NPWP (Tax ID)" value={partner.npwp} />
      <InfoRow
        label="Withholding Category"
        value={
          taxLabels[partner.tax_withholding_category] ||
          partner.tax_withholding_category
        }
      />
      {partner.commission_rate_override != null && (
        <InfoRow
          label="Rate Override"
          value={`${partner.commission_rate_override}%`}
        />
      )}
      {partner.total_earned != null && (
        <InfoRow
          label="Total Earned"
          value={<Money value={partner.total_earned} />}
        />
      )}
    </div>
  );
}

function PaymentTab({ partner }: { partner: Partner }) {
  return (
    <div className="border rounded-xl p-4 space-y-0" style={PANEL}>
      <InfoRow label="Payment Method" value={partner.payment_method} />
      <InfoRow label="Bank Name" value={partner.bank_name} />
      <InfoRow label="Account Number" value={partner.bank_account_number} />
      <InfoRow label="Account Holder" value={partner.bank_account_holder} />
    </div>
  );
}

function ReferralsTab({ partnerId }: { partnerId: string }) {
  const [referrals, setReferrals] = useState<PartnerReferral[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    partnersApi
      .listReferrals(partnerId)
      .then((d) => setReferrals(d.referrals))
      .catch(() => setReferrals([]))
      .finally(() => setIsLoading(false));
  }, [partnerId]);

  if (isLoading)
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="animate-spin text-[var(--bz-accent)]" />
      </div>
    );
  if (referrals.length === 0)
    return (
      <div className="flex flex-col items-center py-12 gap-2 text-[var(--bz-text-3)]">
        <Handshake size={32} />
        <p className="text-sm">No referrals yet</p>
      </div>
    );

  return (
    <div className="border rounded-xl overflow-hidden" style={PANEL}>
      <table className="w-full">
        <thead>
          <tr className="border-b border-[var(--bz-border)]">
            <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
              Client
            </th>
            <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
              Practice
            </th>
            <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
              Commission
            </th>
            <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
              Status
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--bz-border)]">
          {referrals.map((r) => {
            const cs =
              COMMISSION_STATUS_STYLES[r.commission_status] || NEUTRAL_CHIP;
            return (
              <tr key={r.id}>
                <td className="px-4 py-3 text-sm text-[var(--bz-text-1)]">
                  {r.referred_client_name ||
                    (r.referred_client_id
                      ? `Client ${r.referred_client_id.substring(0, 8)}…`
                      : "—")}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--bz-text-2)]">
                  {r.practice_type_name || "—"}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--bz-text-1)]">
                  {r.commission_amount != null ? (
                    <Money value={r.commission_amount} />
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-4 py-3">
                  <span
                    className="inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium capitalize"
                    style={cs}
                  >
                    {r.commission_status.replace(/_/g, " ")}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CommissionsTab({ partnerId }: { partnerId: string }) {
  const [commissions, setCommissions] = useState<PartnerCommission[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    partnersApi
      .listCommissions(partnerId)
      .then((d) => setCommissions(d.commissions))
      .catch(() => setCommissions([]))
      .finally(() => setIsLoading(false));
  }, [partnerId]);

  if (isLoading)
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="animate-spin text-[var(--bz-accent)]" />
      </div>
    );
  if (commissions.length === 0)
    return (
      <div className="flex flex-col items-center py-12 gap-2 text-[var(--bz-text-3)]">
        <BarChart3 size={32} />
        <p className="text-sm">No commissions yet</p>
      </div>
    );

  return (
    <div className="border rounded-xl overflow-hidden" style={PANEL}>
      <table className="w-full">
        <thead>
          <tr className="border-b border-[var(--bz-border)]">
            <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
              Practice
            </th>
            <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
              Gross
            </th>
            <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
              Net
            </th>
            <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
              Status
            </th>
            <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
              Date
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--bz-border)]">
          {commissions.map((c) => {
            const cs = COMMISSION_STATUS_STYLES[c.status] || NEUTRAL_CHIP;
            return (
              <tr key={c.id}>
                <td className="px-4 py-3 text-sm text-[var(--bz-text-1)]">
                  {c.practice_type_name ||
                    (c.practice_id
                      ? `Practice ${c.practice_id.substring(0, 8)}…`
                      : "—")}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--bz-text-1)]">
                  <Money value={c.gross_amount} />
                </td>
                <td className="px-4 py-3 text-sm text-[var(--bz-text-1)]">
                  <Money value={c.net_amount} />
                </td>
                <td className="px-4 py-3">
                  <span
                    className="inline-flex items-center px-2 py-0.5 rounded border text-xs font-medium"
                    style={cs}
                  >
                    {c.status.replace(/_/g, " ")}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-[var(--bz-text-3)]">
                  {new Date(c.created_at).toLocaleDateString()}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function AuditTab({ partnerId }: { partnerId: string }) {
  const [auditEntries, setAuditEntries] = useState<AuditLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    partnersApi
      .listAuditLog(partnerId)
      .then((entries) => setAuditEntries(entries))
      .catch(() => setError("Failed to load audit log"))
      .finally(() => setIsLoading(false));
  }, [partnerId]);

  if (isLoading)
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="animate-spin text-[var(--bz-accent)]" />
      </div>
    );
  if (error)
    return (
      <div
        className="flex items-center gap-3 p-4 border rounded-xl"
        style={DANGER_STRIP}
      >
        <AlertCircle size={16} />
        <span className="text-sm">{error}</span>
      </div>
    );
  if (auditEntries.length === 0)
    return (
      <div className="flex flex-col items-center py-12 gap-2 text-[var(--bz-text-3)]">
        <FileText size={32} />
        <p className="text-sm">No audit log entries yet</p>
      </div>
    );

  return (
    <div className="border rounded-xl overflow-hidden" style={PANEL}>
      <table className="w-full">
        <thead>
          <tr className="border-b border-[var(--bz-border)]">
            <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
              Action
            </th>
            <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase hidden md:table-cell">
              Actor
            </th>
            <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
              Reason
            </th>
            <th className="text-left px-4 py-3 text-xs font-medium text-[var(--bz-text-3)] uppercase">
              Date
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--bz-border)]">
          {auditEntries.map((entry) => (
            <tr key={entry.id}>
              <td className="px-4 py-3 text-sm font-medium text-[var(--bz-text-1)] capitalize">
                {entry.action.replace(/_/g, " ")}
              </td>
              <td className="px-4 py-3 text-xs text-[var(--bz-text-3)] hidden md:table-cell font-mono">
                {entry.actor_user_id
                  ? entry.actor_user_id.substring(0, 8) + "…"
                  : "—"}
              </td>
              <td className="px-4 py-3 text-sm text-[var(--bz-text-2)]">
                {entry.reason || (
                  <span className="text-[var(--bz-text-3)] italic">—</span>
                )}
              </td>
              <td className="px-4 py-3 text-sm text-[var(--bz-text-3)]">
                {new Date(entry.at).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PartnerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { success: toastSuccess, error: toastError } = useToast();

  // CRIT-8: partner IDs are UUIDs (strings). Number(uuid) → NaN → every fetch fails.
  const partnerId = params?.id ? String(params.id) : "";
  const [partner, setPartner] = useState<Partner | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("profile");
  const [isActioning, setIsActioning] = useState(false);

  const loadPartner = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await partnersApi.getPartner(partnerId);
      setPartner(data);
    } catch (err) {
      logger.error(
        "Failed to load partner",
        { component: "PartnerDetailPage" },
        err as Error,
      );
      setError("Failed to load partner. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }, [partnerId]);

  useEffect(() => {
    loadPartner();
  }, [loadPartner]);

  const handleActivate = async () => {
    if (!partner) return;
    setIsActioning(true);
    try {
      await partnersApi.activatePartner(partnerId);
      toastSuccess("Partner activated — welcome email sent");
      await loadPartner();
    } catch (err) {
      toastError("Failed to activate partner");
    } finally {
      setIsActioning(false);
    }
  };

  const handleDeactivate = async () => {
    if (!partner) return;
    setIsActioning(true);
    try {
      await partnersApi.deactivatePartner(partnerId);
      toastSuccess("Partner deactivated");
      await loadPartner();
    } catch (err) {
      toastError("Failed to deactivate partner");
    } finally {
      setIsActioning(false);
    }
  };

  const handleReassign = async () => {
    const newUserId = window.prompt(
      "Enter team member user ID (UUID) to assign to:",
    );
    if (!newUserId?.trim()) return;
    const reason = window.prompt("Reason for reassignment (required):");
    if (!reason?.trim()) return;
    setIsActioning(true);
    try {
      await partnersApi.reassignPartner(partnerId, {
        new_user_id: newUserId.trim(),
        reason: reason.trim(),
      });
      toastSuccess("Partner reassigned");
      await loadPartner();
    } catch (err) {
      toastError("Failed to reassign partner");
    } finally {
      setIsActioning(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 size={32} className="animate-spin text-[var(--bz-accent)]" />
      </div>
    );
  }

  if (error || !partner) {
    return (
      <div className="flex flex-col items-center gap-4 py-16">
        <AlertCircle size={32} className="text-[var(--state-danger)]" />
        <p className="text-[var(--bz-text-2)]">
          {error || "Partner not found"}
        </p>
        <Button onClick={loadPartner} variant="outline" size="sm">
          <RefreshCw size={14} className="mr-1" /> Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/partners">
            <Button
              variant="ghost"
              size="sm"
              className="text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)]"
            >
              <ArrowLeft size={16} className="mr-1" />
              Partners
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold text-[var(--bz-text-1)]">
              {partner.full_name}
            </h1>
            <p className="text-sm text-[var(--bz-text-3)]">{partner.email}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Status actions */}
          {partner.onboarding_status === "pending_approval" && (
            <Button
              size="sm"
              disabled={isActioning}
              onClick={handleActivate}
              className="border text-[var(--state-success)]"
              style={{
                background:
                  "color-mix(in srgb, var(--state-success) 12%, transparent)",
                borderColor:
                  "color-mix(in srgb, var(--state-success) 30%, transparent)",
              }}
            >
              {isActioning ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <CheckCircle size={14} className="mr-1" />
              )}
              Activate
            </Button>
          )}
          {partner.onboarding_status === "active" && (
            <Button
              size="sm"
              variant="outline"
              disabled={isActioning}
              onClick={handleDeactivate}
              className="text-[var(--state-danger)]"
              style={{
                borderColor:
                  "color-mix(in srgb, var(--state-danger) 30%, transparent)",
                background:
                  "color-mix(in srgb, var(--state-danger) 12%, transparent)",
              }}
            >
              {isActioning ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <XCircle size={14} className="mr-1" />
              )}
              Deactivate
            </Button>
          )}
          {api.isAdmin?.() && (
            <Button
              size="sm"
              variant="outline"
              disabled={isActioning}
              onClick={handleReassign}
            >
              {isActioning ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Settings size={14} className="mr-1" />
              )}
              Reassign
            </Button>
          )}
          <Button
            size="sm"
            variant="outline"
            onClick={() => router.push(`/partners/${partnerId}/edit`)}
          >
            <Edit size={14} className="mr-1" />
            Edit
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div
        className="flex gap-1 border rounded-xl p-1 overflow-x-auto"
        style={PANEL}
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg whitespace-nowrap transition-colors ${
              activeTab === tab.id
                ? "bg-[var(--surface-selected)] text-[var(--bz-text-1)]"
                : "text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)] hover:bg-[var(--bz-glass-rim)]"
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "profile" && <ProfileTab partner={partner} />}
      {activeTab === "fiscal" && <FiscalTab partner={partner} />}
      {activeTab === "payment" && <PaymentTab partner={partner} />}
      {activeTab === "referrals" && <ReferralsTab partnerId={partnerId} />}
      {activeTab === "commissions" && <CommissionsTab partnerId={partnerId} />}
      {activeTab === "audit" && <AuditTab partnerId={partnerId} />}
    </div>
  );
}
