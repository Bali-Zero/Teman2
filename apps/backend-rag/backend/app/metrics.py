"""
Enhanced Prometheus Metrics for ZANTARA-PERFECT-100
Provides detailed system monitoring and performance tracking
"""

import logging
import time

import psutil
from prometheus_client import Counter, Gauge, Histogram, generate_latest

logger = logging.getLogger(__name__)

# System Metrics
active_sessions = Gauge("zantara_active_sessions_total", "Number of active user sessions")
redis_latency = Gauge("zantara_redis_latency_ms", "Redis latency in milliseconds")
sse_latency = Gauge("zantara_sse_latency_ms", "Average SSE handshake time")
system_uptime = Gauge("zantara_system_uptime_seconds", "System uptime in seconds")
cpu_usage = Gauge("zantara_cpu_usage_percent", "CPU usage percentage")
memory_usage = Gauge("zantara_memory_usage_mb", "Memory usage in MB")

# Request Metrics
http_requests_total = Counter(
    "zantara_http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
request_duration = Histogram(
    "zantara_request_duration_seconds", "Request duration in seconds", ["method", "endpoint"]
)

# Cache Metrics
cache_hits = Counter("zantara_cache_hits_total", "Total cache hits")
cache_misses = Counter("zantara_cache_misses_total", "Total cache misses")
cache_set_operations = Counter("zantara_cache_set_operations_total", "Total cache set operations")

# AI Metrics
ai_requests = Counter("zantara_ai_requests_total", "Total AI requests", ["model"])
ai_latency = Histogram("zantara_ai_latency_seconds", "AI response latency", ["model"])
ai_tokens_used = Counter("zantara_ai_tokens_used_total", "Total AI tokens used", ["model"])

# LLM Token Usage Metrics (Detailed)
llm_prompt_tokens = Counter(
    "zantara_llm_prompt_tokens_total", "Total prompt/input tokens used", ["model", "endpoint"]
)
llm_completion_tokens = Counter(
    "zantara_llm_completion_tokens_total",
    "Total completion/output tokens used",
    ["model", "endpoint"],
)
llm_cost_usd = Counter("zantara_llm_cost_usd_total", "Total LLM cost in USD", ["model"])
llm_request_tokens = Histogram(
    "zantara_llm_request_tokens",
    "Tokens per request distribution",
    ["model", "type"],  # type = "prompt" or "completion"
    buckets=[10, 50, 100, 500, 1000, 2000, 5000, 10000, 20000],
)

# Database Metrics
db_connections_active = Gauge("zantara_db_connections_active", "Active database connections")
db_query_duration = Histogram("zantara_db_query_duration_seconds", "Database query duration")
db_pool_size = Gauge("zantara_db_pool_size", "Database connection pool size", ["service"])
db_pool_idle = Gauge(
    "zantara_db_pool_idle", "Database connection pool idle connections", ["service"]
)

# RAG Pipeline Metrics (Performance Debug Phase 1)
rag_embedding_duration = Histogram(
    "zantara_rag_embedding_duration_seconds", "Embedding generation duration"
)
rag_vector_search_duration = Histogram(
    "zantara_rag_vector_search_duration_seconds", "Vector search duration"
)
rag_reranking_duration = Histogram("zantara_rag_reranking_duration_seconds", "Reranking duration")
rag_pipeline_duration = Histogram(
    "zantara_rag_pipeline_duration_seconds", "Total RAG pipeline duration"
)
rag_early_exit_total = Counter(
    "zantara_rag_early_exit_total", "Total early exits (skipped reranking)"
)
rag_cache_hit_rate = Gauge("zantara_rag_cache_hit_rate", "RAG cache hit rate")
rag_parallel_searches = Counter(
    "zantara_rag_parallel_searches_total", "Parallel collection searches executed"
)

# RAG Query Metrics (Dec 2025 - Dashboard Alignment)
rag_queries_total = Counter(
    "zantara_rag_queries_total",
    "Total RAG queries processed",
    ["collection", "route_used", "status"],
)
rag_tool_calls_total = Counter(
    "zantara_rag_tool_calls_total", "Total tool calls in agentic RAG", ["tool_name", "status"]
)
rag_fallback_count = Counter(
    "zantara_rag_fallback_count_total", "LLM model fallback events", ["from_model", "to_model"]
)
rag_context_length = Histogram(
    "zantara_rag_context_length_tokens",
    "Context length in tokens per query",
    ["collection"],
    buckets=[100, 500, 1000, 2000, 4000, 8000, 16000, 32000],
)

rag_evidence_score = Histogram(
    "zantara_rag_evidence_score",
    "Evidence score of RAG responses (0.0-1.0)",
    ["route_used"],
    buckets=[0.1, 0.3, 0.5, 0.7, 0.9, 1.0],
)

rag_documents_retrieved = Histogram(
    "zantara_rag_documents_retrieved_count",
    "Number of documents retrieved per query",
    ["collection"],
    buckets=[0, 1, 3, 5, 10, 20, 50],
)

# Knowledge Graph Metrics
kg_extraction_total = Counter(
    "zantara_kg_extraction_total",
    "Total entities/relationships extracted",
    ["type", "method"],  # type: entity/relationship, method: llm/regex
)

kg_relationship_density = Histogram(
    "zantara_kg_relationship_density",
    "Number of relationships per entity extracted",
    buckets=[0, 1, 2, 5, 10, 20],
)

# Race Condition Metrics (Dec 2025 - Lock Contention Monitoring)
memory_lock_timeout_total = Counter(
    "zantara_memory_lock_timeout_total", "Number of memory lock timeouts", ["user_id"]
)
memory_lock_contention_seconds = Histogram(
    "zantara_memory_lock_contention_seconds",
    "Time spent waiting for memory locks",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)
collection_lock_timeout_total = Counter(
    "zantara_collection_lock_timeout_total",
    "Number of collection lock timeouts",
    ["collection_name"],
)
cache_db_consistency_errors_total = Counter(
    "zantara_cache_db_consistency_errors_total",
    "Number of cache-DB consistency errors",
    ["session_id"],
)

# Error Handling Metrics (Dec 2025 - Error Handling Fix)
stream_event_none_total = Counter(
    "zantara_stream_event_none_total",
    "Number of None events in stream",
)
stream_event_invalid_type_total = Counter(
    "zantara_stream_event_invalid_type_total",
    "Number of stream events with invalid type",
)
stream_event_validation_failed_total = Counter(
    "zantara_stream_event_validation_failed_total",
    "Number of stream events that failed validation",
)
stream_event_processing_error_total = Counter(
    "zantara_stream_event_processing_error_total",
    "Number of stream event processing errors",
)
stream_fatal_error_total = Counter(
    "zantara_stream_fatal_error_total",
    "Number of fatal errors in stream",
)

search_hybrid_total = Counter(
    "zantara_search_hybrid_total",
    "Number of hybrid searches (dense + BM25)",
)

# CRM Metrics (Jan 2026 - Client Management Operations)
crm_client_operations = Counter(
    "zantara_crm_client_operations_total",
    "CRM client operations",
    ["operation", "status"],  # operation: create/update/delete, status: success/error
)
crm_validation_errors = Counter(
    "zantara_crm_validation_errors_total",
    "CRM validation errors",
    ["field", "error_type"],  # field: email/date_of_birth/etc, error_type: empty/invalid/format
)
crm_client_creation_duration = Histogram(
    "zantara_crm_client_creation_duration_seconds",
    "Duration of client creation operations",
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
)
search_hybrid_failed_total = Counter(
    "zantara_search_hybrid_failed_total",
    "Number of hybrid search failures",
)
search_dense_only_total = Counter(
    "zantara_search_dense_only_total",
    "Number of dense-only searches (fallback)",
)
search_failed_total = Counter(
    "zantara_search_failed_total",
    "Number of complete search failures",
)

# Memory Extraction Metrics (Jan 2026 - Fact Extraction Quality)
memory_facts_extracted_total = Counter(
    "zantara_memory_facts_extracted_total",
    "Total memory facts extracted",
    ["fact_type", "source", "confidence_level"],  # confidence_level: high (>0.8), medium, low
)

memory_extraction_duration_seconds = Histogram(
    "zantara_memory_extraction_duration_seconds",
    "Time spent extracting memory facts",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1],
)

