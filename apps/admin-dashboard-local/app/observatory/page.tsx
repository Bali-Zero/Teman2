'use client';

import { useEffect, useState } from 'react';
import { observatoryClient } from './lib/observatory-client';
import {
  AnomalyEntry,
  DailyRollup,
  CostSummary,
} from './lib/types';
import CellBreakdown from './components/CellBreakdown';
import AnomalyHotList from './components/AnomalyHotList';
import CostLedger from './components/CostLedger';
import DisagreementWatch from './components/DisagreementWatch';

const REFRESH_INTERVAL_MS = 30_000;

export default function ObservatoryPage() {
  const today = new Date().toISOString().slice(0, 10);
  const [rollup, setRollup] = useState<DailyRollup[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyEntry[]>([]);
  const [cost, setCost] = useState<CostSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [rollupResp, anomaliesResp, costResp] = await Promise.all([
          observatoryClient.rollup(today),
          observatoryClient.anomalies(),
          observatoryClient.cost(),
        ]);
        if (cancelled) return;
        setRollup(rollupResp.items);
        setAnomalies(anomaliesResp.items);
        setCost(costResp);
        setError(null);
      } catch (e: unknown) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'Unknown error');
      }
    }

    load();
    const interval = setInterval(load, REFRESH_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [today]);

  return (
    <main className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Cell Pulse Observatory</h1>
      {error && (
        <div className="border border-red-300 bg-red-50 text-red-700 p-3 rounded">
          API error: {error}
        </div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <CellBreakdown rollups={rollup} />
        <CostLedger summary={cost} />
      </div>
      <DisagreementWatch anomalies={anomalies} />
      <AnomalyHotList anomalies={anomalies} />
    </main>
  );
}
