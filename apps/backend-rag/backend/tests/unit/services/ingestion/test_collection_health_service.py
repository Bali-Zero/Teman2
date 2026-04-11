"""Tests for backend.services.ingestion.collection_health_service"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from backend.services.ingestion.collection_health_service import (
    CollectionHealthService,
    CollectionMetrics,
    HealthStatus,
    StalenessSeverity,
)


@pytest.fixture
def health_service():
    with patch(
        "backend.services.ingestion.collection_health_service.get_canonical_collection_names",
        return_value=["collection_a", "collection_b", "updates_feed"],
    ):
        return CollectionHealthService()


# ── record_query ────────────────────────────────────────────────────────────


class TestRecordQuery:
    def test_record_query_with_results(self, health_service):
        with patch(
            "backend.services.ingestion.collection_health_service.canonicalize_collection_name",
            return_value="collection_a",
        ):
            health_service.record_query("collection_a", had_results=True, result_count=5, avg_score=0.8)
            metrics = health_service.metrics["collection_a"]
            assert metrics["query_count"] == 1
            assert metrics["hit_count"] == 1
            assert metrics["total_results"] == 5
            assert 0.8 in metrics["confidence_scores"]

    def test_record_query_without_results(self, health_service):
        with patch(
            "backend.services.ingestion.collection_health_service.canonicalize_collection_name",
            return_value="collection_a",
        ):
            health_service.record_query("collection_a", had_results=False)
            metrics = health_service.metrics["collection_a"]
            assert metrics["query_count"] == 1
            assert metrics["hit_count"] == 0

    def test_record_query_unknown_collection(self, health_service):
        with patch(
            "backend.services.ingestion.collection_health_service.canonicalize_collection_name",
            return_value="unknown_coll",
        ):
            health_service.record_query("unknown_coll", had_results=True)
            # Should log warning, not raise


# ── record_queries_batch ────────────────────────────────────────────────────


class TestRecordQueriesBatch:
    def test_batch_empty(self, health_service):
        health_service.record_queries_batch([])

    def test_batch_multiple(self, health_service):
        with patch(
            "backend.services.ingestion.collection_health_service.canonicalize_collection_name",
            side_effect=lambda x: x,
        ):
            batch = [
                {"collection_name": "collection_a", "had_results": True, "result_count": 3, "avg_score": 0.7},
                {"collection_name": "collection_a", "had_results": False},
                {"collection_name": "collection_b", "had_results": True, "result_count": 1, "avg_score": 0.5},
            ]
            health_service.record_queries_batch(batch)
            assert health_service.metrics["collection_a"]["query_count"] == 2
            assert health_service.metrics["collection_a"]["hit_count"] == 1
            assert health_service.metrics["collection_b"]["query_count"] == 1

    def test_batch_unknown_collection(self, health_service):
        with patch(
            "backend.services.ingestion.collection_health_service.canonicalize_collection_name",
            return_value="nonexistent",
        ):
            health_service.record_queries_batch([
                {"collection_name": "nonexistent", "had_results": True},
            ])


# ── calculate_staleness ────────────────────────────────────────────────────


class TestCalculateStaleness:
    def test_none_returns_very_stale(self, health_service):
        assert health_service.calculate_staleness(None) == StalenessSeverity.VERY_STALE

    def test_fresh(self, health_service):
        recent = (datetime.now(tz=timezone.utc) - timedelta(days=5)).isoformat()
        assert health_service.calculate_staleness(recent) == StalenessSeverity.FRESH

    def test_aging(self, health_service):
        aging = (datetime.now(tz=timezone.utc) - timedelta(days=60)).isoformat()
        assert health_service.calculate_staleness(aging) == StalenessSeverity.AGING

    def test_stale(self, health_service):
        stale = (datetime.now(tz=timezone.utc) - timedelta(days=120)).isoformat()
        assert health_service.calculate_staleness(stale) == StalenessSeverity.STALE

    def test_very_stale(self, health_service):
        very_old = (datetime.now(tz=timezone.utc) - timedelta(days=400)).isoformat()
        assert health_service.calculate_staleness(very_old) == StalenessSeverity.VERY_STALE

    def test_invalid_date(self, health_service):
        assert health_service.calculate_staleness("not-a-date") == StalenessSeverity.VERY_STALE


# ── calculate_health_status ─────────────────────────────────────────────────


class TestCalculateHealthStatus:
    def test_critical_very_stale(self, health_service):
        result = health_service.calculate_health_status(
            hit_rate=0.9, avg_confidence=0.8,
            staleness=StalenessSeverity.VERY_STALE, query_count=100,
        )
        assert result == HealthStatus.CRITICAL

    def test_critical_low_hit_rate(self, health_service):
        result = health_service.calculate_health_status(
            hit_rate=0.3, avg_confidence=0.8,
            staleness=StalenessSeverity.FRESH, query_count=20,
        )
        assert result == HealthStatus.CRITICAL

    def test_critical_low_confidence(self, health_service):
        result = health_service.calculate_health_status(
            hit_rate=0.9, avg_confidence=0.2,
            staleness=StalenessSeverity.FRESH, query_count=20,
        )
        assert result == HealthStatus.CRITICAL

    def test_warning_stale(self, health_service):
        result = health_service.calculate_health_status(
            hit_rate=0.9, avg_confidence=0.8,
            staleness=StalenessSeverity.STALE, query_count=5,
        )
        assert result == HealthStatus.WARNING

    def test_warning_medium_hit_rate(self, health_service):
        result = health_service.calculate_health_status(
            hit_rate=0.5, avg_confidence=0.8,
            staleness=StalenessSeverity.FRESH, query_count=10,
        )
        assert result == HealthStatus.WARNING

    def test_excellent(self, health_service):
        result = health_service.calculate_health_status(
            hit_rate=0.9, avg_confidence=0.8,
            staleness=StalenessSeverity.FRESH, query_count=20,
        )
        assert result == HealthStatus.EXCELLENT

    def test_good_default(self, health_service):
        result = health_service.calculate_health_status(
            hit_rate=0.7, avg_confidence=0.6,
            staleness=StalenessSeverity.AGING, query_count=3,
        )
        assert result == HealthStatus.GOOD


# ── generate_recommendations ────────────────────────────────────────────────


class TestGenerateRecommendations:
    def test_very_stale_recommendation(self, health_service):
        recs = health_service.generate_recommendations(
            "test", HealthStatus.CRITICAL, StalenessSeverity.VERY_STALE,
            hit_rate=0.9, avg_confidence=0.8, query_count=20,
        )
        assert any("URGENT" in r for r in recs)

    def test_stale_recommendation(self, health_service):
        recs = health_service.generate_recommendations(
            "test", HealthStatus.WARNING, StalenessSeverity.STALE,
            hit_rate=0.9, avg_confidence=0.8, query_count=20,
        )
        assert any("WARNING" in r for r in recs)

    def test_low_hit_rate_recommendation(self, health_service):
        recs = health_service.generate_recommendations(
            "test", HealthStatus.CRITICAL, StalenessSeverity.FRESH,
            hit_rate=0.3, avg_confidence=0.8, query_count=20,
        )
        assert any("hit rate" in r.lower() for r in recs)

    def test_low_confidence_recommendation(self, health_service):
        recs = health_service.generate_recommendations(
            "test", HealthStatus.CRITICAL, StalenessSeverity.FRESH,
            hit_rate=0.9, avg_confidence=0.2, query_count=20,
        )
        assert any("confidence" in r.lower() for r in recs)

    def test_no_queries_recommendation(self, health_service):
        recs = health_service.generate_recommendations(
            "test", HealthStatus.GOOD, StalenessSeverity.FRESH,
            hit_rate=0.0, avg_confidence=0.0, query_count=0,
        )
        assert any("No queries" in r for r in recs)

    def test_updates_collection_not_fresh(self, health_service):
        recs = health_service.generate_recommendations(
            "updates_feed", HealthStatus.WARNING, StalenessSeverity.STALE,
            hit_rate=0.9, avg_confidence=0.8, query_count=20,
        )
        assert any("auto-ingestion" in r for r in recs)

    def test_all_good(self, health_service):
        recs = health_service.generate_recommendations(
            "test", HealthStatus.EXCELLENT, StalenessSeverity.FRESH,
            hit_rate=0.9, avg_confidence=0.8, query_count=20,
        )
        assert any("good" in r.lower() for r in recs)


# ── get_collection_health ───────────────────────────────────────────────────


class TestGetCollectionHealth:
    def test_unknown_collection(self, health_service):
        result = health_service.get_collection_health("nonexistent")
        assert result.health_status == HealthStatus.CRITICAL
        assert "not found" in result.issues[0].lower()

    def test_known_collection_no_queries(self, health_service):
        result = health_service.get_collection_health("collection_a")
        assert isinstance(result, CollectionMetrics)
        assert result.query_count == 0

    def test_known_collection_with_data(self, health_service):
        health_service.metrics["collection_a"]["query_count"] = 20
        health_service.metrics["collection_a"]["hit_count"] = 18
        health_service.metrics["collection_a"]["total_results"] = 90
        health_service.metrics["collection_a"]["confidence_scores"] = [0.8, 0.9, 0.7]
        health_service.metrics["collection_a"]["last_updated"] = (
            datetime.now(tz=timezone.utc) - timedelta(days=5)
        ).isoformat()

        result = health_service.get_collection_health("collection_a", document_count=1000)
        assert result.document_count == 1000
        assert result.query_count == 20
        assert result.avg_confidence > 0

    def test_empty_collection_issue(self, health_service):
        result = health_service.get_collection_health("collection_a", document_count=0)
        assert any("Empty" in issue for issue in result.issues)


# ── get_all_collection_health ───────────────────────────────────────────────


class TestGetAllCollectionHealth:
    def test_includes_all(self, health_service):
        result = health_service.get_all_collection_health(include_empty=True)
        assert len(result) == 3

    def test_excludes_empty(self, health_service):
        result = health_service.get_all_collection_health(include_empty=False)
        assert len(result) == 0  # No queries recorded


# ── get_dashboard_summary ───────────────────────────────────────────────────


class TestGetDashboardSummary:
    def test_summary_structure(self, health_service):
        summary = health_service.get_dashboard_summary()
        assert "total_collections" in summary
        assert "health_distribution" in summary
        assert "staleness_distribution" in summary
        assert "total_queries" in summary
        assert "overall_hit_rate" in summary

    def test_hit_rate_format(self, health_service):
        summary = health_service.get_dashboard_summary()
        assert "%" in summary["overall_hit_rate"]


# ── get_health_report ───────────────────────────────────────────────────────


class TestGetHealthReport:
    def test_text_report(self, health_service):
        report = health_service.get_health_report(format="text")
        assert "COLLECTION HEALTH REPORT" in report
        assert "SUMMARY" in report

    def test_markdown_report(self, health_service):
        report = health_service.get_health_report(format="markdown")
        assert "COLLECTION HEALTH REPORT" in report
