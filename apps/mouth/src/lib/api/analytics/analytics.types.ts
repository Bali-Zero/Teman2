/**
 * Analytics Dashboard Types
 * Types for the Founder-only analytics dashboard
 */

export interface OverviewStats {
  conversations_today: number;
  conversations_week: number;
  users_active: number;
  error_rate: number;
  uptime_seconds: number;
  revenue_pipeline: number;
  services_healthy: number;
  services_total: number;
}

export interface RAGStats {
  avg_latency_ms: number;
  embedding_latency_ms: number;
  search_latency_ms: number;
  rerank_latency_ms: number;
  llm_latency_ms: number;
  cache_hit_rate: number;
  token_usage_today: number;
  queries_today: number;
  top_queries: Array<{ query: string; count: number }>;
  early_exit_rate: number;
}

export interface CRMStats {
  clients_total: number;
  clients_active: number;
  clients_by_status: Record<string, number>;
  practices_total: number;
  practices_by_status: Record<string, number>;
  revenue_quoted: number;
  revenue_paid: number;
  renewals_30_days: number;
  renewals_60_days: number;
  renewals_90_days: number;
  documents_pending: number;
}

export interface TeamStats {
  hours_today: number;
  hours_week: number;
  conversations_by_agent: Record<string, number>;
  productivity_scores: Record<string, number>;
  active_sessions: number;
  action_items_open: number;
}

export interface SystemStats {
  cpu_percent: number;
  memory_mb: number;
  memory_percent: number;
  db_connections_active: number;
  db_connections_idle: number;
  response_time_p50: number;
  response_time_p95: number;
  response_time_p99: number;
  requests_per_minute: number;
  error_rate_percent: number;
  services: Array<{
    name: string;
    healthy: boolean;
    last_check: string;
    error: string;
  }>;
}

export interface QdrantStats {
  total_documents: number;
  collections: Array<{
    name: string;
    documents: number;
    status: string;
  }>;
  search_latency_avg_ms: number;
  search_operations_today: number;
  upsert_operations_today: number;
  error_count: number;
}

export interface FeedbackStats {
  avg_rating: number;
  rating_distribution: Record<string, number>;
  total_ratings: number;
  negative_feedback_count: number;
  recent_negative_feedback: Array<{
    session_id: string;
    rating: number;
    feedback: string;
    date: string;
  }>;
  quality_trend: Array<{
    date: string;
    rating: number;
  }>;
}

export interface AlertStats {
  active_alerts: Array<{
    service: string;
    message: string;
    severity: string;
  }>;
  recent_errors: Array<{
    action: string;
    email: string;
    reason: string;
    time: string;
  }>;
  slow_queries: Array<{
    query: string;
    duration_ms: number;
  }>;
  auth_failures_today: number;
  error_count_today: number;
}

export interface AllAnalytics {
  overview: OverviewStats;
  rag: RAGStats;
  crm: CRMStats;
  team: TeamStats;
  system: SystemStats;
  qdrant: QdrantStats;
  feedback: FeedbackStats;
  alerts: AlertStats;
  generated_at: string;
}
