"""Tests for Scraper Data Normalization Service."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.services.ingestion.scraper_normalizer import (
    NormalizationConfig,
    ScraperDataNormalizer,
)


# ── NormalizationConfig tests ────────────────────────────────────


class TestNormalizationConfig:
    """Tests for NormalizationConfig dataclass."""

    def test_defaults(self) -> None:
        config = NormalizationConfig()
        assert config.enable_content_cleaning is True
        assert config.enable_duplicate_detection is True
        assert config.min_content_length == 50
        assert config.max_content_length == 1000000
        assert config.required_fields == ["title", "content"]

    def test_custom_values(self) -> None:
        config = NormalizationConfig(
            min_content_length=100,
            max_content_length=500000,
            required_fields=["title"],
        )
        assert config.min_content_length == 100
        assert config.max_content_length == 500000
        assert config.required_fields == ["title"]

    def test_none_required_fields_sets_default(self) -> None:
        config = NormalizationConfig(required_fields=None)
        assert config.required_fields == ["title", "content"]


# ── ScraperDataNormalizer helper method tests ────────────────────


class TestCleanText:
    """Tests for _clean_text method."""

    def test_empty_string(self) -> None:
        n = ScraperDataNormalizer()
        assert n._clean_text("") == ""

    def test_none_like(self) -> None:
        n = ScraperDataNormalizer()
        assert n._clean_text("") == ""

    def test_non_string_input(self) -> None:
        n = ScraperDataNormalizer()
        assert n._clean_text(12345) == "12345"  # type: ignore[arg-type]

    def test_removes_html_tags(self) -> None:
        n = ScraperDataNormalizer()
        result = n._clean_text("<p>Hello <b>World</b></p>")
        assert "<" not in result
        assert "Hello" in result
        assert "World" in result

    def test_normalizes_whitespace(self) -> None:
        n = ScraperDataNormalizer()
        result = n._clean_text("  hello   world  ")
        assert result == "hello world"

    def test_removes_special_characters(self) -> None:
        n = ScraperDataNormalizer()
        result = n._clean_text("hello@#$ world")
        assert "hello" in result
        assert "world" in result

    def test_keeps_basic_punctuation(self) -> None:
        n = ScraperDataNormalizer()
        result = n._clean_text("Hello, world! How are you?")
        assert "," in result
        assert "!" in result
        assert "?" in result


class TestNormalizeDate:
    """Tests for _normalize_date method."""

    def test_empty_string(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_date("")
        assert "T" in result  # Returns ISO format current time

    def test_none_input(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_date(None)  # type: ignore[arg-type]
        assert "T" in result

    def test_iso_format_passthrough(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_date("2026-01-15T10:30:00")
        assert result == "2026-01-15T10:30:00"

    def test_yyyy_mm_dd(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_date("2026-01-15")
        assert "2026-01-15" in result

    def test_dd_mm_yyyy(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_date("15/01/2026")
        assert "2026" in result

    def test_mm_dd_yyyy(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_date("01/15/2026")
        assert "2026" in result

    def test_invalid_format_returns_current(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_date("not-a-date")
        assert "T" in result  # Returns current ISO time


class TestNormalizeTags:
    """Tests for _normalize_tags method."""

    def test_list_input(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_tags(["Visa", "Immigration", "Bali"])
        assert "visa" in result
        assert "immigration" in result
        assert "bali" in result

    def test_string_input(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_tags("visa, immigration, bali")
        assert "visa" in result
        assert "immigration" in result
        assert "bali" in result

    def test_deduplication(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_tags(["Visa", "visa", "VISA"])
        assert len(result) == 1
        assert "visa" in result

    def test_removes_short_tags(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_tags(["a", "visa"])
        assert "visa" in result
        assert len(result) == 1

    def test_replaces_spaces_and_hyphens(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_tags(["work permit", "e-visa"])
        assert "work_permit" in result
        assert "e_visa" in result

    def test_non_list_non_string(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_tags(12345)  # type: ignore[arg-type]
        assert result == []


class TestNormalizeUrl:
    """Tests for _normalize_url method."""

    def test_empty_url(self) -> None:
        n = ScraperDataNormalizer()
        assert n._normalize_url("") == ""

    def test_none_url(self) -> None:
        n = ScraperDataNormalizer()
        assert n._normalize_url(None) == ""  # type: ignore[arg-type]

    def test_non_string(self) -> None:
        n = ScraperDataNormalizer()
        assert n._normalize_url(123) == ""  # type: ignore[arg-type]

    def test_adds_https(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_url("example.com")
        assert result == "https://example.com"

    def test_keeps_existing_https(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_url("https://example.com")
        assert result == "https://example.com"

    def test_keeps_existing_http(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_url("http://example.com")
        assert result == "http://example.com"

    def test_strips_whitespace(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_url("  https://example.com  ")
        assert result == "https://example.com"


class TestNormalizeRequirements:
    """Tests for _normalize_requirements method."""

    def test_list_of_strings(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_requirements(["Valid passport", "Photo 4x6"])
        assert len(result) == 2

    def test_non_list_input(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_requirements("not a list")  # type: ignore[arg-type]
        assert result == []

    def test_filters_empty_strings(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_requirements(["Valid passport", "", "  "])
        assert len(result) == 1

    def test_non_string_items_skipped(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_requirements(["Valid passport", 123, None])  # type: ignore[list-item]
        assert len(result) == 1


class TestNormalizeFees:
    """Tests for _normalize_fees method."""

    def test_empty_fees(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_fees("")
        assert result == {"amount": 0, "currency": "USD", "text": ""}

    def test_usd_amount(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_fees("USD 500")
        assert result["currency"] == "USD"
        assert result["amount"] == 500

    def test_idr_amount(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_fees("IDR 2000000")
        assert result["currency"] == "IDR"
        assert result["amount"] == 2000000

    def test_eur_amount(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_fees("EUR 350")
        assert result["currency"] == "EUR"
        assert result["amount"] == 350

    def test_no_currency_defaults_usd(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_fees("500")
        assert result["currency"] == "USD"
        assert result["amount"] == 500

    def test_no_amount(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_fees("Free of charge")
        assert result["amount"] == 0


class TestNormalizeProcessingTime:
    """Tests for _normalize_processing_time method."""

    def test_empty_string(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_processing_time("")
        assert result == {"days_min": 0, "days_max": 0, "text": ""}

    def test_range(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_processing_time("5-10 business days")
        assert result["days_min"] == 5
        assert result["days_max"] == 10

    def test_single_number(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_processing_time("7 days")
        assert result["days_min"] == 7
        assert result["days_max"] == 7

    def test_no_numbers(self) -> None:
        n = ScraperDataNormalizer()
        result = n._normalize_processing_time("varies by case")
        assert result["days_min"] == 0
        assert result["days_max"] == 0


class TestCalculateQualityScore:
    """Tests for _calculate_quality_score method."""

    def test_high_quality(self) -> None:
        n = ScraperDataNormalizer()
        data: dict[str, Any] = {
            "content": "A" * 600,
            "title": "Test Title",
            "author": "Author",
            "published_date": "2026-01-01",
            "tags": ["tag1"],
            "source": "test_source",
            "confidence_score": 1.0,
        }
        score = n._calculate_quality_score(data)
        assert score >= 0.9

    def test_low_quality(self) -> None:
        n = ScraperDataNormalizer()
        data: dict[str, Any] = {"content": "short"}
        score = n._calculate_quality_score(data)
        assert score < 0.3

    def test_medium_content(self) -> None:
        n = ScraperDataNormalizer()
        data: dict[str, Any] = {"content": "A" * 200, "title": "Title"}
        score = n._calculate_quality_score(data)
        assert score >= 0.3

    def test_score_capped_at_one(self) -> None:
        n = ScraperDataNormalizer()
        data: dict[str, Any] = {
            "content": "A" * 1000,
            "title": "T",
            "author": "A",
            "published_date": "D",
            "tags": ["t"],
            "source": "S",
            "confidence_score": 1.0,
        }
        score = n._calculate_quality_score(data)
        assert score <= 1.0


class TestGenerateContentHash:
    """Tests for _generate_content_hash method."""

    def test_empty_content(self) -> None:
        n = ScraperDataNormalizer()
        assert n._generate_content_hash("") == ""

    def test_consistent_hash(self) -> None:
        n = ScraperDataNormalizer()
        h1 = n._generate_content_hash("test content")
        h2 = n._generate_content_hash("test content")
        assert h1 == h2

    def test_case_insensitive(self) -> None:
        n = ScraperDataNormalizer()
        h1 = n._generate_content_hash("Test Content")
        h2 = n._generate_content_hash("test content")
        assert h1 == h2

    def test_whitespace_normalized(self) -> None:
        n = ScraperDataNormalizer()
        h1 = n._generate_content_hash("test  content")
        h2 = n._generate_content_hash("test content")
        assert h1 == h2

    def test_different_content_different_hash(self) -> None:
        n = ScraperDataNormalizer()
        h1 = n._generate_content_hash("content A")
        h2 = n._generate_content_hash("content B")
        assert h1 != h2


class TestValidateRequiredFields:
    """Tests for _validate_required_fields method."""

    def test_all_present(self) -> None:
        n = ScraperDataNormalizer()
        data: dict[str, Any] = {"title": "Test", "content": "Content"}
        n._validate_required_fields(data, ["title", "content"])  # Should not raise

    def test_missing_field(self) -> None:
        n = ScraperDataNormalizer()
        data: dict[str, Any] = {"title": "Test"}
        with pytest.raises(ValueError, match="Missing required fields: content"):
            n._validate_required_fields(data, ["title", "content"])

    def test_empty_string_field(self) -> None:
        n = ScraperDataNormalizer()
        data: dict[str, Any] = {"title": "", "content": "Content"}
        with pytest.raises(ValueError, match="title"):
            n._validate_required_fields(data, ["title", "content"])

    def test_whitespace_only_field(self) -> None:
        n = ScraperDataNormalizer()
        data: dict[str, Any] = {"title": "   ", "content": "Content"}
        with pytest.raises(ValueError, match="title"):
            n._validate_required_fields(data, ["title", "content"])

    def test_none_field(self) -> None:
        n = ScraperDataNormalizer()
        data: dict[str, Any] = {"title": None, "content": "Content"}
        with pytest.raises(ValueError, match="title"):
            n._validate_required_fields(data, ["title", "content"])


class TestDetectDuplicates:
    """Tests for detect_duplicates method."""

    def test_no_duplicates(self) -> None:
        n = ScraperDataNormalizer()
        items: list[dict[str, Any]] = [
            {"content_hash": "hash1", "url": "url1"},
            {"content_hash": "hash2", "url": "url2"},
        ]
        dupes = n.detect_duplicates(items)
        assert dupes == []

    def test_hash_duplicate(self) -> None:
        n = ScraperDataNormalizer()
        items: list[dict[str, Any]] = [
            {"content_hash": "same_hash", "url": "url1"},
            {"content_hash": "same_hash", "url": "url2"},
        ]
        dupes = n.detect_duplicates(items)
        assert len(dupes) == 1
        assert dupes[0]["url"] == "url2"

    def test_url_duplicate(self) -> None:
        n = ScraperDataNormalizer()
        items: list[dict[str, Any]] = [
            {"content_hash": "hash1", "url": "same_url"},
            {"content_hash": "hash2", "url": "same_url"},
        ]
        dupes = n.detect_duplicates(items)
        assert len(dupes) == 1

    def test_disabled_duplicate_detection(self) -> None:
        config = NormalizationConfig(enable_duplicate_detection=False)
        n = ScraperDataNormalizer(config=config)
        items: list[dict[str, Any]] = [
            {"content_hash": "same", "url": "same"},
            {"content_hash": "same", "url": "same"},
        ]
        dupes = n.detect_duplicates(items)
        assert dupes == []

    def test_duplicates_tracked(self) -> None:
        n = ScraperDataNormalizer()
        items: list[dict[str, Any]] = [
            {"content_hash": "h1", "url": "u1"},
            {"content_hash": "h1", "url": "u2"},
        ]
        n.detect_duplicates(items)
        assert len(n.duplicates_detected) == 1


class TestNormalizeNewsArticle:
    """Tests for normalize_news_article method."""

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        n = ScraperDataNormalizer()
        raw: dict[str, Any] = {
            "title": "Test Article",
            "content": "A" * 200,
            "url": "https://example.com/article",
            "source": "test",
            "author": "Test Author",
            "published_date": "2026-01-01",
            "tags": ["bali", "visa"],
        }

        with patch("backend.services.ingestion.scraper_normalizer.ingestion_logger") as mock_logger:
            mock_logger.start_ingestion.return_value = "doc-123"
            mock_logger.scraper_data_normalized = MagicMock()
            with patch("backend.services.ingestion.scraper_normalizer.metrics_collector") as mock_metrics:
                mock_metrics.record_scraper_data_normalized = MagicMock()
                result = await n.normalize_news_article(raw, source="test_scraper")

        assert result["title"] == "Test Article"
        assert result["data_type"] == "news_article"
        assert result["word_count"] > 0
        assert len(n.processed_items) == 1

    @pytest.mark.asyncio
    async def test_missing_required_fields_raises(self) -> None:
        n = ScraperDataNormalizer()
        raw: dict[str, Any] = {"content": "Some content"}

        with patch("backend.services.ingestion.scraper_normalizer.ingestion_logger") as mock_logger:
            mock_logger.start_ingestion.return_value = "doc-fail"
            mock_logger.ingestion_failed = MagicMock()
            with patch("backend.services.ingestion.scraper_normalizer.metrics_collector") as mock_metrics:
                mock_metrics.record_scraper_normalization_error = MagicMock()
                with pytest.raises(ValueError, match="Missing required fields"):
                    await n.normalize_news_article(raw)

        assert len(n.errors) == 1

    @pytest.mark.asyncio
    async def test_short_content_raises(self) -> None:
        n = ScraperDataNormalizer()
        raw: dict[str, Any] = {
            "title": "Title",
            "content": "Short",
        }

        with patch("backend.services.ingestion.scraper_normalizer.ingestion_logger") as mock_logger:
            mock_logger.start_ingestion.return_value = "doc-short"
            mock_logger.ingestion_failed = MagicMock()
            with patch("backend.services.ingestion.scraper_normalizer.metrics_collector") as mock_metrics:
                mock_metrics.record_scraper_normalization_error = MagicMock()
                with pytest.raises(ValueError, match="Content too short"):
                    await n.normalize_news_article(raw)

    @pytest.mark.asyncio
    async def test_long_content_truncated(self) -> None:
        config = NormalizationConfig(max_content_length=100)
        n = ScraperDataNormalizer(config=config)
        raw: dict[str, Any] = {
            "title": "Title",
            "content": "A" * 200,
            "url": "https://example.com",
        }

        with patch("backend.services.ingestion.scraper_normalizer.ingestion_logger") as mock_logger:
            mock_logger.start_ingestion.return_value = "doc-long"
            mock_logger.scraper_data_normalized = MagicMock()
            with patch("backend.services.ingestion.scraper_normalizer.metrics_collector") as mock_metrics:
                mock_metrics.record_scraper_data_normalized = MagicMock()
                result = await n.normalize_news_article(raw)

        assert result["character_count"] <= 100


class TestNormalizeVisaInformation:
    """Tests for normalize_visa_information method."""

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        n = ScraperDataNormalizer()
        raw: dict[str, Any] = {
            "visa_type": "KITAS",
            "description": "Work permit for foreigners",
            "requirements": ["Valid passport", "Sponsor letter"],
            "fees": "USD 500",
            "processing_time": "10-14 business days",
            "source_url": "https://example.com/visa",
        }

        with patch("backend.services.ingestion.scraper_normalizer.ingestion_logger") as mock_logger:
            mock_logger.start_ingestion.return_value = "visa-doc-1"
            mock_logger.scraper_data_normalized = MagicMock()
            with patch("backend.services.ingestion.scraper_normalizer.metrics_collector") as mock_metrics:
                mock_metrics.record_scraper_data_normalized = MagicMock()
                result = await n.normalize_visa_information(raw)

        assert result["visa_type"] == "KITAS"
        assert result["data_type"] == "visa_info"
        assert result["fees"]["currency"] == "USD"
        assert result["processing_time"]["days_min"] == 10

    @pytest.mark.asyncio
    async def test_missing_visa_type_raises(self) -> None:
        n = ScraperDataNormalizer()
        raw: dict[str, Any] = {"description": "Some description"}

        with patch("backend.services.ingestion.scraper_normalizer.ingestion_logger") as mock_logger:
            mock_logger.start_ingestion.return_value = "visa-fail"
            mock_logger.ingestion_failed = MagicMock()
            with patch("backend.services.ingestion.scraper_normalizer.metrics_collector") as mock_metrics:
                mock_metrics.record_scraper_normalization_error = MagicMock()
                with pytest.raises(ValueError, match="Missing required fields"):
                    await n.normalize_visa_information(raw)


class TestGetStatistics:
    """Tests for get_statistics method."""

    def test_initial_stats(self) -> None:
        n = ScraperDataNormalizer()
        stats = n.get_statistics()
        assert stats["total_processed"] == 0
        assert stats["duplicates_detected"] == 0
        assert stats["errors"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["data_types"] == []

    def test_after_processing(self) -> None:
        n = ScraperDataNormalizer()
        n.processed_items = [
            {"data_type": "news_article", "quality_score": 0.8},
            {"data_type": "visa_info", "quality_score": 0.6},
        ]
        n.duplicates_detected = [{"dup": True}]
        n.errors = [{"error": "fail"}]
        stats = n.get_statistics()
        assert stats["total_processed"] == 2
        assert stats["duplicates_detected"] == 1
        assert stats["errors"] == 1
        assert stats["average_quality_score"] == pytest.approx(0.7)
        assert set(stats["data_types"]) == {"news_article", "visa_info"}
