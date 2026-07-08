from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.services.ingestion.collection_health_service import (
    CollectionHealthService,
    HealthStatus,
    StalenessSeverity,
)


def iso_days_ago(days: int) -> str:
    return (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()


def make_service() -> CollectionHealthService:
    service = CollectionHealthService()
    service.metrics = {
        "visa_oracle": service._init_metrics("visa_oracle"),
        "tax_genius": service._init_metrics("tax_genius"),
        "balizero_news": service._init_metrics("balizero_news"),
    }
    return service


def test_record_query_canonicalizes_alias_and_updates_hit_metrics() -> None:
    service = make_service()

    service.record_query("tax_updates", had_results=True, result_count=3, avg_score=0.82)
    service.record_query("missing", had_results=True, result_count=99, avg_score=0.99)

    metrics = service.metrics["tax_genius"]
    assert metrics["query_count"] == 1
    assert metrics["hit_count"] == 1
    assert metrics["total_results"] == 3
    assert metrics["confidence_scores"] == [0.82]
    assert metrics["last_queried"] is not None


def test_record_queries_batch_handles_empty_and_unknown_entries() -> None:
    service = make_service()

    service.record_queries_batch([])
    service.record_queries_batch(
        [
            {
                "collection_name": "visa_oracle",
                "had_results": True,
                "result_count": 2,
                "avg_score": 0.7,
            },
            {
                "collection_name": "legal_unified",
                "had_results": True,
                "result_count": 5,
                "avg_score": 0.9,
            },
            {"collection_name": None, "had_results": True},
        ],
    )

    assert service.metrics["visa_oracle"]["query_count"] == 1
    assert service.metrics["visa_oracle"]["hit_count"] == 1
    assert service.metrics["visa_oracle"]["confidence_scores"] == [0.7]
    assert service.metrics["tax_genius"]["query_count"] == 0


def test_calculate_staleness_maps_age_thresholds_and_invalid_values() -> None:
    service = make_service()

    assert service.calculate_staleness(iso_days_ago(5)) == StalenessSeverity.FRESH
    assert service.calculate_staleness(iso_days_ago(45)) == StalenessSeverity.AGING
    assert service.calculate_staleness(iso_days_ago(120)) == StalenessSeverity.STALE
    assert service.calculate_staleness(iso_days_ago(220)) == StalenessSeverity.VERY_STALE
    assert service.calculate_staleness(None) == StalenessSeverity.VERY_STALE
    assert service.calculate_staleness("not-a-date") == StalenessSeverity.VERY_STALE


def test_calculate_health_status_prioritizes_critical_and_warning_conditions() -> None:
    service = make_service()

    assert (
        service.calculate_health_status(0.9, 0.8, StalenessSeverity.FRESH, 12)
        == HealthStatus.EXCELLENT
    )
    assert (
        service.calculate_health_status(0.35, 0.8, StalenessSeverity.FRESH, 12)
        == HealthStatus.CRITICAL
    )
    assert (
        service.calculate_health_status(0.7, 0.2, StalenessSeverity.FRESH, 12)
        == HealthStatus.CRITICAL
    )
    assert (
        service.calculate_health_status(0.7, 0.6, StalenessSeverity.STALE, 12)
        == HealthStatus.WARNING
    )
    assert (
        service.calculate_health_status(0.7, 0.6, StalenessSeverity.AGING, 4)
        == HealthStatus.GOOD
    )


def test_generate_recommendations_combines_staleness_quality_and_usage() -> None:
    service = make_service()

    recommendations = service.generate_recommendations(
        "tax_updates",
        HealthStatus.CRITICAL,
        StalenessSeverity.VERY_STALE,
        hit_rate=0.2,
        avg_confidence=0.2,
        query_count=20,
    )

    joined = "\n".join(recommendations)
    assert "URGENT: Re-ingest tax_updates" in joined
    assert "Low hit rate (20%)" in joined
    assert "Low confidence (0.20)" in joined
    assert "Updates collection should be fresh" in joined


def test_get_collection_health_derives_rates_issues_and_recommendations() -> None:
    service = make_service()
    for _ in range(12):
        service.record_query("visa_oracle", had_results=False)
    for _ in range(3):
        service.record_query("visa_oracle", had_results=True, result_count=1, avg_score=0.25)

    health = service.get_collection_health(
        "visa_oracle",
        document_count=10,
        last_updated=iso_days_ago(1),
    )

    assert health.collection_name == "visa_oracle"
    assert health.query_count == 15
    assert health.hit_count == 3
    assert health.avg_confidence == 0.25
    assert health.avg_results_per_query == 1.0
    assert health.health_status == HealthStatus.CRITICAL
    assert "Low hit rate (20%)" in health.issues
    assert "Low confidence (0.25)" in health.issues


def test_get_collection_health_returns_critical_for_unknown_collection() -> None:
    service = make_service()

    health = service.get_collection_health("missing")

    assert health.health_status == HealthStatus.CRITICAL
    assert health.issues == ["Collection not found"]
    assert health.recommendations == ["Check collection exists in Qdrant"]


def test_get_all_collection_health_can_exclude_unused_collections() -> None:
    service = make_service()
    service.record_query("visa_oracle", had_results=True, result_count=1, avg_score=0.8)

    all_health = service.get_all_collection_health(include_empty=False)

    assert set(all_health) == {"visa_oracle"}


def test_dashboard_summary_counts_statuses_and_critical_collections() -> None:
    service = make_service()
    service.record_query("visa_oracle", had_results=True, result_count=2, avg_score=0.8)

    summary = service.get_dashboard_summary()

    assert summary["total_collections"] == 3
    assert summary["total_queries"] == 1
    assert summary["overall_hit_rate"] == "100.0%"
    assert summary["health_distribution"]["critical"] >= 2
    assert "tax_genius" in summary["critical_collections"]


def test_health_report_supports_text_and_markdown_formats() -> None:
    service = make_service()

    text_report = service.get_health_report()
    markdown_report = service.get_health_report(format="markdown")

    assert "COLLECTION HEALTH REPORT" in text_report
    assert "SUMMARY" in text_report
    assert "COLLECTION HEALTH REPORT" in markdown_report