bm25_initialization_success_total = Counter(
    "zantara_bm25_initialization_success_total",
    "Number of successful BM25 initializations",
)
bm25_initialization_failed_total = Counter(
    "zantara_bm25_initialization_failed_total",
    "Number of BM25 initialization failures",
    ["error_type"],
)

# Intelligence Center Metrics (Jan 2026 - Scraper + Voting System)
intel_articles_submitted = Counter(
    "zantara_intel_articles_submitted_total",
    "Articles submitted from scrapers",
    ["scraper_type", "intel_type", "tier"],  # scraper: unified/intelligent_visa, intel: visa/news
)
intel_articles_duplicates = Counter(
    "zantara_intel_articles_duplicates_total",
    "Duplicate articles rejected",
    ["intel_type"],
)
intel_scraper_latency = Histogram(
    "zantara_intel_scraper_submission_seconds",
    "Time to submit article to backend",
    ["scraper_type"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

# Classification Metrics
intel_classification_total = Counter(
    "zantara_intel_classification_total",
    "Articles classified",
    ["category_input", "classified_as"],  # Track classification accuracy
)
intel_classification_duration = Histogram(
    "zantara_intel_classification_duration_seconds",
    "Classification time",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1],
)

# Voting Metrics
intel_votes_cast = Counter(
    "zantara_intel_votes_cast_total",
    "Votes cast on intel items",
    ["intel_type", "vote_type", "user"],  # vote_type: approve/reject
)
intel_items_approved = Counter(
    "zantara_intel_items_approved_total",
    "Items approved via voting",
    ["intel_type"],
)
intel_items_rejected = Counter(
    "zantara_intel_items_rejected_total",
    "Items rejected via voting",
    ["intel_type"],
)
intel_voting_duration = Histogram(
    "zantara_intel_voting_duration_seconds",
    "Time from initiation to decision",
    ["intel_type"],
    buckets=[60, 300, 600, 1800, 3600, 7200, 14400],  # 1min to 4hrs
)

# Ingestion Metrics (Data Processing - "The Mouth")
documents_ingested_total = Counter(
    "zantara_documents_ingested_total",
    "Total documents ingested into the system",
    [
        "source",
        "file_type",
        "collection",
        "status",
    ],  # source: file_upload, scraper, api; status: success, error
)
ingestion_failure_rate = Gauge(
    "zantara_ingestion_failure_rate",
    "Current ingestion failure rate (percentage)",
    ["source", "file_type"],  # Track failure rate by source and file type
)
parsing_duration_seconds = Histogram(
    "zantara_parsing_duration_seconds",
    "Time spent parsing documents",
    ["file_type", "source"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],  # 100ms to 1 minute
)
document_processing_duration_seconds = Histogram(
    "zantara_document_processing_duration_seconds",
    "Total time to process documents from upload to storage",
    ["source", "collection"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 900.0],  # 1s to 15 minutes
)
chunks_created_total = Counter(
    "zantara_chunks_created_total",
    "Total chunks created during ingestion",
    ["collection", "source"],
)
parsing_errors_total = Counter(
    "zantara_parsing_errors_total",
    "Total parsing errors encountered",
    ["file_type", "error_type", "source"],
)
metadata_extraction_duration_seconds = Histogram(
    "zantara_metadata_extraction_duration_seconds",
    "Time spent extracting metadata from documents",
    ["document_type", "source"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0],  # 10ms to 2s
)
chunking_duration_seconds = Histogram(
    "zantara_chunking_duration_seconds",
    "Time spent chunking documents",
    ["file_type", "chunk_strategy"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0],  # 10ms to 2s
)
embedding_generation_duration_seconds = Histogram(
    "zantara_embedding_generation_duration_seconds",
    "Time spent generating embeddings",
    ["model", "batch_size"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],  # 100ms to 10s
)
vector_storage_duration_seconds = Histogram(
    "zantara_vector_storage_duration_seconds",
    "Time spent storing embeddings in vector database",
    ["collection", "operation"],  # operation: upsert, update, delete
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

# Scraper Data Normalization Metrics
scraper_data_normalized_total = Counter(
    "zantara_scraper_data_normalized_total",
    "Total scraper data items normalized",
    ["scraper_type", "source", "status"],
)
scraper_normalization_duration_seconds = Histogram(
    "zantara_scraper_normalization_duration_seconds",
    "Time spent normalizing scraper data",
    ["scraper_type", "data_complexity"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0],
)
scraper_normalization_errors_total = Counter(
    "zantara_scraper_normalization_errors_total",
    "Total errors during scraper data normalization",
    ["scraper_type", "error_type"],
)

# Ingestion Pipeline Metrics
intel_qdrant_ingestion_total = Counter(
    "zantara_intel_qdrant_ingestion_total",
    "Items ingested to Qdrant",
    ["collection", "status"],  # status: success/error
)
intel_qdrant_ingestion_duration = Histogram(
    "zantara_intel_qdrant_ingestion_duration_seconds",
    "Qdrant ingestion time",
    ["collection"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0],
)

# System Health
intel_staging_queue_size = Gauge(
    "zantara_intel_staging_queue_size",
    "Pending items in staging",
    ["intel_type"],
)
intel_approval_rate = Gauge(
    "zantara_intel_approval_rate",
    "Approval rate (approved / total voted)",
    ["intel_type"],
)

# Intelligence Center Advanced Metrics (Jan 2026 - Enhanced Features)
intel_bulk_operations_total = Counter(
    "zantara_intel_bulk_operations_total",
    "Total bulk operations performed",
    ["intel_type", "operation"],  # operation: approve/reject/publish
)
intel_bulk_operation_items = Histogram(
    "zantara_intel_bulk_operation_items",
    "Number of items processed in bulk operations",
    ["intel_type", "operation"],
    buckets=[1, 5, 10, 25, 50, 100],
)
intel_filter_usage_total = Counter(
    "zantara_intel_filter_usage_total",
    "Filter usage statistics",
    ["intel_type", "filter_type"],  # filter_type: all/NEW/UPDATED/critical
)
intel_sort_usage_total = Counter(
    "zantara_intel_sort_usage_total",
    "Sort usage statistics",
    ["intel_type", "sort_type"],  # sort_type: date-desc/date-asc/title-asc/title-desc
)
intel_search_queries_total = Counter(
    "zantara_intel_search_queries_total",
    "Search query usage",
    ["intel_type"],
)
intel_analytics_queries_total = Counter(
    "zantara_intel_analytics_queries_total",
    "Analytics dashboard queries",
    ["period_days"],
)
intel_user_actions_total = Counter(
    "zantara_intel_user_actions_total",
    "User action tracking",
    ["intel_type", "action"],  # action: preview/approve/reject/publish/select
)

memory_orchestrator_healthy_total = Counter(
    "zantara_memory_orchestrator_healthy_total",
    "Number of times memory orchestrator initialized in healthy state",
)
memory_orchestrator_degraded_total = Counter(
    "zantara_memory_orchestrator_degraded_total",
    "Number of times memory orchestrator entered degraded mode",
)
memory_orchestrator_unavailable_total = Counter(
    "zantara_memory_orchestrator_unavailable_total",
    "Number of times memory orchestrator initialization failed",
)
memory_context_degraded_total = Counter(
    "zantara_memory_context_degraded_total",
    "Number of times context was returned in degraded mode",
)
memory_context_failed_total = Counter(
    "zantara_memory_context_failed_total",
    "Number of times context retrieval failed",
)

llm_circuit_breaker_open_total = Counter(
    "zantara_llm_circuit_breaker_open_total",
    "Number of times circuit breaker was open (skipped model)",
    ["model"],
)
llm_circuit_breaker_opened_total = Counter(
    "zantara_llm_circuit_breaker_opened_total",
    "Number of times circuit breaker opened",
    ["model", "error_type"],
)
llm_quota_exhausted_total = Counter(
    "zantara_llm_quota_exhausted_total", "Number of quota exhausted errors", ["model"]
)
llm_service_unavailable_total = Counter(
    "zantara_llm_service_unavailable_total", "Number of service unavailable errors", ["model"]
)
llm_model_error_total = Counter(
    "zantara_llm_model_error_total", "Number of model errors", ["model", "error_type"]
)
llm_all_models_failed_total = Counter(
    "zantara_llm_all_models_failed_total",
    "Number of times all models failed",
)
llm_cost_limit_reached_total = Counter(
    "zantara_llm_cost_limit_reached_total",
    "Number of times cost limit was reached",
)
llm_max_depth_reached_total = Counter(
    "zantara_llm_max_depth_reached_total",
    "Number of times max fallback depth was reached",
)
llm_fallback_depth = Histogram(
    "zantara_llm_fallback_depth", "Fallback depth distribution", buckets=[0, 1, 2, 3, 4, 5]
)
llm_query_cost_usd = Histogram(
    "zantara_llm_query_cost_usd",
    "Query cost in USD distribution",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

database_init_success_total = Counter(
    "zantara_database_init_success_total",
    "Number of successful database initializations",
)
database_init_failed_total = Counter(
    "zantara_database_init_failed_total",
    "Number of database initialization failures",
    ["error_type", "is_transient"],
)
database_init_permanent_failure_total = Counter(
    "zantara_database_init_permanent_failure_total",
    "Number of permanent database initialization failures",
)
database_health_check_success_total = Counter(
    "zantara_database_health_check_success_total",
    "Number of successful database health checks",
)
database_health_check_failed_total = Counter(
    "zantara_database_health_check_failed_total",
    "Number of failed database health checks",
)

qdrant_timeout_total = Counter(
    "zantara_qdrant_timeout_total", "Number of Qdrant timeout errors", ["error_type"]
)
qdrant_http_error_total = Counter(
    "zantara_qdrant_http_error_total", "Number of Qdrant HTTP errors", ["status_code", "error_type"]
)

reasoning_low_context_quality_total = Counter(
    "zantara_reasoning_low_context_quality_total",
    "Number of times context quality was too low",
)

# Google Drive Metrics (Jan 2026 - Team Drive Integration)
drive_operations_total = Counter(
    "zantara_drive_operations_total",
    "Total Google Drive operations",
    [
        "operation",
        "user_email",
        "status",
    ],  # operation: upload, download, create_folder, create_doc, rename, delete, move, copy
)
drive_operation_duration_seconds = Histogram(
    "zantara_drive_operation_duration_seconds",
    "Google Drive operation duration in seconds",
    ["operation"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)
drive_file_size_bytes = Histogram(
    "zantara_drive_file_size_bytes",
    "Size of files uploaded/downloaded",
    ["operation"],
    buckets=[1024, 10240, 102400, 1048576, 10485760, 104857600],  # 1KB to 100MB
)
drive_oauth_refresh_total = Counter(
    "zantara_drive_oauth_refresh_total",
    "Number of OAuth token refresh operations",
    ["status"],  # success, failed
)
drive_oauth_token_expiry_seconds = Gauge(
    "zantara_drive_oauth_token_expiry_seconds", "Seconds until OAuth token expires"
)
drive_errors_total = Counter(
    "zantara_drive_errors_total",
    "Total Google Drive errors",
    [
        "error_type",
        "operation",
    ],  # error_type: auth_failed, quota_exceeded, not_found, permission_denied, network_error
)
drive_quota_usage_percent = Gauge(
    "zantara_drive_quota_usage_percent", "Google Drive quota usage percentage"
)
drive_active_users = Gauge(
    "zantara_drive_active_users", "Number of users who accessed Drive in last hour"
)
drive_files_accessed_total = Counter(
    "zantara_drive_files_accessed_total",
    "Total files accessed by type",
    [
        "file_type",
        "action",
    ],  # file_type: folder, document, spreadsheet, pdf, image, other; action: view, download
)

# Email Metrics (Jan 2026 - Zoho Mail Integration)
email_operations_total = Counter(
    "zantara_email_operations_total",
    "Total email operations",
    ["operation", "user_id", "status"],
    # operation: send, reply, forward, delete, mark_read, mark_unread, flag, unflag, move, list, search, get_attachment
)
email_operation_duration_seconds = Histogram(
    "zantara_email_operation_duration_seconds",
    "Email operation duration in seconds",
    ["operation"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)
email_attachment_size_bytes = Histogram(
    "zantara_email_attachment_size_bytes",
    "Size of email attachments uploaded/downloaded",
    ["operation"],
    buckets=[1024, 10240, 102400, 1048576, 10485760],  # 1KB to 10MB
)
email_oauth_refresh_total = Counter(
    "zantara_email_oauth_refresh_total",
    "Number of Zoho OAuth token refresh operations",
    ["status"],  # success, failed
)
email_errors_total = Counter(
    "zantara_email_errors_total",
    "Total email errors",
    ["error_type", "operation"],
    # error_type: auth_failed, rate_limited, not_found, api_error, network_error
)
email_unread_count = Gauge(
    "zantara_email_unread_count",
    "Total unread emails per user",
    ["user_id"],
)
email_active_users = Gauge(
    "zantara_email_active_users",
    "Number of users with connected email accounts",
)

# Boot time tracking
BOOT_TIME = time.time()


class MetricsCollector:
    """Collects and manages system metrics"""

    # Expose module-level metrics as class attributes for service access
    bm25_initialization_success_total = bm25_initialization_success_total
    bm25_initialization_failed_total = bm25_initialization_failed_total
    search_hybrid_total = search_hybrid_total
    search_hybrid_failed_total = search_hybrid_failed_total
    search_dense_only_total = search_dense_only_total
    search_failed_total = search_failed_total

    def __init__(self):
        self.session_count = 0
        self.last_redis_check = 0
        self.last_sse_latency = 0

    def update_session_count(self, count: int):
        """Update active sessions count"""
        self.session_count = count
        active_sessions.set(count)

    async def measure_redis_latency(self) -> float:
        """Measure Redis latency in milliseconds"""
        try:
            from backend.core.cache import get_cache_service

            cache = get_cache_service()
            start = time.time()
            cache.set("metrics_ping", "pong", ttl=1)
            cache.get("metrics_ping")  # Verify cache works
            latency = (time.time() - start) * 1000
            redis_latency.set(latency)
            self.last_redis_check = latency
            return latency
        except Exception as e:
            logger.warning(f"Failed to measure Redis latency: {e}")
            return -1

    async def measure_sse_latency(self) -> float:
        """Measure SSE connection latency"""
        # This would be updated by actual SSE connections
        # For now, return last known value
        return self.last_sse_latency

    def update_sse_latency(self, latency: float):
        """Update SSE latency from actual measurements"""
        self.last_sse_latency = latency
        sse_latency.set(latency)

    def update_system_metrics(self):
        """Update system-level metrics"""
        # Uptime
        uptime = time.time() - BOOT_TIME
        system_uptime.set(uptime)

        # CPU usage
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_usage.set(cpu_percent)
        except Exception:
            pass

        # Memory usage
        try:
            memory = psutil.virtual_memory()
            memory_mb = memory.used / 1024 / 1024
            memory_usage.set(memory_mb)
        except Exception:
            pass

    def record_request(self, method: str, endpoint: str, status: int, duration: float):
        """Record HTTP request metrics"""
        http_requests_total.labels(method=method, endpoint=endpoint, status=str(status)).inc()
        request_duration.labels(method=method, endpoint=endpoint).observe(duration)

    def record_cache_hit(self):
        """Record a cache hit"""
        cache_hits.inc()

    def record_cache_miss(self):
        """Record a cache miss"""
        cache_misses.inc()

    def record_cache_set(self):
        """Record a cache set operation"""
        cache_set_operations.inc()

    def record_ai_request(self, model: str, latency: float, tokens: int = 0):
        """Record AI request metrics"""
        ai_requests.labels(model=model).inc()
        ai_latency.labels(model=model).observe(latency)
        if tokens > 0:
            ai_tokens_used.labels(model=model).inc(tokens)

    def record_llm_token_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        endpoint: str = "chat",
    ):
        """Record detailed LLM token usage metrics.

        Args:
            model: Model name (e.g., 'gemini-3-flash-preview')
            prompt_tokens: Number of input/prompt tokens
            completion_tokens: Number of output/completion tokens
            cost_usd: Cost in USD for this request
            endpoint: API endpoint that triggered the request
        """
        # Increment counters
        llm_prompt_tokens.labels(model=model, endpoint=endpoint).inc(prompt_tokens)
        llm_completion_tokens.labels(model=model, endpoint=endpoint).inc(completion_tokens)
        llm_cost_usd.labels(model=model).inc(cost_usd)

        # Record token distributions
        if prompt_tokens > 0:
            llm_request_tokens.labels(model=model, type="prompt").observe(prompt_tokens)
        if completion_tokens > 0:
            llm_request_tokens.labels(model=model, type="completion").observe(completion_tokens)

        # Also update legacy counter for backward compatibility
        total_tokens = prompt_tokens + completion_tokens
        if total_tokens > 0:
            ai_tokens_used.labels(model=model).inc(total_tokens)

    def update_db_connections(self, count: int):
        """Update database connection count"""
        db_connections_active.set(count)

    def record_db_query(self, duration: float):
        """Record database query duration"""
        db_query_duration.observe(duration)

    def record_rag_query(
        self,
        collection: str,
        route_used: str,
        status: str,
        context_tokens: int = 0,
    ):
        """Record a RAG query with routing and status info.

        Args:
            collection: Collection searched (e.g., 'visa_oracle', 'legal_unified')
            route_used: Routing method ('fast', 'pro', 'deep_think', 'federated')
            status: Query outcome ('success', 'error', 'fallback', 'cache_hit')
            context_tokens: Number of tokens in the context (for histogram)
        """
        rag_queries_total.labels(collection=collection, route_used=route_used, status=status).inc()

        if context_tokens > 0:
            rag_context_length.labels(collection=collection).observe(context_tokens)

    def record_rag_detailed_metrics(
        self,
        duration_seconds: float,
        evidence_score: float,
        documents_count: int,
        collection: str = "unknown",
        route_used: str = "agentic",
    ):
        """Record detailed RAG performance metrics.

        Args:
            duration_seconds: Total pipeline duration
            evidence_score: Calculated evidence score (0.0-1.0)
            documents_count: Number of documents used/retrieved
            collection: Primary collection used
            route_used: Routing strategy
        """
        rag_pipeline_duration.observe(duration_seconds)
        rag_evidence_score.labels(route_used=route_used).observe(evidence_score)
        rag_documents_retrieved.labels(collection=collection).observe(documents_count)

    def record_memory_extraction(
        self,
        duration_seconds: float,
        fact_types: list[str],
    ):
        """Record memory fact extraction metrics.

        Args:
            duration_seconds: Extraction time
            fact_types: List of fact types found
        """
        memory_extraction_duration_seconds.observe(duration_seconds)
        for f_type in fact_types:
            memory_facts_extracted_total.labels(
                fact_type=f_type, source="regex", confidence_level="medium"
            ).inc()

    def record_kg_metrics(self, entity_count: int, relationship_count: int, method: str):
        """Record Knowledge Graph extraction metrics."""
        kg_extraction_total.labels(type="entity", method=method).inc(entity_count)
        kg_extraction_total.labels(type="relationship", method=method).inc(relationship_count)

        if entity_count > 0:
            density = relationship_count / entity_count
            kg_relationship_density.observe(density)

    def record_tool_call(self, tool_name: str, status: str):
        """Record a tool call in agentic RAG.

        Args:
            tool_name: Name of the tool (e.g., 'vector_search', 'pricing', 'calculator')
            status: Call outcome ('success', 'error', 'timeout')
        """
        rag_tool_calls_total.labels(tool_name=tool_name, status=status).inc()

    def record_llm_fallback(self, from_model: str, to_model: str):
        """Record an LLM model fallback event.

        Args:
            from_model: Model that failed (e.g., 'gemini-3-flash-preview')
            to_model: Fallback model used (e.g., 'gemini-2.0-flash')
        """
        rag_fallback_count.labels(from_model=from_model, to_model=to_model).inc()

    def record_memory_lock_timeout(self, user_id: str):
        """Record a memory lock timeout event.

        Args:
            user_id: User identifier that experienced the timeout
        """
        memory_lock_timeout_total.labels(user_id=user_id).inc()

    def record_memory_lock_contention(self, operation: str, wait_time_seconds: float):
        """Record memory lock contention time.

        Args:
            operation: Operation type (e.g., 'save_memory', 'get_context')
            wait_time_seconds: Time spent waiting for lock
        """
        memory_lock_contention_seconds.labels(operation=operation).observe(wait_time_seconds)

    def record_collection_lock_timeout(self, collection_name: str):
        """Record a collection lock timeout event.

        Args:
            collection_name: Collection that experienced the timeout
        """
        collection_lock_timeout_total.labels(collection_name=collection_name).inc()

    def record_cache_db_consistency_error(self, session_id: str):
        """Record a cache-DB consistency error.

        Args:
            session_id: Session ID where the error occurred
        """
        cache_db_consistency_errors_total.labels(session_id=session_id).inc()

    # Google Drive Metrics Methods
    def record_drive_operation(
        self,
        operation: str,
        user_email: str,
        status: str,
        duration_seconds: float = 0,
        file_size_bytes: int = 0,
    ):
        """Record a Google Drive operation.

        Args:
            operation: Type of operation (upload, download, create_folder, create_doc, rename, delete, move, copy, list, search)
            user_email: Email of user performing the operation
            status: Operation outcome (success, error)
            duration_seconds: Time taken for the operation
            file_size_bytes: Size of file for upload/download operations
        """
        # Sanitize email for metrics (use hash or truncate for privacy)
        safe_email = user_email.split("@")[0] if user_email else "unknown"

        drive_operations_total.labels(
            operation=operation, user_email=safe_email, status=status
        ).inc()

        if duration_seconds > 0:
            drive_operation_duration_seconds.labels(operation=operation).observe(duration_seconds)

        if file_size_bytes > 0:
            drive_file_size_bytes.labels(operation=operation).observe(file_size_bytes)

    def record_drive_oauth_refresh(self, status: str):
        """Record an OAuth token refresh operation.

        Args:
            status: Refresh outcome (success, failed)
        """
        drive_oauth_refresh_total.labels(status=status).inc()

    def set_drive_oauth_expiry(self, seconds_until_expiry: float):
        """Set the time until OAuth token expires.

        Args:
            seconds_until_expiry: Seconds until token expires
        """
        drive_oauth_token_expiry_seconds.set(seconds_until_expiry)

    def record_drive_error(self, error_type: str, operation: str):
        """Record a Google Drive error.

        Args:
            error_type: Type of error (auth_failed, quota_exceeded, not_found, permission_denied, network_error)
            operation: Operation that caused the error
        """
        drive_errors_total.labels(error_type=error_type, operation=operation).inc()

    def set_drive_quota_usage(self, usage_percent: float):
        """Set the Drive quota usage percentage.

        Args:
            usage_percent: Quota usage as percentage (0-100)
        """
        drive_quota_usage_percent.set(usage_percent)

    def set_drive_active_users(self, count: int):
        """Set the number of active Drive users.

        Args:
            count: Number of users who accessed Drive recently
        """
        drive_active_users.set(count)

    def record_drive_file_access(self, file_type: str, action: str):
        """Record a file access event.

        Args:
            file_type: Type of file (folder, document, spreadsheet, pdf, image, other)
            action: Access action (view, download)
        """
        drive_files_accessed_total.labels(file_type=file_type, action=action).inc()

    # Email Metrics Methods
    def record_email_operation(
        self,
        operation: str,
        user_id: str,
        status: str,
        duration_seconds: float = 0,
        attachment_size_bytes: int = 0,
    ):
        """Record an email operation.

        Args:
            operation: Type of operation (send, reply, forward, delete, mark_read, mark_unread, flag, unflag, move, list, search, get_attachment, upload_attachment)
            user_id: User performing the operation
            status: Operation outcome (success, error)
            duration_seconds: Time taken for the operation
            attachment_size_bytes: Size of attachment for upload/download operations
        """
        # Sanitize user_id for metrics (use hash or truncate for privacy)
        safe_user_id = user_id[:8] if user_id else "unknown"

        email_operations_total.labels(
            operation=operation, user_id=safe_user_id, status=status
        ).inc()

        if duration_seconds > 0:
            email_operation_duration_seconds.labels(operation=operation).observe(duration_seconds)

        if attachment_size_bytes > 0:
            email_attachment_size_bytes.labels(operation=operation).observe(attachment_size_bytes)

    def record_email_oauth_refresh(self, status: str):
        """Record an email OAuth token refresh operation.

        Args:
            status: Refresh outcome (success, failed)
        """
        email_oauth_refresh_total.labels(status=status).inc()

    def record_email_error(self, error_type: str, operation: str):
        """Record an email error.

        Args:
            error_type: Type of error (auth_failed, rate_limited, not_found, api_error, network_error)
            operation: Operation that caused the error
        """
        email_errors_total.labels(error_type=error_type, operation=operation).inc()

    def set_email_unread_count(self, user_id: str, count: int):
        """Set the unread email count for a user.

        Args:
            user_id: User identifier
            count: Number of unread emails
        """
        safe_user_id = user_id[:8] if user_id else "unknown"
        email_unread_count.labels(user_id=safe_user_id).set(count)

    def set_email_active_users(self, count: int):
        """Set the number of users with connected email accounts.

        Args:
            count: Number of active email users
        """
        email_active_users.set(count)

    # Ingestion Metrics Methods
    def record_document_ingested(
        self,
        source: str,
        file_type: str,
        collection: str,
        status: str,
        chunks_created: int = 0,
    ):
        """Record a document ingestion event.

        Args:
            source: Source of ingestion (file_upload, scraper, api)
            file_type: Type of file (.pdf, .docx, .txt, etc.)
            collection: Target collection name
            status: Ingestion status (success, error)
            chunks_created: Number of chunks created from the document
        """
        documents_ingested_total.labels(
            source=source, file_type=file_type, collection=collection, status=status
        ).inc()

        if chunks_created > 0:
            chunks_created_total.labels(collection=collection, source=source).inc(chunks_created)

    def record_parsing_duration(self, file_type: str, source: str, duration_seconds: float):
        """Record document parsing duration.

        Args:
            file_type: Type of file being parsed
            source: Source of the document
            duration_seconds: Time taken to parse the document
        """
        parsing_duration_seconds.labels(file_type=file_type, source=source).observe(
            duration_seconds
        )

    def record_parsing_error(self, file_type: str, error_type: str, source: str):
        """Record a parsing error.

        Args:
            file_type: Type of file that failed to parse
            error_type: Type of parsing error
            source: Source of the document
        """
        parsing_errors_total.labels(file_type=file_type, error_type=error_type, source=source).inc()

    def record_document_processing_duration(
        self, source: str, collection: str, duration_seconds: float
    ):
        """Record total document processing duration.

        Args:
            source: Source of ingestion
            collection: Target collection
            duration_seconds: Total processing time from upload to storage
        """
        document_processing_duration_seconds.labels(source=source, collection=collection).observe(
            duration_seconds
        )

    def record_metadata_extraction_duration(
        self, document_type: str, source: str, duration_seconds: float
    ):
        """Record metadata extraction duration.

        Args:
            document_type: Type of document (legal, general, etc.)
            source: Source of the document
            duration_seconds: Time taken to extract metadata
        """
        metadata_extraction_duration_seconds.labels(
            document_type=document_type, source=source
        ).observe(duration_seconds)

    def record_chunking_duration(
        self, file_type: str, chunk_strategy: str, duration_seconds: float
    ):
        """Record chunking duration.

        Args:
            file_type: Type of file being chunked
            chunk_strategy: Strategy used for chunking
            duration_seconds: Time taken to chunk the document
        """
        chunking_duration_seconds.labels(
            file_type=file_type, chunk_strategy=chunk_strategy
        ).observe(duration_seconds)

    def record_embedding_generation_duration(
        self, model: str, batch_size: int, duration_seconds: float
    ):
        """Record embedding generation duration.

        Args:
            model: Embedding model used
            batch_size: Size of the batch processed
            duration_seconds: Time taken to generate embeddings
        """
        embedding_generation_duration_seconds.labels(
            model=model, batch_size=str(batch_size)
        ).observe(duration_seconds)

    def record_vector_storage_duration(
        self, collection: str, operation: str, duration_seconds: float
    ):
        """Record vector storage duration.

        Args:
            collection: Target collection
            operation: Type of storage operation (upsert, update, delete)
            duration_seconds: Time taken to store vectors
        """
        vector_storage_duration_seconds.labels(collection=collection, operation=operation).observe(
            duration_seconds
        )

    def update_ingestion_failure_rate(self, source: str, file_type: str, failure_rate: float):
        """Update the ingestion failure rate gauge.

        Args:
            source: Source of ingestion
            file_type: Type of file
            failure_rate: Failure rate as percentage (0-100)
        """
        ingestion_failure_rate.labels(source=source, file_type=file_type).set(failure_rate)

    def record_scraper_data_normalized(
        self, scraper_type: str, source: str, status: str, duration_seconds: float = 0
    ):
        """Record scraper data normalization.

        Args:
            scraper_type: Type of scraper (rss, web, api)
            source: Data source URL or identifier
            status: Normalization status (success, error)
            duration_seconds: Time taken for normalization
        """
        scraper_data_normalized_total.labels(
            scraper_type=scraper_type, source=source, status=status
        ).inc()

        if duration_seconds > 0:
            # Determine data complexity based on duration (simple heuristic)
            complexity = "simple" if duration_seconds < 0.1 else "complex"
            scraper_normalization_duration_seconds.labels(
                scraper_type=scraper_type, data_complexity=complexity
            ).observe(duration_seconds)

    def record_scraper_normalization_error(self, scraper_type: str, error_type: str):
        """Record a scraper normalization error.

        Args:
            scraper_type: Type of scraper
            error_type: Type of error encountered
        """
        scraper_normalization_errors_total.labels(
            scraper_type=scraper_type, error_type=error_type
        ).inc()


# Global metrics collector instance
metrics_collector = MetricsCollector()


async def get_active_sessions_count() -> int:
    """Get count of active sessions"""
    # This would be implemented based on your session management
    # For now, return the stored value
    return metrics_collector.session_count


async def collect_all_metrics():
    """Collect all metrics for Prometheus endpoint"""
    # Update system metrics
    metrics_collector.update_system_metrics()

    # Measure Redis latency
    await metrics_collector.measure_redis_latency()

    # Return Prometheus format
    return generate_latest()


def get_metrics_middleware():
    """Middleware to track request metrics"""
    import time

    from fastapi import Request

    async def metrics_middleware(request: Request, call_next):
        start_time = time.time()

        response = await call_next(request)

        duration = time.time() - start_time
        metrics_collector.record_request(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code,
            duration=duration,
        )

        return response

    return metrics_middleware
