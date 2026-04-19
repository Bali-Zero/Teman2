"use client";

import { useEffect, useState } from "react";

type Rec = {
  id: number;
  endpoint: string;
  current_model: string;
  proposed_model: string;
  estimated_monthly_saving_usd: number;
  quality_tradeoff: string;
  confidence: "low" | "medium" | "high";
  spike_flag: boolean;
  status: string;
};

export default function RecommendationPanel() {
  const [recs, setRecs] = useState<Rec[]>([]);
  const [busy, setBusy] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    setErr(null);
    try {
      const r = await fetch("/api/llm-costs/recommendations");
      if (!r.ok) throw new Error(r.statusText);
      const data = await r.json();
      setRecs(data.rows ?? []);
    } catch (e) {
      setErr(String(e));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function markReviewed(id: number) {
    setBusy(id);
    try {
      await fetch("/api/llm-costs/recommendations", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ id, status: "reviewed" }),
      });
      await load();
    } finally {
      setBusy(null);
    }
  }

  if (err) return <div className="text-red-400">Recommendations error: {err}</div>;

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-200">
        Pending recommendations ({recs.length})
      </h2>
      {recs.length === 0 ? (
        <div className="text-slate-500 text-sm">
          No pending recommendations. Weekly CostAdvisor cron populates these on
          Mondays.
        </div>
      ) : (
        <ul className="space-y-3">
          {recs.map((r) => (
            <li
              key={r.id}
              className="rounded border border-slate-800 bg-slate-950 p-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-mono text-slate-300">{r.endpoint}</span>
                    {r.spike_flag && (
                      <span className="rounded bg-red-900/60 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-red-300">
                        spike
                      </span>
                    )}
                    <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-slate-300">
                      {r.confidence}
                    </span>
                  </div>
                  <div className="mt-1 text-sm text-slate-200">
                    <span className="text-slate-400">{r.current_model}</span>
                    {" → "}
                    <span className="font-semibold">{r.proposed_model}</span>
                    <span className="ml-2 text-emerald-400">
                      ~${Number(r.estimated_monthly_saving_usd).toFixed(2)}/mo
                    </span>
                  </div>
                  <div className="mt-1 text-xs italic text-slate-400">
                    {r.quality_tradeoff}
                  </div>
                </div>
                <button
                  onClick={() => void markReviewed(r.id)}
                  disabled={busy === r.id}
                  className="shrink-0 rounded bg-slate-700 px-3 py-1 text-xs text-slate-100 hover:bg-slate-600 disabled:opacity-50"
                >
                  {busy === r.id ? "…" : "Mark reviewed"}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
