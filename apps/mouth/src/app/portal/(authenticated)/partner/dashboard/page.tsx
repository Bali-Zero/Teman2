"use client";

import { useEffect, useState } from "react";
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
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(n);
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

  if (loading) return <div className="p-6">Loading...</div>;
  if (error) return <div className="p-6 text-red-500">Error: {error}</div>;

  const totalEarned = commissions
    .filter((c) => c.status === "paid")
    .reduce((sum, c) => sum + (c.net_amount ?? 0), 0);
  const totalPending = commissions
    .filter((c) => c.status === "accrued" || c.status === "approved" || c.status === "pending_approval")
    .reduce((sum, c) => sum + (c.net_amount ?? 0), 0);
  const recentReferrals = referrals.slice(0, 5);
  const recentCommissions = commissions.slice(0, 5);

  return (
    <div className="p-6 space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-white">Partner Dashboard</h1>
        {partner && (
          <p className="text-sm text-gray-400 mt-1">
            Welcome, {partner.full_name}
          </p>
        )}
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-lg border border-white/10 bg-white/5 p-5">
          <p className="text-xs text-gray-400 uppercase tracking-wide">Total Earned</p>
          <p className="text-2xl font-bold text-white mt-1">{fmt(totalEarned)}</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/5 p-5">
          <p className="text-xs text-gray-400 uppercase tracking-wide">Pending</p>
          <p className="text-2xl font-bold text-white mt-1">{fmt(totalPending)}</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/5 p-5">
          <p className="text-xs text-gray-400 uppercase tracking-wide">Referral Count</p>
          <p className="text-2xl font-bold text-white mt-1">{referrals.length}</p>
        </div>
      </div>

      {/* Recent referrals */}
      <div>
        <h2 className="text-lg font-medium text-white mb-3">Recent Referrals</h2>
        {recentReferrals.length === 0 ? (
          <p className="text-gray-400 text-sm">No referrals yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left border border-white/10 rounded-lg">
              <thead className="bg-white/5 text-gray-400">
                <tr>
                  <th className="px-4 py-2">Client</th>
                  <th className="px-4 py-2">Service</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Referred At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {recentReferrals.map((r) => (
                  <tr key={r.id} className="text-gray-200">
                    <td className="px-4 py-2">{r.referred_client_name ?? "—"}</td>
                    <td className="px-4 py-2">{r.practice_type_name ?? "—"}</td>
                    <td className="px-4 py-2">{r.status}</td>
                    <td className="px-4 py-2">
                      {new Date(r.created_at).toLocaleDateString("id-ID")}
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
        <h2 className="text-lg font-medium text-white mb-3">Recent Commissions</h2>
        {recentCommissions.length === 0 ? (
          <p className="text-gray-400 text-sm">No commissions yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left border border-white/10 rounded-lg">
              <thead className="bg-white/5 text-gray-400">
                <tr>
                  <th className="px-4 py-2">Date</th>
                  <th className="px-4 py-2">Net Amount</th>
                  <th className="px-4 py-2">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10">
                {recentCommissions.map((c) => (
                  <tr key={c.id} className="text-gray-200">
                    <td className="px-4 py-2">
                      {new Date(c.created_at).toLocaleDateString("id-ID")}
                    </td>
                    <td className="px-4 py-2">{fmt(c.net_amount)}</td>
                    <td className="px-4 py-2">{c.status}</td>
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
