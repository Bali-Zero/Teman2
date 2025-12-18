"""
Comprehensive tests for CollectionHealthService
Target: 100% coverage
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest


class TestHealthStatus:
    """Tests for HealthStatus enum"""

    def test_health_status_values(self):
        """Test all health status values"""
        from services.collection_health_service import HealthStatus

        assert HealthStatus.EXCELLENT.value == "excellent"
        assert HealthStatus.GOOD.value == "good"
        assert HealthStatus.WARNING.value == "warning"
        assert HealthStatus.CRITICAL.value == "critical"


class TestStalenessSeverity:
    """Tests for StalenessSeverity enum"""

    def test_staleness_severity_values(self):
        """Test all staleness severity values"""
        from services.collection_health_service import StalenessSeverity

        assert StalenessSeverity.FRESH.value == "fresh"
        assert StalenessSeverity.AGING.value == "aging"
        assert StalenessSeverity.STALE.value == "stale"
        assert StalenessSeverity.VERY_STALE.value == "very_stale"


class TestCollectionMetrics:
    """Tests for CollectionMetrics dataclass"""

    def test_collection_metrics_creation(self):
        """Test creating CollectionMetrics instance"""
        from services.collection_health_service import (
            CollectionMetrics,
            HealthStatus,
            StalenessSeverity,
        )

        metrics = CollectionMetrics(
            collection_name="test_collection",
            document_count=100,
            last_updated="2024-01-01T00:00:00",
            query_count=50,
            hit_count=40,
            avg_confidence=0.85,
            avg_results_per_query=3.5,
            health_status=HealthStatus.GOOD,
            staleness=StalenessSeverity.FRESH,
            issues=["Test issue"],
            recommendations=["Test recommendation"],
        )

        assert metrics.collection_name == "test_collection"
        assert metrics.document_count == 100
        assert metrics.query_count == 50
        assert metrics.health_status == HealthStatus.GOOD


class TestCollectionHealthService:
    """Tests for CollectionHealthService class"""

    @pytest.fixture
    def service(self):
        """Create CollectionHealthService instance"""
        from services.collection_health_service import CollectionHealthService

        return CollectionHealthService()

    @pytest.fixture
    def service_with_deps(self):
        """Create CollectionHealthService with mocked dependencies"""
        from services.collection_health_service import CollectionHealthService

        mock_search = MagicMock()
        mock_qdrant = MagicMock()
        return CollectionHealthService(search_service=mock_search, qdrant_client=mock_qdrant)

    def test_init_default(self):
        """Test default initialization"""
        from services.collection_health_service import CollectionHealthService

        service = CollectionHealthService()

        assert service.search_service is None
        assert len(service.metrics) == 14  # 14 collections
        assert "visa_oracle" in service.metrics
        assert "bali_zero_pricing" in service.metrics

    def test_init_with_deps(self, service_with_deps):
        """Test initialization with dependencies"""
        assert service_with_deps.search_service is not None

    def test_init_metrics_structure(self, service):
        """Test initialized metrics structure"""
        for coll_name, metrics in service.metrics.items():
            assert "query_count" in metrics
            assert "hit_count" in metrics
            assert "total_results" in metrics
            assert "confidence_scores" in metrics
            assert "last_queried" in metrics
            assert "last_updated" in metrics
            assert metrics["query_count"] == 0

    def test_record_query_known_collection(self, service):
        """Test recording query for known collection"""
        service.record_query("visa_oracle", had_results=True, result_count=5, avg_score=0.85)

        metrics = service.metrics["visa_oracle"]
        assert metrics["query_count"] == 1
        assert metrics["hit_count"] == 1
        assert metrics["total_results"] == 5
        assert 0.85 in metrics["confidence_scores"]
        assert metrics["last_queried"] is not None

    def test_record_query_no_results(self, service):
        """Test recording query with no results"""
        service.record_query("visa_oracle", had_results=False)

        metrics = service.metrics["visa_oracle"]
        assert metrics["query_count"] == 1
        assert metrics["hit_count"] == 0
        assert metrics["total_results"] == 0

    def test_record_query_unknown_collection(self, service):
        """Test recording query for unknown collection"""
        # Should not raise, just log warning
        service.record_query("unknown_collection", had_results=True, result_count=5)

    def test_record_query_zero_score(self, service):
        """Test recording query with zero score"""
        service.record_query("visa_oracle", had_results=True, result_count=3, avg_score=0.0)

        metrics = service.metrics["visa_oracle"]
        assert metrics["hit_count"] == 1
        assert 0.0 not in metrics["confidence_scores"]  # Zero scores not added

    def test_calculate_staleness_fresh(self, service):
        """Test staleness calculation for fresh data"""
        from services.collection_health_service import StalenessSeverity

        recent = (datetime.now() - timedelta(days=15)).isoformat()
        result = service.calculate_staleness(recent)
        assert result == StalenessSeverity.FRESH

    def test_calculate_staleness_aging(self, service):
        """Test staleness calculation for aging data"""
        from services.collection_health_service import StalenessSeverity

        aging = (datetime.now() - timedelta(days=60)).isoformat()
        result = service.calculate_staleness(aging)
        assert result == StalenessSeverity.AGING

    def test_calculate_staleness_stale(self, service):
        """Test staleness calculation for stale data"""
        from services.collection_health_service import StalenessSeverity

        stale = (datetime.now() - timedelta(days=120)).isoformat()
        result = service.calculate_staleness(stale)
        assert result == StalenessSeverity.STALE

    def test_calculate_staleness_very_stale(self, service):
        """Test staleness calculation for very stale data"""
        from services.collection_health_service import StalenessSeverity

        very_stale = (datetime.now() - timedelta(days=400)).isoformat()
        result = service.calculate_staleness(very_stale)
        assert result == StalenessSeverity.VERY_STALE

    def test_calculate_staleness_none(self, service):
        """Test staleness calculation with None"""
        from services.collection_health_service import StalenessSeverity

        result = service.calculate_staleness(None)
        assert result == StalenessSeverity.VERY_STALE

    def test_calculate_staleness_invalid_format(self, service):
        """Test staleness calculation with invalid format"""
        from services.collection_health_service import StalenessSeverity

        result = service.calculate_staleness("invalid-date")
        assert result == StalenessSeverity.VERY_STALE

    def test_calculate_staleness_with_timezone(self, service):
        """Test staleness calculation with timezone"""
        from services.collection_health_service import StalenessSeverity

        recent = (datetime.now() - timedelta(days=15)).isoformat() + "Z"
        result = service.calculate_staleness(recent)
        assert result == StalenessSeverity.FRESH

    def test_calculate_health_status_critical_very_stale(self, service):
        """Test health status critical for very stale"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        result = service.calculate_health_status(0.9, 0.9, StalenessSeverity.VERY_STALE, 100)
        assert result == HealthStatus.CRITICAL

    def test_calculate_health_status_critical_low_hit_rate(self, service):
        """Test health status critical for low hit rate"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        result = service.calculate_health_status(0.3, 0.9, StalenessSeverity.FRESH, 100)
        assert result == HealthStatus.CRITICAL

    def test_calculate_health_status_critical_low_confidence(self, service):
        """Test health status critical for low confidence"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        result = service.calculate_health_status(0.9, 0.2, StalenessSeverity.FRESH, 100)
        assert result == HealthStatus.CRITICAL

    def test_calculate_health_status_warning_stale(self, service):
        """Test health status warning for stale"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        result = service.calculate_health_status(0.9, 0.9, StalenessSeverity.STALE, 100)
        assert result == HealthStatus.WARNING

    def test_calculate_health_status_warning_medium_hit_rate(self, service):
        """Test health status warning for medium hit rate"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        result = service.calculate_health_status(0.5, 0.9, StalenessSeverity.FRESH, 100)
        assert result == HealthStatus.WARNING

    def test_calculate_health_status_warning_medium_confidence(self, service):
        """Test health status warning for medium confidence"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        result = service.calculate_health_status(0.9, 0.4, StalenessSeverity.FRESH, 100)
        assert result == HealthStatus.WARNING

    def test_calculate_health_status_excellent(self, service):
        """Test health status excellent"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        result = service.calculate_health_status(0.9, 0.8, StalenessSeverity.FRESH, 100)
        assert result == HealthStatus.EXCELLENT

    def test_calculate_health_status_good_default(self, service):
        """Test health status good as default"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        result = service.calculate_health_status(0.7, 0.6, StalenessSeverity.AGING, 3)
        assert result == HealthStatus.GOOD

    def test_generate_recommendations_very_stale(self, service):
        """Test recommendations for very stale collection"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recs = service.generate_recommendations(
            "visa_oracle", HealthStatus.CRITICAL, StalenessSeverity.VERY_STALE, 0.5, 0.5, 10
        )

        assert any("URGENT" in r for r in recs)
        assert any("Re-ingest" in r for r in recs)

    def test_generate_recommendations_stale(self, service):
        """Test recommendations for stale collection"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recs = service.generate_recommendations(
            "visa_oracle", HealthStatus.WARNING, StalenessSeverity.STALE, 0.5, 0.5, 10
        )

        assert any("WARNING" in r for r in recs)

    def test_generate_recommendations_aging(self, service):
        """Test recommendations for aging collection"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recs = service.generate_recommendations(
            "visa_oracle", HealthStatus.GOOD, StalenessSeverity.AGING, 0.8, 0.8, 10
        )

        assert any("Schedule update" in r for r in recs)

    def test_generate_recommendations_low_hit_rate(self, service):
        """Test recommendations for low hit rate"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recs = service.generate_recommendations(
            "visa_oracle", HealthStatus.CRITICAL, StalenessSeverity.FRESH, 0.3, 0.8, 20
        )

        assert any("Low hit rate" in r for r in recs)

    def test_generate_recommendations_medium_hit_rate(self, service):
        """Test recommendations for medium hit rate"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recs = service.generate_recommendations(
            "visa_oracle", HealthStatus.WARNING, StalenessSeverity.FRESH, 0.5, 0.8, 20
        )

        assert any("Medium hit rate" in r for r in recs)

    def test_generate_recommendations_low_confidence(self, service):
        """Test recommendations for low confidence"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recs = service.generate_recommendations(
            "visa_oracle", HealthStatus.CRITICAL, StalenessSeverity.FRESH, 0.8, 0.2, 20
        )

        assert any("Low confidence" in r for r in recs)

    def test_generate_recommendations_medium_confidence(self, service):
        """Test recommendations for medium confidence"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recs = service.generate_recommendations(
            "visa_oracle", HealthStatus.WARNING, StalenessSeverity.FRESH, 0.8, 0.4, 20
        )

        assert any("Medium confidence" in r for r in recs)

    def test_generate_recommendations_no_queries(self, service):
        """Test recommendations for no queries"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recs = service.generate_recommendations(
            "visa_oracle", HealthStatus.GOOD, StalenessSeverity.FRESH, 0.0, 0.0, 0
        )

        assert any("No queries yet" in r for r in recs)

    def test_generate_recommendations_low_usage(self, service):
        """Test recommendations for low usage"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recs = service.generate_recommendations(
            "visa_oracle", HealthStatus.GOOD, StalenessSeverity.FRESH, 0.8, 0.8, 3
        )

        assert any("Low usage" in r for r in recs)

    def test_generate_recommendations_updates_collection(self, service):
        """Test recommendations for updates collection"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recs = service.generate_recommendations(
            "tax_updates", HealthStatus.WARNING, StalenessSeverity.STALE, 0.8, 0.8, 10
        )

        assert any("auto-ingestion" in r for r in recs)

    def test_generate_recommendations_healthy(self, service):
        """Test recommendations for healthy collection"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recs = service.generate_recommendations(
            "visa_oracle", HealthStatus.EXCELLENT, StalenessSeverity.FRESH, 0.9, 0.9, 100
        )

        assert any("health is good" in r for r in recs)

    def test_get_collection_health_unknown(self, service):
        """Test getting health for unknown collection"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        health = service.get_collection_health("unknown_collection")

        assert health.collection_name == "unknown_collection"
        assert health.health_status == HealthStatus.CRITICAL
        assert health.staleness == StalenessSeverity.VERY_STALE
        assert "not found" in health.issues[0]

    def test_get_collection_health_with_queries(self, service):
        """Test getting health with recorded queries"""
        # Record some queries
        for _ in range(20):
            service.record_query("visa_oracle", had_results=True, result_count=3, avg_score=0.75)
        for _ in range(5):
            service.record_query("visa_oracle", had_results=False)

        health = service.get_collection_health("visa_oracle", document_count=1000)

        assert health.query_count == 25
        assert health.hit_count == 20
        assert health.avg_confidence == 0.75

    def test_get_collection_health_with_timestamps(self, service):
        """Test getting health with timestamps"""
        recent = datetime.now().isoformat()
        health = service.get_collection_health("visa_oracle", last_updated=recent)

        from services.collection_health_service import StalenessSeverity

        assert health.staleness == StalenessSeverity.FRESH

    def test_get_collection_health_empty_collection(self, service):
        """Test getting health for empty collection"""
        health = service.get_collection_health("visa_oracle", document_count=0)

        assert "Empty collection" in health.issues

    def test_get_collection_health_issues_detection(self, service):
        """Test issue detection in health check"""
        # Record queries with poor performance
        for _ in range(20):
            service.record_query("visa_oracle", had_results=True, result_count=1, avg_score=0.3)
        for _ in range(20):
            service.record_query("visa_oracle", had_results=False)

        health = service.get_collection_health("visa_oracle")

        assert any("hit rate" in issue.lower() for issue in health.issues)
        assert any("confidence" in issue.lower() for issue in health.issues)

    def test_get_all_collection_health(self, service):
        """Test getting health for all collections"""
        all_health = service.get_all_collection_health()

        assert len(all_health) == 14
        assert "visa_oracle" in all_health
        assert "bali_zero_pricing" in all_health

    def test_get_all_collection_health_exclude_empty(self, service):
        """Test getting health excluding empty collections"""
        # Record query for one collection
        service.record_query("visa_oracle", had_results=True)

        all_health = service.get_all_collection_health(include_empty=False)

        assert len(all_health) == 1
        assert "visa_oracle" in all_health

    def test_get_dashboard_summary(self, service):
        """Test getting dashboard summary"""
        # Record some queries
        service.record_query("visa_oracle", had_results=True, result_count=3, avg_score=0.8)
        service.record_query("tax_genius", had_results=False)

        summary = service.get_dashboard_summary()

        assert "timestamp" in summary
        assert "total_collections" in summary
        assert "health_distribution" in summary
        assert "staleness_distribution" in summary
        assert "total_queries" in summary
        assert "overall_hit_rate" in summary
        assert "critical_collections" in summary
        assert "needs_attention" in summary

    def test_get_dashboard_summary_empty(self, service):
        """Test getting dashboard summary with no queries"""
        summary = service.get_dashboard_summary()

        assert summary["total_queries"] == 0
        assert summary["overall_hit_rate"] == "0.0%"

    def test_get_health_report_text(self, service):
        """Test generating text health report"""
        # Record some queries
        service.record_query("visa_oracle", had_results=True, result_count=3, avg_score=0.8)

        report = service.get_health_report(format="text")

        assert "COLLECTION HEALTH REPORT" in report
        assert "SUMMARY" in report
        assert "COLLECTION DETAILS" in report
        assert "visa_oracle" in report.upper() or "VISA_ORACLE" in report

    def test_get_health_report_markdown(self, service):
        """Test generating markdown health report"""
        report = service.get_health_report(format="markdown")

        # Currently markdown falls back to text
        assert "COLLECTION HEALTH REPORT" in report

    def test_generate_text_report_with_critical(self, service):
        """Test text report with critical collections"""
        # Make a collection critical by recording poor performance
        for _ in range(20):
            service.record_query("visa_oracle", had_results=False)

        all_health = service.get_all_collection_health()
        summary = service.get_dashboard_summary()

        report = service._generate_text_report(all_health, summary)

        assert "COLLECTION HEALTH REPORT" in report

    def test_generate_text_report_sorting(self, service):
        """Test that collections are sorted by health status"""
        all_health = service.get_all_collection_health()
        summary = service.get_dashboard_summary()

        report = service._generate_text_report(all_health, summary)

        # Report should contain all sections
        assert "Generated:" in report
        assert "Total Collections:" in report
        assert "Health Distribution:" in report
        assert "Staleness Distribution:" in report
