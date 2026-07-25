"use client";

/**
 * Partner Referrals — every client the partner has referred.
 *
 * WS3 final slice (GARUDA Day Edition, 2026-07-26): day-theme token
 * alignment. Masthead = copper rule + serif (--font-serif) in --tx-pure;
 * table on --bz-card + --bz-border hairlines with the concept .panel
 * shadow; rows --tx-primary with --bz-card-hover hover (was text-white /
 * text-gray-400 + white/5-10 dark surfaces). Referral process_status is a
 * free-form backend vocabulary, so it stays plain token-colored text (the
 * shared StatusBadge would fall back to its "None" label on unknown
 * values). No hardcoded hexes.
 */

import { useEffect, useState } from "react";
import {
  getMyReferrals,
  type PartnerReferral,
} from "@/lib/api/partners/partners";

export default function PartnerReferralsPage() {
  const [referrals, setReferrals] = useState<PartnerReferral[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMyReferrals()
      .then((data) => setReferrals(Array.isArray(data) ? data : []))
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : String(e)),
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading)
    return <div className="p-6 text-[var(--tx-secondary)]">Loading...</div>;
  if (error)
    return (
      <div className="p-6" style={{ color: "var(--state-danger)" }}>
        Error: {error}
      </div>
    );

  return (
    <div className="p-6 space-y-6">
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
          My Referrals
        </h1>
      </section>

      {referrals.length === 0 ? (
        <p className="text-[var(--tx-secondary)] text-sm">
          No referrals found.
        </p>
      ) : (
        <div
          className="overflow-x-auto rounded-xl border"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
            boxShadow: "0 14px 34px rgba(22, 33, 58, 0.07)",
          }}
        >
          <table className="w-full text-sm text-left">
            <thead className="text-[var(--tx-secondary)]">
              <tr>
                <th className="px-4 py-2">Client</th>
                <th className="px-4 py-2">Service Type</th>
                <th className="px-4 py-2">Process Status</th>
                <th className="px-4 py-2">Referred At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--bz-border)]">
              {referrals.map((r) => (
                <tr
                  key={r.id}
                  className="text-[var(--tx-primary)] hover:bg-[var(--bz-card-hover)]"
                >
                  <td className="px-4 py-2">{r.client_display ?? "—"}</td>
                  <td className="px-4 py-2">
                    {r.service_type ?? r.practice_type_name ?? "—"}
                  </td>
                  <td className="px-4 py-2">{r.process_status ?? r.status}</td>
                  <td className="px-4 py-2">
                    {new Date(r.referred_at ?? r.created_at).toLocaleDateString(
                      "id-ID",
                      {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                      },
                    )}
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
