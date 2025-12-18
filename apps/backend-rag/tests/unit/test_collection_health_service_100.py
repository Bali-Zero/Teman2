"""
Complete 100% Coverage Tests for Collection Health Service

Tests all methods and edge cases in collection_health_service.py.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest


class TestHealthStatus:
    """Tests for HealthStatus enum"""

    def test_health_status_values(self):
        """Test all HealthStatus values"""
        from services.collection_health_service import HealthStatus

        assert HealthStatus.EXCELLENT.value == "excellent"
        assert HealthStatus.GOOD.value == "good"
        assert HealthStatus.WARNING.value == "warning"
        assert HealthStatus.CRITICAL.value == "critical"


class TestStalenessSeverity:
    """Tests for StalenessSeverity enum"""

    def test_staleness_severity_values(self):
        """Test all StalenessSeverity values"""
        from services.collection_health_service import StalenessSeverity

        assert StalenessSeverity.FRESH.value == "fresh"
        assert StalenessSeverity.AGING.value == "aging"
        assert StalenessSeverity.STALE.value == "stale"
        assert StalenessSeverity.VERY_STALE.value == "very_stale"


class TestCollectionMetrics:
    """Tests for CollectionMetrics dataclass"""

    def test_collection_metrics_creation(self):
        """Test CollectionMetrics dataclass"""
        from services.collection_health_service import (
            CollectionMetrics,
            HealthStatus,
            StalenessSeverity,
        )

        metrics = CollectionMetrics(
            collection_name="test_collection",
            document_count=100,
            last_updated="2025-01-01T00:00:00",
            query_count=50,
            hit_count=40,
            avg_confidence=0.8,
            avg_results_per_query=3.5,
            health_status=HealthStatus.GOOD,
            staleness=StalenessSeverity.FRESH,
            issues=[],
            recommendations=["Test recommendation"],
        )

        assert metrics.collection_name == "test_collection"
        assert metrics.document_count == 100
        assert metrics.query_count == 50
        assert metrics.hit_count == 40
        assert metrics.avg_confidence == 0.8
        assert metrics.health_status == HealthStatus.GOOD


class TestCollectionHealthService:
    """Tests for CollectionHealthService class"""

    @pytest.fixture
    def service(self):
        """Create a CollectionHealthService instance"""
        from services.collection_health_service import CollectionHealthService

        return CollectionHealthService()

    @pytest.fixture
    def service_with_search(self):
        """Create service with search_service"""
        from services.collection_health_service import CollectionHealthService

        mock_search = MagicMock()
        return CollectionHealthService(search_service=mock_search)

    def test_init_default(self, service):
        """Test default initialization"""
        assert service.search_service is None
        assert len(service.metrics) == 14  # 14 collections
        assert "visa_oracle" in service.metrics
        assert "tax_genius" in service.metrics

    def test_init_with_search_service(self, service_with_search):
        """Test initialization with search service"""
        assert service_with_search.search_service is not None

    def test_init_metrics(self, service):
        """Test _init_metrics creates empty metrics"""
        metrics = service._init_metrics("test_collection")

        assert metrics["query_count"] == 0
        assert metrics["hit_count"] == 0
        assert metrics["total_results"] == 0
        assert metrics["confidence_scores"] == []
        assert metrics["last_queried"] is None
        assert metrics["last_updated"] is None

    def test_record_query_unknown_collection(self, service):
        """Test record_query with unknown collection"""
        # Should not raise, just log warning
        service.record_query("unknown_collection", True, 5, 0.9)

        # Collection should not be added
        assert "unknown_collection" not in service.metrics

    def test_record_query_no_results(self, service):
        """Test record_query with no results"""
        service.record_query("visa_oracle", False, 0, 0.0)

        metrics = service.metrics["visa_oracle"]
        assert metrics["query_count"] == 1
        assert metrics["hit_count"] == 0
        assert metrics["total_results"] == 0
        assert metrics["last_queried"] is not None

    def test_record_query_with_results(self, service):
        """Test record_query with results"""
        service.record_query("visa_oracle", True, 5, 0.85)

        metrics = service.metrics["visa_oracle"]
        assert metrics["query_count"] == 1
        assert metrics["hit_count"] == 1
        assert metrics["total_results"] == 5
        assert len(metrics["confidence_scores"]) == 1
        assert metrics["confidence_scores"][0] == 0.85

    def test_record_query_multiple(self, service):
        """Test multiple record_query calls"""
        service.record_query("visa_oracle", True, 3, 0.7)
        service.record_query("visa_oracle", True, 5, 0.9)
        service.record_query("visa_oracle", False, 0, 0.0)

        metrics = service.metrics["visa_oracle"]
        assert metrics["query_count"] == 3
        assert metrics["hit_count"] == 2
        assert metrics["total_results"] == 8
        assert len(metrics["confidence_scores"]) == 2

    def test_record_query_zero_score(self, service):
        """Test record_query with zero confidence score"""
        service.record_query("visa_oracle", True, 2, 0.0)

        metrics = service.metrics["visa_oracle"]
        assert metrics["hit_count"] == 1
        # Zero score should not be added
        assert len(metrics["confidence_scores"]) == 0

    def test_calculate_staleness_none(self, service):
        """Test calculate_staleness with None"""
        from services.collection_health_service import StalenessSeverity

        result = service.calculate_staleness(None)
        assert result == StalenessSeverity.VERY_STALE

    def test_calculate_staleness_fresh(self, service):
        """Test calculate_staleness with fresh timestamp"""
        from services.collection_health_service import StalenessSeverity

        fresh_date = (datetime.now() - timedelta(days=15)).isoformat()
        result = service.calculate_staleness(fresh_date)
        assert result == StalenessSeverity.FRESH

    def test_calculate_staleness_aging(self, service):
        """Test calculate_staleness with aging timestamp"""
        from services.collection_health_service import StalenessSeverity

        aging_date = (datetime.now() - timedelta(days=60)).isoformat()
        result = service.calculate_staleness(aging_date)
        assert result == StalenessSeverity.AGING

    def test_calculate_staleness_stale(self, service):
        """Test calculate_staleness with stale timestamp"""
        from services.collection_health_service import StalenessSeverity

        stale_date = (datetime.now() - timedelta(days=120)).isoformat()
        result = service.calculate_staleness(stale_date)
        assert result == StalenessSeverity.STALE

    def test_calculate_staleness_very_stale(self, service):
        """Test calculate_staleness with very stale timestamp"""
        from services.collection_health_service import StalenessSeverity

        very_stale_date = (datetime.now() - timedelta(days=200)).isoformat()
        result = service.calculate_staleness(very_stale_date)
        assert result == StalenessSeverity.VERY_STALE

    def test_calculate_staleness_with_z_suffix(self, service):
        """Test calculate_staleness with Z timezone suffix"""
        from services.collection_health_service import StalenessSeverity

        fresh_date = (datetime.now() - timedelta(days=10)).isoformat() + "Z"
        result = service.calculate_staleness(fresh_date)
        assert result == StalenessSeverity.FRESH

    def test_calculate_staleness_invalid_format(self, service):
        """Test calculate_staleness with invalid format"""
        from services.collection_health_service import StalenessSeverity

        result = service.calculate_staleness("invalid-date")
        assert result == StalenessSeverity.VERY_STALE

    def test_calculate_health_status_critical_very_stale(self, service):
        """Test calculate_health_status returns CRITICAL for very stale"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        result = service.calculate_health_status(
            hit_rate=0.9,
            avg_confidence=0.8,
            staleness=StalenessSeverity.VERY_STALE,
            query_count=100,
        )
        assert result == HealthStatus.CRITICAL

    def test_calculate_health_status_critical_low_hit_rate(self, service):
        """Test calculate_health_status returns CRITICAL for low hit rate"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        result = service.calculate_health_status(
            hit_rate=0.3,  # Below 0.4
            avg_confidence=0.8,
            staleness=StalenessSeverity.FRESH,
            query_count=100,  # > 10
        )
        assert result == HealthStatus.CRITICAL

    def test_calculate_health_status_critical_low_confidence(self, service):
        """Test calculate_health_status returns CRITICAL for low confidence"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        result = service.calculate_health_status(
            hit_rate=0.9,
            avg_confidence=0.2,  # Below 0.3
            staleness=StalenessSeverity.FRESH,
            query_count=100,
        )
        assert result == HealthStatus.CRITICAL

    def test_calculate_health_status_warning_stale(self, service):
        """Test calculate_health_status returns WARNING for stale"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        result = service.calculate_health_status(
            hit_rate=0.9, avg_confidence=0.8, staleness=StalenessSeverity.STALE, query_count=100
        )
        assert result == HealthStatus.WARNING

    def test_calculate_health_status_warning_medium_hit_rate(self, service):
        """Test calculate_health_status returns WARNING for medium hit rate"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        result = service.calculate_health_status(
            hit_rate=0.5,  # Below 0.6 but >= 0.4
            avg_confidence=0.8,
            staleness=StalenessSeverity.FRESH,
            query_count=10,
        )
        assert result == HealthStatus.WARNING

    def test_calculate_health_status_warning_medium_confidence(self, service):
        """Test calculate_health_status returns WARNING for medium confidence"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        result = service.calculate_health_status(
            hit_rate=0.9,
            avg_confidence=0.4,  # Below 0.5 but >= 0.3
            staleness=StalenessSeverity.FRESH,
            query_count=10,
        )
        assert result == HealthStatus.WARNING

    def test_calculate_health_status_excellent(self, service):
        """Test calculate_health_status returns EXCELLENT"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        result = service.calculate_health_status(
            hit_rate=0.85,  # > 0.8
            avg_confidence=0.75,  # > 0.7
            staleness=StalenessSeverity.FRESH,
            query_count=50,  # > 10
        )
        assert result == HealthStatus.EXCELLENT

    def test_calculate_health_status_good(self, service):
        """Test calculate_health_status returns GOOD by default"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        result = service.calculate_health_status(
            hit_rate=0.7,  # Not excellent but not warning
            avg_confidence=0.6,
            staleness=StalenessSeverity.AGING,
            query_count=8,
        )
        assert result == HealthStatus.GOOD

    def test_generate_recommendations_very_stale(self, service):
        """Test generate_recommendations for very stale collection"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recommendations = service.generate_recommendations(
            "visa_oracle",
            HealthStatus.CRITICAL,
            StalenessSeverity.VERY_STALE,
            hit_rate=0.8,
            avg_confidence=0.8,
            query_count=50,
        )

        assert any("URGENT" in r for r in recommendations)

    def test_generate_recommendations_stale(self, service):
        """Test generate_recommendations for stale collection"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recommendations = service.generate_recommendations(
            "visa_oracle",
            HealthStatus.WARNING,
            StalenessSeverity.STALE,
            hit_rate=0.8,
            avg_confidence=0.8,
            query_count=50,
        )

        assert any("WARNING" in r for r in recommendations)

    def test_generate_recommendations_aging(self, service):
        """Test generate_recommendations for aging collection"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recommendations = service.generate_recommendations(
            "visa_oracle",
            HealthStatus.GOOD,
            StalenessSeverity.AGING,
            hit_rate=0.8,
            avg_confidence=0.8,
            query_count=50,
        )

        assert any("INFO" in r for r in recommendations)

    def test_generate_recommendations_low_hit_rate(self, service):
        """Test generate_recommendations for low hit rate"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recommendations = service.generate_recommendations(
            "visa_oracle",
            HealthStatus.CRITICAL,
            StalenessSeverity.FRESH,
            hit_rate=0.3,
            avg_confidence=0.8,
            query_count=50,
        )

        assert any("hit rate" in r.lower() for r in recommendations)

    def test_generate_recommendations_medium_hit_rate(self, service):
        """Test generate_recommendations for medium hit rate"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recommendations = service.generate_recommendations(
            "visa_oracle",
            HealthStatus.WARNING,
            StalenessSeverity.FRESH,
            hit_rate=0.5,
            avg_confidence=0.8,
            query_count=50,
        )

        assert any("expanding" in r.lower() for r in recommendations)

    def test_generate_recommendations_low_confidence(self, service):
        """Test generate_recommendations for low confidence"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recommendations = service.generate_recommendations(
            "visa_oracle",
            HealthStatus.CRITICAL,
            StalenessSeverity.FRESH,
            hit_rate=0.8,
            avg_confidence=0.2,
            query_count=50,
        )

        assert any("confidence" in r.lower() for r in recommendations)

    def test_generate_recommendations_no_queries(self, service):
        """Test generate_recommendations for unused collection"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recommendations = service.generate_recommendations(
            "visa_oracle",
            HealthStatus.GOOD,
            StalenessSeverity.FRESH,
            hit_rate=0.0,
            avg_confidence=0.0,
            query_count=0,
        )

        assert any("unused" in r.lower() or "no queries" in r.lower() for r in recommendations)

    def test_generate_recommendations_low_usage(self, service):
        """Test generate_recommendations for low usage"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recommendations = service.generate_recommendations(
            "visa_oracle",
            HealthStatus.GOOD,
            StalenessSeverity.FRESH,
            hit_rate=0.8,
            avg_confidence=0.8,
            query_count=3,
        )

        assert any("low usage" in r.lower() or "routing" in r.lower() for r in recommendations)

    def test_generate_recommendations_updates_collection(self, service):
        """Test generate_recommendations for updates collection"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recommendations = service.generate_recommendations(
            "tax_updates",
            HealthStatus.WARNING,
            StalenessSeverity.STALE,
            hit_rate=0.8,
            avg_confidence=0.8,
            query_count=50,
        )

        assert any("auto-ingestion" in r.lower() for r in recommendations)

    def test_generate_recommendations_healthy(self, service):
        """Test generate_recommendations for healthy collection"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        recommendations = service.generate_recommendations(
            "visa_oracle",
            HealthStatus.EXCELLENT,
            StalenessSeverity.FRESH,
            hit_rate=0.9,
            avg_confidence=0.9,
            query_count=100,
        )

        assert any("no action needed" in r.lower() for r in recommendations)

    def test_get_collection_health_unknown(self, service):
        """Test get_collection_health for unknown collection"""
        from services.collection_health_service import HealthStatus, StalenessSeverity

        result = service.get_collection_health("unknown_collection")

        assert result.collection_name == "unknown_collection"
        assert result.document_count == 0
        assert result.health_status == HealthStatus.CRITICAL
        assert result.staleness == StalenessSeverity.VERY_STALE
        assert "not found" in result.issues[0].lower()

    def test_get_collection_health_empty(self, service):
        """Test get_collection_health for empty collection"""
        result = service.get_collection_health("visa_oracle", document_count=0)

        assert "Empty collection" in result.issues

    def test_get_collection_health_with_queries(self, service):
        """Test get_collection_health after queries"""
        # Simulate some queries
        service.record_query("visa_oracle", True, 5, 0.8)
        service.record_query("visa_oracle", True, 3, 0.7)
        service.record_query("visa_oracle", False, 0, 0.0)

        result = service.get_collection_health(
            "visa_oracle",
            document_count=1000,
            last_updated=(datetime.now() - timedelta(days=10)).isoformat(),
        )

        assert result.query_count == 3
        assert result.hit_count == 2
        assert result.avg_confidence == 0.75  # (0.8 + 0.7) / 2
        assert result.avg_results_per_query == 4.0  # 8 / 2

    def test_get_collection_health_uses_provided_timestamp(self, service):
        """Test get_collection_health uses provided last_updated"""
        from services.collection_health_service import StalenessSeverity

        result = service.get_collection_health(
            "visa_oracle", last_updated=(datetime.now() - timedelta(days=10)).isoformat()
        )

        assert result.staleness == StalenessSeverity.FRESH

    def test_get_collection_health_uses_tracked_timestamp(self, service):
        """Test get_collection_health uses tracked last_updated"""
        from services.collection_health_service import StalenessSeverity

        # Set tracked timestamp
        service.metrics["visa_oracle"]["last_updated"] = (
            datetime.now() - timedelta(days=200)
        ).isoformat()

        result = service.get_collection_health("visa_oracle")

        assert result.staleness == StalenessSeverity.VERY_STALE

    def test_get_all_collection_health_include_empty(self, service):
        """Test get_all_collection_health including empty"""
        result = service.get_all_collection_health(include_empty=True)

        assert len(result) == 14  # All collections

    def test_get_all_collection_health_exclude_empty(self, service):
        """Test get_all_collection_health excluding empty"""
        # Add query to one collection
        service.record_query("visa_oracle", True, 5, 0.8)

        result = service.get_all_collection_health(include_empty=False)

        assert len(result) == 1
        assert "visa_oracle" in result

    def test_get_dashboard_summary(self, service):
        """Test get_dashboard_summary"""
        # Add some queries
        service.record_query("visa_oracle", True, 5, 0.8)
        service.record_query("tax_genius", True, 3, 0.9)
        service.record_query("kbli_eye", False, 0, 0.0)

        result = service.get_dashboard_summary()

        assert "timestamp" in result
        assert "total_collections" in result
        assert "health_distribution" in result
        assert "staleness_distribution" in result
        assert "total_queries" in result
        assert result["total_queries"] == 3
        assert "overall_hit_rate" in result
        assert "collections_with_issues" in result

    def test_get_health_report_text(self, service):
        """Test get_health_report with text format"""
        service.record_query("visa_oracle", True, 5, 0.8)

        result = service.get_health_report(format="text")

        assert isinstance(result, str)
        assert "COLLECTION HEALTH REPORT" in result
        assert "SUMMARY" in result

    def test_get_health_report_markdown(self, service):
        """Test get_health_report with markdown format"""
        service.record_query("visa_oracle", True, 5, 0.8)

        result = service.get_health_report(format="markdown")

        assert isinstance(result, str)
        # Currently markdown is same as text
        assert "COLLECTION HEALTH REPORT" in result

    def test_generate_text_report(self, service):
        """Test _generate_text_report"""
        # Add various health states
        service.record_query("visa_oracle", True, 5, 0.8)
        service.metrics["tax_genius"]["last_updated"] = (
            datetime.now() - timedelta(days=200)
        ).isoformat()

        all_health = service.get_all_collection_health()
        summary = service.get_dashboard_summary()

        result = service._generate_text_report(all_health, summary)

        assert "=" * 80 in result
        assert "Generated:" in result
        assert "SUMMARY" in result
        assert "Health Distribution:" in result
        assert "COLLECTION DETAILS" in result

    def test_generate_text_report_with_critical(self, service):
        """Test _generate_text_report with critical collections"""
        # Make a collection critical
        service.metrics["visa_oracle"]["last_updated"] = (
            datetime.now() - timedelta(days=400)
        ).isoformat()

        all_health = service.get_all_collection_health()
        summary = service.get_dashboard_summary()

        result = service._generate_text_report(all_health, summary)

        assert "CRITICAL" in result

    def test_generate_markdown_report(self, service):
        """Test _generate_markdown_report"""
        all_health = service.get_all_collection_health()
        summary = service.get_dashboard_summary()

        result = service._generate_markdown_report(all_health, summary)

        # Currently same as text report
        assert isinstance(result, str)


class TestIntegration:
    """Integration tests"""

    def test_full_workflow(self):
        """Test complete health monitoring workflow"""
        from services.collection_health_service import (
            CollectionHealthService,
            HealthStatus,
            StalenessSeverity,
        )

        service = CollectionHealthService()

        # Simulate real usage
        for _ in range(20):
            service.record_query("visa_oracle", True, 5, 0.85)

        for _ in range(5):
            service.record_query("visa_oracle", False, 0, 0.0)

        # Get health
        health = service.get_collection_health(
            "visa_oracle",
            document_count=1500,
            last_updated=(datetime.now() - timedelta(days=5)).isoformat(),
        )

        # Should be healthy
        assert health.query_count == 25
        assert health.hit_count == 20
        assert health.staleness == StalenessSeverity.FRESH
        assert health.health_status in [HealthStatus.GOOD, HealthStatus.EXCELLENT]

        # Get summary
        summary = service.get_dashboard_summary()
        assert summary["total_queries"] == 25

        # Get report
        report = service.get_health_report()
        assert "visa_oracle" in report.upper()
