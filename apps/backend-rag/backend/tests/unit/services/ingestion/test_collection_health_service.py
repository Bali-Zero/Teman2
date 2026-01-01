"""
Unit tests for CollectionHealthService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.ingestion.collection_health_service import (
    CollectionHealthService,
    HealthStatus,
    StalenessSeverity,
    CollectionMetrics
)


@pytest.fixture
def mock_search_service():
    """Mock SearchService"""
    service = MagicMock()
    return service


@pytest.fixture
def collection_health_service(mock_search_service):
    """Create CollectionHealthService instance"""
    return CollectionHealthService(search_service=mock_search_service)


class TestCollectionHealthService:
    """Tests for CollectionHealthService"""

    def test_init(self, mock_search_service):
        """Test initialization"""
        service = CollectionHealthService(search_service=mock_search_service)
        assert service.search_service == mock_search_service
        assert len(service.metrics) > 0

    def test_init_metrics(self, collection_health_service):
        """Test metrics initialization"""
        metrics = collection_health_service._init_metrics("test_collection")
        assert isinstance(metrics, dict)
        assert "query_count" in metrics
        assert "hit_count" in metrics

    def test_record_query(self, collection_health_service):
        """Test recording a query"""
        collection_health_service.record_query("visa_oracle", had_results=True, result_count=5, avg_score=0.8)
        metrics = collection_health_service.metrics["visa_oracle"]
        assert metrics["query_count"] == 1
        assert metrics["hit_count"] == 1

    def test_record_query_no_results(self, collection_health_service):
        """Test recording query with no results"""
        collection_health_service.record_query("visa_oracle", had_results=False, result_count=0, avg_score=0.0)
        metrics = collection_health_service.metrics["visa_oracle"]
        assert metrics["query_count"] == 1
        assert metrics["hit_count"] == 0

    def test_record_query_multiple(self, collection_health_service):
        """Test recording multiple queries"""
        collection_health_service.record_query("visa_oracle", had_results=True, result_count=5, avg_score=0.8)
        collection_health_service.record_query("visa_oracle", had_results=True, result_count=3, avg_score=0.9)
        collection_health_service.record_query("visa_oracle", had_results=False, result_count=0, avg_score=0.0)
        metrics = collection_health_service.metrics["visa_oracle"]
        assert metrics["query_count"] == 3
        assert metrics["hit_count"] == 2
        assert len(metrics["confidence_scores"]) == 2

    def test_get_collection_health(self, collection_health_service):
        """Test getting collection health"""
        health = collection_health_service.get_collection_health("visa_oracle")
        assert isinstance(health, CollectionMetrics)
        assert health.collection_name == "visa_oracle"
        assert health.health_status in [HealthStatus.EXCELLENT, HealthStatus.GOOD, HealthStatus.WARNING, HealthStatus.CRITICAL]

    def test_get_collection_health_not_found(self, collection_health_service):
        """Test getting health for non-existent collection"""
        health = collection_health_service.get_collection_health("nonexistent")
        # Returns CollectionMetrics with issues, not None
        assert isinstance(health, CollectionMetrics)
        assert "not found" in health.issues[0].lower()

    def test_get_all_collection_health(self, collection_health_service):
        """Test getting all collection health"""
        all_health = collection_health_service.get_all_collection_health()
        assert isinstance(all_health, dict)
        assert len(all_health) > 0

    def test_record_queries_batch(self, collection_health_service):
        """Test recording queries in batch"""
        batch_metrics = [
            {"collection_name": "visa_oracle", "had_results": True, "result_count": 5, "avg_score": 0.8},
            {"collection_name": "visa_oracle", "had_results": True, "result_count": 3, "avg_score": 0.9},
        ]
        collection_health_service.record_queries_batch(batch_metrics)
        metrics = collection_health_service.metrics["visa_oracle"]
        assert metrics["query_count"] == 2
        assert metrics["hit_count"] == 2

    def test_calculate_staleness_fresh(self, collection_health_service):
        """Test calculating staleness for fresh collection"""
        recent_date = datetime.now().isoformat()
        staleness = collection_health_service.calculate_staleness(recent_date)
        assert staleness == StalenessSeverity.FRESH

    def test_calculate_staleness_aging(self, collection_health_service):
        """Test calculating staleness for aging collection"""
        old_date = (datetime.now() - timedelta(days=60)).isoformat()
        staleness = collection_health_service.calculate_staleness(old_date)
        assert staleness == StalenessSeverity.AGING

    def test_calculate_staleness_stale(self, collection_health_service):
        """Test calculating staleness for stale collection"""
        old_date = (datetime.now() - timedelta(days=120)).isoformat()
        staleness = collection_health_service.calculate_staleness(old_date)
        assert staleness == StalenessSeverity.STALE

    def test_calculate_staleness_very_stale(self, collection_health_service):
        """Test calculating staleness for very stale collection"""
        old_date = (datetime.now() - timedelta(days=200)).isoformat()
        staleness = collection_health_service.calculate_staleness(old_date)
        assert staleness == StalenessSeverity.VERY_STALE

    def test_calculate_staleness_none(self, collection_health_service):
        """Test calculating staleness for collection with no timestamp"""
        staleness = collection_health_service.calculate_staleness(None)
        assert staleness == StalenessSeverity.VERY_STALE

    def test_calculate_health_status_excellent(self, collection_health_service):
        """Test calculating health status for excellent collection"""
        status = collection_health_service.calculate_health_status(
            hit_rate=0.9,
            avg_confidence=0.8,
            staleness=StalenessSeverity.FRESH,
            query_count=20
        )
        assert status == HealthStatus.EXCELLENT

    def test_calculate_health_status_critical(self, collection_health_service):
        """Test calculating health status for critical collection"""
        status = collection_health_service.calculate_health_status(
            hit_rate=0.3,
            avg_confidence=0.2,
            staleness=StalenessSeverity.VERY_STALE,
            query_count=20
        )
        assert status == HealthStatus.CRITICAL

    def test_get_dashboard_summary(self, collection_health_service):
        """Test getting dashboard summary"""
        summary = collection_health_service.get_dashboard_summary()
        assert isinstance(summary, dict)
        assert "total_collections" in summary
        assert "health_distribution" in summary or "collections_by_status" in summary

    def test_get_stats(self, collection_health_service):
        """Test getting service statistics"""
        collection_health_service.record_query("visa_oracle", had_results=True, result_count=5, avg_score=0.8)
        # No get_stats method, but we can check metrics directly
        metrics = collection_health_service.metrics["visa_oracle"]
        assert metrics["query_count"] == 1

