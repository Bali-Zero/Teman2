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
  ChevronRight,
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import * as partnersApi from "@/lib/api/partners/partners";
import type { Partner, PartnerReferral, PartnerCommission } from "@/lib/api/partners/partners";

type TabId = "profile" | "fiscal" | "payment" | "referrals" | "commissions" | "audit";

const TABS: { id: TabId; label: string; icon: React.ReactNode }[] = [
  { id: "profile", label: "Profile", icon: <User size={14} /> },
  { id: "fiscal", label: "Fiscal", icon: <CreditCard size={14} /> },
  { id: "payment", label: "Payment", icon: <Building2 size={14} /> },
  { id: "referrals", label: "Referrals", icon: <Handshake size={14} /> },
  { id: "commissions", label: "Commissions", icon: <BarChart3 size={14} /> },
  { id: "audit", label: "Audit", icon: <FileText size={14} /> },
];

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  pending_review: { bg: "bg-amber-500/20", text: "text-amber-400", label: "Pending Review" },
  active: { bg: "bg-green-500/20", text: "text-green-400", label: "Active" },
  inactive: { bg: "bg-gray-500/20", text: "text-gray-400", label: "Inactive" },
  suspended: { bg: "bg-red-500/20", text: "text-red-400", label: "Suspended" },
};

const COMMISSION_STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  pending_approval: { bg: "bg-amber-500/20", text: "text-amber-400" },
  approved: { bg: "bg-blue-500/20", text: "text-blue-400" },
  ready_to_pay: { bg: "bg-purple-500/20", text: "text-purple-400" },
  paid: { bg: "bg-green-500/20", text: "text-green-400" },
  clawback_pending: { bg: "bg-orange-500/20", text: "text-orange-400" },
  clawed_back: { bg: "bg-red-500/20", text: "text-red-400" },
  waived: { bg: "bg-gray-500/20", text: "text-gray-400" },
};

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between py-2 border-b border-zinc-800 last:border-0">
      <span className="text-sm text-zinc-500 min-w-36">{label}</span>
      <span className="text-sm text-zinc-200 text-right">{value || <span className="text-zinc-600 italic">—</span>}</span>
    </div>
  );
}

function formatIDR(amount: number): string {
  return new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(amount);
}

