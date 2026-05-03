/**
 * AI Insights types
 * Type-safe definitions for AI-generated insights and predictions
 */

/**
 * Historical data structure for AI analysis
 */
export interface HistoricalData {
  cases?: CaseData[];
  revenue?: RevenueData[];
  clients?: ClientData[];
  interactions?: InteractionData[];
  practices?: PracticeData[];
  metrics?: MetricData[];
  efficiency?: number[];
  errorRate?: number[];
  responseTime?: number[];
  currentWorkload?: number;
}

/**
 * Case data structure
 */
export interface CaseData {
  id: string | number;
  status: string;
  created_at: string;
  completed_at?: string;
  priority?: string;
  assigned_to?: string;
  [key: string]: unknown;
}

/**
 * Revenue data structure
 */
export interface RevenueData {
  date: string;
  amount: number;
  currency?: string;
  practice_id?: string | number;
  [key: string]: unknown;
}

/**
 * Client data structure
 */
export interface ClientData {
  id: string | number;
  status: string;
  created_at: string;
  last_interaction_date?: string;
  [key: string]: unknown;
}

/**
 * Interaction data structure
 */
export interface InteractionData {
  id: string | number;
  type: string;
  date: string;
  sentiment?: string;
  [key: string]: unknown;
}

/**
 * Practice data structure
 */
export interface PracticeData {
  id: string | number;
  status: string;
  created_at: string;
  completed_at?: string;
  [key: string]: unknown;
}

/**
 * Metric data structure
 */
export interface MetricData {
  name: string;
  value: number;
  date: string;
  unit?: string;
  [key: string]: unknown;
}

/**
 * Prediction result
 */
export interface PredictionResult {
  value: number;
  confidence: number;
  range?: {
    min: number;
    max: number;
  };
  factors?: string[];
}

/**
 * Trend analysis result
 */
export interface TrendAnalysis {
  direction: "up" | "down" | "stable";
  magnitude: number;
  period: string;
  dataPoints: number[];
}

/**
 * Anomaly detection result
 */
export interface AnomalyDetection {
  detected: boolean;
  deviation: number;
  threshold: number;
  affectedMetrics?: string[];
}

/**
 * Client churn prediction
 */
export interface ClientChurnPrediction {
  riskScore: number;
  highRiskClients: Array<{
    clientId: string | number;
    riskScore: number;
    reasons: string[];
  }>;
}

/**
 * Workload prediction
 */
export interface WorkloadPrediction {
  values: number[];
  period: string;
  confidence: number;
}

/**
 * Type guard for HistoricalData
 */
export function isHistoricalData(value: unknown): value is HistoricalData {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const data = value as Record<string, unknown>;
  // At least one of the expected fields should be present
  return (
    Array.isArray(data.cases) ||
    Array.isArray(data.revenue) ||
    Array.isArray(data.clients) ||
    Array.isArray(data.interactions) ||
    Array.isArray(data.practices) ||
    Array.isArray(data.metrics)
  );
}

/**
 * Type guard for CaseData
 */
export function isCaseData(value: unknown): value is CaseData {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const data = value as Record<string, unknown>;
  return (
    (typeof data.id === "string" || typeof data.id === "number") &&
    typeof data.status === "string" &&
    typeof data.created_at === "string"
  );
}

/**
 * Type guard for RevenueData
 */
export function isRevenueData(value: unknown): value is RevenueData {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const data = value as Record<string, unknown>;
  return typeof data.date === "string" && typeof data.amount === "number";
}
