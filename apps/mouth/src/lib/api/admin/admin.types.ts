/**
 * Admin API Types
 */

export type ServiceStatus = 'ok' | 'warning' | 'error' | 'skipped' | 'unknown';

export interface HealthCheckResult {
  name: string;
  status: ServiceStatus;
  message: string;
  latency_ms?: number;
  metadata?: Record<string, unknown>;
  timestamp?: number;
}

export interface SystemMetrics {
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  uptime: number;
  timestamp: number;
}

export interface SystemHealthReport {
  overall_status: ServiceStatus;
  timestamp: string;
  checks: Record<string, HealthCheckResult>;
  system_metrics: SystemMetrics;
  service_registry: Record<string, string>;
}

// Data Explorer Types
export interface TableDataResponse {
  table: string;
  total_rows: number;
  columns: string[];
  rows: Record<string, unknown>[];
}

export interface QdrantCollection {
  name: string;
  status: string;
  vectors_count?: number;
}

export interface QdrantCollectionsResponse {
  collections: QdrantCollection[];
}

export interface QdrantPoint {
  id: string | number;
  payload: Record<string, unknown>;
  score?: number;
}

export interface QdrantPointsResponse {
  points: QdrantPoint[];
  next_page_offset?: string | number;
}
