"use client";

/**
 * Partner Dashboard — referral + commission overview.
 *
 * WS3 final slice (GARUDA Day Edition, 2026-07-26): day-theme token
 * alignment, mirroring slices 1-7. Masthead = copper rule + Cormorant serif
 * (--font-serif) in --tx-pure; stat cards + tables read --bz-card /
 * --bz-border with the concept .panel shadow; commission statuses render the
 * shared StatusBadge on --state-* AA tokens; text reads --tx-* tokens
 * (was text-white / text-gray-400 dark utilities + white/5-10 surfaces).
 * No hardcoded hexes.
 */

import { useEffect, useState } from "react";
import { formatIDR } from "@balizero/core/utils";
import { StatusBadge } from "@/components/portal/StatusBadge";
import {
  getMe,
  getMyReferrals,
  getMyCommissions,
  type Partner,
  type PartnerReferral,
  type PartnerCommission,
} from "@/lib/api/partners/partners";

function fmt(n: number | undefined): string {
  if (n == null) return "—";
  return formatIDR(n);
}

// Day surface: token card + concept .panel shadow (soft navy on paper,
// near-invisible on dark). Was border-white/10 + bg-white/5 dark glass.
const CARD_STYLE = {
  background: "var(--bz-card)",
  borderColor: "var(--bz-border)",
  boxShadow: "0 14px 34px rgba(22, 33, 58, 0.07)",
} as const;

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border p-5" style={CARD_STYLE}>
      <p className="text-xs text-[var(--tx-secondary)] uppercase tracking-wide">
        {label}
      </p>
      <p className="text-2xl font-bold text-[var(--tx-pure)] mt-1">{value}</p>
    </div>
  );
}

export default function PartnerDashboardPage() {
  const [partner, setPartner] = useState<Partner | null>(null);
  const [referrals, setReferrals] = useState<PartnerReferral[]>([]);
  const [commissions, setCommissions] = useState<PartnerCommission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [p, r, c] = await Promise.all([
          getMe(),
          getMyReferrals(),
          getMyCommissions(),
        ]);
        setPartner(p);
        setReferrals(Array.isArray(r) ? r : []);
        setCommissions(Array.isArray(c) ? c : []);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading)
    return <div className="p-6 text-[var(--tx-secondary)]">Loading...</div>;
  if (error)
    return (
      <div className="p-6" style={{ color: "var(--state-danger)" }}>
        Error: {error}
      </div>
    );

  const totalEarned = commissions
    .filter((c) => c.status === "paid")
    .reduce((sum, c) => sum + Number(c.net_amount ?? 0), 0);
  const totalPending = commissions
    .filter(
      (c) =>
        c.status === "accrued" ||
        c.status === "approved" ||
        c.status === "pending_approval",
    )
    .reduce((sum, c) => sum + Number(c.net_amount ?? 0), 0);
  const recentReferrals = referrals.slice(0, 5);
  const recentCommissions = commissions.slice(0, 5);

  return (
    <div className="p-6 space-y-8">
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
          Partner Dashboard
        </h1>
        {partner && (
          <p className="text-sm text-[var(--tx-secondary)] mt-1">
            Welcome, {partner.full_name}
          </p>
        )}
      </section>

      {/* Metric cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="Total Earned" value={fmt(totalEarned)} />
        <StatCard label="Pending" value={fmt(totalPending)} />
        <StatCard label="Referral Count" value={String(referrals.length)} />
      </div>

      {/* Recent referrals */}
      <div>
        <h2 className="text-lg font-medium text-[var(--tx-pure)] mb-3">
          Recent Referrals
        </h2>
        {recentReferrals.length === 0 ? (
          <p className="text-[var(--tx-secondary)] text-sm">
            No referrals yet.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-xl border" style={CARD_STYLE}>
            <table className="w-full text-sm text-left">
              <thead className="text-[var(--tx-secondary)]">
                <tr>
                  <th className="px-4 py-2">Client</th>
                  <th className="px-4 py-2">Service</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Referred At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--bz-border)]">
                {recentReferrals.map((r) => (
                  <tr key={r.id} className="text-[var(--tx-primary)]">
                    <td className="px-4 py-2">{r.client_display ?? "—"}</td>
                    <td className="px-4 py-2">
                      {r.service_type ?? r.practice_type_name ?? "—"}
                    </td>
                    <td className="px-4 py-2">
                      {r.process_status ?? r.status}
                    </td>
                    <td className="px-4 py-2">
                      {new Date(
                        r.referred_at ?? r.created_at,
                      ).toLocaleDateString("id-ID")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Recent commissions */}
      <div>
        <h2 className="text-lg font-medium text-[var(--tx-pure)] mb-3">
          Recent Commissions
        </h2>
        {recentCommissions.length === 0 ? (
          <p className="text-[var(--tx-secondary)] text-sm">
            No commissions yet.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-xl border" style={CARD_STYLE}>
            <table className="w-full text-sm text-left">
              <thead className="text-[var(--tx-secondary)]">
                <tr>
                  <th className="px-4 py-2">Date</th>
                  <th className="px-4 py-2">Net Amount</th>
                  <th className="px-4 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--bz-border)]">
                {recentCommissions.map((c) => (
                  <tr key={c.id} className="text-[var(--tx-primary)]">
                    <td className="px-4 py-2">
                      {new Date(c.created_at).toLocaleDateString("id-ID")}
                    </td>
                    <td className="px-4 py-2">{fmt(c.net_amount)}</td>
                    <td className="px-4 py-2">
                      <StatusBadge status={c.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
