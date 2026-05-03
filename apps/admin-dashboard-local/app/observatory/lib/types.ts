/**
 * TypeScript types mirroring Pydantic models in
 * apps/cell-observatory-collector/cell_observatory/models.py.
 *
 * Keep these in sync with the source Python models — drift is a known risk.
 */

export type ClassificationLabel = 'normal' | 'anomaly' | 'critical' | 'uncertain';
export type LabelDiff = 'agree' | 'disagree';
export type ClassifierSelf = 'green' | 'yellow' | 'red';

/**
 * Compact pulse event row from /api/observatory/pulse list endpoint.
 * Mirrors the SELECT projection in storage._fetchall, NOT the full
 * payload_json.
 */
export interface PulseEvent {
  outbox_id: number;
  cell_id: string;
  pulse_id: string;
  pulse_timestamp: number; // unix ms
  classifier_self: ClassifierSelf;
}

/**
 * Full pulse event detail from /api/observatory/pulse/{outbox_id} (TBD endpoint).
 * Includes payload_json + reception metadata.
 */
export interface PulseEventDetail extends PulseEvent {
  cell_kind: string;
  phase: string;
  payload_json: string;
  received_at: number;
  received_lag_ms: number;
}

/**
 * Persisted classification result from MiniMax M2 (mirror of
 * Python ClassificationResult).
 */
export interface PulseClassification {
  outbox_id: number;
  classified_at: number;
  label: ClassificationLabel;
  confidence: number;
  reasoning: string;
  label_diff: LabelDiff;
  cost_usd: number;
}

/**
 * Anomaly hot-list entry: classification joined with cell_id + pulse_timestamp
 * from /api/observatory/anomalies endpoint.
 */
export interface AnomalyEntry extends PulseClassification {
  cell_id: string;
  pulse_timestamp: number;
}

/**
 * Daily rollup row from /api/observatory/rollup.
 * Mirror of Python pulse_daily_rollup table.
 */
export interface DailyRollup {
  day: string; // YYYY-MM-DD WITA
  cell_id: string;
  n_pulse: number;
  n_self_green: number;
  n_self_yellow: number;
  n_self_red: number;
  n_classified: number;
  n_anomaly: number;
  n_critical: number;
  n_disagree: number;
  cost_usd: number;
}

/**
 * Cost summary from /api/observatory/cost.
 * total_usd may be null if no classifications yet — convert to 0 in UI.
 */
export interface CostSummary {
  total_usd: number;
  calls: number;
  alert_threshold_usd: number;
}

/**
 * Health response from /api/observatory/health.
 */
export interface HealthResponse {
  alive: boolean;
  uptime_s: number;
  events_total: number;
  events_24h: number;
}