function ProfileTab({ partner }: { partner: Partner }) {
  const statusStyle = STATUS_STYLES[partner.onboarding_status] || STATUS_STYLES.inactive;
  return (
    <div className="space-y-4">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-0">
        <InfoRow label="Full Name" value={partner.full_name} />
        <InfoRow label="Email" value={<span className="flex items-center gap-1.5"><Mail size={12} className="text-zinc-500" />{partner.email}</span>} />
        <InfoRow label="Phone" value={partner.phone && <span className="flex items-center gap-1.5"><Phone size={12} className="text-zinc-500" />{partner.phone}</span>} />
        <InfoRow label="WhatsApp" value={partner.whatsapp} />
        <InfoRow label="Nationality" value={partner.nationality} />
        <InfoRow label="Company" value={partner.company_name} />
        <InfoRow label="Work Role" value={partner.work_role} />
        <InfoRow label="Status" value={
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusStyle.bg} ${statusStyle.text}`}>
            {statusStyle.label}
          </span>
        } />
        <InfoRow label="Commission Tier" value={<span className="capitalize">{partner.commission_tier}</span>} />
        <InfoRow label="Assigned To" value={partner.assigned_to} />
        <InfoRow label="PDP Consent" value={partner.pdp_consent ? (
          <span className="flex items-center gap-1 text-green-400"><CheckCircle size={12} /> Yes</span>
        ) : (
          <span className="flex items-center gap-1 text-red-400"><XCircle size={12} /> No</span>
        )} />
        {partner.pdp_consent_at && <InfoRow label="Consent Date" value={new Date(partner.pdp_consent_at).toLocaleDateString()} />}
        <InfoRow label="Welcome Email" value={partner.welcome_email_sent_at ? new Date(partner.welcome_email_sent_at).toLocaleDateString() : "Not sent"} />
      </div>
      {partner.notes && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <p className="text-xs text-zinc-500 mb-1 uppercase tracking-wide font-medium">Notes</p>
          <p className="text-sm text-zinc-300 whitespace-pre-wrap">{partner.notes}</p>
        </div>
      )}
    </div>
  );
}

function FiscalTab({ partner }: { partner: Partner }) {
  const taxLabels: Record<string, string> = {
    tbd: "TBD — not yet determined",
    withheld_tarif_umum: "Withheld — Tarif Umum",
    withheld_tarif_final: "Withheld — Tarif Final",
    exempt: "Exempt",
  };
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-0">
      <InfoRow label="NPWP (Tax ID)" value={partner.tax_id} />
      <InfoRow label="Withholding Category" value={taxLabels[partner.tax_withholding_category] || partner.tax_withholding_category} />
      {partner.commission_rate_override != null && (
        <InfoRow label="Rate Override" value={`${partner.commission_rate_override}%`} />
      )}
      {partner.total_earned != null && (
        <InfoRow label="Total Earned" value={formatIDR(partner.total_earned)} />
      )}
    </div>
  );
}

function PaymentTab({ partner }: { partner: Partner }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-0">
      <InfoRow label="Payment Method" value={partner.payment_method} />
      <InfoRow label="Bank Name" value={partner.bank_name} />
      <InfoRow label="Account Number" value={partner.bank_account_number} />
      <InfoRow label="Account Holder" value={partner.bank_account_name} />
    </div>
  );
}

function ReferralsTab({ partnerId }: { partnerId: number }) {
  const [referrals, setReferrals] = useState<PartnerReferral[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    partnersApi.listReferrals(partnerId)
      .then((d) => setReferrals(d.referrals))
      .catch(() => setReferrals([]))
      .finally(() => setIsLoading(false));
  }, [partnerId]);

  if (isLoading) return <div className="flex justify-center py-12"><Loader2 className="animate-spin text-amber-400" /></div>;
  if (referrals.length === 0) return (
    <div className="flex flex-col items-center py-12 gap-2 text-zinc-600">
      <Handshake size={32} />
      <p className="text-sm">No referrals yet</p>
    </div>
  );

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-zinc-800">
            <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">Client</th>
            <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">Practice</th>
            <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">Commission</th>
            <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800">
          {referrals.map((r) => {
            const cs = COMMISSION_STATUS_STYLES[r.commission_status] || { bg: "bg-gray-500/20", text: "text-gray-400" };
            return (
              <tr key={r.id}>
                <td className="px-4 py-3 text-sm text-zinc-300">{r.referred_client_name || `Client #${r.referred_client_id}`}</td>
                <td className="px-4 py-3 text-sm text-zinc-400">{r.practice_type_name || "—"}</td>
                <td className="px-4 py-3 text-sm text-zinc-300">
                  {r.commission_amount != null ? formatIDR(r.commission_amount) : "—"}
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize ${cs.bg} ${cs.text}`}>
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

function CommissionsTab({ partnerId }: { partnerId: number }) {
  const [commissions, setCommissions] = useState<PartnerCommission[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    partnersApi.listCommissions(partnerId)
      .then((d) => setCommissions(d.commissions))
      .catch(() => setCommissions([]))
      .finally(() => setIsLoading(false));
  }, [partnerId]);

  if (isLoading) return <div className="flex justify-center py-12"><Loader2 className="animate-spin text-amber-400" /></div>;
  if (commissions.length === 0) return (
    <div className="flex flex-col items-center py-12 gap-2 text-zinc-600">
      <BarChart3 size={32} />
      <p className="text-sm">No commissions yet</p>
    </div>
  );

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-zinc-800">
            <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">Practice</th>
            <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">Gross</th>
            <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">Net</th>
            <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">Status</th>
            <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase">Date</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800">
          {commissions.map((c) => {
            const cs = COMMISSION_STATUS_STYLES[c.status] || { bg: "bg-gray-500/20", text: "text-gray-400" };
            return (
              <tr key={c.id}>
                <td className="px-4 py-3 text-sm text-zinc-300">{c.practice_type_name || `Practice #${c.practice_id}`}</td>
                <td className="px-4 py-3 text-sm text-zinc-300">{formatIDR(c.gross_amount)}</td>
                <td className="px-4 py-3 text-sm text-zinc-300">{formatIDR(c.net_amount)}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${cs.bg} ${cs.text}`}>
                    {c.status.replace(/_/g, " ")}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-zinc-500">{new Date(c.created_at).toLocaleDateString()}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function AuditTab({ partner }: { partner: Partner }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-0">
      <InfoRow label="Partner ID" value={`#${partner.id}`} />
      <InfoRow label="Created" value={new Date(partner.created_at).toLocaleString()} />
      <InfoRow label="Last Updated" value={partner.updated_at ? new Date(partner.updated_at).toLocaleString() : "—"} />
      <InfoRow label="Welcome Sent" value={partner.welcome_email_sent_at ? new Date(partner.welcome_email_sent_at).toLocaleString() : "Not sent"} />
      <InfoRow label="PDP Consent At" value={partner.pdp_consent_at ? new Date(partner.pdp_consent_at).toLocaleString() : "—"} />
    </div>
  );
}

