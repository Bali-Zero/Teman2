/**
 * Typed fetch wrapper for the Cell Observatory loopback API at 127.0.0.1:17891.
 * Uses X-Observatory-Key header authentication.
 */
import {
  PulseEvent,
  AnomalyEntry,
  DailyRollup,
  CostSummary,
  HealthResponse,
} from './types';

const BASE = process.env.NEXT_PUBLIC_OBSERVATORY_BASE ?? 'http://127.0.0.1:17891';
const KEY = process.env.NEXT_PUBLIC_OBSERVATORY_API_KEY ?? '';

async function fetchAuth<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    headers: { 'X-Observatory-Key': KEY },
    cache: 'no-store',
  });
  if (!r.ok) throw new Error(`${path}: ${r.status} ${r.statusText}`);
  return r.json();
}

export const observatoryClient = {
  /**
   * GET /api/observatory/health — collector liveness + event count
   */
  health: (): Promise<HealthResponse> =>
    fetchAuth<HealthResponse>('/api/observatory/health'),

  /**
   * GET /api/observatory/pulse?cell_id=&since=&limit=
   * Lists raw pulse events ordered by pulse_timestamp DESC.
   */
  pulses: (cellId?: string, since?: string): Promise<{ items: PulseEvent[] }> => {
    const params = new URLSearchParams({
      ...(cellId && { cell_id: cellId }),
      ...(since && { since }),
      limit: '500',
    });
    return fetchAuth<{ items: PulseEvent[] }>(
      `/api/observatory/pulse?${params.toString()}`
    );
  },

  /**
   * GET /api/observatory/anomalies?since=&label=
   * Lists anomaly/critical/uncertain classifications with cell_id + pulse_timestamp.
   * Note: response items do NOT include classified_at (PR-4 Task 4.1 known mismatch
   * with type definition — handle missing field gracefully in UI).
   */
  anomalies: (since?: string): Promise<{ items: AnomalyEntry[] }> => {
    const params = new URLSearchParams({
      ...(since && { since }),
    });
    return fetchAuth<{ items: AnomalyEntry[] }>(
      `/api/observatory/anomalies?${params.toString()}`
    );
  },

  /**
   * GET /api/observatory/rollup?day=YYYY-MM-DD&cell_id=
   * Returns daily aggregates per cell.
   */
  rollup: (day: string, cellId?: string): Promise<{ items: DailyRollup[] }> => {
    const params = new URLSearchParams({
      day,
      ...(cellId && { cell_id: cellId }),
    });
    return fetchAuth<{ items: DailyRollup[] }>(
      `/api/observatory/rollup?${params.toString()}`
    );
  },

  /**
   * GET /api/observatory/cost?since=
   * Returns total cost + call count + threshold.
   * Note: total_usd may be 0.0 (server coerces null → 0.0 server-side).
   */
  cost: (since?: string): Promise<CostSummary> => {
    const params = new URLSearchParams({
      ...(since && { since }),
    });
    return fetchAuth<CostSummary>(
      `/api/observatory/cost?${params.toString()}`
    );
  },
};
