"use client";

import { useEffect, useState } from "react";
import { getMyReferrals, type PartnerReferral } from "@/lib/api/partners/partners";

export default function PartnerReferralsPage() {
  const [referrals, setReferrals] = useState<PartnerReferral[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMyReferrals()
      .then((data) => setReferrals(Array.isArray(data) ? data : []))
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : String(e))
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-6">Loading...</div>;
  if (error) return <div className="p-6 text-red-500">Error: {error}</div>;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-semibold text-white">My Referrals</h1>

      {referrals.length === 0 ? (
        <p className="text-gray-400 text-sm">No referrals found.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left border border-white/10 rounded-lg">
            <thead className="bg-white/5 text-gray-400">
              <tr>
                <th className="px-4 py-2">Client</th>
                <th className="px-4 py-2">Service Type</th>
                <th className="px-4 py-2">Process Status</th>
                <th className="px-4 py-2">Referred At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {referrals.map((r) => (
                <tr key={r.id} className="text-gray-200 hover:bg-white/5">
                  <td className="px-4 py-2">{r.referred_client_name ?? "—"}</td>
                  <td className="px-4 py-2">{r.practice_type_name ?? "—"}</td>
                  <td className="px-4 py-2">{r.status}</td>
                  <td className="px-4 py-2">
                    {new Date(r.created_at).toLocaleDateString("id-ID", {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
