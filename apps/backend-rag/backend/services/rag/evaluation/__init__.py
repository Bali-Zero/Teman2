"""
Nuzantara RAG - Evaluation and A/B Testing Module

This module provides A/B testing capabilities and quality monitoring for
the RAG system, including retrieval quality metrics, alerting, and dashboards.

Components:
- ABTestManager: Core A/B testing logic with statistical significance
- MetricsTracker: Persistent storage for experiment metrics
- RetrievalQualityMonitor: Real-time RAG quality monitoring and metrics
- AlertThresholds: Configurable alert thresholds

Usage:
    from backend.services.rag.evaluation import (
        ABTestManager,
        MetricsTracker,
        RetrievalQualityMonitor,
        retrieval_quality_monitor,
    )

    # A/B Testing
    ab_manager = ABTestManager()
    variant = ab_manager.assign_variant(user_id="user123", experiment="hybrid_vs_dense")

    # Record metrics
    await metrics_tracker.record_metric(
        experiment="hybrid_vs_dense",
        variant=variant,
        metric="ctr",
        value=1.0,
        user_id="user123",
        query_id="query456"
    )

    # Monitoring
    retrieval_quality_monitor.record_query_metrics(
        query="test query",
        results=results,
        latency_ms=150.0,
    )
"""

from backend.services.rag.evaluation.ab_testing import (
    ABTestManager,
    ExperimentConfig,
    Variant,
)
from backend.services.rag.evaluation.benchmark import (
    BenchmarkResult,
    RAGBenchmark,
    run_weekly_benchmark,
)
from backend.services.rag.evaluation.metrics_tracker import (
    MetricsTracker,
    QueryMetric,
)
from backend.services.rag.evaluation.monitoring import (
    AlertThresholds,
    QueryMetricsRecord,
    RetrievalQualityMonitor,
    get_retrieval_quality_monitor,
    retrieval_quality_monitor,
)
from backend.services.rag.evaluation.ragas_evaluator import (
    EvaluationResult,
    RAGASEvaluator,
    get_ragas_evaluator,
)

__all__ = [
    # A/B Testing
    "ABTestManager",
    "ExperimentConfig",
    "Variant",
    # Metrics Tracking
    "MetricsTracker",
    "QueryMetric",
    # Quality Monitoring
    "AlertThresholds",
    "QueryMetricsRecord",
    "RetrievalQualityMonitor",
    "retrieval_quality_monitor",
    "get_retrieval_quality_monitor",
    # RAGAS Evaluation
    "RAGASEvaluator",
    "EvaluationResult",
    "get_ragas_evaluator",
    # Benchmark
    "RAGBenchmark",
    "BenchmarkResult",
    "run_weekly_benchmark",
]
