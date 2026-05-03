'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { CTAHandoff } from '@balizero/core';

interface ProposalData {
  token: string;
  lat: number;
  lng: number;
  zone_code: string;
  zone_name: string;
  verdict_label: string;
  verdict_score: number;
  kbli_code: string | null;
  investor_name: string | null;
  status: string;
  created_at: string;
  expires_at: string;
  analysis: Record<string, unknown>;
  error?: string;
}

const VERDICT_COLORS: Record<string, string> = {
  GREEN: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  YELLOW: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  RED: 'bg-red-500/20 text-red-300 border-red-500/30',
};

export default function ProposalPage() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<ProposalData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    fetch(`/api/prime/v2/proposal/${token}`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0c0c0e] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-slate-700 border-t-[#d4845a] rounded-full animate-spin" />
      </div>
    );
  }

  if (!data || data.error === 'not_found') {
    return (
      <div className="min-h-screen bg-[#0c0c0e] flex items-center justify-center">
        <div className="text-center">
          <span className="text-4xl block mb-3">&#x1F50D;</span>
          <h1 className="text-lg font-semibold text-white">Proposal Not Found</h1>
          <p className="text-sm text-slate-500 mt-1">
            This proposal may have expired or been removed.
          </p>
        </div>
      </div>
    );
  }

  if (data.error === 'expired') {
    return (
      <div className="min-h-screen bg-[#0c0c0e] flex items-center justify-center">
        <div className="text-center">
          <span className="text-4xl block mb-3">&#x23F3;</span>
          <h1 className="text-lg font-semibold text-white">Proposal Expired</h1>
          <p className="text-sm text-slate-500 mt-1">This proposal is no longer available.</p>
        </div>
      </div>
    );
  }

  const daysLeft = data.expires_at
    ? Math.max(0, Math.ceil((new Date(data.expires_at).getTime() - Date.now()) / 86400000))
    : 0;

  const verdictClass = VERDICT_COLORS[data.verdict_label] || VERDICT_COLORS.YELLOW;

  return (
    <div
      data-theme="operative-light"
      className="min-h-screen bg-[#0c0c0e] text-white"
    >
      <div className="max-w-lg mx-auto px-4 py-8 pb-28 space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent-warm/20 text-accent-warm text-xs font-medium">
            Bali Zero Investment Proposal
          </div>
          <h1 className="text-xl font-bold">
            Zone {data.zone_code}
            {data.zone_name && (
              <span className="text-slate-400 font-normal text-base ml-2">{data.zone_name}</span>
            )}
          </h1>
          {data.investor_name && (
            <p className="text-sm text-slate-400">Prepared for {data.investor_name}</p>
          )}
        </div>

        {/* Verdict */}
        <div className="flex items-center justify-center gap-4">
          <div
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl border ${verdictClass}`}
          >
            <span className="text-2xl font-bold">{data.verdict_score}</span>
            <div>
              <div className="text-xs font-semibold">{data.verdict_label}</div>
              <div className="text-[10px] opacity-70">Investment Score</div>
            </div>
          </div>
        </div>

        {/* Details */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl bg-white/5 border border-white/10 p-3">
            <div className="text-[10px] text-slate-500 uppercase tracking-wide">Location</div>
            <div className="text-sm font-medium mt-1">
              {data.lat.toFixed(4)}, {data.lng.toFixed(4)}
            </div>
          </div>
          <div className="rounded-xl bg-white/5 border border-white/10 p-3">
            <div className="text-[10px] text-slate-500 uppercase tracking-wide">KBLI Code</div>
            <div className="text-sm font-medium mt-1">{data.kbli_code || '—'}</div>
          </div>
          <div className="rounded-xl bg-white/5 border border-white/10 p-3">
            <div className="text-[10px] text-slate-500 uppercase tracking-wide">Created</div>
            <div className="text-sm font-medium mt-1">{data.created_at?.slice(0, 10)}</div>
          </div>
          <div className="rounded-xl bg-white/5 border border-white/10 p-3">
            <div className="text-[10px] text-slate-500 uppercase tracking-wide">Expires In</div>
            <div className={`text-sm font-medium mt-1 ${daysLeft <= 2 ? 'text-red-400' : ''}`}>
              {daysLeft} days
            </div>
          </div>
        </div>

        <p className="text-[10px] text-slate-600 text-center">
          Powered by Bali Zero Prime Intelligence
        </p>
      </div>
      <CTAHandoff
        source="prime-proposal"
        sessionId={data.token}
        payload={{
          zone_code: data.zone_code,
          zone_name: data.zone_name,
          verdict: data.verdict_label,
          score: data.verdict_score,
          kbli: data.kbli_code ?? undefined,
        }}
      />
    </div>
  );
}