export default function PartnerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { success: toastSuccess, error: toastError } = useToast();

  const partnerId = params?.id ? Number(params.id) : 0;
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
      logger.error("Failed to load partner", { component: "PartnerDetailPage" }, err as Error);
      setError("Failed to load partner. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }, [partnerId]);

  useEffect(() => { loadPartner(); }, [loadPartner]);

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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 size={32} className="animate-spin text-amber-400" />
      </div>
    );
  }

  if (error || !partner) {
    return (
      <div className="flex flex-col items-center gap-4 py-16">
        <AlertCircle size={32} className="text-red-400" />
        <p className="text-zinc-400">{error || "Partner not found"}</p>
        <Button onClick={loadPartner} variant="outline" size="sm" className="border-zinc-700 text-zinc-300">
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
            <Button variant="ghost" size="sm" className="text-zinc-400 hover:text-zinc-200">
              <ArrowLeft size={16} className="mr-1" />
              Partners
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold text-zinc-100">{partner.full_name}</h1>
            <p className="text-sm text-zinc-500">{partner.email}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Status actions */}
          {partner.onboarding_status === "pending_review" && (
            <Button
              size="sm"
              disabled={isActioning}
              onClick={handleActivate}
              className="bg-green-600 hover:bg-green-700 text-white"
            >
              {isActioning ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle size={14} className="mr-1" />}
              Activate
            </Button>
          )}
          {partner.onboarding_status === "active" && (
            <Button
              size="sm"
              variant="outline"
              disabled={isActioning}
              onClick={handleDeactivate}
              className="border-red-700 text-red-400 hover:bg-red-900/20"
            >
              {isActioning ? <Loader2 size={14} className="animate-spin" /> : <XCircle size={14} className="mr-1" />}
              Deactivate
            </Button>
          )}
          <Button
            size="sm"
            variant="outline"
            onClick={() => router.push(`/partners/${partnerId}/edit`)}
            className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
          >
            <Edit size={14} className="mr-1" />
            Edit
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-zinc-900 border border-zinc-800 rounded-xl p-1 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg whitespace-nowrap transition-colors ${
              activeTab === tab.id
                ? "bg-amber-600 text-white"
                : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
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
      {activeTab === "audit" && <AuditTab partner={partner} />}
    </div>
  );
}
