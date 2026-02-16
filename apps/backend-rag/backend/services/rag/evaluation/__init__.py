"""
Nuzantara RAG - Evaluation and A/B Testing Module

This module provides A/B testing capabilities for comparing different
retrieval strategies, ranking algorithms, and query processing techniques.

Components:
- ABTestManager: Core A/B testing logic with statistical significance
- MetricsTracker: Persistent storage for experiment metrics
- Experiment variants for hybrid search, reranking, and query expansion

Usage:
    from backend.services.rag.evaluation import ABTestManager, MetricsTracker
    
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
"""

from backend.services.rag.evaluation.ab_testing import ABTestManager, ExperimentConfig, Variant
from backend.services.rag.evaluation.metrics_tracker import MetricsTracker, QueryMetric

__all__ = [
    "ABTestManager",
    "ExperimentConfig", 
    "Variant",
    "MetricsTracker",
    "QueryMetric",
]
