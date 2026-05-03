'use client';

import { useState } from 'react';
import { usePrimeNexus } from '@/contexts/PrimeNexusContext';
import { VerdictBadge } from './VerdictBadge';

type Step = 'review' | 'investor' | 'confirm';

export function DealFlowWizard({ onClose }: { onClose: () => void }) {
  const { analysis } = usePrimeNexus();
  const [step, setStep] = useState<Step>('review');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [nationality, setNationality] = useState('');
  const [loading, setLoading] = useState(false);
  const [proposalLink, setProposalLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  if (!analysis || !analysis.verdict) return null;

  const handleCreate = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/prime/v2/proposal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lat: analysis.coordinates.lat,
          lng: analysis.coordinates.lng,
          zone_code: analysis.zone?.zone_code || '',
          zone_name: analysis.zone?.zone_name || '',
          kbli_code: analysis.kbli?.code || null,
          verdict_label: analysis.verdict?.label ?? '',
          verdict_score: analysis.verdict?.score ?? 0,
          analysis_snapshot: analysis,
          investor_name: name || null,
          investor_email: email || null,
          investor_nationality: nationality || null,
        }),
      });
      const data = await res.json();
      if (data.token) {
        setProposalLink(`${window.location.origin}/prime/proposal/${data.token}`);
        setStep('confirm');
      }
    } catch {
      // Silent fail
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (proposalLink) {
      navigator.clipboard.writeText(proposalLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-96 max-h-[80vh] overflow-y-auto rounded-2xl bg-black/95 border border-white/10 shadow-2xl">
        {/* Header */}
        <div className="px-5 py-4 border-b border-white/10 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">
            {step === 'review' && 'Review Analysis'}
            {step === 'investor' && 'Investor Details'}
            {step === 'confirm' && 'Proposal Ready'}
          </h2>
          <button onClick={onClose} className="text-slate-500 hover:text-white text-lg" aria-label="Close wizard">
            &times;
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          {/* Step 1: Review */}
          {step === 'review' && (
            <>
              <VerdictBadge
                verdict={analysis.verdict?.label ?? 'YELLOW'}
                score={analysis.verdict?.score ?? 0}
              />
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-lg bg-white/5 p-2">
                  <div className="text-slate-500">Zone</div>
                  <div className="text-white font-medium">
                    {String(analysis.zone?.zone_code ?? '—')}
                  </div>
                </div>
                <div className="rounded-lg bg-white/5 p-2">
                  <div className="text-slate-500">KBLI</div>
                  <div className="text-white font-medium">{String(analysis.kbli?.code ?? '—')}</div>
                </div>
                <div className="rounded-lg bg-white/5 p-2">
                  <div className="text-slate-500">Latitude</div>
                  <div className="text-white font-medium">
                    {analysis.coordinates.lat.toFixed(4)}
                  </div>
                </div>
                <div className="rounded-lg bg-white/5 p-2">
                  <div className="text-slate-500">Longitude</div>
                  <div className="text-white font-medium">
                    {analysis.coordinates.lng.toFixed(4)}
                  </div>
                </div>
              </div>
              <button
                onClick={() => setStep('investor')}
                className="w-full py-2.5 rounded-xl bg-accent-warm hover:bg-[#c4744a] text-white text-sm font-semibold transition-colors"
              >
                Next: Investor Details
              </button>
            </>
          )}

          {/* Step 2: Investor info */}
          {step === 'investor' && (
            <>
              <p className="text-xs text-slate-400">
                Optional — leave blank to create without investor details.
              </p>
              <div className="space-y-3">
                <input
                  type="text"
                  placeholder="Investor Name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-slate-600 focus:border-accent-warm focus:outline-none"
                />
                <input
                  type="email"
                  placeholder="Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-slate-600 focus:border-accent-warm focus:outline-none"
                />
                <input
                  type="text"
                  placeholder="Nationality"
                  value={nationality}
                  onChange={(e) => setNationality(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-slate-600 focus:border-accent-warm focus:outline-none"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setStep('review')}
                  className="flex-1 py-2.5 rounded-xl border border-white/10 text-slate-400 hover:text-white text-sm transition-colors"
                >
                  Back
                </button>
                <button
                  onClick={handleCreate}
                  disabled={loading}
                  className="flex-1 py-2.5 rounded-xl bg-accent-warm hover:bg-[#c4744a] text-white text-sm font-semibold transition-colors disabled:opacity-50"
                >
                  {loading ? 'Creating...' : 'Create Proposal'}
                </button>
              </div>
            </>
          )}

          {/* Step 3: Confirm */}
          {step === 'confirm' && proposalLink && (
            <>
              <div className="text-center py-2">
                <span className="text-3xl block mb-2">&#x2705;</span>
                <p className="text-sm font-medium text-white">Proposal Created</p>
                <p className="text-xs text-slate-500 mt-1">
                  Share this link with your investor (valid 7 days)
                </p>
              </div>
              <div className="flex items-center gap-2 bg-white/5 rounded-lg p-2">
                <input
                  type="text"
                  readOnly
                  value={proposalLink}
                  className="flex-1 bg-transparent text-xs text-accent-warm outline-none truncate"
                />
                <button
                  onClick={handleCopy}
                  className="shrink-0 px-3 py-1.5 rounded-lg bg-accent-warm hover:bg-[#c4744a] text-white text-xs font-medium transition-colors"
                >
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
              <button
                onClick={onClose}
                className="w-full py-2.5 rounded-xl border border-white/10 text-slate-400 hover:text-white text-sm transition-colors"
              >
                Close
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
