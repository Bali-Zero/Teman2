from __future__ import annotations

from typing import Any

import pytest

from backend.services.ingestion import scraper_normalizer as normalizer_module
from backend.services.ingestion.scraper_normalizer import (
    NormalizationConfig,
    ScraperDataNormalizer,
)


class FakeIngestionLogger:
    def __init__(self) -> None:
        self.started: list[dict[str, Any]] = []
        self.normalized: list[dict[str, Any]] = []
        self.failures: list[dict[str, Any]] = []

    def start_ingestion(self, **kwargs: Any) -> str:
        self.started.append(kwargs)
        return kwargs["document_id"]

    def scraper_data_normalized(self, **kwargs: Any) -> None:
        self.normalized.append(kwargs)

    def ingestion_failed(self, **kwargs: Any) -> None:
        self.failures.append(kwargs)


class FakeMetricsCollector:
    def __init__(self) -> None:
        self.normalized: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []

    def record_scraper_data_normalized(self, **kwargs: Any) -> None:
        self.normalized.append(kwargs)

    def record_scraper_normalization_error(self, **kwargs: Any) -> None:
        self.errors.append(kwargs)


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeIngestionLogger, FakeMetricsCollector]:
    fake_logger = FakeIngestionLogger()
    fake_metrics = FakeMetricsCollector()
    monkeypatch.setattr(normalizer_module, "ingestion_logger", fake_logger)
    monkeypatch.setattr(normalizer_module, "metrics_collector", fake_metrics)
    return fake_logger, fake_metrics


@pytest.mark.asyncio
async def test_normalize_news_article_cleans_fields_and_records_metrics(
    fakes: tuple[FakeIngestionLogger, FakeMetricsCollector],
) -> None:
    fake_logger, fake_metrics = fakes
    normalizer = ScraperDataNormalizer()

    result = await normalizer.normalize_news_article(
        {
            "title": "  <b>New KITAS Rule</b>  ",
            "content": "Paragraph " * 30,
            "summary": "<p>Short summary</p>",
            "url": "example.com/news",
            "source": "Immigration",
            "author": " Reporter ",
            "published_date": "2026-07-05",
            "tags": "Visa Updates, Bali-Zero, visa updates",
            "category": "visa",
            "language": "en",
            "confidence_score": 0.8,
        },
        source="unit-test",
        trace_id="trace-1",
    )

    assert result["title"] == "New KITAS Rule"
    assert result["url"] == "https://example.com/news"
    assert set(result["tags"]) == {"bali_zero", "visa_updates"}
    assert result["data_type"] == "news_article"
    assert result["word_count"] == 30
    assert result["quality_score"] > 0.5
    assert normalizer.processed_items == [result]
    assert fake_logger.started[0]["source"] == "unit-test"
    assert fake_logger.normalized[0]["source_url"] == "example.com/news"
    assert fake_metrics.normalized[0]["scraper_type"] == "news"


@pytest.mark.asyncio
async def test_normalize_news_article_records_errors_for_missing_required_fields(
    fakes: tuple[FakeIngestionLogger, FakeMetricsCollector],
) -> None:
    fake_logger, fake_metrics = fakes
    normalizer = ScraperDataNormalizer()

    with pytest.raises(ValueError, match="Missing required fields: content"):
        await normalizer.normalize_news_article({"title": "Only title"})

    assert len(normalizer.errors) == 1
    assert fake_metrics.errors == [
        {"scraper_type": "news", "error_type": "ValueError"},
    ]
    assert fake_logger.failures[0]["stage"].value == "cleaning"


@pytest.mark.asyncio
async def test_normalize_visa_information_normalizes_structured_fields(
    fakes: tuple[FakeIngestionLogger, FakeMetricsCollector],
) -> None:
    fake_logger, fake_metrics = fakes
    normalizer = ScraperDataNormalizer()

    result = await normalizer.normalize_visa_information(
        {
            "visa_type": "  E33G Remote Worker ",
            "description": "<p>Remote worker visa</p>",
            "requirements": [" Passport ", "", 123],
            "fees": "IDR 2,500,000",
            "processing_time": "7-14 days",
            "source_url": "imigrasi.go.id/e33g",
            "last_updated": "05/07/2026",
            "validity": "1 year",
        },
        trace_id="trace-2",
    )

    assert result["visa_type"] == "E33G Remote Worker"
    assert result["description"] == "Remote worker visa"
    assert result["requirements"] == ["Passport"]
    assert result["fees"] == {"amount": 2500000, "currency": "IDR", "text": "IDR 2,500,000"}
    assert result["processing_time"] == {"days_min": 7, "days_max": 14, "text": "7-14 days"}
    assert result["source_url"] == "https://imigrasi.go.id/e33g"
    assert result["data_type"] == "visa_info"
    assert fake_logger.normalized[0]["source_url"] == "imigrasi.go.id/e33g"
    assert fake_metrics.normalized[0]["scraper_type"] == "visa"


def test_detect_duplicates_matches_content_hash_or_url() -> None:
    normalizer = ScraperDataNormalizer()
    items = [
        {"id": "1", "content_hash": "hash-1", "url": "https://a.test"},
        {"id": "2", "content_hash": "hash-1", "url": "https://b.test"},
        {"id": "3", "content_hash": "hash-3", "url": "https://a.test"},
    ]

    duplicates = normalizer.detect_duplicates(items)

    assert [item["id"] for item in duplicates] == ["2", "3"]
    assert normalizer.duplicates_detected == duplicates


def test_duplicate_detection_can_be_disabled() -> None:
    normalizer = ScraperDataNormalizer(
        NormalizationConfig(enable_duplicate_detection=False),
    )

    assert normalizer.detect_duplicates([{"content_hash": "same"}, {"content_hash": "same"}]) == []


def test_helper_normalizers_are_deterministic() -> None:
    normalizer = ScraperDataNormalizer()

    assert normalizer._clean_text("<b>Hello</b>   world!!!") == "Hello world!!!"
    assert normalizer._normalize_date("2026-07-05").startswith("2026-07-05T")
    assert normalizer._normalize_tags(["Visa Updates", "visa-updates", "x"]) == [
        "visa_updates",
    ]
    assert normalizer._normalize_url("example.com") == "https://example.com"
    assert normalizer._normalize_fees("USD 1,250") == {
        "amount": 1250,
        "currency": "USD",
        "text": "USD 1,250",
    }
    assert normalizer._normalize_processing_time("5 days") == {
        "days_min": 5,
        "days_max": 5,
        "text": "5 days",
    }


def test_statistics_aggregate_processed_duplicates_and_errors() -> None:
    normalizer = ScraperDataNormalizer()
    normalizer.processed_items = [
        {"data_type": "news_article", "quality_score": 0.5},
        {"data_type": "visa_info", "quality_score": 0.9},
    ]
    normalizer.duplicates_detected = [{"id": "dup"}]
    normalizer.errors = [{"error": "bad"}]

    stats = normalizer.get_statistics()

    assert stats["total_processed"] == 2
    assert stats["duplicates_detected"] == 1
    assert stats["errors"] == 1
    assert stats["success_rate"] == pytest.approx(66.666, rel=0.01)
    assert set(stats["data_types"]) == {"news_article", "visa_info"}
    assert stats["average_quality_score"] == pytest.approx(0.7)
